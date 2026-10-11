"""
Creates a handful of test users (one per role), sample venues, and dummy
events for local development.

ConnectSphere accounts are expected to be provisioned outside the system in
production (Q&A #28/#45), so there is no self-registration endpoint. This
script stands in for that external provisioning process during development.

Run with:  python scripts/seed_users.py
Safe to re-run: existing users, venues and events (matched by name) are skipped.
"""
import os
import sys
from datetime import datetime, time, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.event import Event  # noqa: E402  (adjust if your Event model lives elsewhere)
from app.models.user import Organisation, Role, User  # noqa: E402
from app.models.venue import Venue  # noqa: E402

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

TEST_VENUES = [
    {"name": "Main Auditorium", "location": "North Campus", "capacity": 300,
     "accessibility_info": "Wheelchair accessible", "operating_hours": "08:00-22:00",
     "accessibility_features": ["Wheelchair accessible"],
     "facilities": ["Microphone", "Projector", "Wi-Fi"],
     "setup_minutes": 30, "turnaround_minutes": 45},
    {"name": "Seminar Room A", "location": "North Campus", "capacity": 40,
     "accessibility_info": None, "operating_hours": "08:00-22:00",
     "facilities": ["Projector", "Whiteboard", "Wi-Fi"],
     "setup_minutes": 15, "turnaround_minutes": 15},
    {"name": "Banquet Hall", "location": "South Campus", "capacity": 150,
     "accessibility_info": "Step-free entrance", "operating_hours": "08:00-23:00",
     "accessibility_features": ["Step-free entrance"],
     "facilities": ["Microphone", "Stage"],
     "setup_minutes": 60, "turnaround_minutes": 60},
]

# ---------------------------------------------------------------------------
# Dummy events. One per status so every screen/state in the app has data.
# "coordinator" is the email of the assigned coordinator (None = unassigned,
# as for drafts). "days" is the proposed date offset from today (negative =
# past). "resubmits" names an earlier event this one was resubmitted from.
# ---------------------------------------------------------------------------
TEST_EVENTS = [
    {
        "name": "Spring Product Showcase",
        "purpose": "Customer-facing product demo",
        "description": "Annual showcase of new products for clients and partners.",
        "category": "Conference",
        "status": "draft",
        "coordinator": None,
        "days": 45, "time": time(10, 0),
        "expected_attendance": 120, "capacity_needed": 150,
        "required_layout": "Theatre",
        "accessibility_needs": "Wheelchair access and hearing loop",
        "required_facilities": ["Projector", "Microphone", "Wi-Fi"],
        "registration_required": 1, "intended_capacity": 150,
    },
    {
        "name": "Quarterly All-Hands Meeting",
        "purpose": "Company-wide update",
        "description": "Leadership update on quarterly results and priorities.",
        "category": "Meeting",
        "status": "submitted",
        "coordinator": "coordinator1@example.com",
        "days": 30, "time": time(14, 0),
        "expected_attendance": 250, "capacity_needed": 280,
        "required_layout": "Theatre",
        "accessibility_needs": None,
        "required_facilities": ["Projector", "Microphone", "Live Streaming"],
        "registration_required": 0, "intended_capacity": 280,
        "submitted_days_ago": 2,
    },
    {
        "name": "Leadership Workshop",
        "purpose": "Professional development",
        "description": "Half-day interactive workshop for team leads.",
        "category": "Workshop",
        "status": "under_review",
        "coordinator": "coordinator2@example.com",
        "days": 21, "time": time(9, 30),
        "expected_attendance": 35, "capacity_needed": 40,
        "required_layout": "Classroom",
        "accessibility_needs": None,
        "required_facilities": ["Whiteboard", "Projector"],
        "registration_required": 1, "intended_capacity": 40,
        "submitted_days_ago": 5,
        "clarification_flag": 1,
        "clarification_comments": "Please confirm whether catering is needed and the exact end time.",
    },
    {
        "name": "Alumni Networking Dinner",
        "purpose": "Alumni engagement",
        "description": "Evening dinner and networking for alumni and sponsors.",
        "category": "Social",
        "status": "approved",
        "coordinator": "coordinator1@example.com",
        "days": 60, "time": time(18, 30),
        "expected_attendance": 120, "capacity_needed": 130,
        "required_layout": "Banquet",
        "accessibility_needs": "Step-free access",
        "required_facilities": ["Microphone", "Stage"],
        "registration_required": 1, "intended_capacity": 130,
        "submitted_days_ago": 10,
        "review_outcome": "approved", "review_reason": "Meets requirements; proceed to venue planning.",
        "review_days_ago": 7,
    },
    {
        "name": "Hackathon Kickoff",
        "purpose": "Student innovation event",
        "description": "Kickoff session for the 48-hour campus hackathon.",
        "category": "Competition",
        "status": "planning",
        "coordinator": "coordinator2@example.com",
        "days": 35, "time": time(9, 0),
        "expected_attendance": 200, "capacity_needed": 220,
        "required_layout": "Theatre",
        "accessibility_needs": "Wheelchair access",
        "required_facilities": ["Projector", "Microphone", "Wi-Fi", "Power Outlets"],
        "registration_required": 1, "intended_capacity": 220,
        "submitted_days_ago": 20,
        "review_outcome": "approved", "review_reason": "Approved. Venue and equipment to be arranged.",
        "review_days_ago": 15,
    },
    {
        "name": "Industry Panel: Future of AI",
        "purpose": "Public panel discussion",
        "description": "Panel of industry speakers followed by Q&A.",
        "category": "Panel",
        "status": "confirmed",
        "coordinator": "coordinator1@example.com",
        "days": 14, "time": time(17, 0),
        "expected_attendance": 180, "capacity_needed": 200,
        "required_layout": "Theatre",
        "accessibility_needs": "Hearing loop",
        "required_facilities": ["Projector", "Microphones", "Recording"],
        "registration_required": 1, "intended_capacity": 200,
        "submitted_days_ago": 30,
        "review_outcome": "approved", "review_reason": "Approved.",
        "review_days_ago": 26,
    },
    {
        "name": "Orientation Welcome Session",
        "purpose": "New student orientation",
        "description": "Welcome session for incoming students.",
        "category": "Orientation",
        "status": "completed",
        "coordinator": "coordinator2@example.com",
        "days": -20, "time": time(10, 0),
        "expected_attendance": 280, "capacity_needed": 300,
        "required_layout": "Theatre",
        "accessibility_needs": "Wheelchair access",
        "required_facilities": ["Projector", "Microphone"],
        "registration_required": 0, "intended_capacity": 300,
        "submitted_days_ago": 60,
        "review_outcome": "approved", "review_reason": "Approved.",
        "review_days_ago": 55,
    },
    {
        "name": "Charity Gala Evening",
        "purpose": "Fundraising",
        "description": "Gala dinner raising funds for a local charity.",
        "category": "Social",
        "status": "cancelled",
        "coordinator": "coordinator1@example.com",
        "days": 25, "time": time(19, 0),
        "expected_attendance": 140, "capacity_needed": 150,
        "required_layout": "Banquet",
        "accessibility_needs": None,
        "required_facilities": ["Stage", "Microphone"],
        "registration_required": 1, "intended_capacity": 150,
        "submitted_days_ago": 40,
        "review_outcome": "approved", "review_reason": "Approved.",
        "review_days_ago": 35,
    },
    {
        "name": "Open Air Music Night",
        "purpose": "Student entertainment",
        "description": "Live music event with a large expected crowd.",
        "category": "Entertainment",
        "status": "rejected",
        "coordinator": "coordinator1@example.com",
        "days": 28, "time": time(20, 0),
        "expected_attendance": 800, "capacity_needed": 800,
        "required_layout": "Standing",
        "accessibility_needs": None,
        "required_facilities": ["Stage", "PA System"],
        "registration_required": 0, "intended_capacity": 800,
        "submitted_days_ago": 12,
        "review_outcome": "rejected",
        "review_reason": "Expected attendance exceeds the capacity of all available venues.",
        "review_days_ago": 9,
    },
    {
        "name": "Open Air Music Night (Revised)",
        "purpose": "Student entertainment",
        "description": "Scaled-down version of the music night, sized to fit the Banquet Hall.",
        "category": "Entertainment",
        "status": "submitted",
        "coordinator": "coordinator1@example.com",
        "days": 40, "time": time(20, 0),
        "expected_attendance": 140, "capacity_needed": 150,
        "required_layout": "Standing",
        "accessibility_needs": None,
        "required_facilities": ["Stage", "PA System"],
        "registration_required": 0, "intended_capacity": 150,
        "submitted_days_ago": 1,
        "resubmits": "Open Air Music Night",
    },
]

