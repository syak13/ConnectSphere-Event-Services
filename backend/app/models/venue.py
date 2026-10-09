"""
Venue Catalogue / Venue Availability Calendar / Venue Booking Request /
Venue Booking Approval models.
"""
from app.common.time import utcnow
from app.extensions import db
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.dialects.mysql import BIGINT

NOT_SPECIFIED = "not specified"
VENUE_ID_TYPE = db.BigInteger().with_variant(BIGINT(unsigned=True), "mysql")
# Single source of truth for venue booking statuses (must match the ENUM in
# database/schema.sql). Only APPROVED bookings block a venue.
BOOKING_PENDING = "pending"
BOOKING_APPROVED = "approved"
BOOKING_REJECTED = "rejected"
BOOKING_WITHDRAWN = "withdrawn"
ACTIVE_BOOKING_STATUSES = (BOOKING_PENDING, BOOKING_APPROVED)

class Venue(db.Model):
    __tablename__ = "venues"

    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)

    accessibility_info = db.Column(db.Text, nullable=True)
    operating_hours = db.Column(db.String(255), nullable=True)
    # Week 7 change #1: minutes the venue is occupied before / after an event
    setup_minutes = db.Column(db.Integer, nullable=False, default=0)
    turnaround_minutes = db.Column(db.Integer, nullable=False, default=0)

    facility_entries = db.relationship(
        "VenueFacility",
        back_populates="venue",
        cascade="all, delete-orphan",
        order_by="VenueFacility.facility_name",
    )
    facilities = association_proxy(
        "facility_entries",
        "facility_name",
        creator=lambda facility_name: VenueFacility(facility_name=facility_name),
    )
    accessibility_entries = db.relationship(
        "VenueAccessibilityFeature",
        back_populates="venue",
        cascade="all, delete-orphan",
        order_by="VenueAccessibilityFeature.feature_name",
    )
    accessibility_features = association_proxy(
        "accessibility_entries",
        "feature_name",
        creator=lambda feature_name: VenueAccessibilityFeature(feature_name=feature_name),
    )

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    unavailabilities = db.relationship(
        "VenueUnavailability",
        backref="venue",
        cascade="all, delete-orphan",
    )

    bookings = db.relationship(
        "VenueBooking",
        backref="venue",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "capacity": self.capacity,
            "accessibilityInfo": self.accessibility_info,
            "accessibilityFeatures": list(self.accessibility_features or []),
            "facilities": list(self.facilities or []),
            "operatingHours": self.operating_hours,
            "isActive": self.is_active,
        }


class VenueFacility(db.Model):
    __tablename__ = "venue_facilities"
    __table_args__ = (
        db.UniqueConstraint("venue_id", "facility_name", name="uq_venue_facility"),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    venue_id = db.Column(
        VENUE_ID_TYPE, db.ForeignKey("venues.id", ondelete="CASCADE"), nullable=False
    )
    facility_name = db.Column(db.String(150), nullable=False)
    venue = db.relationship("Venue", back_populates="facility_entries")


class VenueAccessibilityFeature(db.Model):
    __tablename__ = "venue_accessibility_features"
    __table_args__ = (
        db.UniqueConstraint("venue_id", "feature_name", name="uq_venue_accessibility_feature"),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    venue_id = db.Column(
        VENUE_ID_TYPE, db.ForeignKey("venues.id", ondelete="CASCADE"), nullable=False
    )
    feature_name = db.Column(db.String(150), nullable=False)
    venue = db.relationship("Venue", back_populates="accessibility_entries")


class VenueUnavailability(db.Model):
    """Venue Staff blocking a venue for maintenance, renovation, etc.
    (Venue Availability Calendar epic)."""
    __tablename__ = "venue_unavailability"

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
    __tablename__ = "venue_bookings"

    id = db.Column(db.BigInteger, primary_key=True)

    event_id = db.Column(
        db.BigInteger,
        db.ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )

    venue_id = db.Column(
        db.BigInteger,
        db.ForeignKey("venues.id"),
        nullable=False,
    )

    requested_by = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id"),
        nullable=False,
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="pending",
    )

    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)

    decision_reason = db.Column(db.Text, nullable=True)

    decided_by = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    decided_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=utcnow,
        onupdate=utcnow,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "eventId": self.event_id,
            "venueId": self.venue_id,
            "status": self.status,
            "startDatetime": (
                self.start_datetime.isoformat()
                if self.start_datetime
                else None
            ),
            "endDatetime": (
                self.end_datetime.isoformat()
                if self.end_datetime
                else None
            ),
            "requestedBy": self.requested_by,
            "decidedBy": self.decided_by,
            "decisionReason": self.decision_reason,
            "createdAt": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
            "decidedAt": (
                self.decided_at.isoformat()
                if self.decided_at
                else None
            ),
        }

class VenueAvailabilityFlag(db.Model):
    """Flag raised when a venue's availability changes in a way that
    affects an already-planned upcoming event (e.g. a new maintenance
    block overlaps an approved booking)."""
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
