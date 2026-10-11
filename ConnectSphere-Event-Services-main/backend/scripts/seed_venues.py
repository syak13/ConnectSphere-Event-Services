"""
Creates a small venue catalogue for local development of the Venue
Suitability Check (capacities, layouts and accessibility features chosen so
every flag type can be seen in the UI). Layouts and accessibility features are
stored the same way the Venue Catalogue page stores them.

Run with:  python scripts/seed_venues.py
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.venue import Venue  # noqa: E402

app = create_app(os.getenv("FLASK_ENV", "development"))

VENUES = [
    {
        "name": "Harbour Hall", "location": "Level 1, Marina Wing", "capacity": 300,
        "layouts": ["theatre", "banquet", "cabaret", "reception"],
        "access": ["Step-free access", "Hearing loop", "Accessible toilet", "Wheelchair seating", "Accessible parking"],
    },
    {
        "name": "Orchid Room", "location": "Level 3, East Wing", "capacity": 35,
        "layouts": ["classroom", "boardroom", "u-shape"],
        "access": ["Step-free access", "Accessible toilet"],
    },
    {
        "name": "Skyline Studio", "location": "Rooftop", "capacity": 80,
        "layouts": ["theatre", "reception"],
        "access": ["Hearing loop"],
    },
    {
        "name": "Garden Pavilion", "location": "Ground floor, outdoor terrace", "capacity": 120,
        "layouts": ["banquet", "exhibition"],
        "access": ["Ramp", "Wheelchair seating", "Accessible parking"],
    },
]

with app.app_context():
    created = 0
    for v in VENUES:
        if Venue.query.filter_by(name=v["name"]).first():
            continue
        venue = Venue(name=v["name"], location=v["location"], capacity=v["capacity"], is_active=True)
        venue.supported_layouts = v["layouts"]
        venue.accessibility_features = v["access"]
        db.session.add(venue)
        created += 1
    db.session.commit()
    print(f"Seeded {created} new venue(s).")