# Fields that are not columns on Event and are handled separately.
_HELPER_KEYS = {"coordinator", "days", "time", "submitted_days_ago",
                "review_days_ago", "resubmits"}

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

    venues_created = 0
    for entry in TEST_VENUES:
        venue = Venue.query.filter_by(name=entry["name"]).first()
        if venue:
            for field in ("facilities", "accessibility_features"):
                if not getattr(venue, field) and entry.get(field):
                    setattr(venue, field, entry[field])
            continue
        db.session.add(Venue(**entry))
        venues_created += 1

    # Commit users/venues first so events can reference their ids.
    db.session.commit()

    # -----------------------------------------------------------------
    # Events
    # -----------------------------------------------------------------
    organiser = User.query.filter_by(email="organiser@example.com").first()
    coordinators = {
        u.email: u
        for u in User.query.filter(
            User.email.in_(["coordinator1@example.com", "coordinator2@example.com"])
        ).all()
    }

    now = datetime.utcnow()
    today = now.date()
    events_created = 0

    for entry in TEST_EVENTS:
        if Event.query.filter_by(name=entry["name"], organiser_id=organiser.id).first():
            continue

        coord = coordinators.get(entry["coordinator"]) if entry["coordinator"] else None

        fields = {k: v for k, v in entry.items() if k not in _HELPER_KEYS}
        fields["organiser_id"] = organiser.id
        fields["coordinator_id"] = coord.id if coord else None
        fields["proposed_date"] = today + timedelta(days=entry["days"])
        fields["proposed_time"] = entry["time"]

        if "submitted_days_ago" in entry:
            fields["submitted_at"] = now - timedelta(days=entry["submitted_days_ago"])

        if "review_outcome" in entry:
            fields["review_coordinator_id"] = coord.id if coord else None
            fields["review_timestamp"] = now - timedelta(days=entry["review_days_ago"])

        if "resubmits" in entry:
            original = Event.query.filter_by(
                name=entry["resubmits"], organiser_id=organiser.id
            ).first()
            if original:
                fields["resubmitted_from_event_id"] = original.id

        db.session.add(Event(**fields))
        db.session.flush()  # so a later event can reference this one's id
        events_created += 1

    db.session.commit()

    print(f"Seeded {created} new test user(s). Password for all: '{DEFAULT_PASSWORD}'")
    print(f"Seeded {venues_created} new sample venue(s).")
    print(f"Seeded {events_created} new sample event(s).")