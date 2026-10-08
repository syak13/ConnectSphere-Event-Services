"""
Venue Booking Request / Venue Booking Approval / Booking Conflict Detection.

Only APPROVED bookings block a venue due to a booking conflict.
Pending conflicts are resolved outside the system by default.

An event can request multiple different venues, but it cannot have more than
one active (pending or approved) booking for the same venue.

Each booking carries its own start_datetime/end_datetime, so conflicts are
checked booking-against-booking, not event-against-event.
"""

from app.common.time import utcnow
from app.extensions import db
from app.models.event import Event
from app.models.venue import (
    ACTIVE_BOOKING_STATUSES as ACTIVE_STATUSES,
    BOOKING_APPROVED as APPROVED,
    BOOKING_PENDING as PENDING,
    BOOKING_REJECTED as REJECTED,
    BOOKING_WITHDRAWN as WITHDRAWN,
    Venue,
    VenueBooking,
)
from app.venues.services.availability import compute_booking_window


def submit_booking_request(
    event: Event,
    venue: Venue,
    user_id: int,
) -> VenueBooking:
    """
    Submit a booking request for a venue.

    An event may have more than one venue booking, but it cannot
    have another active booking for the same venue.
    """

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

    booking = VenueBooking(
        event_id=event.id,
        venue_id=venue.id,
        requested_by=user_id,
        status=PENDING,
    )

    db.session.add(booking)
    db.session.commit()

    return booking


def withdraw_booking_request(
    booking: VenueBooking,
    user_id: int,
) -> VenueBooking:
    """Withdraw a pending booking request."""

    if booking.status != PENDING:
        raise ValueError(
            "Only a pending booking request can be withdrawn"
        )

    booking.status = WITHDRAWN
    booking.decided_by = user_id
    booking.decided_at = utcnow()

    db.session.commit()

    return booking


def has_confirmed_conflict(
    venue_id: int,
    candidate: VenueBooking,
    exclude_booking_id: int = None,
) -> bool:
    """
    Return True if approving the candidate would double-book
    the venue against another APPROVED booking.

    The function name is kept as has_confirmed_conflict for
    compatibility with existing code.
    """

    venue = Venue.query.get(venue_id)

    if not venue:
        return False

    window = compute_booking_window(
        candidate,
        venue,
    )

    if window is None:
        return False

    start, end = compute_booking_window(
        candidate,
        venue,
    )
    
    approved_bookings = VenueBooking.query.filter(
        VenueBooking.venue_id == venue_id,
        VenueBooking.status == APPROVED,
    )

    if exclude_booking_id:
        approved_bookings = approved_bookings.filter(
            VenueBooking.id != exclude_booking_id
        )

    for other in approved_bookings.all():
        other_start, other_end = compute_booking_window(
            other,
            venue,
        )

        if other_start < end and start < other_end:
            return True

    return False


def approve_booking(
    booking: VenueBooking,
    decided_by: int,
) -> VenueBooking:
    """Approve a pending booking request."""

    if booking.status != PENDING:
        raise ValueError(
            "Only a pending booking request can be approved"
        )

    if has_confirmed_conflict(
        booking.venue_id,
        booking,
        exclude_booking_id=booking.id,
    ):
        raise ValueError(
            "This venue already has an approved booking "
            "that overlaps with this booking's time"
        )

    booking.status = APPROVED
    booking.decided_by = decided_by
    booking.decided_at = utcnow()

    db.session.commit()

    return booking


def reject_booking(
    booking: VenueBooking,
    decided_by: int,
    reason: str = None,
) -> VenueBooking:
    """Reject a pending booking request."""

    if booking.status != PENDING:
        raise ValueError(
            "Only a pending booking request can be rejected"
        )

    booking.status = REJECTED
    booking.decided_by = decided_by
    booking.decision_reason = reason
    booking.decided_at = utcnow()

    db.session.commit()

    return booking