"""
Venue Suitability Check — business rules beyond the 18 acceptance criteria.

test_venue_suitability.py has one test per AC. This file covers the
supporting rules those ACs rely on, each named for the rule it protects.
Expected values come from the rules, not from running the code.
"""
from datetime import time, timedelta

import pytest

from app.common.time import utcnow
from app.extensions import db
from app.models.event import Event
from app.models.venue import Venue, VenueBooking
from app.venues.services import suitability_check as s
from app.venues.services.booking_requests import BookingRequestError, submit_booking_requests
from app.venues.services.requirements import (
    ACCESSIBILITY_FEATURES,
    accessibility_code_for,
    clean_accessibility_codes,
    normalise_layout,
)

FUTURE = utcnow().date() + timedelta(days=60)


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


def _item(venue):
    return {"venue_id": venue.id, "date": FUTURE, "start_time": time(10, 0), "end_time": time(12, 0)}


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


# ---------------------------------------------------------------------
# Layout vocabulary
# ---------------------------------------------------------------------

class TestLayoutVocabulary:
    @pytest.mark.parametrize("raw,expected", [
        ("Theatre", "theatre"),
        ("theater", "theatre"),        # US spelling
        ("U shape", "u_shape"),
        ("U-Shape", "u_shape"),
        ("  Board Room ", "boardroom"),
        ("Fishbowl", None),            # not a recognised layout
        ("   ", None),                 # blank
        (None, None),
    ])
    def test_free_text_layouts_map_onto_the_fixed_list(self, raw, expected):
        assert normalise_layout(raw) == expected

    def test_venue_with_no_recorded_layouts_is_not_verified(self, event_factory):
        event = event_factory(required_layout="Theatre")
        lay = _check(s.evaluate_venue(event, _venue(capacity=100, layouts=[])), "layout")
        assert lay["status"] == "not_verified"
        assert lay["reasons"] == ["No supported layouts are recorded for this venue."]

    def test_duplicate_and_unknown_venue_layouts_are_listed_once(self, event_factory):
        event = event_factory(required_layout="Classroom")
        venue = _venue(capacity=100, layouts=["Theatre", "Theater", "Fishbowl"])
        lay = _check(s.evaluate_venue(event, venue), "layout")
        assert lay["reasons"] == ["Classroom layout required but this venue only supports: Theatre."]


# ---------------------------------------------------------------------
# Accessibility input cleaning
# ---------------------------------------------------------------------

class TestAccessibilityInput:
    @pytest.mark.parametrize("raw,expected", [
        (None, []),
        ([], []),
        ("hearing_loop", ["hearing_loop"]),                 # single value, not a list
        (["Hearing_Loop", " ", "hearing_loop"], ["hearing_loop"]),
    ])
    def test_requirements_are_trimmed_lowercased_and_deduplicated(self, raw, expected):
        assert clean_accessibility_codes(raw) == expected


# ---------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------

class TestOverrideRules:
    def test_override_clears_when_the_mismatch_disappears(self, event_factory, coord):
        event = event_factory(expected_attendance=40)
        venue = _venue(capacity=35)
        s.override_flag(event, venue, coord, "capacity", "Extra chairs arranged")

        event.expected_attendance = 30  # now fits, so no flag at all
        db.session.commit()

        assert _check(s.evaluate_venue(event, venue), "capacity")["status"] == "pass"
        # Discard anything not committed, as happens at the end of every web
        # request, so we check what was actually SAVED to the database.
        db.session.rollback()
        [entry] = s.override_history(event)
        assert entry["isActive"] is False
        assert entry["clearedReason"] == "Mismatch no longer applies after event or venue details changed"

    @pytest.mark.parametrize("status", ["completed", "cancelled", "rejected"])
    def test_flags_cannot_be_overridden_on_a_finished_event(self, event_factory, coord, status):
        event = event_factory(status=status, expected_attendance=40)
        with pytest.raises(s.SuitabilityError, match="cannot be overridden"):
            s.override_flag(event, _venue(capacity=35), coord, "capacity", "Extra chairs arranged")

    @pytest.mark.parametrize("bad", [None, "", "price", "CAPACITY"])
    def test_only_the_three_flag_types_can_be_overridden(self, event_factory, coord, bad):
        event = event_factory(expected_attendance=40)
        with pytest.raises(s.SuitabilityError, match="flagType must be one of"):
            s.override_flag(event, _venue(capacity=35), coord, bad, "Extra chairs arranged")

    def test_the_same_flag_cannot_be_overridden_twice(self, event_factory, coord):
        event = event_factory(expected_attendance=40)
        venue = _venue(capacity=35)
        s.override_flag(event, venue, coord, "capacity", "Extra chairs arranged")
        with pytest.raises(s.SuitabilityError, match="already overridden"):
            s.override_flag(event, venue, coord, "capacity", "Second reason given here")


