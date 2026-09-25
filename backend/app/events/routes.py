from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.auth.decorators import roles_required
from app.events.services import assignment, drafts, review
from app.events.services import status as status_service
from app.models.event import Event
from app.models.user import User

events_bp = Blueprint("events", __name__)


def _current_user():
    return User.query.get(int(get_jwt_identity()))


INTERNAL_ROLES = ("event_coordinator", "venue_staff", "technical_support_staff")


INTERNAL_ROLES = ("event_coordinator", "venue_staff", "technical_support_staff")


def _can_view(event: Event, user: User) -> bool:
    if user.has_role("event_organiser") and event.organiser_id == user.id:
        return True
    if event.status == "draft":
        return False  # drafts are private to their organiser until submitted
    return any(user.has_role(r) for r in INTERNAL_ROLES)


# ---------------------------------------------------------------------
# Event Request Creation / Draft Event Requests
# ---------------------------------------------------------------------

@events_bp.post("/drafts")
@roles_required("event_organiser")
def create_draft():
    user = _current_user()
    event = drafts.create_draft(user.id, request.get_json() or {})
    return jsonify(event.to_dict()), 201


@events_bp.get("/drafts")
@roles_required("event_organiser")
def list_drafts():
    user = _current_user()
    return jsonify([e.to_dict() for e in drafts.list_drafts(user.id)]), 200


@events_bp.put("/drafts/<int:event_id>")
@roles_required("event_organiser")
def update_draft(event_id):
    user = _current_user()
    event = Event.query.get(event_id)
    if not event or event.organiser_id != user.id:
        return jsonify({"error": "Draft not found"}), 404
    try:
        event = drafts.update_draft(event, request.get_json() or {})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(event.to_dict()), 200


@events_bp.delete("/drafts/<int:event_id>")
@roles_required("event_organiser")
def delete_draft(event_id):
    user = _current_user()
    event = Event.query.get(event_id)
    if not event or event.organiser_id != user.id:
        return jsonify({"error": "Draft not found"}), 404
    try:
        drafts.delete_draft(event)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return "", 204


@events_bp.post("")
@roles_required("event_organiser")
def create_event():
    """Creates an event request. Pass `"submit": true` in the body to submit
    it directly instead of leaving it as a draft (Event Request Creation:
    'Submit a newly created event request directly')."""
    user = _current_user()
    data = request.get_json() or {}
    submit_now = data.pop("submit", False)

    event = drafts.create_draft(user.id, data)
    if submit_now:
        try:
            event = review.submit_event(event, user.id)
        except (ValueError, PermissionError) as e:
            return jsonify({"error": str(e), "event": event.to_dict()}), 400

    return jsonify(event.to_dict()), 201


