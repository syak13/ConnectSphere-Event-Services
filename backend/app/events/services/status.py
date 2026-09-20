"""
Event Status Management
------------------------
Owns the status-transition rules for the Event Status Management epic:
- Display current event status consistently (single source of truth: Event.status)
- Automatic transition to Confirmed once arrangements are complete
- Revert a confirmed event to Planning on major change
- Retain rejected and cancelled requests with final status visible (never deleted)
"""
from app.extensions import db
from app.models.event import Event, EventStatusHistory

ALLOWED_TRANSITIONS = {
    "draft": {"submitted"},
    "submitted": {"under_review"},
    "under_review": {"approved", "rejected"},
    "approved": {"planning", "cancelled"},
    "planning": {"confirmed", "cancelled"},
    "confirmed": {"planning", "completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
    "rejected": set(),  # resubmission creates a new record instead of reopening this one
}


class InvalidTransitionError(Exception):
    pass


def change_status(event: Event, new_status: str, changed_by_id: int, reason: str = None) -> Event:
    allowed = ALLOWED_TRANSITIONS.get(event.status, set())
    if new_status not in allowed:
        raise InvalidTransitionError(f"Cannot transition event from '{event.status}' to '{new_status}'")

    old_status = event.status
    event.status = new_status
    db.session.add(
        EventStatusHistory(
            event_id=event.id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by_id,
            reason=reason,
        )
    )
    db.session.commit()
    return event


def try_auto_confirm(event: Event, changed_by_id: int) -> Event:
    """
    Automatically moves an event from 'planning' to 'confirmed' once essential
    arrangements are complete. Venue/equipment confirmation checks are wired
    in by the Venue and Equipment epics (not yet implemented); for an event
    that has no venue or equipment requirements at all, planning is already
    sufficient, so it can confirm immediately.
    """
    if event.status != "planning":
        return event

    has_outstanding_requirements = bool(event.capacity_needed or event.equipment_requirements)
    if not has_outstanding_requirements:
        return change_status(event, "confirmed", changed_by_id, reason="No outstanding arrangements required")
    return event


def revert_to_planning(event: Event, changed_by_id: int, reason: str) -> Event:
    if event.status != "confirmed":
        raise InvalidTransitionError("Only a confirmed event can be reverted to planning")
    return change_status(event, "planning", changed_by_id, reason=reason)
