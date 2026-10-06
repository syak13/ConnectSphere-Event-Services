from flask import Flask

from app.config import config_by_name
from app.extensions import db, migrate, jwt, cors


def create_app(config_name="development"):
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # Import models so Flask-Migrate can detect them
    from app.models import user, event, venue  # noqa: F401

    from app.auth.routes import auth_bp
    from app.events.routes import events_bp
    from app.venues.routes import venues_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(events_bp, url_prefix="/api/events")
    app.register_blueprint(venues_bp, url_prefix="/api/venues")

    from app.common.errors import register_error_handlers
    register_error_handlers(app)

    return app
