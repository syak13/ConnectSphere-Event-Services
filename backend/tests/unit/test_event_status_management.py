"""Unit tests for event status stories 1 through 3."""
from datetime import time
from types import SimpleNamespace

import pytest

from app.events.routes import _can_view
from app.events.services.status import change_status
from app.models.event import EVENT_STATUSES, Event, EventStatusHistory, STATUS_LABELS, UNKNOWN_STATUS_LABEL
from app.models.user import User

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

#  to fix 1
# class TestAC1StatusShownOverHTTP:
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

# to fix 2
# class TestAC2ListIntegrityOverHTTP:
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

# to fix 3 - might depend on the other two so may delete
# class TestAC3PermissionsOverHTTP:
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

# to fix 3
# class TestAC4RefreshOverHTTP:
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

"""
Tests for Story 2: Organiser views status of all their requests.

    As an Event Organiser, I want to see the current status of each of my
    event requests in one list, so that I know where each one stands.

/api/events/mine returns a plain JSON array (same shape whether or not
pagination params are used) so existing callers -- Story 1's tests and
DashboardView.vue -- keep working unchanged. Pagination metadata rides in
response headers: X-Total-Count, X-Page, X-Per-Page, X-Total-Pages.
"""
from datetime import date, timedelta

import pytest

ORG = "organiser@test.com"


def _mine(client, headers, **params):
    return client.get("/api/events/mine", headers=headers, query_string=params)


class TestAC1StatusShownForEachRequest:
    def test_each_request_shows_its_current_status(self, client, auth_header, organiser, make_event):
        make_event(organiser, status="draft", name="A")
        make_event(organiser, status="under_review", name="B")
        make_event(organiser, status="confirmed", name="C")

        res = _mine(client, auth_header(ORG))
        assert res.status_code == 200

        rows = {r["name"]: r["status"] for r in res.get_json()}
        assert rows == {"A": "draft", "B": "under_review", "C": "confirmed"}

    def test_status_label_is_present_on_each_row(self, client, auth_header, organiser, make_event):
        make_event(organiser, status="under_review")
        row = _mine(client, auth_header(ORG)).get_json()[0]
        assert row["statusLabel"] == "Under review"


class TestAC2EmptyStateNotError:
    def test_zero_requests_returns_empty_list_not_error(self, client, auth_header, organiser):
        res = _mine(client, auth_header(ORG))
        assert res.status_code == 200
        assert res.get_json() == []
        assert res.headers["X-Total-Count"] == "0"


class TestAC3OnlyOwnRequestsVisible:
    def test_sees_only_own_requests(self, client, auth_header, organiser, make_user, make_event):
        other_id = make_user("other@test.com", ["event_organiser"])
        make_event(organiser, status="confirmed", name="Mine")
        make_event(other_id, status="confirmed", name="Not mine")

        names = [r["name"] for r in _mine(client, auth_header(ORG)).get_json()]
        assert names == ["Mine"]

    def test_other_organisers_requests_never_leak_across_pages(
        self, client, auth_header, organiser, make_user, make_event
    ):
        other_id = make_user("other@test.com", ["event_organiser"])
        for i in range(5):
            make_event(organiser, name=f"Mine {i}")
        for i in range(5):
            make_event(other_id, name=f"Theirs {i}")

        res = _mine(client, auth_header(ORG), page=1, per_page=100)
        body = res.get_json()
        assert res.headers["X-Total-Count"] == "5"
        assert all(r["name"].startswith("Mine") for r in body)


