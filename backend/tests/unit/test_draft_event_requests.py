"""
Unit tests for the Draft Event Requests epic (ISP-8).
Stories: ISP-13 save, ISP-14 list, ISP-15 edit, ISP-16 submit (validation only),
ISP-17 delete.  Target: app/events/services/drafts.py
"""
from datetime import date, time, timedelta

import pytest
from werkzeug.security import generate_password_hash

from app.events.services import drafts
from app.events.services.validators import validate_for_submission
from app.extensions import db
from app.models.event import Event, EventEquipmentRequirement
from app.models.user import Role, User

FUTURE_DATE = (date.today() + timedelta(days=30)).isoformat()

NON_DRAFT_STATUSES = [
    "submitted", "under_review", "approved", "planning",
    "confirmed", "completed", "cancelled", "rejected",
]


def _full_data(**overrides):
    data = {
        "name": "Annual Tech Conference",
        "purpose": "Knowledge sharing",
        "description": "A conference for the tech community.",
        "category": "conference",
        "proposed_date": FUTURE_DATE,
        "proposed_time": "09:00",
        "expected_attendance": 100,
        "capacity_needed": 120,
        "required_layout": "theatre",
        "accessibility_needs": "Wheelchair access required",
        "registration_required": False,
    }
    data.update(overrides)
    return data


def _other_organiser():
    user = User(
        name="Other Organiser",
        email="other@test.com",
        password_hash=generate_password_hash("password"),
    )
    user.roles = [Role.query.filter_by(name="event_organiser").first()]
    db.session.add(user)
    db.session.commit()
    return user.id


def _draft_with_status(organiser_id, status):
    event = drafts.create_draft(organiser_id, {"name": "Status test"})
    event.status = status
    db.session.commit()
    return event


# ---------------------------------------------------------------------
# ISP-13  Save an in-progress event request as a draft
# ---------------------------------------------------------------------

def test_saving_an_incomplete_request_creates_it_with_status_draft(app, organiser):
    """ISP-13 AC1"""
    with app.app_context():
        event = drafts.create_draft(organiser, {"name": "Half-finished event"})
        assert event.status == "draft"


def test_saved_draft_returns_an_identifier(app, organiser):
    """ISP-13 AC2"""
    with app.app_context():
        event = drafts.create_draft(organiser, {"name": "Needs an id"})
        assert isinstance(event.id, int)


def test_reopened_draft_contains_every_field_saved_earlier(app, organiser):
    """ISP-13 AC3"""
    with app.app_context():
        event_id = drafts.create_draft(organiser, _full_data()).id
        db.session.expire_all()
        reopened = db.session.get(Event, event_id)

        assert reopened.name == "Annual Tech Conference"
        assert reopened.purpose == "Knowledge sharing"
        assert reopened.description == "A conference for the tech community."
        assert reopened.category == "conference"
        assert reopened.proposed_date == date.fromisoformat(FUTURE_DATE)
        assert str(reopened.proposed_time)[:5] == "09:00"
        assert reopened.expected_attendance == 100
        assert reopened.capacity_needed == 120
        assert reopened.required_layout == "theatre"
        assert reopened.accessibility_needs == "Wheelchair access required"


@pytest.mark.parametrize("payload", [{}, {"name": "Only a name"}, {"purpose": "Only a purpose"}])
def test_draft_saves_without_the_fields_required_for_submission(app, organiser, payload):
    """ISP-13 AC4, including the minimum possible input (empty payload)"""
    with app.app_context():
        event = drafts.create_draft(organiser, payload)
        assert event.id is not None
        assert event.status == "draft"
        assert validate_for_submission(event) != []


def test_saving_a_draft_does_not_assign_a_coordinator_or_submit(app, organiser):
    """ISP-13 AC5"""
    with app.app_context():
        event = drafts.create_draft(organiser, _full_data())
        assert event.status == "draft"
        assert event.coordinator_id is None


