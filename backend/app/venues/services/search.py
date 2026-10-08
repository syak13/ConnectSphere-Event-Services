"""Venue Search and Filtering epic: Story 1 (date, time, attendance)."""
from datetime import datetime, timedelta

from app.models.venue import BOOKING_APPROVED, Venue, VenueBooking, VenueUnavailability
from app.venues.services.availability import compute_booking_window, pad_window

# Coarse DB prefilter so a venue's whole booking history is never loaded; the
# exact overlap check is done in Python. Must be >= the largest setup +
# turnaround time any venue can be given.
PREFILTER_BUFFER = timedelta(hours=24)


def _is_available(venue: Venue, start: datetime, end: datetime) -> bool:
    """A venue is free if the requested window, padded by the venue's own
    setup/turnaround time (Week 7 change #1), overlaps no APPROVED booking
    (also padded) and no recorded unavailability. Pending, rejected and
    withdrawn bookings never block. Windows that only touch do not overlap."""
    requested_start, requested_end = pad_window(start, end, venue)

    approved = VenueBooking.query.filter(
        VenueBooking.venue_id == venue.id,
        VenueBooking.status == BOOKING_APPROVED,
        VenueBooking.start_datetime < requested_end + PREFILTER_BUFFER,
        VenueBooking.end_datetime > requested_start - PREFILTER_BUFFER,
    ).all()
    for booking in approved:
        busy_start, busy_end = compute_booking_window(booking, venue)
        if busy_start < requested_end and requested_start < busy_end:
            return False

    closure = VenueUnavailability.query.filter(
        VenueUnavailability.venue_id == venue.id,
        VenueUnavailability.start_datetime < requested_end,
        VenueUnavailability.end_datetime > requested_start,
    ).first()
    return closure is None


def search_venues(date, start_time, end_time, expected_attendance):
    """Active venues with capacity >= expected_attendance that are free for
    the whole window, sorted by name."""
    start = datetime.combine(date, start_time)
    end = datetime.combine(date, end_time)

    venues = Venue.query.filter(
        Venue.is_active.is_(True),
        Venue.capacity >= expected_attendance,
    ).all()

    available = [venue for venue in venues if _is_available(venue, start, end)]
    return sorted(available, key=lambda venue: venue.name.casefold())