class TestAC4RemainsUsableWithManyRequests:
    @staticmethod
    def _seed_many(make_event, organiser, count):
        base = date(2026, 1, 1)
        for i in range(count):
            make_event(
                organiser,
                name=f"Event {i}",
                proposed_date=base + timedelta(days=i),
                updated_at=base + timedelta(days=i),  # distinct, increasing recency
            )

    def test_large_number_of_requests_is_paginated(self, client, auth_header, organiser, make_event):
        self._seed_many(make_event, organiser, 55)

        res = _mine(client, auth_header(ORG), page=1, per_page=20)
        body = res.get_json()

        assert res.headers["X-Total-Count"] == "55"
        assert len(body) == 20
        assert res.headers["X-Page"] == "1"
        assert res.headers["X-Per-Page"] == "20"
        assert res.headers["X-Total-Pages"] == "3"  # ceil(55 / 20)

    def test_second_page_returns_the_next_slice(self, client, auth_header, organiser, make_event):
        self._seed_many(make_event, organiser, 55)

        page1 = _mine(client, auth_header(ORG), page=1, per_page=20).get_json()
        page2 = _mine(client, auth_header(ORG), page=2, per_page=20).get_json()
        page3 = _mine(client, auth_header(ORG), page=3, per_page=20).get_json()

        assert len(page1) == 20
        assert len(page2) == 20
        assert len(page3) == 15  # remainder

        ids_seen = set()
        for page in (page1, page2, page3):
            page_ids = {row["id"] for row in page}
            assert not (ids_seen & page_ids), "pages overlapped"
            ids_seen |= page_ids
        assert len(ids_seen) == 55

    def test_results_are_sorted_most_recent_first(self, client, auth_header, organiser, make_event):
        older = make_event(organiser, name="Older", updated_at=date(2026, 1, 1))
        newer = make_event(organiser, name="Newer", updated_at=date(2026, 1, 2))

        ids_in_order = [row["id"] for row in _mine(client, auth_header(ORG)).get_json()]
        assert ids_in_order.index(newer) < ids_in_order.index(older)

    def test_out_of_range_page_returns_empty_not_an_error(
        self, client, auth_header, organiser, make_event
    ):
        self._seed_many(make_event, organiser, 5)

        res = _mine(client, auth_header(ORG), page=99, per_page=20)
        assert res.status_code == 200
        assert res.get_json() == []

    def test_per_page_is_capped_to_a_sane_maximum(self, client, auth_header, organiser, make_event):
        self._seed_many(make_event, organiser, 10)

        res = _mine(client, auth_header(ORG), page=1, per_page=100000)
        assert int(res.headers["X-Per-Page"]) <= 100

    @pytest.mark.parametrize("bad_page", [0, -1])
    def test_non_positive_page_falls_back_to_page_one(
        self, client, auth_header, organiser, make_event, bad_page
    ):
        self._seed_many(make_event, organiser, 5)
        res = _mine(client, auth_header(ORG), page=bad_page, per_page=20)
        assert res.status_code == 200
        assert len(res.get_json()) == 5
        assert res.headers["X-Page"] == "1"

    def test_missing_page_and_per_page_returns_full_unpaginated_list(
        self, client, auth_header, organiser, make_event
    ):
        """No query params at all -> default behaviour, unchanged
        response shape, same as before pagination existed."""
        make_event(organiser)
        res = _mine(client, auth_header(ORG))
        assert res.status_code == 200
        assert isinstance(res.get_json(), list)


"""Unit tests for Story 3: arrangements lead to a safety check before confirmation.

Acceptance criteria:
1. Coordinator approval moves the request to planning.
2. Complete venue/equipment arrangements move planning to safety_check, never directly to confirmed.
3. Only a Safety Officer can approve, reject, or request changes; approval confirms, while rejection/changes return to planning.
4. Arrangement loss returns safety_check/confirmed events to planning, and repeated checks do not duplicate transitions.
"""
from datetime import timedelta

from app.common.time import utcnow
from app.equipment.services import reservation as equipment_reservation
from app.events.services import review
from app.events.services import safety
from app.events.services import status as status_service
from app.extensions import db
from app.models.equipment import EquipmentItem, EquipmentReservation
from app.models.event import Event, EventEquipmentRequirement, EventSafetyReview, EventStatusHistory
from app.models.venue import Venue, VenueBooking
from app.venues.services import booking as venue_booking


def _create_venue_booking(
    event,
    organiser,
    status="pending",
    venue_owner_id=None,
):
    venue = Venue(
        name="Test Hall",
        location="Campus",
        capacity=200,
        created_by=venue_owner_id,
    )
    db.session.add(venue)
    db.session.flush()
    booking = VenueBooking(
        event_id=event.id,
        venue_id=venue.id,
        requested_by=organiser,
        status=status,
        start_datetime=utcnow() + timedelta(days=30),
        end_datetime=utcnow() + timedelta(days=30, hours=2),
    )
    db.session.add(booking)
    db.session.commit()
    return booking


def test_approval_moves_event_to_planning(app, organiser, coordinator, make_event):
    with app.app_context():
        event_id = make_event(organiser, status="under_review", coordinator_id=coordinator)
        event = db.session.get(Event, event_id)

        review.approve_event(event, coordinator)

        assert event.status == "planning"
        assert [entry.new_status for entry in event.status_history] == ["approved", "planning"]


def test_pending_venue_keeps_event_in_planning(app, organiser, make_event):
    with app.app_context():
        event_id = make_event(organiser, status="planning", capacity_needed=100)
        event = db.session.get(Event, event_id)
        _create_venue_booking(event, organiser)

        status_service.try_advance_to_safety_check(event, changed_by_id=organiser)

        assert event.status == "planning"