# ---------------------------------------------------------------------
# Suitability inside the Venue Booking Request
# ---------------------------------------------------------------------

class TestBookingRequestGate:
    def test_not_verified_flags_do_not_block_a_request(self, event_factory, coord):
        event = event_factory(expected_attendance=None, required_layout="Fishbowl")
        [booking] = submit_booking_requests(event, [_item(_venue(capacity=100))], coord.id)
        assert booking.status == "pending"

    def test_one_error_per_unsuitable_flag(self, event_factory, coord):
        event = event_factory(expected_attendance=40, required_layout="Classroom",
                              accessibility_requirements=["hearing_loop"])
        venue = _venue(capacity=35, layouts=["Theatre"])
        with pytest.raises(BookingRequestError) as exc:
            submit_booking_requests(event, [_item(venue)], coord.id)
        assert [e["field"] for e in exc.value.errors] == ["suitability"] * 3
        assert all(e["message"].startswith("Room: Unsuitable") for e in exc.value.errors)

    def test_whole_request_is_refused_if_any_venue_is_unsuitable(self, event_factory, coord):
        event = event_factory(expected_attendance=40)
        good, bad = _venue(name="Big Hall", capacity=300), _venue(name="Small Room", capacity=35)
        with pytest.raises(BookingRequestError) as exc:
            submit_booking_requests(event, [_item(good), _item(bad)], coord.id)
        assert [e["venue_id"] for e in exc.value.errors] == [bad.id]
        assert VenueBooking.query.count() == 0

    def test_missing_venue_is_reported_without_a_suitability_check(self, event_factory, coord):
        event = event_factory(expected_attendance=40)
        with pytest.raises(BookingRequestError) as exc:
            submit_booking_requests(
                event, [{"venue_id": 9999, "date": FUTURE, "start_time": time(10), "end_time": time(12)}], coord.id
            )
        assert [e["field"] for e in exc.value.errors] == ["venue_id"]


class TestEvaluateContract:
    def test_evaluate_ignores_an_override_granted_for_a_different_mismatch(self, event_factory, coord):
        """evaluate() is pure and may be handed overrides that were never
        synced; it must only apply one whose snapshot matches today's data."""
        event = event_factory(expected_attendance=40)
        venue = _venue(capacity=35)
        override = s.override_flag(event, venue, coord, "capacity", "Extra chairs arranged")
        event.expected_attendance = 60  # not committed, not synced
        result = s.evaluate(event, venue, {"capacity": override})
        assert _check(result, "capacity")["status"] == "unsuitable"
        assert result["isBlocked"] is True


