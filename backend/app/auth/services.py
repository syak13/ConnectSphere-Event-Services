from datetime import datetime, timezone

from flask_jwt_extended import create_access_token, create_refresh_token, decode_token
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models.user import RefreshToken, User


def authenticate(email: str, password: str):
    """Verifies credentials against the users table. Returns the User or None."""
    user = User.query.filter_by(email=email, is_active=True).first()
    if not user or not check_password_hash(user.password_hash, password):
        return None
    return user


def issue_tokens(user: User):
    """Issues an access + refresh JWT pair, recording the refresh token's
    jti so it can be revoked on logout."""
    claims = {"roles": user.role_names(), "name": user.name}
    access_token = create_access_token(identity=str(user.id), additional_claims=claims)
    refresh_token = create_refresh_token(identity=str(user.id), additional_claims=claims)

    decoded = decode_token(refresh_token)
    db.session.add(
        RefreshToken(
            user_id=user.id,
            jti=decoded["jti"],
            expires_at=datetime.fromtimestamp(decoded["exp"], tz=timezone.utc).replace(tzinfo=None),
        )
    )
    db.session.commit()

    return access_token, refresh_token


def revoke_refresh_token(jti: str):
    token = RefreshToken.query.filter_by(jti=jti).first()
    if token:
        token.revoked = True
        db.session.commit()


def is_refresh_token_valid(jti: str) -> bool:
    token = RefreshToken.query.filter_by(jti=jti).first()
    return bool(token and not token.revoked)