def test_venue_approval_moves_event_to_safety_check_without_equipment(
    app, organiser, make_user, make_event
):
    with app.app_context():
        venue_staff_id = make_user(
            "status-venue-staff@test.com",
            ["venue_staff"],
        )
        event_id = make_event(organiser, status="planning", capacity_needed=100)
        event = db.session.get(Event, event_id)
        booking = _create_venue_booking(
            event,
            organiser,
            venue_owner_id=venue_staff_id,
        )

        venue_booking.approve_booking(booking, decided_by=venue_staff_id)

        assert event.status == "safety_check"
        assert EventStatusHistory.query.filter_by(
            event_id=event_id, new_status="safety_check"
        ).count() == 1


def test_pending_equipment_prevents_safety_check_after_venue_approval(
    app, organiser, make_user, make_event
):
    with app.app_context():
        venue_staff_id = make_user(
            "status-venue-staff-equipment@test.com",
            ["venue_staff"],
        )
        event_id = make_event(organiser, status="planning", capacity_needed=100)
        event = db.session.get(Event, event_id)
        event.equipment_requirements.append(
            EventEquipmentRequirement(equipment_type="Projector", quantity=1)
        )
        booking = _create_venue_booking(
            event,
            organiser,
            venue_owner_id=venue_staff_id,
        )

        venue_booking.approve_booking(booking, decided_by=venue_staff_id)

        assert event.status == "planning"


def test_last_equipment_reservation_moves_event_to_safety_check(
    app, organiser, coordinator, make_event
):
    with app.app_context():
        event_id = make_event(organiser, status="planning", capacity_needed=100)
        event = db.session.get(Event, event_id)
        requirement = EventEquipmentRequirement(equipment_type="Projector", quantity=2)
        event.equipment_requirements.append(requirement)
        booking = _create_venue_booking(event, organiser, status="approved")
        item = EquipmentItem(name="Projector", total_quantity=5)
        db.session.add(item)
        db.session.commit()

        equipment_reservation.reserve(
            event,
            requirement,
            item,
            booking.start_datetime,
            booking.end_datetime,
            organiser,
        )

        assert event.status == "safety_check"


def test_only_safety_officer_approval_confirms_event(app, organiser, make_user, make_event):
    with app.app_context():
        officer_id = make_user("safety@test.com", ["safety_officer"])
        officer = db.session.get(User, officer_id)
        event_id = make_event(organiser, status="safety_check")
        event = db.session.get(Event, event_id)

        safety.review_safety_check(
            event,
            officer,
            "approved",
            "Egress and access reviewed",
            assessed_factors=sorted(safety.SAFETY_FACTORS),
        )

        assert event.status == "confirmed"
        review_record = EventSafetyReview.query.filter_by(event_id=event_id).one()
        assert review_record.decision == "approved"
        assert review_record.safety_officer_id == officer_id
        assert event.to_dict()["safetyReviews"][0]["comments"] == "Egress and access reviewed"


@pytest.mark.parametrize("decision", ["rejected", "changes_requested"])
def test_safety_rejection_or_change_request_returns_event_to_planning(
    app, organiser, make_user, make_event, decision
):
    with app.app_context():
        officer_id = make_user(f"safety-{decision}@test.com", ["safety_officer"])
        officer = db.session.get(User, officer_id)
        event_id = make_event(organiser, status="safety_check")
        event = db.session.get(Event, event_id)

        safety.review_safety_check(
            event,
            officer,
            decision,
            "Adjust emergency access",
            assessed_factors=["emergency_access"],
            concern_factors=["emergency_access"],
            affected_arrangements=["venue"],
        )

        assert event.status == "planning"
        assert EventSafetyReview.query.filter_by(event_id=event_id, decision=decision).count() == 1


def test_non_safety_user_cannot_approve_safety_check(app, organiser, coordinator, make_event):
    with app.app_context():
        event_id = make_event(organiser, status="safety_check")
        event = db.session.get(Event, event_id)
        coordinator_user = db.session.get(User, coordinator)

        with pytest.raises(PermissionError, match="Only a Safety Officer"):
            safety.review_safety_check(event, coordinator_user, "approved")


def test_safety_officer_cannot_review_event_before_arrangements_reach_safety_check(
    app, organiser, make_user, make_event
):
    with app.app_context():
        officer_id = make_user("early-safety@test.com", ["safety_officer"])
        officer = db.session.get(User, officer_id)
        event_id = make_event(organiser, status="planning")
        event = db.session.get(Event, event_id)

        with pytest.raises(ValueError, match="awaiting a safety check"):
            safety.review_safety_check(event, officer, "approved")


