from app.common.time import utcnow
from app.extensions import db


class Venue(db.Model):
    __tablename__ = "venues"

    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=True)
    capacity = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=True)
    supported_layouts = db.Column(db.JSON, nullable=True)
    facilities = db.Column(db.JSON, nullable=True)
    accessibility_features = db.Column(db.JSON, nullable=True)
    operating_hours = db.Column(db.JSON, nullable=True)
    setup_minutes = db.Column(db.Integer, nullable=False, default=0)
    turnaround_minutes = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

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