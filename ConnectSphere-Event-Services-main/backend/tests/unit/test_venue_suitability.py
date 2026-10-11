"""
Venue Suitability Check — one test class per user story, one test per
acceptance criterion (names reference the AC number).

Story 1: Flag capacity mismatch as unsuitable
Story 2: Flag accessibility or layout mismatch as unsuitable
Story 3: Coordinator overrides a suitability flag

"Assigning" a venue means putting it in a Venue Booking Request
(booking_requests.submit_booking_requests).
"""
from datetime import date, time, timedelta

import pytest

from app.common.time import utcnow
from app.events.services import drafts
from app.extensions import db
from app.models.event import Event
from app.models.venue import Venue, VenueBooking, VenueSuitabilityOverride
from app.venues.services import suitability_check as s
from app.venues.services.requirements import ACCESSIBILITY_FEATURES
from app.venues.services.booking_requests import BookingRequestError, submit_booking_requests

EN_DASH = "–"
FUTURE = utcnow().date() + timedelta(days=60)


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

def _venue(name="Room", capacity=35, layouts=("Theatre",), access=(), active=True):
    """A Venue Catalogue record. Layouts are stored lowercase (as the catalogue
    does); accessibility features are free-text names, given here as codes and
    stored as their human labels (e.g. "Step-free access")."""
    v = Venue(name=name, location="Somewhere", capacity=capacity, is_active=active)
    v.supported_layouts = [l.lower() for l in layouts]
    v.accessibility_features = [ACCESSIBILITY_FEATURES.get(c, c) for c in access]
    db.session.add(v)
    db.session.commit()
    return v


def _check(result, flag_type):
    return next(c for c in result["checks"] if c["type"] == flag_type)


def _request(event, venue, user_id):
    """Submit a one-venue booking request (the "assignment")."""
    return submit_booking_requests(
        event,
        [{"venue_id": venue.id, "date": FUTURE, "start_time": time(10, 0), "end_time": time(12, 0)}],
        user_id,
    )


@pytest.fixture()
def coord(app, coordinator):
    from app.models.user import User
    return db.session.get(User, coordinator)


@pytest.fixture()
def event_factory(app, organiser, coordinator, make_event):
    def _make(status="approved", **fields):
        defaults = dict(
            coordinator_id=coordinator,
            expected_attendance=40,
            required_layout=None,
            accessibility_requirements=[],
            proposed_date=FUTURE,
            proposed_time=time(10, 0),
        )
        defaults.update(fields)
        return db.session.get(Event, make_event(organiser, status=status, **defaults))
    return _make


# =====================================================================
# Story 1 — capacity
# =====================================================================

class TestStory1Capacity:
    def test_ac1_flags_when_capacity_below_expected_attendance(self, event_factory):
        event = event_factory(expected_attendance=40)
        venue = _venue(capacity=35)
        cap = _check(s.evaluate_venue(event, venue), "capacity")
        assert cap["status"] == "unsuitable"
        assert cap["statusLabel"] == f"Unsuitable {EN_DASH} Capacity"
        assert cap["reasons"] == ["Capacity 35 is less than expected attendance 40."]

    def test_ac2_no_flag_when_capacity_is_enough(self, event_factory):
        event = event_factory(expected_attendance=40)
        result = s.evaluate_venue(event, _venue(capacity=120))
        assert _check(result, "capacity")["status"] == "pass"
        assert not any(f["type"] == "capacity" for f in result["flags"])

    def test_ac3_exact_match_is_suitable(self, event_factory):
        event = event_factory(expected_attendance=40)
        assert _check(s.evaluate_venue(event, _venue(capacity=40)), "capacity")["status"] == "pass"

    def test_ac4_flag_recalculated_when_attendance_edited(self, event_factory):
        event = event_factory(expected_attendance=40)
        venue = _venue(capacity=35)
        assert _check(s.evaluate_venue(event, venue), "capacity")["status"] == "unsuitable"

        event.expected_attendance = 35
        db.session.commit()
        assert _check(s.evaluate_venue(event, venue), "capacity")["status"] == "pass"

    # capacity 0 = "not recorded" (the venues.capacity column cannot be NULL)
    @pytest.mark.parametrize("attendance,capacity", [(None, 35), (40, 0), (None, 0)])
    def test_ac5_missing_data_shows_not_verified(self, event_factory, attendance, capacity):
        event = event_factory(expected_attendance=attendance)
        cap = _check(s.evaluate_venue(event, _venue(capacity=capacity)), "capacity")
        assert cap["status"] == "not_verified"
        assert cap["statusLabel"] == "Capacity not verified"

    def test_ac6_flag_and_reason_shown_when_venue_is_requested(self, event_factory, coord):
        event = event_factory(expected_attendance=40)
        venue = _venue(name="Orchid Room", capacity=35)
        with pytest.raises(BookingRequestError) as exc:
            _request(event, venue, coord.id)
        [err] = exc.value.errors
        assert err["field"] == "suitability"
        assert err["venue_id"] == venue.id
        assert f"Unsuitable {EN_DASH} Capacity" in err["message"]
        assert "Capacity 35 is less than expected attendance 40." in err["message"]
        assert VenueBooking.query.count() == 0


