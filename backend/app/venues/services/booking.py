"""
Venue Booking Request / Venue Booking Approval / Booking Conflict Detection.

Booking Conflict Detection scope note: only CONFIRMED bookings block a venue
(Q&A: confirmed bookings block availability; pending conflicts are resolved
outside the system by default). approve_booking() enforces this as a hard
block; submitting two pending requests for an overlapping slot is allowed
and is only surfaced as an advisory warning, never blocked.
"""
from app.common.time import utcnow
from app.extensions import db
from app.models.event import Event
from app.models.venue import Venue, VenueBooking
from app.venues.services.availability import compute_effective_window

PENDING = "pending"
CONFIRMED = "confirmed"
REJECTED = "rejected"
WITHDRAWN = "withdrawn"
ACTIVE_STATUSES = (PENDING, CONFIRMED)


def submit_booking_request(event: Event, venue: Venue, user_id: int, label: str = None) -> VenueBooking:
    """Week 7 change #3: an event can have more than one venue booking
    (e.g. a main auditorium plus several breakout rooms), so this no
    longer blocks on the event already having *an* active booking -- only
    on the event already having an active booking for *this specific
    venue*, which would just be a redundant duplicate request."""
    existing = VenueBooking.query.filter(
        VenueBooking.event_id == event.id,
        VenueBooking.venue_id == venue.id,
        VenueBooking.status.in_(ACTIVE_STATUSES),
    ).first()
    if existing:
        raise ValueError(
            "This event already has an active booking for this venue; "
            "withdraw it before requesting it again"
        )

    booking = VenueBooking(event_id=event.id, venue_id=venue.id, requested_by=user_id, status=PENDING, label=label)
    db.session.add(booking)
    db.session.commit()
    return booking


def withdraw_booking_request(booking: VenueBooking, user_id: int) -> VenueBooking:
    if booking.status != PENDING:
        raise ValueError("Only a pending booking request can be withdrawn")
    booking.status = WITHDRAWN
    booking.decided_by = user_id
    booking.decided_at = utcnow()
    db.session.commit()
    return booking


def has_confirmed_conflict(venue_id: int, event: Event, exclude_booking_id: int = None) -> bool:
    """Booking Conflict Detection: True if approving this booking would
    double-book the venue against another CONFIRMED booking. Uses the same
    setup/turnaround-padded window as the Availability Calendar (Week 7
    change #1), via compute_effective_window, so the two can't drift."""
    venue = Venue.query.get(venue_id)
    if not venue or not event.proposed_date:
        return False
    start, end = compute_effective_window(event, venue)

    confirmed = VenueBooking.query.filter(
        VenueBooking.venue_id == venue_id,
        VenueBooking.status == CONFIRMED,
    )
    if exclude_booking_id:
        confirmed = confirmed.filter(VenueBooking.id != exclude_booking_id)

    for other in confirmed.all():
        other_event = other.event
        if not other_event or not other_event.proposed_date:
            continue
        other_start, other_end = compute_effective_window(other_event, venue)
        if other_start < end and start < other_end:
            return True
    return False


def approve_booking(booking: VenueBooking, decided_by: int) -> VenueBooking:
    if booking.status != PENDING:
        raise ValueError("Only a pending booking request can be approved")

    if has_confirmed_conflict(booking.venue_id, booking.event, exclude_booking_id=booking.id):
        raise ValueError("This venue already has a confirmed booking that overlaps with this event's time")

    booking.status = CONFIRMED
    booking.decided_by = decided_by
    booking.decided_at = utcnow()
    db.session.commit()
    return booking


def reject_booking(booking: VenueBooking, decided_by: int, reason: str = None) -> VenueBooking:
    if booking.status != PENDING:
        raise ValueError("Only a pending booking request can be rejected")
    booking.status = REJECTED
    booking.decided_by = decided_by
    booking.decision_reason = reason
    booking.decided_at = utcnow()
    db.session.commit()
    return booking