@events_bp.post("/<int:event_id>/submit")
@roles_required("event_organiser")
def submit_event_route(event_id):
    user = _current_user()
    event = Event.query.get(event_id)
    if not event or event.organiser_id != user.id:
        return jsonify({"error": "Event not found"}), 404
    try:
        event = review.submit_event(event, user.id)
    except (ValueError, PermissionError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(event.to_dict()), 200


# ---------------------------------------------------------------------
# Viewing (Event Status Management + Coordinator Assignment visibility)
# ---------------------------------------------------------------------

@events_bp.get("/mine")
@roles_required("event_organiser")
def my_events():
    """Organiser views status of all their requests."""
    user = _current_user()
    query = Event.query.filter_by(organiser_id=user.id).order_by(Event.updated_at.desc())
    return jsonify([e.to_dict() for e in query.all()]), 200


@events_bp.get("/assigned")
@roles_required("event_coordinator")
def assigned_events():
    """Coordinator views requests currently assigned to them."""
    user = _current_user()
    query = Event.query.filter_by(coordinator_id=user.id).order_by(Event.updated_at.desc())
    return jsonify([e.to_dict() for e in query.all()]), 200

@jwt_required()
def list_all_events():
    """Single combined calendar view: Coordinators, Venue Staff and Technical
    Support Staff can see all events for planning purposes, read-only unless
    they are the event's assigned Coordinator (Q&A #30/#34)."""
    user = _current_user()
    if not any(user.has_role(r) for r in ("event_coordinator", "venue_staff", "technical_support_staff")):
        return jsonify({"error": "Forbidden"}), 403
    events = (
        Event.query.filter(Event.status != "draft")
        .order_by(Event.proposed_date.asc())
        .all()
    )
    return jsonify([e.to_dict() for e in events]), 200


@events_bp.get("/<int:event_id>")
@jwt_required()
def get_event(event_id):
    user = _current_user()
    event = Event.query.get(event_id)
    if not event or not _can_view(event, user):
        return jsonify({"error": "Event not found"}), 404
    return jsonify(event.to_dict()), 200


# ---------------------------------------------------------------------
# Event Review and Approval
# ---------------------------------------------------------------------

@events_bp.post("/<int:event_id>/clarification")
@roles_required("event_coordinator")
def request_clarification(event_id):
    user = _current_user()
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    data = request.get_json() or {}
    try:
        event = review.request_clarification(event, user.id, data.get("comments", ""))
    except (ValueError, PermissionError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(event.to_dict()), 200


@events_bp.post("/<int:event_id>/clarification/response")
@roles_required("event_organiser")
def respond_clarification(event_id):
    user = _current_user()
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    try:
        event = review.respond_to_clarification(event, user.id, request.get_json() or {})
    except (ValueError, PermissionError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(event.to_dict()), 200


@events_bp.post("/<int:event_id>/approve")
@roles_required("event_coordinator")
def approve_event_route(event_id):
    user = _current_user()
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    data = request.get_json() or {}
    try:
        event = review.approve_event(event, user.id, data.get("comments"))
    except (ValueError, PermissionError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(event.to_dict()), 200


@events_bp.post("/<int:event_id>/reject")
@roles_required("event_coordinator")
def reject_event_route(event_id):
    user = _current_user()
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    data = request.get_json() or {}
    try:
        event = review.reject_event(event, user.id, data.get("reason"))
    except (ValueError, PermissionError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(event.to_dict()), 200


@events_bp.post("/<int:event_id>/resubmit")
@roles_required("event_organiser")
def resubmit_event_route(event_id):
    user = _current_user()
    original = Event.query.get(event_id)
    if not original:
        return jsonify({"error": "Event not found"}), 404
    try:
        new_event = review.resubmit_rejected_event(original, user.id, request.get_json() or {})
    except (ValueError, PermissionError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(new_event.to_dict()), 201


@events_bp.get("/<int:event_id>/outcome")
@jwt_required()
def review_outcome(event_id):
    """Organiser views review outcome and comments (also usable by the
    assigned Coordinator to review their own decision history)."""
    user = _current_user()
    event = Event.query.get(event_id)
    if not event or not _can_view(event, user):
        return jsonify({"error": "Event not found"}), 404
    return (
        jsonify(
            {
                "status": event.status,
                "reviewDecision": event.to_dict()["reviewDecision"],
                "clarificationFlag": event.clarification_flag,
                "clarificationComments": event.clarification_comments,
                "reviewHistory": [r.to_dict() for r in event.reviews],
            }
        ),
        200,
    )


# ---------------------------------------------------------------------
# Coordinator Assignment
# ---------------------------------------------------------------------

@events_bp.post("/<int:event_id>/reassign")
@roles_required("event_coordinator")
def reassign_event(event_id):
    """Reassignment after offline agreement: the currently assigned
    Coordinator hands the event to a named replacement Coordinator
    (Q&A #6/#13/#22 — no accept/decline step, agreement happens outside
    the system first)."""
    user = _current_user()
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    if event.coordinator_id != user.id:
        return jsonify({"error": "Only the currently assigned Coordinator can hand off this event"}), 403

    data = request.get_json() or {}
    new_coordinator = User.query.get(data.get("newCoordinatorId"))
    if not new_coordinator or not new_coordinator.has_role("event_coordinator"):
        return jsonify({"error": "newCoordinatorId must reference an active Event Coordinator"}), 400

    event = assignment.reassign_coordinator(event, new_coordinator)
    return jsonify(event.to_dict()), 200


# ---------------------------------------------------------------------
# Event Status Management
# ---------------------------------------------------------------------

@events_bp.post("/<int:event_id>/status")
@roles_required("event_coordinator")
def change_event_status(event_id):
    """Generic status-change endpoint for the assigned Coordinator, covering
    cancellation and confirmed -> planning reversion on major change. Approve
    /reject/submit have their own dedicated endpoints above since they carry
    extra business rules (reason required, review-decision snapshot, etc.)."""
    user = _current_user()
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    if event.coordinator_id != user.id:
        return jsonify({"error": "Only the assigned Coordinator can change this event's status"}), 403

    data = request.get_json() or {}
    new_status = data.get("status")
    reason = data.get("reason")

    try:
        if new_status == "planning" and event.status == "confirmed":
            event = status_service.revert_to_planning(
                event, user.id, reason or "Major change requires re-planning"
            )
        else:
            event = status_service.change_status(event, new_status, user.id, reason)
    except status_service.InvalidTransitionError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(event.to_dict()), 200