def test_payload_cannot_override_status_coordinator_or_owner(app, organiser):
    """ISP-13 AC5: a client must not be able to submit or reassign via the save payload"""
    with app.app_context():
        other = _other_organiser()
        event = drafts.create_draft(
            organiser,
            {"name": "Sneaky", "status": "approved", "coordinator_id": other, "organiser_id": other},
        )
        assert event.status == "draft"
        assert event.coordinator_id is None
        assert event.organiser_id == organiser


def test_draft_is_owned_by_the_organiser_who_saved_it(app, organiser):
    """ISP-13 AC1 / ISP-14 AC5 precondition"""
    with app.app_context():
        assert drafts.create_draft(organiser, {"name": "Mine"}).organiser_id == organiser


def test_equipment_requirements_are_saved_with_the_draft(app, organiser):
    """ISP-13 AC3 (equipment is part of the request)"""
    with app.app_context():
        event = drafts.create_draft(
            organiser,
            {"equipment_requirements": [
                {"type": "Projector", "quantity": 2, "technicalNotes": "HDMI input"},
            ]},
        )
        item = event.equipment_requirements[0]
        assert item.equipment_type == "Projector"
        assert item.quantity == 2
        assert item.technical_notes == "HDMI input"


def test_equipment_item_without_quantity_is_saved_with_zero_so_submission_can_block_it(app, organiser):
    """ISP-13 AC4: incomplete equipment is allowed in a draft, blocked at submission"""
    with app.app_context():
        event = drafts.create_draft(organiser, {"equipment_requirements": [{"type": "Microphone"}]})
        assert event.equipment_requirements[0].quantity == 0
        assert any("quantity" in e for e in validate_for_submission(event))


def test_negative_attendance_is_saved_in_a_draft_but_blocked_at_submission(app, organiser):
    """ISP-13 AC4 + submission rule: drafts are lenient, submission is strict"""
    with app.app_context():
        event = drafts.create_draft(organiser, _full_data(expected_attendance=-5))
        assert event.status == "draft"
        assert any("Expected attendance" in e for e in validate_for_submission(event))


@pytest.mark.parametrize("value, expected", [
    ("2026-12-31", date(2026, 12, 31)),
    ("2027-01-01", date(2027, 1, 1)),
    ("2028-02-29", date(2028, 2, 29)),
])
def test_valid_date_strings_are_stored_as_dates(app, organiser, value, expected):
    with app.app_context():
        assert drafts.create_draft(organiser, {"proposed_date": value}).proposed_date == expected


@pytest.mark.parametrize("bad_value", ["2026-02-29", "2026-13-01", "09/10/2026", "tomorrow"])
def test_invalid_date_strings_are_rejected(app, organiser, bad_value):
    with app.app_context():
        with pytest.raises(ValueError):
            drafts.create_draft(organiser, {"proposed_date": bad_value})


@pytest.mark.parametrize("value, expected", [
    ("00:00", "00:00"),
    ("09:00", "09:00"),
    ("23:59", "23:59"),
])
def test_valid_time_strings_are_stored_as_times(app, organiser, value, expected):
    with app.app_context():
        event = drafts.create_draft(organiser, {"proposed_time": value})
        assert str(event.proposed_time)[:5] == expected


@pytest.mark.parametrize("bad_value", ["24:00", "12:60", "25:00", "9am"])
def test_invalid_time_strings_are_rejected(app, organiser, bad_value):
    with app.app_context():
        with pytest.raises(ValueError):
            drafts.create_draft(organiser, {"proposed_time": bad_value})


def test_missing_date_and_time_are_stored_as_empty(app, organiser):
    """ISP-13 AC4: schedule fields are optional in a draft"""
    with app.app_context():
        event = drafts.create_draft(organiser, {"proposed_date": None, "proposed_time": None})
        assert event.proposed_date is None
        assert event.proposed_time is None


def test_date_and_time_objects_are_accepted_as_they_are(app, organiser):
    """ISP-13 AC3: the service accepts already-parsed values as well as strings"""
    with app.app_context():
        event = drafts.create_draft(
            organiser, {"proposed_date": date(2027, 6, 1), "proposed_time": time(14, 30)}
        )
        assert event.proposed_date == date(2027, 6, 1)
        assert str(event.proposed_time)[:5] == "14:30"


