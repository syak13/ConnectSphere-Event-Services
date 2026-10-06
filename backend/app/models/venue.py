"""
Venue Catalogue / Venue Availability Calendar / Venue Booking Request /
Venue Booking Approval models.
"""
from app.common.time import utcnow
from app.extensions import db


class Venue(db.Model):
    __tablename__ = "venues"

    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=True)
    capacity = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=True)
    supported_layouts = db.Column(db.JSON, nullable=True)       # e.g. ["theatre", "banquet"]
    facilities = db.Column(db.JSON, nullable=True)              # e.g. ["projector", "stage"]
    accessibility_features = db.Column(db.JSON, nullable=True)  # e.g. ["wheelchair_access"]
    operating_hours = db.Column(db.JSON, nullable=True)         # e.g. {"open": "08:00", "close": "22:00"}
    setup_minutes = db.Column(db.Integer, nullable=False, default=0)       # Week 7 change #1
    turnaround_minutes = db.Column(db.Integer, nullable=False, default=0)  # Week 7 change #1
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    unavailabilities = db.relationship(
        "VenueUnavailability", backref="venue", cascade="all, delete-orphan"
    )
    bookings = db.relationship("VenueBooking", backref="venue", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "capacity": self.capacity,
            "description": self.description,
            "supportedLayouts": self.supported_layouts or [],
            "facilities": self.facilities or [],
            "accessibilityFeatures": self.accessibility_features or [],
            "operatingHours": self.operating_hours,
            "setupMinutes": self.setup_minutes,
            "turnaroundMinutes": self.turnaround_minutes,
            "isActive": self.is_active,
        }


class VenueUnavailability(db.Model):
    """Venue Staff blocking a venue for maintenance, renovation, etc.
    (Venue Availability Calendar epic)."""
    __tablename__ = "venue_unavailabilities"

    id = db.Column(db.BigInteger, primary_key=True)
    venue_id = db.Column(db.BigInteger, db.ForeignKey("venues.id", ondelete="CASCADE"), nullable=False)
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "venueId": self.venue_id,
            "start": self.start_datetime.isoformat(),
            "end": self.end_datetime.isoformat(),
            "reason": self.reason,
        }


class VenueBooking(db.Model):
    """Venue Booking Request / Venue Booking Approval epics.
    One event has at most one active (pending/confirmed) booking at a time
    (Q&A: each event can only have one venue)."""
    __tablename__ = "venue_bookings"

    id = db.Column(db.BigInteger, primary_key=True)
    event_id = db.Column(db.BigInteger, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    venue_id = db.Column(db.BigInteger, db.ForeignKey("venues.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    # pending | confirmed | rejected | withdrawn
    # Week 7 change #3: one event can now have several VenueBooking rows
    # (one per venue it needs) -- no uniqueness constraint on event_id.
    label = db.Column(db.String(150), nullable=True)  # Week 7 change #3, e.g. "Main auditorium", "Breakout room 2"
    requested_by = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    decided_by = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    decision_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    decided_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "eventId": self.event_id,
            "venueId": self.venue_id,
            "label": self.label,
            "status": self.status,
            "requestedBy": self.requested_by,
            "decidedBy": self.decided_by,
            "decisionReason": self.decision_reason,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "decidedAt": self.decided_at.isoformat() if self.decided_at else None,
        }


class VenueAvailabilityFlag(db.Model):
    """Flag raised when a venue's availability changes in a way that
    affects an already-planned upcoming event (e.g. a new maintenance
    block overlaps a confirmed booking)."""
    __tablename__ = "venue_availability_flags"

    id = db.Column(db.BigInteger, primary_key=True)
    event_id = db.Column(db.BigInteger, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    venue_id = db.Column(db.BigInteger, db.ForeignKey("venues.id", ondelete="CASCADE"), nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    resolved = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "eventId": self.event_id,
            "venueId": self.venue_id,
            "reason": self.reason,
            "resolved": self.resolved,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
