"""
Unit tests for Event Request Creation validation logic.

Tests validate_for_submission() in isolation against directly-constructed
Event objects with proper Python types. No HTTP layer, no realistic
request-body parsing involved here -- see tests/integration for that.
"""
from datetime import date, timedelta

import pytest

from app.events.services.validators import validate_for_submission
from app.models.event import Event, EventEquipmentRequirement

FUTURE_DATE = date.today() + timedelta(days=7)


def _valid_event(organiser_id):
    """A fully valid Event, built directly with proper Python types."""
    return Event(
        organiser_id=organiser_id,
        status="draft",
        name="Annual Tech Conference",
        purpose="Knowledge sharing",
        description="A conference for the tech community.",
        proposed_date=FUTURE_DATE,
        proposed_time="09:00",
        expected_attendance=100,
        capacity_needed=120,
        required_layout="theatre",
        accessibility_needs="Wheelchair access required",
        registration_required=False,
    )

def test_valid_event_has_no_errors(app, organiser):
    with app.app_context():
        event = _valid_event(organiser)
        assert validate_for_submission(event) == []


def test_missing_name_is_blocked(app, organiser):
    with app.app_context():
        event = _valid_event(organiser)
        event.name = ""
        errors = validate_for_submission(event)
        assert any("name" in e for e in errors)


def test_missing_proposed_time_is_blocked(app, organiser):
    """Regression test: proposed_time was missing from the original
    REQUIRED_FOR_SUBMISSION list even though the AC requires it."""
    with app.app_context():
        event = _valid_event(organiser)
        event.proposed_time = None
        errors = validate_for_submission(event)
        assert any("proposed_time" in e for e in errors)


def test_missing_venue_requirements_is_blocked(app, organiser):
    """Regression test: venue requirements weren't checked at all originally."""
    with app.app_context():
        event = _valid_event(organiser)
        event.capacity_needed = None
        event.required_layout = ""
        event.accessibility_needs = ""
        errors = validate_for_submission(event)
        assert any("capacity_needed" in e for e in errors)
        assert any("required_layout" in e for e in errors)
        assert any("accessibility_needs" in e for e in errors)


def test_category_is_optional(app, organiser):
    with app.app_context():
        event = _valid_event(organiser)
        event.category = None
        assert validate_for_submission(event) == []


def test_registration_without_intended_capacity_is_blocked(app, organiser):
    with app.app_context():
        event = _valid_event(organiser)
        event.registration_required = True
        event.intended_capacity = None
        errors = validate_for_submission(event)
        assert any("Intended capacity" in e for e in errors)


def test_registration_with_intended_capacity_succeeds(app, organiser):
    with app.app_context():
        event = _valid_event(organiser)
        event.registration_required = True
        event.intended_capacity = 50
        assert validate_for_submission(event) == []


def test_negative_expected_attendance_is_blocked(app, organiser):
    with app.app_context():
        event = _valid_event(organiser)
        event.expected_attendance = -5
        errors = validate_for_submission(event)
        assert any("Expected attendance" in e for e in errors)


def test_past_proposed_date_is_blocked(app, organiser):
    with app.app_context():
        event = _valid_event(organiser)
        event.proposed_date = date.today() - timedelta(days=1)
        errors = validate_for_submission(event)
        assert any("past" in e for e in errors)


def test_equipment_item_missing_quantity_is_blocked(app, organiser):
    with app.app_context():
        event = _valid_event(organiser)
        event.equipment_requirements = [
            EventEquipmentRequirement(equipment_type="Projector", quantity=0)
        ]
        errors = validate_for_submission(event)
        assert any("quantity" in e for e in errors)


def test_equipment_item_missing_type_is_blocked(app, organiser):
    with app.app_context():
        event = _valid_event(organiser)
        event.equipment_requirements = [
            EventEquipmentRequirement(equipment_type="", quantity=2)
        ]
        errors = validate_for_submission(event)
        assert any("type" in e for e in errors)