class TestVenueCatalogueNames:
    """Venue Staff type accessibility features and layouts as free text in the
    Venue Catalogue; they are matched onto the fixed lists."""

    @pytest.mark.parametrize("name,code", [
        ("Step-free access", "step_free_access"),
        ("RAMP", "step_free_access"),
        ("Wheelchair access", "step_free_access"),
        ("Induction loop", "hearing_loop"),
        ("accessible toilet", "accessible_toilet"),
        ("Disabled parking", "accessible_parking"),
        ("Coffee machine", None),
        ("", None),
    ])
    def test_feature_names_map_onto_the_fixed_list(self, name, code):
        assert accessibility_code_for(name) == code

    def test_typed_feature_names_satisfy_requirements(self, event_factory):
        event = event_factory(accessibility_requirements=["step_free_access", "hearing_loop"])
        venue = Venue(name="Typed", location="X", capacity=100, is_active=True)
        venue.accessibility_features = ["Ramp", "Induction loop", "Coffee machine"]
        db.session.add(venue)
        db.session.commit()
        assert _check(s.evaluate_venue(event, venue), "accessibility")["status"] == "pass"

    def test_unrecognised_feature_names_do_not_count(self, event_factory):
        event = event_factory(accessibility_requirements=["hearing_loop"])
        venue = Venue(name="Vague", location="X", capacity=100, is_active=True)
        venue.accessibility_features = ["Good acoustics"]
        db.session.add(venue)
        db.session.commit()
        acc = _check(s.evaluate_venue(event, venue), "accessibility")
        assert acc["reasons"] == ["Hearing loop required but not available."]

    def test_catalogue_standard_exhibition_layout_is_recognised(self, event_factory):
        event = event_factory(required_layout="Exhibition")
        assert _check(s.evaluate_venue(event, _venue(capacity=100, layouts=["exhibition"])), "layout")["status"] == "pass"

    def test_existing_catalogue_suitability_check_is_unchanged(self, event_factory):
        """The Venue Catalogue's own check_suitability() keeps its behaviour."""
        from app.venues.services.suitability import check_suitability
        event = event_factory(expected_attendance=40)
        flags = check_suitability(event, _venue(capacity=35))
        assert len(flags) == 1 and "exceeds" in flags[0]


class TestSuitabilityList:
    def test_inactive_venues_are_left_out(self, event_factory):
        event = event_factory(expected_attendance=10)
        _venue(name="Open Hall", capacity=100)
        _venue(name="Closed Hall", capacity=100, active=False)
        assert [r["venue"]["name"] for r in s.list_suitability(event)] == ["Open Hall"]

    def test_best_options_are_listed_first(self, event_factory):
        event = event_factory(expected_attendance=40, required_layout="Theatre")
        _venue(name="A Too Small", capacity=35)
        _venue(name="B No Layouts", capacity=100, layouts=[])
        _venue(name="C Fits", capacity=100)
        names = [r["venue"]["name"] for r in s.list_suitability(event)]
        assert names == ["C Fits", "B No Layouts", "A Too Small"]


# ---------------------------------------------------------------------
# HTTP layer: not-found, drafts, and permission responses
# ---------------------------------------------------------------------

class TestApiGuards:
    @pytest.fixture()
    def ids(self, app, organiser, coordinator, make_event, make_user):
        venue = _venue(name="Orchid Room", capacity=35)
        approved = make_event(organiser, status="approved", coordinator_id=coordinator, expected_attendance=40)
        draft = make_event(organiser, status="draft", coordinator_id=coordinator, expected_attendance=40)
        make_user("other.coord@test.com", ["event_coordinator"])
        return {"venue": venue.id, "approved": approved, "draft": draft}

    def test_single_venue_suitability_endpoint(self, client, auth_header, ids):
        h = auth_header("coordinator@test.com")
        res = client.get(f"/api/events/{ids['approved']}/venue-suitability/{ids['venue']}", headers=h)
        assert res.status_code == 200
        assert res.get_json()["overallStatus"] == "unsuitable"
        missing = client.get(f"/api/events/{ids['approved']}/venue-suitability/9999", headers=h)
        assert missing.status_code == 404

    @pytest.mark.parametrize("path", [
        "/api/events/{draft}/venue-suitability",
        "/api/events/{draft}/venue-suitability/overrides",
        "/api/events/9999/venue-suitability",
        "/api/events/9999/venue-suitability/overrides",
    ])
    def test_drafts_and_missing_events_are_not_found(self, client, auth_header, ids, path):
        res = client.get(path.format(**ids), headers=auth_header("coordinator@test.com"))
        assert res.status_code == 404

    def test_override_on_missing_venue_is_not_found(self, client, auth_header, ids):
        res = client.post(
            f"/api/events/{ids['approved']}/venue-suitability/9999/overrides",
            json={"flagType": "capacity", "reason": "Extra chairs arranged"},
            headers=auth_header("coordinator@test.com"),
        )
        assert res.status_code == 404

    def test_coordinator_not_assigned_to_event_cannot_override(self, client, auth_header, ids):
        res = client.post(
            f"/api/events/{ids['approved']}/venue-suitability/{ids['venue']}/overrides",
            json={"flagType": "capacity", "reason": "Extra chairs arranged"},
            headers=auth_header("other.coord@test.com"),
        )
        assert res.status_code == 403