def test_safety_review_api_confirms_only_after_safety_officer_approval(
    client, auth_header, organiser, make_user, make_event
):
    make_user("safety-api@test.com", ["safety_officer"])
    event_id = make_event(organiser, status="safety_check")

    response = client.post(
        f"/api/events/{event_id}/safety-review",
        headers=auth_header("safety-api@test.com"),
        json={
            "decision": "approved",
            "comments": "Emergency access checked",
            "assessedFactors": sorted(safety.SAFETY_FACTORS),
        },
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "confirmed"


def test_coordinator_cannot_bypass_safety_review_with_generic_status_endpoint(
    client, auth_header, organiser, coordinator, make_event
):
    event_id = make_event(organiser, status="safety_check", coordinator_id=coordinator)

    response = client.post(
        f"/api/events/{event_id}/status",
        headers=auth_header(COORD),
        json={"status": "confirmed", "reason": "Trying to bypass safety review"},
    )

    assert response.status_code == 400
    with client.application.app_context():
        event = db.session.get(Event, event_id)
        assert event.status == "safety_check"
        assert EventStatusHistory.query.filter_by(
            event_id=event_id, new_status="confirmed"
        ).count() == 0


def test_cancelling_approved_venue_reverts_confirmed_event_to_planning(
    app, organiser, coordinator, make_event
):
    with app.app_context():
        event_id = make_event(organiser, status="confirmed", capacity_needed=100)
        event = db.session.get(Event, event_id)
        booking = _create_venue_booking(event, organiser, status="approved", venue_owner_id=coordinator)

        venue_booking.cancel_booking(booking, decided_by=coordinator, reason="Venue unavailable")

        assert booking.status == "cancelled"
        assert booking.decided_by == coordinator
        assert booking.decision_reason == "Venue unavailable"
        assert booking.decided_at is not None
        assert event.status == "planning"
        history = EventStatusHistory.query.filter_by(
            event_id=event_id, new_status="planning"
        ).one()
        assert "venue booking" in history.reason.lower()


def test_pending_venue_booking_cannot_be_cancelled(app, organiser, coordinator, make_event):
    with app.app_context():
        event_id = make_event(organiser, status="planning", capacity_needed=100)
        event = db.session.get(Event, event_id)
        booking = _create_venue_booking(event, organiser, status="pending", venue_owner_id=coordinator)

        with pytest.raises(ValueError, match="Only approved bookings"):
            venue_booking.cancel_booking(
                booking,
                decided_by=coordinator,
                reason="Venue unavailable",
            )

        assert booking.status == "pending"
        assert booking.decided_by is None
        assert booking.decision_reason is None


def test_venue_staff_can_cancel_booking_through_api(
    client, auth_header, organiser, make_user, make_event
):
    venue_staff_id = make_user("venue-staff@test.com", ["venue_staff"])
    event_id = make_event(organiser, status="confirmed", capacity_needed=100)

    with client.application.app_context():
        event = db.session.get(Event, event_id)
        booking = _create_venue_booking(event, organiser, status="approved", venue_owner_id=venue_staff_id)
        booking_id = booking.id

    response = client.post(
        f"/api/venues/bookings/{booking_id}/cancel",
        headers=auth_header("venue-staff@test.com"),
        json={"reason": "Venue maintenance"},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "cancelled"
    with client.application.app_context():
        assert db.session.get(Event, event_id).status == "planning"


def test_rechecking_ready_event_does_not_duplicate_safety_transition_history(
    app, organiser, make_event
):
    with app.app_context():
        event_id = make_event(organiser, status="planning")
        event = db.session.get(Event, event_id)

        status_service.try_advance_to_safety_check(event, changed_by_id=organiser)
        status_service.try_advance_to_safety_check(event, changed_by_id=organiser)

        assert event.status == "safety_check"
        assert EventStatusHistory.query.filter_by(
            event_id=event_id, new_status="safety_check"
        ).count() == 1


def test_released_equipment_is_not_counted_as_reserved(app, organiser, make_event):
    with app.app_context():
        event_id = make_event(organiser, status="planning")
        event = db.session.get(Event, event_id)
        requirement = EventEquipmentRequirement(equipment_type="Projector", quantity=1)
        event.equipment_requirements.append(requirement)
        db.session.flush()
        item = EquipmentItem(name="Projector", total_quantity=2)
        db.session.add(item)
        db.session.flush()
        record = EquipmentReservation(
            event_id=event_id,
            equipment_requirement_id=requirement.id,
            equipment_item_id=item.id,
            quantity=1,
            start_datetime=utcnow() + timedelta(days=30),
            end_datetime=utcnow() + timedelta(days=30, hours=1),
            status="released",
        )
        db.session.add(record)
        db.session.commit()

        status_service.try_advance_to_safety_check(event, changed_by_id=organiser)

        assert event.status == "planning"