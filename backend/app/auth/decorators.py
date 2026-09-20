from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request


def roles_required(*allowed_roles):
    """Restricts a route to users holding at least one of the given roles.
    Supports multiple roles per account: a user passes if any one of their
    roles is in allowed_roles."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            user_roles = set(claims.get("roles", []))
            if not user_roles.intersection(allowed_roles):
                return jsonify({"error": "Forbidden: insufficient role"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator
