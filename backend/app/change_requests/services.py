"""Event Change Requests: an Organiser requests a change to an event."""
from datetime import date, time

from app.common.text_validation import validate_descriptive_text
from app.extensions import db
from app.models.change_request import ChangeRequest
from app.models.event import Event
from app.models.venue import BOOKING_APPROVED, Venue, VenueBooking

CHANGEABLE_STATUSES = ("approved", "planning", "confirmed")
STATUS_MESSAGE = "Changes can only be requested for an event that is approved, planning or confirmed"

# Changing these can affect arrangements already made, so the request is
# marked significant. Everything else the organiser may change is routine.
SIGNIFICANT_FIELDS = {
    "proposed_date", "proposed_time", "expected_attendance",
    "capacity_needed", "required_layout", "required_facilities",
    "venue_id", "equipment_requirements",
}


class ChangeRequestError(ValueError):
    """`errors` maps a field name (or "changes" / "reason" / "event") to a message."""

    def __init__(self, errors: dict):
        self.errors = errors
        super().__init__("; ".join(errors.values()))


# ---------------------------------------------------------------------
# Cleaning: raw input -> JSON-friendly value, or ValueError(message)
# ---------------------------------------------------------------------

def _text(label, required):
    def clean(value):
        if not isinstance(value, str):
            raise ValueError(f"{label} must be text")
        value = value.strip()
        if required and not value:
            raise ValueError(f"{label} cannot be blank")
        return value or None
    return clean


def _positive_int(label):
    def clean(value):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{label} must be a positive whole number")
        return value
    return clean


def _clean_date(value):
    try:
        parsed = value if isinstance(value, date) else date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("Enter a valid date")
    # local calendar day, the same clock the organiser sees
    if parsed < date.today():
        raise ValueError("Event date cannot be in the past")
    return parsed.isoformat()


def _clean_time(value):
    try:
        parsed = value if isinstance(value, time) else time.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("Enter a valid time")
    return parsed.isoformat()


def _clean_bool(value):
    if not isinstance(value, bool):
        raise ValueError("Must be yes or no")
    return value


def _clean_facilities(value):
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError("Facilities must be a list of text values")
    return [v.strip() for v in value if v.strip()]


def _clean_venue(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Choose a venue from the catalogue")
    venue = db.session.get(Venue, value)
    if venue is None or not venue.is_active:
        raise ValueError("That venue is not available in the catalogue")
    return venue.id


def _valid_equipment_item(item):
    quantity = item.get("quantity") if isinstance(item, dict) else None
    return (
        isinstance(item, dict)
        and str(item.get("type") or "").strip() != ""
        and isinstance(quantity, int)
        and not isinstance(quantity, bool)
        and quantity > 0
    )


def _clean_equipment(value):
    if not isinstance(value, list) or not all(_valid_equipment_item(i) for i in value):
        raise ValueError("Each equipment item needs a type and a positive quantity")
    return value  # stored exactly as given


CLEANERS = {
    "name": _text("Event name", True),
    "purpose": _text("Purpose", True),
    "description": _text("Description", True),
    "category": _text("Category", False),
    "accessibility_needs": _text("Accessibility needs", False),
    "required_layout": _text("Venue Required", False),
    "proposed_date": _clean_date,
    "proposed_time": _clean_time,
    "expected_attendance": _positive_int("Expected attendance"),
    "capacity_needed": _positive_int("Equipment Required"),
    "intended_capacity": _positive_int("Intended capacity"),
    "required_facilities": _clean_facilities,
    "registration_required": _clean_bool,
    "venue_id": _clean_venue,
    "equipment_requirements": _clean_equipment,
}


# ---------------------------------------------------------------------
# Current value and comparison
# ---------------------------------------------------------------------

def _current_value(event: Event, field: str):
    if field == "proposed_date":
        return event.proposed_date.isoformat() if event.proposed_date else None
    if field == "proposed_time":
        return event.proposed_time.isoformat() if event.proposed_time else None
    if field == "required_facilities":
        return list(event.required_facilities or [])
    if field == "registration_required":
        return bool(event.registration_required)
    if field == "venue_id":
        booking = (
            VenueBooking.query.filter_by(event_id=event.id, status=BOOKING_APPROVED)
            .order_by(VenueBooking.start_datetime.asc())
            .first()
        )
        return booking.venue_id if booking else None
    if field == "equipment_requirements":
        return [
            {"type": e.equipment_type, "quantity": e.quantity, "technicalNotes": e.technical_notes}
            for e in event.equipment_requirements
        ]
    return getattr(event, field)


def _equipment_key(items):
    return sorted(
        (str(i["type"]).strip().lower(), i["quantity"], (i.get("technicalNotes") or "").strip())
        for i in items
    )


def _blank(value):
    return value in (None, "", [])


def _same(field, current, proposed):
    if field == "equipment_requirements":
        return _equipment_key(current) == _equipment_key(proposed)
    return current == proposed or (_blank(current) and _blank(proposed))


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------
def current_venue_id(event: Event):
    """The venue shown as 'current' on the change form (earliest approved booking)."""
    return _current_value(event, "venue_id")

def can_request_change(event: Event, user_id: int) -> bool:
    return event.organiser_id == user_id and event.status in CHANGEABLE_STATUSES


def submit_change_request(event: Event, organiser_id: int, changes: dict, reason: str) -> ChangeRequest:
    if event.organiser_id != organiser_id:
        raise PermissionError("Only the organiser of this event can request a change")
    if event.status not in CHANGEABLE_STATUSES:
        raise ChangeRequestError({"event": STATUS_MESSAGE})

    errors, requested = {}, {}
    for field, raw in (changes or {}).items():
        if field not in CLEANERS:
            errors[field] = f"{field} cannot be changed through a change request"
            continue
        try:
            proposed = CLEANERS[field](raw)
        except ValueError as problem:
            errors[field] = str(problem)
            continue
        current = _current_value(event, field)
        if not _same(field, current, proposed):
            requested[field] = {"from": current, "to": proposed}

    if not errors and not requested:
        errors["changes"] = "Change at least one value before submitting"
    try:
        validate_descriptive_text(reason if isinstance(reason, str) else "", "reason")
    except ValueError as problem:
        errors["reason"] = str(problem)
    if errors:
        raise ChangeRequestError(errors)  # nothing has been added to the session

    change_request = ChangeRequest(
        event_id=event.id,
        organiser_id=organiser_id,
        requested_changes=requested,
        reason=reason.strip(),
        is_significant=any(field in SIGNIFICANT_FIELDS for field in requested),
        status="pending",
    )
    db.session.add(change_request)
    db.session.commit()
    return change_request


def list_change_requests_for_event(event: Event, user_id: int):
    """The organiser's own requests for this event, newest first."""
    if event.organiser_id != user_id:
        raise PermissionError("Only the organiser of this event can view its change requests")
    return (
        ChangeRequest.query.filter_by(event_id=event.id)
        .order_by(ChangeRequest.created_at.desc(), ChangeRequest.id.desc())
        .all()
    )


def list_change_requests_for_coordinator(coordinator_id: int):
    """Requests on events this Coordinator is currently assigned to, oldest
    first. Uses the event's current Coordinator, so reassignment is respected."""
    return (
        ChangeRequest.query.join(Event, ChangeRequest.event_id == Event.id)
        .filter(Event.coordinator_id == coordinator_id)
        .order_by(ChangeRequest.created_at.asc(), ChangeRequest.id.asc())
        .all()
    )