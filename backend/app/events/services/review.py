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
from app.common.time import utcnow
import re

from app.extensions import db
from app.events.services.assignment import assign_coordinator
from app.events.services.status import InvalidTransitionError, change_status
from app.models.event import Event, EventClarificationResponse, EventReview

from app.events.services.validators import validate_for_submission
from sqlalchemy.exc import IntegrityError

_COMMENT_CONTAINS_WORD = re.compile(r"[A-Za-z]")

def submit_event(event: Event, organiser_id: int) -> Event:
    if event.organiser_id != organiser_id:
        raise PermissionError("Only the requesting Organiser can submit this request")
    if event.status != "draft":
        raise InvalidTransitionError("Only a draft request can be submitted")

    errors = validate_for_submission(event)
    if errors:
        raise ValueError("Cannot submit: " + "; ".join(errors))

    event.submitted_at = utcnow()
    change_status(event, "submitted", changed_by_id=organiser_id)

    # Coordinator Assignment epic: exactly one Coordinator auto-assigned here,
    # in the same action that moves the event into review (shared contract 3.4).
    #
    # If no active Coordinator is available right now, that is a valid,
    # non-error outcome rather than a failed submission: the request has
    # already been recorded as "submitted" above, so we leave it there,
    # unassigned. It becomes visible to Coordinators as an unassigned event
    # (see assignment.list_unassigned_events / the Planning view) and can be
    # picked up automatically later via assignment.try_assign_and_advance,
    # without ever exposing a manual self-assign step.
    try:
        assign_coordinator(event)
    except ValueError:
        return event

    change_status(event, "under_review", changed_by_id=event.coordinator_id)
    return event


def request_clarification(event: Event, coordinator_id: int, comments: str, editable_fields: list = None) -> Event:
    if event.coordinator_id != coordinator_id:
        raise PermissionError("Only the assigned Coordinator can request clarification")
    if event.status != "under_review":
        raise ValueError("Clarification can only be requested while a request is under review")
    if not comments or not comments.strip():
        raise ValueError("At least one clarification comment is required")
    if not _COMMENT_CONTAINS_WORD.search(comments):
        raise ValueError("Clarification comments must contain descriptive text, not just symbols or numbers")

    from app.events.services.drafts import CLARIFICATION_EDITABLE_FIELD_CHOICES  # local import avoids circular import

    editable_fields = editable_fields or []
    invalid_fields = [f for f in editable_fields if f not in CLARIFICATION_EDITABLE_FIELD_CHOICES]
    if invalid_fields:
        raise ValueError(f"Unknown field(s) in editableFields: {', '.join(invalid_fields)}")

    db.session.add(
        EventReview(
            event_id=event.id,
            coordinator_id=coordinator_id,
            action="clarification_requested",
            comments=comments,
            editable_fields=editable_fields,
        )
    )

    # clarification_flag now just means "at least one open request exists" -
    # any number of requests can be open at once, each answered independently
    event.clarification_flag = True
    event.clarification_comments = comments
    db.session.commit()
    return event


def respond_to_clarification(event: Event, organiser_id: int, review_id: int, data: dict) -> Event:
    if event.organiser_id != organiser_id:
        raise PermissionError("Only the requesting Organiser can respond")

    target_review = next(
        (r for r in event.reviews if r.id == review_id and r.action == "clarification_requested"),
        None,
    )
    if target_review is None:
        raise ValueError("No such clarification request for this event")

    if EventClarificationResponse.query.filter_by(review_id=review_id).first():
        raise ValueError("This clarification has already been responded to")

    comments = data.get("comments", "")
    if not comments or not comments.strip():
        raise ValueError("At least one response comment is required")
    if not _COMMENT_CONTAINS_WORD.search(comments):
        raise ValueError("Response comments must contain descriptive text, not just symbols or numbers")

    allowed_fields = target_review.editable_fields or []
    restricted_data = {k: v for k, v in data.items() if k in allowed_fields}

    from app.events.services.drafts import _apply_fields  # local import avoids circular import

    _apply_fields(event, restricted_data)

    db.session.add(
        EventClarificationResponse(
            event_id=event.id,
            review_id=review_id,
            organiser_id=organiser_id,
            comments=comments,
            updated_fields=restricted_data,
        )
    )

    answered_review_ids = {
        r.review_id for r in EventClarificationResponse.query.filter_by(event_id=event.id).all()
    }
    answered_review_ids.add(review_id)
    event.clarification_flag = any(
        r.action == "clarification_requested" and r.id not in answered_review_ids for r in event.reviews
    )

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError("This clarification has already been responded to")

    return event


def approve_event(event: Event, coordinator_id: int, comments: str = None) -> Event:
    if event.coordinator_id != coordinator_id:
        raise PermissionError("Only the assigned Coordinator can approve this request")
    if event.status != "under_review":
        raise ValueError("Only a request under review can be approved")

    event.review_outcome = "approved"
    event.review_reason = comments
    event.review_timestamp = utcnow()
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
    event.review_timestamp = utcnow()
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

def get_clarification_thread(event: Event) -> list:
    """Every clarification request paired with its response (or None if
    still awaiting one), in chronological order. Each request carries the
    specific fields the Coordinator opened up for THAT request, so several
    can be open at once and answered independently."""
    responses_by_review = {r.review_id: r for r in event.clarification_responses}
    thread = []
    for entry in event.reviews:
        if entry.action != "clarification_requested":
            continue
        response = responses_by_review.get(entry.id)
        thread.append(
            {
                "reviewId": entry.id,
                "request": {
                    "coordinatorId": entry.coordinator_id,
                    "comments": entry.comments,
                    "editableFields": entry.editable_fields or [],
                    "createdAt": entry.created_at.isoformat() if entry.created_at else None,
                },
                "response": response.to_dict() if response else None,
            }
        )
    return thread