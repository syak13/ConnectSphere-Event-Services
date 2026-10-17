from app.common.time import utcnow
from app.extensions import db


class ChangeRequest(db.Model):
    __tablename__ = "change_requests"

    id = db.Column(db.BigInteger, primary_key=True)
    event_id = db.Column(db.BigInteger, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    organiser_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    request_type = db.Column(db.String(20), nullable=False, default="change")
    # {field: {"from": current value, "to": proposed value}}, only fields that differ
    requested_changes = db.Column(db.JSON, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    is_significant = db.Column(db.Boolean, nullable=False, default=False)
    # pending | processed | rejected | cannot_accommodate
    status = db.Column(db.String(30), nullable=False, default="pending")
    coordinator_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)  # who decided it
    decision_reason = db.Column(db.Text, nullable=True)
    decided_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "eventId": self.event_id,
            "organiserId": self.organiser_id,
            "requestType": self.request_type,
            "status": self.status,
            "isSignificant": self.is_significant,
            "requestedChanges": self.requested_changes or {},
            "reason": self.reason,
            "decisionReason": self.decision_reason,
            "decidedAt": self.decided_at.isoformat() if self.decided_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
    
class EventChangeHistory(db.Model):
    """One row per field changed when a Coordinator processes a change request."""

    __tablename__ = "event_change_history"

    id = db.Column(db.BigInteger, primary_key=True)
    event_id = db.Column(db.BigInteger, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    change_request_id = db.Column(
        db.BigInteger, db.ForeignKey("change_requests.id", ondelete="CASCADE"), nullable=False
    )
    field = db.Column(db.String(100), nullable=False)
    old_value = db.Column(db.JSON, nullable=True)
    new_value = db.Column(db.JSON, nullable=True)
    changed_by = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    changed_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "eventId": self.event_id,
            "changeRequestId": self.change_request_id,
            "field": self.field,
            "oldValue": self.old_value,
            "newValue": self.new_value,
            "changedBy": self.changed_by,
            "changedAt": self.changed_at.isoformat() if self.changed_at else None,
        }