from datetime import date, datetime, time, timedelta

import pytest

from app.extensions import db
from app.models.event import Event
from app.models.venue import (
    BOOKING_APPROVED,
    BOOKING_PENDING,
    BOOKING_REJECTED,
    BOOKING_WITHDRAWN,
    Venue,
    VenueBooking,
    VenueUnavailability,
)
from app.venues.services.search import search_venues

SEARCH_DATE = date(2026, 10, 8)


def _add_venue(app, name="Test venue", **overrides):
    data = {
        "name": name,
        "location": "North Campus",
        "capacity": 50,
        "is_active": True,
        "setup_minutes": 0,
        "turnaround_minutes": 0,
    }
    data.update(overrides)
    with app.app_context():
        venue = Venue(**data)
        db.session.add(venue)
        db.session.commit()
        return venue.id


def _add_booking(
    app,
    venue_id,
    coordinator_id,
    start,
    end,
    status=BOOKING_APPROVED,
):
    with app.app_context():
        event = Event(
            name="Booking event",
            organiser_id=coordinator_id,
            proposed_date=start.date(),
            proposed_time=start.time(),
        )
        db.session.add(event)
        db.session.flush()
        booking = VenueBooking(
            event_id=event.id,
            venue_id=venue_id,
            requested_by=coordinator_id,
            status=status,
            start_datetime=start,
            end_datetime=end,
        )
        db.session.add(booking)
        db.session.commit()
        return booking.id


def _search(app, attendance=50, start=time(10), end=time(12)):
    with app.app_context():
        return search_venues(SEARCH_DATE, start, end, attendance)


def test_capacity_comparison_includes_exact_boundary_and_excludes_under_and_inactive(
    app,
):
    exact_id = _add_venue(app, "Exact", capacity=50)
    larger_id = _add_venue(app, "Larger", capacity=51)
    _add_venue(app, "Too small", capacity=49)
    _add_venue(app, "Inactive", capacity=200, is_active=False)

    results = _search(app, attendance=50)

    assert {venue.id for venue in results} == {exact_id, larger_id}
    assert [venue.name for venue in results] == ["Exact", "Larger"]


@pytest.mark.parametrize(
    ("status", "should_block"),
    [
        (BOOKING_APPROVED, True),
        (BOOKING_PENDING, False),
        (BOOKING_REJECTED, False),
        (BOOKING_WITHDRAWN, False),
    ],
)
def test_only_approved_overlapping_bookings_block_search(
    app, coordinator, status, should_block
):
    venue_id = _add_venue(app)
    _add_booking(
        app,
        venue_id,
        coordinator,
        datetime(2026, 10, 8, 11, 0),
        datetime(2026, 10, 8, 13, 0),
        status,
    )

    results = _search(app)

    assert bool(results) == (not should_block)


@pytest.mark.parametrize(
    ("booking_start", "booking_end", "should_block"),
    [
        (datetime(2026, 10, 8, 8), datetime(2026, 10, 8, 10), False),
        (datetime(2026, 10, 8, 8), datetime(2026, 10, 8, 10, 1), True),
        (datetime(2026, 10, 8, 12), datetime(2026, 10, 8, 13), False),
        (datetime(2026, 10, 8, 11, 59), datetime(2026, 10, 8, 13), True),
        (datetime(2026, 10, 9, 10), datetime(2026, 10, 9, 12), False),
    ],
)
def test_booking_overlap_uses_half_open_datetimes_and_search_date(
    app, coordinator, booking_start, booking_end, should_block
):
    venue_id = _add_venue(app)
    _add_booking(
        app, venue_id, coordinator, booking_start, booking_end, BOOKING_APPROVED
    )

    results = _search(app)

    assert bool(results) == (not should_block)


@pytest.mark.parametrize(
    ("block_start", "block_end", "should_block"),
    [
        (datetime(2026, 10, 8, 11), datetime(2026, 10, 13), True),
        (datetime(2026, 10, 8, 9), datetime(2026, 10, 8, 10), False),
        (datetime(2026, 10, 8, 12), datetime(2026, 10, 8, 13), False),
        (datetime(2026, 10, 8, 9, 59), datetime(2026, 10, 8, 10, 1), True),
        (datetime(2026, 10, 8, 11, 59), datetime(2026, 10, 8, 12, 1), True),
    ],
)
def test_recorded_unavailability_uses_half_open_overlap(
    app, block_start, block_end, should_block
):
    venue_id = _add_venue(app)
    with app.app_context():
        db.session.add(
            VenueUnavailability(
                venue_id=venue_id,
                start_datetime=block_start,
                end_datetime=block_end,
                reason="Maintenance",
            )
        )
        db.session.commit()

    results = _search(app)

    assert bool(results) == (not should_block)


@pytest.mark.parametrize(
    ("setup", "turnaround", "booking_start", "booking_end", "should_block"),
    [
        (30, 30, datetime(2026, 10, 8, 8), datetime(2026, 10, 8, 9), False),
        (30, 30, datetime(2026, 10, 8, 8), datetime(2026, 10, 8, 9, 1), True),
        (30, 30, datetime(2026, 10, 8, 12, 59), datetime(2026, 10, 8, 13), True),
        (30, 30, datetime(2026, 10, 8, 13), datetime(2026, 10, 8, 14), False),
        (1500, 0, datetime(2026, 10, 9, 12, 30), datetime(2026, 10, 9, 13, 30), True),
        (0, 1500, datetime(2026, 10, 7, 8, 30), datetime(2026, 10, 7, 9, 30), True),
    ],
)
def test_setup_and_turnaround_are_included_in_effective_overlap_window(
    app, coordinator, setup, turnaround, booking_start, booking_end, should_block
):
    venue_id = _add_venue(
        app, setup_minutes=setup, turnaround_minutes=turnaround
    )
    _add_booking(
        app, venue_id, coordinator, booking_start, booking_end, BOOKING_APPROVED
    )

    results = _search(app)

    assert bool(results) == (not should_block)


def test_empty_result_for_no_capacity_match(app):
    _add_venue(app, capacity=49)

    assert _search(app, attendance=50) == []


def test_search_reflects_booking_status_and_capacity_mutations(app, coordinator):
    venue_id = _add_venue(app, capacity=49)
    booking_id = _add_booking(
        app,
        venue_id,
        coordinator,
        datetime(2026, 10, 8, 11),
        datetime(2026, 10, 8, 13),
        BOOKING_PENDING,
    )

    assert _search(app) == []

    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        venue.capacity = 50
        db.session.commit()
    assert len(_search(app)) == 1

    with app.app_context():
        booking = db.session.get(VenueBooking, booking_id)
        booking.status = BOOKING_APPROVED
        db.session.commit()
    assert _search(app) == []
