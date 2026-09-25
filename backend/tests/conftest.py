import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.user import Organisation, Role, User  # noqa: E402

from sqlalchemy import BigInteger
from sqlalchemy.ext.compiler import compiles


@compiles(BigInteger, "sqlite")
def _compile_big_integer_as_integer_for_sqlite(type_, compiler, **kw):
    """
    SQLite only auto-generates a primary key when its type compiles to
    exactly INTEGER. Our schema uses BIGINT UNSIGNED everywhere (matching
    MySQL), which breaks autoincrement under SQLite-backed tests. This
    only affects the SQLite test dialect -- the real MySQL schema is untouched.
    """
    return "INTEGER"


@pytest.fixture()
def app():
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        for name in ("event_organiser", "event_coordinator", "venue_staff", "technical_support_staff", "attendee"):
            db.session.add(Role(name=name))
        db.session.commit()
        yield application
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def organiser(app):
    with app.app_context():
        org = Organisation(name="Test Org")
        db.session.add(org)
        db.session.commit()
        user = User(
            name="Test Organiser",
            email="organiser@test.com",
            password_hash=generate_password_hash("password"),
            organisation_id=org.id,
        )
        user.roles = [Role.query.filter_by(name="event_organiser").first()]
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture()
def coordinator(app):
    with app.app_context():
        user = User(
            name="Test Coordinator",
            email="coordinator@test.com",
            password_hash=generate_password_hash("password"),
        )
        user.roles = [Role.query.filter_by(name="event_coordinator").first()]
        db.session.add(user)
        db.session.commit()
        return user.id
