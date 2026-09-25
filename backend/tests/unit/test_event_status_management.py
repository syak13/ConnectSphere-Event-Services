"""Unit tests for Story 1: consistent event status display."""
from datetime import time
from types import SimpleNamespace

import pytest

from app.events.routes import _can_view
from app.events.services.status import change_status
from app.models.event import EVENT_STATUSES, Event, EventStatusHistory, STATUS_LABELS, UNKNOWN_STATUS_LABEL

ORG = "organiser@test.com"
COORD = "coordinator@test.com"


# =====================================================================
# Model / permission-function level (fast, no HTTP, no JWT)
# =====================================================================

@pytest.mark.parametrize("status", EVENT_STATUSES)
def test_event_serialization_exposes_current_status_and_label(app, organiser, status):
    with app.app_context():
        event = Event(organiser_id=organiser, status=status)

        payload = event.to_dict()

        assert payload["status"] == status
        assert payload["statusLabel"] == STATUS_LABELS[status]
        assert payload["statusValid"] is True


def test_status_serialization_is_independent_for_each_event(app, organiser):
    with app.app_context():
        events = [
            Event(organiser_id=organiser, status="draft"),
            Event(organiser_id=organiser, status="planning"),
            Event(organiser_id=organiser, status="confirmed"),
        ]

        payloads = [event.to_dict() for event in events]

        assert [payload["status"] for payload in payloads] == [
            "draft",
            "planning",
            "confirmed",
        ]
        assert [payload["statusLabel"] for payload in payloads] == [
            "Draft",
            "Planning",
            "Confirmed",
        ]


def test_status_changes_are_reflected_by_a_fresh_serialization(
    app, organiser, coordinator
):
    with app.app_context():
        event = Event(organiser_id=organiser, status="draft")
        from app.extensions import db

        db.session.add(event)
        db.session.commit()
        assert event.to_dict()["status"] == "draft"

        change_status(event, "submitted", changed_by_id=coordinator)
        refreshed = db.session.get(Event, event.id)

        assert refreshed.to_dict()["status"] == "submitted"
        assert EventStatusHistory.query.filter_by(event_id=event.id).count() == 1


def test_unauthorised_user_cannot_view_event_or_status(app, organiser):
    with app.app_context():
        event = SimpleNamespace(organiser_id=organiser, status="confirmed")
        unrelated_organiser = SimpleNamespace(
            id=organiser + 1,
            has_role=lambda role: role == "event_organiser",
        )

        assert _can_view(event, unrelated_organiser) is False


def test_authorised_internal_user_can_view_non_draft_event_status(app, organiser):
    with app.app_context():
        event = SimpleNamespace(organiser_id=organiser, status="planning")
        coordinator = SimpleNamespace(
            id=organiser + 1,
            has_role=lambda role: role == "event_coordinator",
        )

        assert _can_view(event, coordinator) is True


def test_new_event_defaults_to_draft(app, organiser):
    with app.app_context():
        event = Event(organiser_id=organiser)

        payload = event.to_dict()

        # SQLAlchemy applies the column default on insert, not construction.
        assert event.status is None
        assert payload["statusLabel"] == UNKNOWN_STATUS_LABEL


def test_persisted_new_event_defaults_to_draft(app, organiser):
    with app.app_context():
        from app.extensions import db

        event = Event(organiser_id=organiser)
        db.session.add(event)
        db.session.commit()

        assert event.status == "draft"
        assert event.to_dict()["statusLabel"] == "Draft"


@pytest.mark.parametrize("invalid_status", [None, "", "banana", "UNDER_REVIEW"])
def test_missing_or_unknown_status_has_explicit_fallback(
    app, organiser, invalid_status
):
    with app.app_context():
        payload = Event(organiser_id=organiser, status=invalid_status).to_dict()

        assert payload["statusValid"] is False
        assert payload["statusLabel"] == UNKNOWN_STATUS_LABEL
        assert payload["statusLabel"]


# =====================================================================
# HTTP / real-auth level
# -----------------------------------------------------------------------
# Everything above calls the model or _can_view() directly. That proves
# the logic is correct in isolation, but it never sends a request through
# a real JWT, a real route, or a real query — which is exactly where the
# submit-event and list-events bugs previously showed up. These tests
# close that gap so every AC is proven through the actual system, not
# just the function backing it.
# =====================================================================

def _get(client, headers, event_id):
    return client.get(f"/api/events/{event_id}", headers=headers)


def _status(client, headers, event_id):
    res = _get(client, headers, event_id)
    assert res.status_code == 200, res.get_json()
    return res.get_json()["status"]


class TestAC1StatusShownOverHTTP:
    """AC1: status is clearly shown on detail and list views, and stays
    consistent with the actions actually performed on the event."""

    def test_detail_endpoint_shows_status(self, client, auth_header, organiser, make_event):
        event_id = make_event(organiser, status="planning")
        body = _get(client, auth_header(ORG), event_id).get_json()
        assert body["status"] == "planning"
        assert body["statusLabel"] == "Planning"
        assert body["statusValid"] is True

    def test_list_endpoint_shows_status(self, client, auth_header, organiser, make_event):
        make_event(organiser, status="confirmed")
        rows = client.get("/api/events/mine", headers=auth_header(ORG)).get_json()
        assert rows[0]["status"] == "confirmed"
        assert rows[0]["statusLabel"] == "Confirmed"

    def test_status_reflects_real_submit_and_approve_actions(
        self, client, auth_header, organiser, coordinator, make_event
    ):
        org, coord = auth_header(ORG), auth_header(COORD)
        event_id = make_event(
            organiser,
            proposed_time=time(9, 0),
            capacity_needed=100,
            required_layout="theatre",
            accessibility_needs="None",
        )
        assert _status(client, org, event_id) == "draft"

        res = client.post(f"/api/events/{event_id}/submit", headers=org)
        assert res.status_code == 200, res.get_json()
        assert _status(client, org, event_id) == "under_review"
        assert _status(client, coord, event_id) == "under_review"

        res = client.post(f"/api/events/{event_id}/approve", headers=coord, json={"comments": "ok"})
        assert res.status_code == 200, res.get_json()
        assert _status(client, org, event_id) == "approved"

    def test_status_reflects_real_rejection(
        self, client, auth_header, organiser, coordinator, make_event
    ):
        event_id = make_event(organiser, status="under_review", coordinator_id=coordinator)
        res = client.post(
            f"/api/events/{event_id}/reject", headers=auth_header(COORD), json={"reason": "No venue"}
        )
        assert res.status_code == 200, res.get_json()
        assert _status(client, auth_header(ORG), event_id) == "rejected"


class TestAC2ListIntegrityOverHTTP:
    """AC2: a list of multiple events shows each event's own status, with
    no stale or cross-contaminated values."""

    def test_each_row_reflects_its_own_status(self, client, auth_header, organiser, make_event):
        ids = {
            s: make_event(organiser, status=s, name=f"Event {s}")
            for s in ("draft", "under_review", "confirmed", "rejected")
        }
        rows = {r["id"]: r for r in client.get("/api/events/mine", headers=auth_header(ORG)).get_json()}
        assert len(rows) == 4
        for status, event_id in ids.items():
            assert rows[event_id]["status"] == status
            assert rows[event_id]["name"] == f"Event {status}"

    def test_changing_one_event_does_not_affect_others_in_the_list(
        self, client, auth_header, organiser, coordinator, make_event
    ):
        a = make_event(organiser, "under_review", coordinator_id=coordinator, name="A")
        b = make_event(organiser, "under_review", coordinator_id=coordinator, name="B")
        client.post(f"/api/events/{a}/approve", headers=auth_header(COORD), json={})
        rows = {
            r["id"]: r["status"]
            for r in client.get("/api/events/mine", headers=auth_header(ORG)).get_json()
        }
        assert rows[a] == "approved"
        assert rows[b] == "under_review"


class TestAC3PermissionsOverHTTP:
    """AC3: without permission to view an event, its status is not shown.
    Uses real login + JWT, not a hand-built SimpleNamespace."""

    def test_other_organiser_cannot_see_event_detail(
        self, client, auth_header, organiser, make_user, make_event
    ):
        make_user("other@test.com", ["event_organiser"])
        event_id = make_event(organiser, status="confirmed")
        res = _get(client, auth_header("other@test.com"), event_id)
        assert res.status_code == 404
        assert "status" not in res.get_json()

    def test_other_organiser_list_is_empty(
        self, client, auth_header, organiser, make_user, make_event
    ):
        make_user("other@test.com", ["event_organiser"])
        make_event(organiser, status="confirmed")
        rows = client.get("/api/events/mine", headers=auth_header("other@test.com")).get_json()
        assert rows == []

    def test_attendee_cannot_see_event(self, client, auth_header, organiser, make_user, make_event):
        make_user("att@test.com", ["attendee"])
        event_id = make_event(organiser, status="confirmed")
        res = _get(client, auth_header("att@test.com"), event_id)
        assert res.status_code == 404
        assert "status" not in res.get_json()

    def test_unauthenticated_request_cannot_see_event(self, client, organiser, make_event):
        event_id = make_event(organiser, status="confirmed")
        res = client.get(f"/api/events/{event_id}")
        assert res.status_code == 401
        assert "status" not in res.get_json()

    @pytest.mark.parametrize("role", ["event_coordinator", "venue_staff", "technical_support_staff"])
    def test_internal_staff_cannot_see_someone_elses_draft(
        self, client, auth_header, organiser, make_user, make_event, role
    ):
        make_user(f"{role}@x.com", [role])
        draft_id = make_event(organiser, status="draft")
        headers = auth_header(f"{role}@x.com")

        assert _get(client, headers, draft_id).status_code == 404

        res = client.get("/api/events", headers=headers)
        assert res.status_code == 200
        listed_ids = [e["id"] for e in res.get_json()]
        assert draft_id not in listed_ids

    @pytest.mark.parametrize("role", ["event_coordinator", "venue_staff", "technical_support_staff"])
    def test_internal_staff_can_see_submitted_events(
        self, client, auth_header, organiser, make_user, make_event, role
    ):
        make_user(f"{role}@x.com", [role])
        event_id = make_event(organiser, status="planning")
        assert _status(client, auth_header(f"{role}@x.com"), event_id) == "planning"


class TestAC4RefreshOverHTTP:
    """AC4: if status changes while a detail page is open, refreshing
    (i.e. re-fetching) shows the updated status."""

    def test_second_fetch_returns_the_new_status(
        self, client, auth_header, organiser, coordinator, make_event
    ):
        org, coord = auth_header(ORG), auth_header(COORD)
        event_id = make_event(organiser, "under_review", coordinator_id=coordinator)
        assert _status(client, org, event_id) == "under_review"  # page loaded here

        client.post(f"/api/events/{event_id}/approve", headers=coord, json={})
        assert _status(client, org, event_id) == "approved"  # refresh #1

        client.post(
            f"/api/events/{event_id}/status",
            headers=coord,
            json={"status": "cancelled", "reason": "Client withdrew"},
        )
        assert _status(client, org, event_id) == "cancelled"  # refresh #2


class TestAC5DraftDefaultOverHTTP:
    """AC5: a newly created draft event shows status 'draft' by default,
    through the real draft-creation endpoints."""

    def test_draft_creation_endpoint_defaults_to_draft(self, client, auth_header, organiser):
        org = auth_header(ORG)
        res = client.post("/api/events/drafts", headers=org, json={"name": "Partial"})
        assert res.status_code == 201
        body = res.get_json()
        assert body["status"] == "draft"
        assert body["statusLabel"] == "Draft"
        assert _status(client, org, body["id"]) == "draft"

    def test_empty_draft_still_defaults_to_draft(self, client, auth_header, organiser):
        res = client.post("/api/events/drafts", headers=auth_header(ORG), json={})
        assert res.get_json()["status"] == "draft"

    def test_create_event_without_submit_flag_stays_draft(self, client, auth_header, organiser):
        res = client.post("/api/events", headers=auth_header(ORG), json={"name": "x"})
        assert res.get_json()["status"] == "draft"

    def test_new_draft_is_listed_with_draft_status(self, client, auth_header, organiser):
        org = auth_header(ORG)
        client.post("/api/events/drafts", headers=org, json={"name": "D"})
        rows = client.get("/api/events/mine", headers=org).get_json()
        assert [r["status"] for r in rows] == ["draft"]


class TestAC6FallbackOverHTTP:
    """AC6: an unrecognised status reaches the real API response with the
    fallback label, and a bad row doesn't break the rest of a list."""

    def test_detail_endpoint_falls_back_for_bad_status(
        self, client, auth_header, organiser, make_event
    ):
        event_id = make_event(organiser, status="banana")
        body = _get(client, auth_header(ORG), event_id).get_json()
        assert body["statusValid"] is False
        assert body["statusLabel"] == UNKNOWN_STATUS_LABEL

    def test_bad_row_does_not_break_the_rest_of_the_list(
        self, client, auth_header, organiser, make_event
    ):
        good = make_event(organiser, status="confirmed")
        bad = make_event(organiser, status="banana")
        rows = {
            r["id"]: r for r in client.get("/api/events/mine", headers=auth_header(ORG)).get_json()
        }
        assert rows[good]["statusValid"] is True
        assert rows[bad]["statusValid"] is False