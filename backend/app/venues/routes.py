from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.auth.decorators import roles_required
from app.models.user import User
from app.venues.services import catalogue

venues_bp = Blueprint("venues", __name__)


def _current_user():
    return User.query.get(int(get_jwt_identity()))


@venues_bp.post("")
@roles_required("venue_staff")
def create_venue():
    user = _current_user()
    try:
        venue = catalogue.create_venue(user.id, request.get_json() or {})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(venue.to_dict()), 201