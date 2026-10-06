"""Tests for: Venue Staff create a new venue record."""
from werkzeug.security import generate_password_hash

import pytest
from app.extensions import db
from app.models.user import Role, User
from app.venues.services import catalogue


@pytest.fixture()
def venue_staff(app):
    with app.app_context():
        user = User(name="Test Venue Staff", email="venue_staff@test.com",
                    password_hash=generate_password_hash("password"))
        user.roles = [Role.query.filter_by(name="venue_staff").first()]
        db.session.add(user)
        db.session.commit()
        return user.id


def test_create_venue_with_full_details_succeeds(app, venue_staff):
    with app.app_context():
        venue = catalogue.create_venue(venue_staff, {
            "name": "Grand Ballroom",
            "location": "Level 3",
            "capacity": 300,
            "description": "Large event space",
            "supportedLayouts": ["banquet", "theatre"],
            "facilities": ["projector", "stage"],
            "accessibilityFeatures": ["wheelchair_access"],
            "operatingHours": {"open": "08:00", "close": "22:00"},
            "setupMinutes": 30,
            "turnaroundMinutes": 45,
        })
        assert venue.id is not None
        assert venue.name == "Grand Ballroom"
        assert venue.setup_minutes == 30
        assert venue.turnaround_minutes == 45
        assert venue in catalogue.list_venues()


def test_create_venue_with_minimal_fields_uses_safe_defaults(app, venue_staff):
    with app.app_context():
        venue = catalogue.create_venue(venue_staff, {"name": "Small Room", "capacity": 10})
        assert venue.supported_layouts == []
        assert venue.facilities == []
        assert venue.accessibility_features == []
        assert venue.operating_hours is None
        assert venue.setup_minutes == 0
        assert venue.turnaround_minutes == 0
        assert venue.is_active is True


def test_create_venue_missing_name_is_rejected(app, venue_staff):
    with app.app_context():
        with pytest.raises(ValueError, match="name"):
            catalogue.create_venue(venue_staff, {"capacity": 50})


def test_create_venue_missing_capacity_is_rejected(app, venue_staff):
    with app.app_context():
        with pytest.raises(ValueError, match="capacity"):
            catalogue.create_venue(venue_staff, {"name": "No Capacity Room"})


def test_create_venue_zero_capacity_is_rejected(app, venue_staff):
    with app.app_context():
        with pytest.raises(ValueError, match="capacity"):
            catalogue.create_venue(venue_staff, {"name": "Zero Room", "capacity": 0})


def test_create_venue_negative_setup_minutes_is_rejected(app, venue_staff):
    with app.app_context():
        with pytest.raises(ValueError, match="Setup"):
            catalogue.create_venue(venue_staff, {"name": "Bad Setup", "capacity": 50, "setupMinutes": -10})


def test_create_venue_negative_turnaround_minutes_is_rejected(app, venue_staff):
    with app.app_context():
        with pytest.raises(ValueError, match="Turnaround"):
            catalogue.create_venue(venue_staff, {"name": "Bad Turnaround", "capacity": 50, "turnaroundMinutes": -5})
