"""HTTP-level checks for the Venue Suitability Check, including how it works
together with the Venue Booking Request endpoint (POST /api/venues/bookings)."""
from datetime import time, timedelta

import pytest

from app.common.time import utcnow
from app.extensions import db
from app.models.venue import Venue

FUTURE = (utcnow().date() + timedelta(days=60)).isoformat()


@pytest.fixture()
def setup(app, organiser, coordinator, make_event, make_user):
    small = Venue(name="Orchid Room", location="L3", capacity=35, is_active=True)
    small.supported_layouts = ["classroom"]
    big = Venue(name="Harbour Hall", location="L1", capacity=300, is_active=True)
    big.supported_layouts = ["theatre"]
    big.accessibility_features = ["Step-free access"]
    db.session.add_all([small, big])
    db.session.commit()

    event_id = make_event(
        organiser,
        status="approved",
        coordinator_id=coordinator,
        expected_attendance=40,
        required_layout="Theatre",
        accessibility_requirements=["step_free_access"],
        proposed_time=time(10, 0),
    )
    make_user("venue@test.com", ["venue_staff"])
    make_user("attendee@test.com", ["attendee"])
    return {"event_id": event_id, "small": small.id, "big": big.id}


def _booking(event_id, venue_id):
    return {
        "eventId": event_id,
        "venues": [{"venueId": venue_id, "date": FUTURE, "startTime": "10:00", "endTime": "12:00"}],
    }


def test_list_returns_flags_per_venue(client, auth_header, setup):
    res = client.get(f"/api/events/{setup['event_id']}/venue-suitability", headers=auth_header("coordinator@test.com"))
    assert res.status_code == 200
    body = res.get_json()
    by_name = {v["venue"]["name"]: v for v in body["venues"]}
    assert by_name["Harbour Hall"]["overallStatus"] == "pass"
    small_flags = {f["type"] for f in by_name["Orchid Room"]["flags"]}
    assert small_flags == {"capacity", "accessibility", "layout"}
    assert body["isAssignedCoordinator"] is True


def test_venue_staff_can_view_but_not_override(client, auth_header, setup):
    h = auth_header("venue@test.com")
    assert client.get(f"/api/events/{setup['event_id']}/venue-suitability", headers=h).status_code == 200
    res = client.post(
        f"/api/events/{setup['event_id']}/venue-suitability/{setup['small']}/overrides",
        json={"flagType": "capacity", "reason": "Extra chairs arranged"},
        headers=h,
    )
    assert res.status_code == 403


def test_attendee_cannot_view(client, auth_header, setup):
    res = client.get(f"/api/events/{setup['event_id']}/venue-suitability", headers=auth_header("attendee@test.com"))
    assert res.status_code == 403


def test_override_short_reason_rejected(client, auth_header, setup):
    res = client.post(
        f"/api/events/{setup['event_id']}/venue-suitability/{setup['small']}/overrides",
        json={"flagType": "capacity", "reason": "chairs"},
        headers=auth_header("coordinator@test.com"),
    )
    assert res.status_code == 400
    assert "10 characters" in res.get_json()["error"]


def test_full_override_then_booking_request_flow(client, auth_header, setup):
    h = auth_header("coordinator@test.com")
    eid, vid = setup["event_id"], setup["small"]

    blocked = client.post("/api/venues/bookings", json=_booking(eid, vid), headers=h)
    assert blocked.status_code == 400
    errors = blocked.get_json()["errors"]
    assert {e["field"] for e in errors} == {"suitability"}
    assert len(errors) == 3

    for flag in ("capacity", "accessibility", "layout"):
        r = client.post(
            f"/api/events/{eid}/venue-suitability/{vid}/overrides",
            json={"flagType": flag, "reason": f"Coordinator accepted {flag} risk"},
            headers=h,
        )
        assert r.status_code == 201, r.get_json()

    done = client.post("/api/venues/bookings", json=_booking(eid, vid), headers=h)
    assert done.status_code == 201, done.get_json()
    assert done.get_json()[0]["status"] == "pending"

    history = client.get(f"/api/events/{eid}/venue-suitability/overrides", headers=h).get_json()
    assert len(history) == 3 and all(e["overriddenByName"] for e in history)


def test_suitable_venue_books_straight_away(client, auth_header, setup):
    res = client.post(
        "/api/venues/bookings", json=_booking(setup["event_id"], setup["big"]), headers=auth_header("coordinator@test.com")
    )
    assert res.status_code == 201


def test_options(client, auth_header, setup):
    res = client.get("/api/venues/suitability-options", headers=auth_header("coordinator@test.com"))
    codes = [f["code"] for f in res.get_json()["accessibilityFeatures"]]
    assert "step_free_access" in codes
    assert res.get_json()["minOverrideReasonLength"] == 10
