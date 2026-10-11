from datetime import date, datetime, time

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
from app.venues.services import search as search_service
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


def _search(app, attendance=50, start=time(10), end=time(12), **filters):
    with app.app_context():
        return search_venues(SEARCH_DATE, start, end, attendance, **filters)


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

def test_attendance_above_capacity_column_range_returns_empty_without_query(app):
    assert _search(app, attendance=4_294_967_296) == []


# Story 1: Rechecks existing search behavior after a booking or capacity changes.
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


# ---------------------------------------------------------------------------
# User Story 2 unit tests: catalogue filters only; date/time availability is
# covered by the Story 1 tests above.
# ---------------------------------------------------------------------------


# AC1/AC2/AC4: Combines location and max capacity with all-selected feature
# filters, while preserving the attendance lower bound and exact max boundary.
def test_combined_filters_require_all_values_and_keep_attendance_bound(app):
    matching_id = _add_venue(
        app,
        "Matching",
        capacity=60,
        location="East Campus",
        facilities=["Projector", "Wi-Fi"],
        accessibility_features=["Step-free access", "Hearing loop"],
    )
    _add_venue(
        app,
        "Wrong location",
        capacity=60,
        location="West Campus",
        facilities=["Projector", "Wi-Fi"],
        accessibility_features=["Step-free access", "Hearing loop"],
    )
    _add_venue(
        app,
        "Missing facility",
        capacity=60,
        location="East Campus",
        facilities=["Projector"],
        accessibility_features=["Step-free access", "Hearing loop"],
    )
    _add_venue(
        app,
        "Missing accessibility feature",
        capacity=60,
        location="East Campus",
        facilities=["Projector", "Wi-Fi"],
        accessibility_features=["Step-free access"],
    )
    _add_venue(
        app,
        "Above maximum",
        capacity=61,
        location="East Campus",
        facilities=["Projector", "Wi-Fi"],
        accessibility_features=["Step-free access", "Hearing loop"],
    )
    below_attendance_id = _add_venue(
        app,
        "Below attendance",
        capacity=49,
        location="East Campus",
        facilities=["Projector", "Wi-Fi"],
        accessibility_features=["Step-free access", "Hearing loop"],
    )

    results = _search(
        app,
        attendance=50,
        location="East Campus",
        max_capacity=60,
        accessibility_features=["Step-free access", "Hearing loop"],
        required_facilities=["Projector", "Wi-Fi"],
    )

    assert [venue.id for venue in results] == [matching_id]
    assert below_attendance_id not in {venue.id for venue in results}


# AC2: Rejects a maximum one below attendance rather than returning empty results.
def test_max_capacity_below_attendance_is_rejected_by_service(app):
    _add_venue(app, capacity=100)

    with pytest.raises(ValueError, match="lower than expected attendance"):
        _search(app, attendance=50, max_capacity=49)


# AC2: Checks the maximum against oversized attendance before the database cap shortcut.
def test_max_capacity_is_checked_when_attendance_exceeds_database_range(app):
    with pytest.raises(ValueError, match="lower than expected attendance"):
        _search(app, attendance=4_294_967_296, max_capacity=4_294_967_295)


# AC3: Derives sorted, unique filter options from active catalogue entries only.
def test_filter_options_are_distinct_catalogue_values_for_active_venues(app):
    _add_venue(
        app,
        "First",
        location="East Campus",
        facilities=["Projector", "Wi-Fi"],
        accessibility_features=["Lift access"],
    )
    _add_venue(
        app,
        "Second",
        location="East Campus",
        facilities=["Projector", "Microphone"],
        accessibility_features=["Hearing loop"],
    )
    _add_venue(
        app,
        "Inactive",
        location="Closed Campus",
        is_active=False,
        facilities=["Unused"],
        accessibility_features=["Unused"],
    )

    with app.app_context():
        options = search_service.get_filter_options()

    assert options == {
        "locations": ["East Campus"],
        "facilities": ["Microphone", "Projector", "Wi-Fi"],
        "accessibilityFeatures": ["Hearing loop", "Lift access"], 
        "layouts": [],
    }


# AC5: Reapplying changed filters updates matches; an unmatched value returns
# zero, and clearing filters restores all base-search matches.
def test_changing_and_clearing_filters_recomputes_matches(app):
    east_id = _add_venue(
        app,
        "East venue",
        capacity=60,
        location="East Campus",
        facilities=["Projector"],
    )
    west_id = _add_venue(
        app,
        "West venue",
        capacity=70,
        location="West Campus",
        facilities=["Whiteboard"],
    )

    east_results = _search(app, location="East Campus")
    missing_results = _search(app, location="East Campus", max_capacity=59)
    changed_results = _search(app, location="West Campus")
    cleared_results = _search(app)

    assert [venue.id for venue in east_results] == [east_id]
    assert missing_results == []
    assert [venue.id for venue in changed_results] == [west_id]
    assert {venue.id for venue in cleared_results} == {east_id, west_id}

# =====================================================================
# Story 2 follow-up fixes (unit): paste at the bottom of
# tests/unit/test_venue_search_service.py
# =====================================================================
def _names(venues):
    return [v.name for v in venues]

def test_s2_free_text_accessibility_info_is_not_a_filter_option_or_match(app):
    _add_venue(
        app,
        "Text only",
        accessibility_info="Wheelchair accessible, hearing loop",  # free text, no feature rows
    )
    _add_venue(app, "Structured", accessibility_features=["Wheelchair accessible"])

    with app.app_context():
        options = search_service.get_filter_options()
    assert options["accessibilityFeatures"] == ["Wheelchair accessible"]
    assert _names(_search(app, accessibility_features=["Wheelchair accessible"])) == ["Structured"]


def test_s2_facility_location_and_accessibility_matching_ignore_case(app):
    _add_venue(
        app,
        "Hall",
        location="North Campus",
        facilities=["Projector"],
        accessibility_features=["Hearing loop"],
    )

    assert _names(_search(app, required_facilities=["projector"])) == ["Hall"]
    assert _names(_search(app, location="north campus")) == ["Hall"]
    assert _names(_search(app, accessibility_features=["HEARING LOOP"])) == ["Hall"]


def test_s2_venues_without_a_location_do_not_create_a_blank_location_option(app):
    _add_venue(app, "No location", location=None)
    _add_venue(app, "Blank location", location="")
    _add_venue(app, "Has location", location="East Campus")

    with app.app_context():
        assert search_service.get_filter_options()["locations"] == ["East Campus"]


@pytest.mark.parametrize(
    "start,end,expected",
    [
        (time(8), time(10), True),     # starts exactly at opening
        (time(20), time(22), True),    # ends exactly at closing
        (time(7, 30), time(9), False),  # starts before opening
        (time(21), time(22, 30), False),  # ends after closing
    ],
)
def test_s2_search_respects_operating_hours(app, start, end, expected):
    _add_venue(app, "Day venue", operating_hours="08:00-22:00")
    _add_venue(app, "No hours recorded", operating_hours=None)

    names = _names(_search(app, start=start, end=end))
    assert ("Day venue" in names) is expected
    assert "No hours recorded" in names  # blank hours = no restriction