# =====================================================================
# Story 2 — accessibility / layout
# =====================================================================

class TestStory2AccessibilityLayout:
    def test_ac1_flags_missing_accessibility_feature(self, event_factory):
        event = event_factory(accessibility_requirements=["step_free_access"])
        acc = _check(s.evaluate_venue(event, _venue(capacity=100, access=["hearing_loop"])), "accessibility")
        assert acc["status"] == "unsuitable"
        assert acc["statusLabel"] == f"Unsuitable {EN_DASH} Accessibility"
        assert acc["reasons"] == ["Step-free access required but not available."]

    def test_ac2_flags_layout_mismatch_with_specific_reason(self, event_factory):
        event = event_factory(required_layout="Classroom")
        lay = _check(s.evaluate_venue(event, _venue(capacity=100, layouts=["Theatre"])), "layout")
        assert lay["status"] == "unsuitable"
        assert lay["statusLabel"] == f"Unsuitable {EN_DASH} Layout"
        assert lay["reasons"] == ["Classroom layout required but this venue only supports: Theatre."]

    def test_ac3_lists_every_unmet_requirement(self, event_factory):
        event = event_factory(
            accessibility_requirements=["step_free_access", "hearing_loop", "accessible_toilet"]
        )
        acc = _check(s.evaluate_venue(event, _venue(capacity=100, access=["hearing_loop"])), "accessibility")
        assert acc["reasons"] == [
            "Step-free access required but not available.",
            "Accessible toilet nearby required but not available.",
        ]

    def test_ac4_no_flag_when_all_requirements_met(self, event_factory):
        event = event_factory(
            required_layout="theater",  # free-text spelling is normalised
            accessibility_requirements=["step_free_access", "hearing_loop"],
        )
        venue = _venue(capacity=100, layouts=["Theatre", "Banquet"], access=["step_free_access", "hearing_loop"])
        result = s.evaluate_venue(event, venue)
        assert _check(result, "accessibility")["status"] == "pass"
        assert _check(result, "layout")["status"] == "pass"

    def test_ac5_no_requirements_means_no_flag(self, event_factory):
        event = event_factory(required_layout=None, accessibility_requirements=[])
        result = s.evaluate_venue(event, _venue(capacity=100, layouts=[], access=[]))
        assert _check(result, "accessibility")["status"] == "pass"
        assert _check(result, "layout")["status"] == "pass"
        assert result["overallStatus"] == "pass"

    def test_ac6_capacity_and_accessibility_flags_shown_separately(self, event_factory):
        event = event_factory(expected_attendance=40, accessibility_requirements=["step_free_access"])
        result = s.evaluate_venue(event, _venue(capacity=35))
        types = [f["type"] for f in result["flags"]]
        assert types == ["capacity", "accessibility"]
        assert all(f["reasons"] for f in result["flags"])

    def test_unrecognised_layout_is_not_verified_rather_than_guessed(self, event_factory):
        event = event_factory(required_layout="Fishbowl")
        lay = _check(s.evaluate_venue(event, _venue(capacity=100)), "layout")
        assert lay["status"] == "not_verified"


# =====================================================================
# Story 3 — overrides
# =====================================================================

