"""
Venue Suitability Check — HTTP API (mounted at /api)

GET  /api/venues/suitability-options                         fixed accessibility + layout vocabularies
GET  /api/events/<id>/venue-suitability                      every active venue, checked against the event
GET  /api/events/<id>/venue-suitability/<venue_id>           one venue
GET  /api/events/<id>/venue-suitability/overrides            override audit trail for the event
POST /api/events/<id>/venue-suitability/<venue_id>/overrides { flagType, reason }

Booking itself goes through the existing Venue Booking Request endpoint
(POST /api/venues/bookings), which refuses venues with un-overridden
unsuitable flags (see services/booking_requests.py).
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.auth.decorators import roles_required
from app.extensions import db
from app.models.event import Event
from app.models.user import User
from app.models.venue import Venue
from app.venues.services import suitability_check as suitability
from app.venues.services.requirements import ACCESSIBILITY_FEATURES, LAYOUT_TYPES

suitability_bp = Blueprint("venue_suitability", __name__)

STAFF_ROLES = ("event_coordinator", "venue_staff", "technical_support_staff")


def _current_user():
    return db.session.get(User, int(get_jwt_identity()))


def _visible_event(event_id):
    """Suitability is a staff planning tool: drafts are private to their
    organiser, so they are never checked here."""
    event = db.session.get(Event, event_id)
    if not event or event.status == "draft":
        return None
    return event


@suitability_bp.get("/venues/suitability-options")
@jwt_required()
def options():
    return (
        jsonify(
            {
                "accessibilityFeatures": [{"code": k, "label": v} for k, v in ACCESSIBILITY_FEATURES.items()],
                "layoutTypes": [{"code": k, "label": v} for k, v in LAYOUT_TYPES.items()],
                "minOverrideReasonLength": suitability.MIN_OVERRIDE_REASON_LENGTH,
            }
        ),
        200,
    )


@suitability_bp.get("/events/<int:event_id>/venue-suitability")
@roles_required(*STAFF_ROLES)
def list_venue_suitability(event_id):
    user = _current_user()
    event = _visible_event(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    return (
        jsonify(
            {
                "eventId": event.id,
                "eventStatus": event.status,
                "requirements": suitability.event_requirements(event),
                "isAssignedCoordinator": event.coordinator_id == user.id and user.has_role("event_coordinator"),
                "venues": suitability.list_suitability(event),
                "overrideHistory": suitability.override_history(event),
            }
        ),
        200,
    )


@suitability_bp.get("/events/<int:event_id>/venue-suitability/overrides")
@roles_required(*STAFF_ROLES)
def list_overrides(event_id):
    event = _visible_event(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    return jsonify(suitability.override_history(event)), 200


@suitability_bp.get("/events/<int:event_id>/venue-suitability/<int:venue_id>")
@roles_required(*STAFF_ROLES)
def get_venue_suitability(event_id, venue_id):
    event = _visible_event(event_id)
    venue = db.session.get(Venue, venue_id)
    if not event or not venue:
        return jsonify({"error": "Event or venue not found"}), 404
    return jsonify(suitability.evaluate_venue(event, venue)), 200


@suitability_bp.post("/events/<int:event_id>/venue-suitability/<int:venue_id>/overrides")
@roles_required("event_coordinator")
def create_override(event_id, venue_id):
    user = _current_user()
    event = _visible_event(event_id)
    venue = db.session.get(Venue, venue_id)
    if not event or not venue:
        return jsonify({"error": "Event or venue not found"}), 404

    data = request.get_json() or {}
    try:
        override = suitability.override_flag(event, venue, user, data.get("flagType"), data.get("reason"))
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:  # SuitabilityError + descriptive-text validation
        return jsonify({"error": str(e)}), 400

    return (
        jsonify({"override": override.to_dict(), "suitability": suitability.evaluate_venue(event, venue)}),
        201,
    )
