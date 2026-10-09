"""Venue Catalogue epic."""
from app.extensions import db
from app.models.venue import (
    ACTIVE_BOOKING_STATUSES,
    BOOKING_APPROVED,
    Venue,
    VenueAvailabilityFlag,
    VenueBooking,
)
SUITABILITY_FIELDS = {"capacity", "supported_layouts", "accessibility_features"}
TIMING_FIELDS = {"setup_minutes", "turnaround_minutes"}  # Week 7 change #1


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


def _flag_suitability_change(venue: Venue, reason: str):
    """Re-checks every confirmed booking on this venue against the venue's
    (now-updated) capacity/layout/accessibility and raises a flag for any
    event that no longer fits."""
    from app.venues.services.suitability import check_suitability

    confirmed = VenueBooking.query.filter(
        VenueBooking.venue_id == venue.id, VenueBooking.status == BOOKING_APPROVED
    ).all()

    flags = []
    for booking in confirmed:
        event = booking.event
        if not event:
            continue
        issues = check_suitability(event, venue)
        if issues:
            flag = VenueAvailabilityFlag(
                event_id=event.id, venue_id=venue.id, reason=f"{reason}: {'; '.join(issues)}"
            )
            db.session.add(flag)
            flags.append(flag)
    return flags


def update_venue(venue: Venue, data: dict):
    """Edit an existing venue record. Returns (venue, flags_raised).
    flags_raised can come from two independent checks: a capacity/layout/
    accessibility change that no longer suits an existing confirmed
    booking, or (Week 7 change #1) a setup/turnaround time change that
    makes two existing confirmed bookings newly overlap."""
    changed_fields = set()

    for field, key in (
        ("name", "name"),
        ("location", "location"),
        ("capacity", "capacity"),
        ("description", "description"),
        ("supported_layouts", "supportedLayouts"),
        ("facilities", "facilities"),
        ("accessibility_features", "accessibilityFeatures"),
        ("operating_hours", "operatingHours"),
        ("setup_minutes", "setupMinutes"),
        ("turnaround_minutes", "turnaroundMinutes"),
    ):
        if key in data and data[key] != getattr(venue, field):
            setattr(venue, field, data[key])
            changed_fields.add(field)

    if venue.setup_minutes is not None and venue.setup_minutes < 0:
        raise ValueError("Setup time cannot be negative")
    if venue.turnaround_minutes is not None and venue.turnaround_minutes < 0:
        raise ValueError("Turnaround time cannot be negative")

    flags = []
    if changed_fields & SUITABILITY_FIELDS:
        flags += _flag_suitability_change(venue, "Venue details changed after booking was confirmed")
    if changed_fields & TIMING_FIELDS:
        from app.venues.services.availability import flag_timing_conflicts

        flags += flag_timing_conflicts(
            venue, "Venue setup/turnaround time changed, creating a new scheduling conflict"
        )

    db.session.commit()
    return venue, flags


def deactivate_venue(venue: Venue) -> Venue:
    """Delete/deactivate a venue record. Per the AC, this is only permitted
    when the venue has no active (pending or confirmed) bookings -- a venue
    mid-use should not be silently pulled out from under an event."""
    active_booking = VenueBooking.query.filter(
        VenueBooking.venue_id == venue.id,
        VenueBooking.status.in_(ACTIVE_BOOKING_STATUSES),
    ).first()
    if active_booking:
        raise ValueError(
            "Cannot deactivate a venue with active bookings. "
            "Cancel or reassign them first."
        )

    venue.is_active = False
    db.session.commit()
    return venue


def list_venues(active_only: bool = True):
    query = Venue.query
    if active_only:
        query = query.filter_by(is_active=True)
    return query.order_by(Venue.name.asc()).all()


def get_venue(venue_id: int):
    return Venue.query.get(venue_id)
