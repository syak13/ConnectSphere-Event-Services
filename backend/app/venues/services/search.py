"""Venue Search and Filtering epic."""
from datetime import datetime, timedelta

from app.models.venue import Venue, VenueBooking, VenueUnavailability

CONFIRMED = "confirmed"


def _is_available(venue_id: int, start: datetime, end: datetime) -> bool:
    overlapping_booking = VenueBooking.query.filter(
        VenueBooking.venue_id == venue_id,
        VenueBooking.status == CONFIRMED,
    ).all()
    for b in overlapping_booking:
        event = b.event
        if event and event.proposed_date:
            # Approximate the event's window as its proposed date/time,
            # defaulting to a 2-hour slot when no explicit end is modelled.
            event_start = datetime.combine(event.proposed_date, event.proposed_time or datetime.min.time())
            event_end = event_start + timedelta(hours=2)
            if event_start < end and start < event_end:
                return False

    blocks = VenueUnavailability.query.filter(
        VenueUnavailability.venue_id == venue_id,
        VenueUnavailability.end_datetime > start,
        VenueUnavailability.start_datetime < end,
    ).all()
    return len(blocks) == 0


def search_venues(
    date=None,
    time=None,
    expected_attendance=None,
    location=None,
    accessibility_needs=None,
    required_facilities=None,
    required_layout=None,
):
    query = Venue.query.filter_by(is_active=True)

    if expected_attendance:
        query = query.filter(Venue.capacity >= expected_attendance)
    if location:
        query = query.filter(Venue.location.ilike(f"%{location}%"))

    candidates = query.all()

    results = []
    for venue in candidates:
        if required_layout and (venue.supported_layouts is None or required_layout not in venue.supported_layouts):
            continue
        if required_facilities:
            venue_facilities = set(venue.facilities or [])
            if not set(required_facilities).issubset(venue_facilities):
                continue
        if accessibility_needs:
            venue_access = set(venue.accessibility_features or [])
            if not set(accessibility_needs).issubset(venue_access):
                continue
        if date and time:
            start = datetime.combine(date, time)
            end = start + timedelta(hours=2)
            if not _is_available(venue.id, start, end):
                continue
        results.append(venue)

    return results