def test_a_saved_date_and_time_can_be_cleared_by_an_update(app, organiser):
    """ISP-15 AC2: an edit can remove a value as well as change it"""
    with app.app_context():
        event = drafts.create_draft(organiser, _full_data())
        drafts.update_draft(event, {"proposed_date": None, "proposed_time": None})
        assert event.proposed_date is None
        assert event.proposed_time is None

# ---------------------------------------------------------------------
# ISP-14  View my list of draft event requests
# ---------------------------------------------------------------------

def test_every_listed_draft_has_status_draft(app, organiser):
    """ISP-14 AC1"""
    with app.app_context():
        for name in ("A", "B", "C"):
            drafts.create_draft(organiser, {"name": name})
        listed = drafts.list_drafts(organiser)
        assert len(listed) == 3
        assert all(d.status == "draft" for d in listed)


@pytest.mark.parametrize("status", NON_DRAFT_STATUSES)
def test_submitted_and_later_requests_are_not_listed_as_drafts(app, organiser, status):
    """ISP-14 AC2: drafts are distinguishable from requests already submitted"""
    with app.app_context():
        drafts.create_draft(organiser, {"name": "Still a draft"})
        _draft_with_status(organiser, status)
        listed = drafts.list_drafts(organiser)
        assert [d.name for d in listed] == ["Still a draft"]


def test_organiser_with_no_drafts_gets_an_empty_list(app, organiser):
    """ISP-14 AC3 (data side; the empty-state message is a UI test)"""
    with app.app_context():
        assert drafts.list_drafts(organiser) == []


def test_listed_draft_carries_id_name_and_last_updated(app, organiser):
    """ISP-14 AC4"""
    with app.app_context():
        drafts.create_draft(organiser, {"name": "Identifiable"})
        item = drafts.list_drafts(organiser)[0]
        assert item.id is not None
        assert item.name == "Identifiable"
        assert item.updated_at is not None


def test_most_recently_updated_draft_is_listed_first(app, organiser):
    """ISP-14 AC4: last-updated information drives the order"""
    with app.app_context():
        old = drafts.create_draft(organiser, {"name": "Old"})
        new = drafts.create_draft(organiser, {"name": "New"})
        old.updated_at = new.updated_at - timedelta(days=1)
        db.session.commit()
        assert [d.name for d in drafts.list_drafts(organiser)] == ["New", "Old"]


def test_another_organisers_draft_is_not_listed(app, organiser):
    """ISP-14 AC5"""
    with app.app_context():
        other = _other_organiser()
        drafts.create_draft(other, {"name": "Not mine"})
        drafts.create_draft(organiser, {"name": "Mine"})
        assert [d.name for d in drafts.list_drafts(organiser)] == ["Mine"]


# ---------------------------------------------------------------------
# ISP-15  Edit a saved draft event request
# ---------------------------------------------------------------------

def test_updating_a_draft_stores_new_values_and_keeps_the_rest(app, organiser):
    """ISP-15 AC2"""
    with app.app_context():
        event = drafts.create_draft(organiser, _full_data())
        drafts.update_draft(event, {"name": "Renamed", "expected_attendance": 250})
        db.session.expire_all()
        reopened = db.session.get(Event, event.id)

        assert reopened.name == "Renamed"
        assert reopened.expected_attendance == 250
        assert reopened.purpose == "Knowledge sharing"
        assert reopened.capacity_needed == 120


def test_updating_a_draft_keeps_it_a_draft(app, organiser):
    """ISP-15 AC2"""
    with app.app_context():
        event = drafts.create_draft(organiser, {"name": "Edit me"})
        assert drafts.update_draft(event, {"name": "Edited"}).status == "draft"


def test_payload_cannot_change_status_through_an_update(app, organiser):
    """ISP-15 AC5 (stops editing from becoming a back-door submission)"""
    with app.app_context():
        event = drafts.create_draft(organiser, {"name": "Edit me"})
        drafts.update_draft(event, {"status": "submitted", "coordinator_id": 99})
        assert event.status == "draft"
        assert event.coordinator_id is None


