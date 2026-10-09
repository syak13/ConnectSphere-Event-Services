"""Venue Suitability Checking epic. Advisory only -- returns flags, never
blocks a Coordinator from proceeding (per Q&A: suitability is based on
human judgement, not a hard system-enforced constraint)."""
from app.models.event import Event
from app.models.venue import Venue


def check_suitability(event: Event, venue: Venue) -> list[str]:
    flags = []

    if event.expected_attendance and venue.capacity and event.expected_attendance > venue.capacity:
        flags.append(
            f"Expected attendance ({event.expected_attendance}) exceeds venue capacity ({venue.capacity})"
        )

    if event.required_layout:
        supported = {str(layout).strip().lower() for layout in (venue.supported_layouts or [])}
        if event.required_layout.strip().lower() not in supported:
            flags.append(f"Venue does not support the required layout: {event.required_layout}")

    if event.accessibility_needs and event.accessibility_needs.lower() not in ("none", "n/a", ""):
        venue_access = venue.accessibility_features or []
        if not venue_access:
            flags.append("Venue has no recorded accessibility features")

    return flags
