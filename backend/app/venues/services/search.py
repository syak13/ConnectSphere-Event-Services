"""Venue Search and Filtering epic: Story 1 (date, time, attendance)."""
from datetime import datetime, timedelta

from app.models.venue import BOOKING_APPROVED, Venue, VenueBooking, VenueUnavailability
from app.venues.services.availability import compute_booking_window, pad_window

# Venue capacity is INT UNSIGNED in database/schema.sql.
MAX_VENUE_CAPACITY = (1 << 32) - 1


def _is_available(venue: Venue, start: datetime, end: datetime) -> bool:
    """A venue is free if the requested window, padded by the venue's own
    setup/turnaround time (Week 7 change #1), overlaps no APPROVED booking
    (also padded) and no recorded unavailability. Pending, rejected and
    withdrawn bookings never block. Windows that only touch do not overlap."""
    requested_start, requested_end = pad_window(start, end, venue)
    prefilter_buffer = timedelta(
        minutes=(venue.setup_minutes or 0) + (venue.turnaround_minutes or 0)
    )

    approved = VenueBooking.query.filter(
        VenueBooking.venue_id == venue.id,
        VenueBooking.status == BOOKING_APPROVED,
        VenueBooking.start_datetime < requested_end + prefilter_buffer,
        VenueBooking.end_datetime > requested_start - prefilter_buffer,
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
    if expected_attendance > MAX_VENUE_CAPACITY:
        return []

    start = datetime.combine(date, start_time)
    end = datetime.combine(date, end_time)

    venues = Venue.query.filter(
        Venue.is_active.is_(True),
        Venue.capacity >= expected_attendance,
    ).all()

    available = [venue for venue in venues if _is_available(venue, start, end)]
    return sorted(available, key=lambda venue: venue.name.casefold())