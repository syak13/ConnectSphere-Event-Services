from app.extensions import db
from app.models.venue import Venue


def create_venue(user_id: int, data: dict) -> Venue:
    venue = Venue(
        name=data.get("name"),
        location=data.get("location"),
        capacity=data.get("capacity"),
        description=data.get("description"),
        supported_layouts=data.get("supportedLayouts") or [],
        facilities=data.get("facilities") or [],
        accessibility_features=data.get("accessibilityFeatures") or [],
        operating_hours=data.get("operatingHours"),
        setup_minutes=data.get("setupMinutes", 0),
        turnaround_minutes=data.get("turnaroundMinutes", 0),
        created_by=user_id,
    )
    if not venue.name:
        raise ValueError("Venue name is required")
    if not venue.capacity or venue.capacity <= 0:
        raise ValueError("Venue capacity must be greater than zero")
    if venue.setup_minutes < 0:
        raise ValueError("Setup time cannot be negative")
    if venue.turnaround_minutes < 0:
        raise ValueError("Turnaround time cannot be negative")

    db.session.add(venue)
    db.session.commit()
    return venue


def get_venue(venue_id: int):
    return Venue.query.get(venue_id)


def list_venues(active_only: bool = True):
    query = Venue.query
    if active_only:
        query = query.filter_by(is_active=True)
    return query.order_by(Venue.name.asc()).all()