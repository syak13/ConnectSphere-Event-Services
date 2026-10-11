"""Venue Search and Filtering epic: Stories 1 and 2."""
from datetime import datetime, timedelta

from sqlalchemy import or_

from app.models.venue import (
    BOOKING_APPROVED,
    Venue,
    VenueAccessibilityFeature,
    VenueBooking,
    VenueFacility,
    VenueUnavailability,
)
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


def search_venues(
    date,
    start_time,
    end_time,
    expected_attendance,
    location=None,
    max_capacity=None,
    accessibility_features=None,
    required_facilities=None,
):
    """Active venues with capacity >= expected_attendance that are free for
    the whole window, narrowed by any catalogue filters, sorted by name."""
    if max_capacity is not None and max_capacity < expected_attendance:
        raise ValueError("Maximum capacity cannot be lower than expected attendance.")
    if expected_attendance > MAX_VENUE_CAPACITY:
        return []

    start = datetime.combine(date, start_time)
    end = datetime.combine(date, end_time)

    query = Venue.query.filter(
        Venue.is_active.is_(True),
        Venue.capacity >= expected_attendance,
    )
    if location:
        query = query.filter(Venue.location == location)
    if max_capacity is not None:
        query = query.filter(Venue.capacity <= max_capacity)
    for feature in accessibility_features or []:
        query = query.filter(
            or_(
                Venue.accessibility_entries.any(
                    VenueAccessibilityFeature.feature_name == feature
                ),
                Venue.accessibility_info == feature,
            )
        )
    for facility in required_facilities or []:
        query = query.filter(
            Venue.facility_entries.any(VenueFacility.facility_name == facility)
        )

    venues = query.all()
    available = [venue for venue in venues if _is_available(venue, start, end)]
    return sorted(available, key=lambda venue: venue.name.casefold())


def get_filter_options():
    """Return selectable filter values represented in the active catalogue."""
    active_venues = Venue.query.filter(Venue.is_active.is_(True))
    locations = (
        active_venues.with_entities(Venue.location)
        .distinct()
        .order_by(Venue.location)
        .all()
    )
    facilities = (
        VenueFacility.query.join(Venue)
        .filter(Venue.is_active.is_(True))
        .with_entities(VenueFacility.facility_name)
        .distinct()
        .order_by(VenueFacility.facility_name)
        .all()
    )
    accessibility_features = (
        VenueAccessibilityFeature.query.join(Venue)
        .filter(Venue.is_active.is_(True))
        .with_entities(VenueAccessibilityFeature.feature_name)
        .distinct()
        .order_by(VenueAccessibilityFeature.feature_name)
        .all()
    )
    legacy_accessibility_info = (
        Venue.query.filter(
            Venue.is_active.is_(True),
            Venue.accessibility_info.isnot(None),
            Venue.accessibility_info != "",
        )
        .with_entities(Venue.accessibility_info)
        .distinct()
        .all()
    )
    return {
        "locations": [value for (value,) in locations],
        "facilities": [value for (value,) in facilities],
        "accessibilityFeatures": sorted(
            {
                value
                for (value,) in accessibility_features + legacy_accessibility_info
            },
            key=str.casefold,
        ),
    }