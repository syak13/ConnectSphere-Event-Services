"""
Coordinator Assignment
-----------------------
- Automatic coordinator assignment on submission (fair, workload-based;
  exactly one Coordinator per event, no self-assign / accept-decline step)
- Coordinator views assigned requests (routes.py)
- Reassign coordinator after offline agreement
- Coordinators view unassigned/all events for planning visibility (routes.py)
- Previous coordinator retains read-only visibility after reassignment
"""
from datetime import datetime

from sqlalchemy import func

from app.extensions import db
from app.models.event import Event, EventCoordinatorHistory
from app.models.user import Role, User

OPEN_STATUSES = ("under_review", "approved", "planning")


def _active_coordinators():
    return (
        User.query.join(User.roles)
        .filter(Role.name == "event_coordinator", User.is_active.is_(True))
        .all()
    )


def get_next_coordinator():
    """Picks the active Coordinator with the fewest currently open assigned
    events (workload-based, deterministic tie-break by id for fairness)."""
    coordinators = _active_coordinators()
    if not coordinators:
        return None

    counts = (
        db.session.query(Event.coordinator_id, func.count(Event.id))
        .filter(Event.status.in_(OPEN_STATUSES))
        .group_by(Event.coordinator_id)
        .all()
    )
    workload = {c.id: 0 for c in coordinators}
    for coordinator_id, count in counts:
        if coordinator_id in workload:
            workload[coordinator_id] = count

    return min(coordinators, key=lambda c: (workload[c.id], c.id))


def assign_coordinator(event: Event, coordinator: User = None, assignment_type: str = "auto") -> Event:
    coordinator = coordinator or get_next_coordinator()
    if coordinator is None:
        raise ValueError("No active Event Coordinator is available for assignment")

    event.coordinator_id = coordinator.id
    db.session.add(
        EventCoordinatorHistory(
            event_id=event.id,
            coordinator_id=coordinator.id,
            assignment_type=assignment_type,
        )
    )
    db.session.commit()
    return event


def reassign_coordinator(event: Event, new_coordinator: User) -> Event:
    """Reassignment is agreed offline between coordinators; this records the
    handover once that agreement has been made (per Q&A #6/#13/#22)."""
    open_entry = (
        EventCoordinatorHistory.query.filter_by(
            event_id=event.id, coordinator_id=event.coordinator_id, unassigned_at=None
        ).first()
    )
    if open_entry:
        open_entry.unassigned_at = datetime.utcnow()

    return assign_coordinator(event, coordinator=new_coordinator, assignment_type="reassignment")


def has_coordinator_history(event: Event, user_id: int) -> bool:
    """True if user_id is or ever was a coordinator on this event (keeps
    previous coordinators' read-only visibility after reassignment)."""
    return any(h.coordinator_id == user_id for h in event.coordinator_history)
