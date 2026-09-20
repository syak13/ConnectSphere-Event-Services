"""
Event Review and Approval
---------------------------
- Coordinator reviews full request details (routes.py -> GET /events/<id>)
- Coordinator requests clarification or amendment
- Organiser responds to a clarification request
- Coordinator approves / rejects (with reason) an event request
- Organiser revises and resubmits a rejected request (new record, per
  status enum rule: rejected -> new submitted record on resubmission)
- Organiser views review outcome and comments (routes.py)
"""
from datetime import datetime

from app.extensions import db
from app.events.services.assignment import assign_coordinator
from app.events.services.status import InvalidTransitionError, change_status
from app.models.event import Event, EventReview

REQUIRED_FOR_SUBMISSION = ["name", "purpose", "description", "proposed_date", "expected_attendance"]


def submit_event(event: Event, organiser_id: int) -> Event:
    if event.organiser_id != organiser_id:
        raise PermissionError("Only the requesting Organiser can submit this request")
    if event.status != "draft":
        raise InvalidTransitionError("Only a draft request can be submitted")

    missing = [f for f in REQUIRED_FOR_SUBMISSION if getattr(event, f) in (None, "")]
    if missing:
        raise ValueError(f"Cannot submit: missing required field(s): {', '.join(missing)}")

    event.submitted_at = datetime.utcnow()
    change_status(event, "submitted", changed_by_id=organiser_id)

    # Coordinator Assignment epic: exactly one Coordinator auto-assigned here,
    # in the same action that moves the event into review (shared contract 3.4)
    assign_coordinator(event)
    change_status(event, "under_review", changed_by_id=event.coordinator_id)
    return event


def request_clarification(event: Event, coordinator_id: int, comments: str) -> Event:
    if event.coordinator_id != coordinator_id:
        raise PermissionError("Only the assigned Coordinator can request clarification")
    if event.status != "under_review":
        raise ValueError("Clarification can only be requested while a request is under review")
    if not comments:
        raise ValueError("Clarification comments are required")

    event.clarification_flag = True
    event.clarification_comments = comments
    db.session.add(
        EventReview(
            event_id=event.id,
            coordinator_id=coordinator_id,
            action="clarification_requested",
            comments=comments,
        )
    )
    db.session.commit()
    return event


def respond_to_clarification(event: Event, organiser_id: int, data: dict) -> Event:
    if event.organiser_id != organiser_id:
        raise PermissionError("Only the requesting Organiser can respond")
    if not event.clarification_flag:
        raise ValueError("This request has no outstanding clarification")

    from app.events.services.drafts import _apply_fields  # local import avoids circular import

    _apply_fields(event, data)
    event.clarification_flag = False
    db.session.commit()
    return event


def approve_event(event: Event, coordinator_id: int, comments: str = None) -> Event:
    if event.coordinator_id != coordinator_id:
        raise PermissionError("Only the assigned Coordinator can approve this request")
    if event.status != "under_review":
        raise ValueError("Only a request under review can be approved")

    event.review_outcome = "approved"
    event.review_reason = comments
    event.review_timestamp = datetime.utcnow()
    event.review_coordinator_id = coordinator_id
    db.session.add(
        EventReview(event_id=event.id, coordinator_id=coordinator_id, action="approved", comments=comments)
    )
    change_status(event, "approved", changed_by_id=coordinator_id, reason=comments)
    return event


def reject_event(event: Event, coordinator_id: int, reason: str) -> Event:
    if event.coordinator_id != coordinator_id:
        raise PermissionError("Only the assigned Coordinator can reject this request")
    if event.status != "under_review":
        raise ValueError("Only a request under review can be rejected")
    if not reason:
        raise ValueError("A reason is required to reject a request")

    event.review_outcome = "rejected"
    event.review_reason = reason
    event.review_timestamp = datetime.utcnow()
    event.review_coordinator_id = coordinator_id
    db.session.add(
        EventReview(event_id=event.id, coordinator_id=coordinator_id, action="rejected", comments=reason)
    )
    change_status(event, "rejected", changed_by_id=coordinator_id, reason=reason)
    return event


def resubmit_rejected_event(original: Event, organiser_id: int, data: dict) -> Event:
    if original.organiser_id != organiser_id:
        raise PermissionError("Only the requesting Organiser can resubmit this request")
    if original.status != "rejected":
        raise ValueError("Only a rejected request can be resubmitted")

    new_event = Event(
        organiser_id=organiser_id,
        status="draft",
        resubmitted_from_event_id=original.id,
        name=original.name,
        purpose=original.purpose,
        description=original.description,
        category=original.category,
        proposed_date=original.proposed_date,
        proposed_time=original.proposed_time,
        expected_attendance=original.expected_attendance,
        capacity_needed=original.capacity_needed,
        required_layout=original.required_layout,
        accessibility_needs=original.accessibility_needs,
        required_facilities=original.required_facilities,
        registration_required=original.registration_required,
        intended_capacity=original.intended_capacity,
    )
    db.session.add(new_event)
    db.session.commit()

    from app.events.services.drafts import _apply_fields  # local import avoids circular import

    if data:
        _apply_fields(new_event, data)
        db.session.commit()

    return submit_event(new_event, organiser_id)