@pytest.mark.parametrize("status", NON_DRAFT_STATUSES)
def test_a_request_that_is_not_a_draft_cannot_be_edited_this_way(app, organiser, status):
    """ISP-15 AC5"""
    with app.app_context():
        event = _draft_with_status(organiser, status)
        with pytest.raises(ValueError, match="Only a draft"):
            drafts.update_draft(event, {"name": "Changed"})
        assert event.name == "Status test"


def test_replacing_equipment_removes_the_old_items(app, organiser):
    """ISP-15 AC2"""
    with app.app_context():
        event = drafts.create_draft(
            organiser, {"equipment_requirements": [{"type": "Projector", "quantity": 1}]}
        )
        drafts.update_draft(
            event, {"equipment_requirements": [{"type": "Microphone", "quantity": 3}]}
        )
        assert [(i.equipment_type, i.quantity) for i in event.equipment_requirements] == [("Microphone", 3)]


def test_updating_other_fields_leaves_equipment_untouched(app, organiser):
    """ISP-15 AC2: saving the form without an equipment list must not wipe saved equipment"""
    with app.app_context():
        event = drafts.create_draft(
            organiser, {"equipment_requirements": [{"type": "Projector", "quantity": 1}]}
        )
        drafts.update_draft(event, {"name": "New name"})
        assert len(event.equipment_requirements) == 1


def test_invalid_date_in_an_update_is_rejected(app, organiser):
    """ISP-15 AC2 negative case"""
    with app.app_context():
        event = drafts.create_draft(organiser, {"name": "Edit me"})
        with pytest.raises(ValueError):
            drafts.update_draft(event, {"proposed_date": "not-a-date"})


# ---------------------------------------------------------------------
# ISP-16  Submit a completed draft (validation side only; the route is
# covered by tests/integration/test_event_request_submission.py)
# ---------------------------------------------------------------------

def test_complete_draft_passes_submission_validation(app, organiser):
    """ISP-16 AC1 precondition"""
    with app.app_context():
        event = drafts.create_draft(organiser, _full_data())
        assert validate_for_submission(event) == []


def test_incomplete_draft_names_its_missing_fields_and_stays_a_draft(app, organiser):
    """ISP-16 AC3"""
    with app.app_context():
        event = drafts.create_draft(organiser, {"name": "Missing most things"})
        errors = validate_for_submission(event)
        assert any("purpose" in e for e in errors)
        assert any("description" in e for e in errors)
        assert event.status == "draft"


# ---------------------------------------------------------------------
# ISP-17  Delete an unwanted draft
# ---------------------------------------------------------------------

def test_deleted_draft_is_removed_from_the_list_and_the_database(app, organiser):
    """ISP-17 AC1, AC4"""
    with app.app_context():
        event = drafts.create_draft(organiser, {"name": "Delete me"})
        event_id = event.id
        drafts.delete_draft(event)
        assert db.session.get(Event, event_id) is None
        assert drafts.list_drafts(organiser) == []


def test_deleting_one_draft_leaves_the_others(app, organiser):
    """ISP-17 AC1"""
    with app.app_context():
        keep = drafts.create_draft(organiser, {"name": "Keep"})
        remove = drafts.create_draft(organiser, {"name": "Remove"})
        drafts.delete_draft(remove)
        assert [d.id for d in drafts.list_drafts(organiser)] == [keep.id]


def test_deleting_a_draft_removes_its_equipment_requirements(app, organiser):
    """ISP-17 AC1: no orphaned data is left behind"""
    with app.app_context():
        event = drafts.create_draft(
            organiser, {"equipment_requirements": [{"type": "Projector", "quantity": 2}]}
        )
        drafts.delete_draft(event)
        assert db.session.query(EventEquipmentRequirement).count() == 0


@pytest.mark.parametrize("status", NON_DRAFT_STATUSES)
def test_a_request_that_is_not_a_draft_cannot_be_deleted(app, organiser, status):
    """ISP-17 AC5"""
    with app.app_context():
        event = _draft_with_status(organiser, status)
        event_id = event.id
        with pytest.raises(ValueError, match="Only a draft"):
            drafts.delete_draft(event)
        assert db.session.get(Event, event_id) is not None

