"""
Smoke test covering the core Sprint-1 path across the first six epics:
draft -> submit -> auto-assign -> approve, and reject -> resubmit.
"""
from datetime import date, timedelta

from app.extensions import db
from app.events.services import drafts, review
from app.models.event import Event

# Relative dates: submission rejects past dates, so fixed calendar dates
# would make these tests start failing once that date has passed.
_FUTURE = date.today() + timedelta(days=60)


def test_draft_submit_and_auto_assignment_flow(app, organiser, coordinator):
    with app.app_context():
        event = drafts.create_draft(
            organiser,
            {
                "name": "Annual Conference",
                "purpose": "Networking",
                "description": "A conference for the team",
                "proposed_date": _FUTURE.isoformat(),
                "expected_attendance": 100,
                "proposed_time": "10:00",
                "capacity_needed": 100,
                "required_layout": "Theatre",
                "accessibility_needs": "None",
            },
        )
        assert event.status == "draft"

        event = review.submit_event(event, organiser)
        assert event.status == "under_review"
        assert event.coordinator_id == coordinator

        event = review.approve_event(event, coordinator, comments="Looks good")
        assert event.status == "approved"
        assert event.review_outcome == "approved"


def test_reject_and_resubmit_creates_new_record(app, organiser, coordinator):
    with app.app_context():
        event = drafts.create_draft(
            organiser,
            {
                "name": "Product Launch",
                "purpose": "Launch",
                "description": "Launch event",
                "proposed_date": (_FUTURE + timedelta(days=1)).isoformat(),
                "expected_attendance": 50,
                "proposed_time": "10:00",
                "capacity_needed": 50,
                "required_layout": "Theatre",
                "accessibility_needs": "None",
            },
        )
        event = review.submit_event(event, organiser)
        event = review.reject_event(event, coordinator, reason="Date conflicts with another event")
        assert event.status == "rejected"

        new_event = review.resubmit_rejected_event(event, organiser, {"proposed_date": (_FUTURE + timedelta(days=14)).isoformat()})
        assert new_event.id != event.id
        assert new_event.resubmitted_from_event_id == event.id
        assert new_event.status == "under_review"

        # original stays retained with its final status (Event Status Management)
        original = db.session.get(Event, event.id)
        assert original.status == "rejected"