class TestStory3Override:
    def test_ac1_override_requires_reason_of_at_least_10_chars(self, event_factory, coord):
        event = event_factory(expected_attendance=40)
        venue = _venue(capacity=35)
        for bad in (None, "", "   ", "too short", "1234567890!"):
            with pytest.raises(ValueError):
                s.override_flag(event, venue, coord, "capacity", bad)
        assert VenueSuitabilityOverride.query.count() == 0

        s.override_flag(event, venue, coord, "capacity", "Extra chairs arranged")
        assert VenueSuitabilityOverride.query.count() == 1

    def test_ac2_venue_can_be_requested_and_shows_overridden(self, event_factory, coord):
        event = event_factory(expected_attendance=40)
        venue = _venue(capacity=35)
        s.override_flag(event, venue, coord, "capacity", "Extra chairs arranged")

        cap = _check(s.evaluate_venue(event, venue), "capacity")
        assert cap["status"] == "overridden"
        assert cap["statusLabel"] == f"Overridden {EN_DASH} Capacity"

        [booking] = _request(event, venue, coord.id)
        assert booking.status == "pending" and booking.venue_id == venue.id

    def test_ac3_audit_record_kept(self, event_factory, coord):
        event = event_factory(expected_attendance=40)
        venue = _venue(capacity=35)
        s.override_flag(event, venue, coord, "capacity", "Extra chairs arranged")
        [entry] = s.override_history(event)
        assert entry["overriddenByName"] == "Test Coordinator"
        assert entry["createdAt"]
        assert entry["flagType"] == "capacity"
        assert entry["reason"] == "Extra chairs arranged"

    def test_ac4_only_assigned_coordinator_can_override(self, event_factory, make_user):
        from app.models.user import User
        event = event_factory(expected_attendance=40)
        venue = _venue(capacity=35)
        venue_staff = db.session.get(User, make_user("vs@test.com", ["venue_staff"]))
        other_coord = db.session.get(User, make_user("c2@test.com", ["event_coordinator"]))
        for user in (venue_staff, other_coord):
            with pytest.raises(PermissionError):
                s.override_flag(event, venue, user, "capacity", "Extra chairs arranged")

    def test_ac5_overrides_are_per_flag(self, event_factory, coord):
        event = event_factory(expected_attendance=40, accessibility_requirements=["step_free_access"])
        venue = _venue(capacity=35)
        s.override_flag(event, venue, coord, "capacity", "Extra chairs arranged")

        result = s.evaluate_venue(event, venue)
        assert _check(result, "capacity")["status"] == "overridden"
        assert _check(result, "accessibility")["status"] == "unsuitable"
        with pytest.raises(BookingRequestError) as exc:
            _request(event, venue, coord.id)
        [err] = exc.value.errors
        assert f"Unsuitable {EN_DASH} Accessibility" in err["message"]

    def test_ac6_override_resets_when_mismatch_changes(self, event_factory, coord):
        event = event_factory(expected_attendance=40)
        venue = _venue(capacity=35)
        s.override_flag(event, venue, coord, "capacity", "Extra chairs arranged")

        event.expected_attendance = 60  # a different mismatch
        db.session.commit()

        cap = _check(s.evaluate_venue(event, venue), "capacity")
        assert cap["status"] == "unsuitable"
        db.session.rollback()  # check what was actually saved
        [entry] = s.override_history(event)
        assert entry["isActive"] is False and entry["clearedReason"]

        # reverting the number does NOT silently resurrect the old override
        event.expected_attendance = 40
        db.session.commit()
        assert _check(s.evaluate_venue(event, venue), "capacity")["status"] == "unsuitable"

    def test_cannot_override_a_flag_that_is_not_active(self, event_factory, coord):
        event = event_factory(expected_attendance=10)
        with pytest.raises(s.SuitabilityError):
            s.override_flag(event, _venue(capacity=35), coord, "capacity", "Extra chairs arranged")


# =====================================================================
# Event request plumbing for the new structured field
# =====================================================================

def test_accessibility_requirements_saved_on_draft_and_cleaned(app, organiser):
    event = drafts.create_draft(
        organiser, {"name": "X", "accessibility_requirements": [" Step_Free_Access ", "step_free_access"]}
    )
    assert event.accessibility_requirements == ["step_free_access"]
    assert event.to_dict()["venueRequirements"]["accessibilityRequirements"] == ["step_free_access"]


def test_unknown_accessibility_code_blocks_submission(app, organiser):
    from app.events.services.validators import validate_for_submission
    event = Event(organiser_id=organiser, accessibility_requirements=["teleporter"])
    assert any("teleporter" in e for e in validate_for_submission(event))
