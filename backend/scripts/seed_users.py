"""
Creates a handful of test users (one per role) for local development.

ConnectSphere accounts are expected to be provisioned outside the system in
production (Q&A #28/#45), so there is no self-registration endpoint. This
script stands in for that external provisioning process during development.

Run with:  python scripts/seed_users.py
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.user import Organisation, Role, User  # noqa: E402

app = create_app(os.getenv("FLASK_ENV", "development"))

DEFAULT_PASSWORD = "Password123!"

TEST_USERS = [
    {"name": "Olivia Organiser", "email": "organiser@example.com", "roles": ["event_organiser"]},
    {"name": "Carlos Coordinator", "email": "coordinator1@example.com", "roles": ["event_coordinator"]},
    {"name": "Priya Coordinator", "email": "coordinator2@example.com", "roles": ["event_coordinator"]},
    {"name": "Vince Venue", "email": "venue@example.com", "roles": ["venue_staff"]},
    {"name": "Tara TechSupport", "email": "techsupport@example.com", "roles": ["technical_support_staff"]},
    {"name": "Alex Attendee", "email": "attendee@example.com", "roles": ["attendee"]},
]

with app.app_context():
    org = Organisation.query.first()
    if not org:
        org = Organisation(name="Acme Events Ltd")
        db.session.add(org)
        db.session.commit()

    created = 0
    for entry in TEST_USERS:
        if User.query.filter_by(email=entry["email"]).first():
            continue
        user = User(
            name=entry["name"],
            email=entry["email"],
            password_hash=generate_password_hash(DEFAULT_PASSWORD),
            organisation_id=org.id,
        )
        user.roles = [Role.query.filter_by(name=r).first() for r in entry["roles"]]
        db.session.add(user)
        created += 1

    db.session.commit()
    print(f"Seeded {created} new test user(s). Password for all: '{DEFAULT_PASSWORD}'")
