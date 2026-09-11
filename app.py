from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_migrate import upgrade as alembic_upgrade
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from config import BASE_DIR, get_config
from extensions import csrf, db, login_manager, migrate
from models import (
    AlertEvent,
    EmergencyFacility,
    EmergencyRequest,
    IncidentReport,
    Location,
    PredictionHistory,
    User,
    UserNotification,
)
from routes import api_bp, auth_bp, main_bp

# Imported so Flask-Migrate can discover the complete schema.
_MIGRATION_MODELS = (
    User,
    Location,
    PredictionHistory,
    EmergencyFacility,
    EmergencyRequest,
    AlertEvent,
    IncidentReport,
    UserNotification,
)
MIGRATIONS_DIR = BASE_DIR / "migrations"


def create_app(config_class=None):
    """Application factory so later phases can register ML, GIS, and data modules cleanly."""
    app = Flask(__name__)
    app.config.from_object(config_class or get_config())

    if not app.config.get("SECRET_KEY"):
        fallback_secret = "nidars-default-insecure-secret-key-change-in-production"
        app.config["SECRET_KEY"] = fallback_secret
        app.logger.warning(
            "SECRET_KEY is not set. Using temporary fallback key. Provide SECRET_KEY in environment variables."
        )

    db.init_app(app)
    migrate.init_app(app, db, directory=str(MIGRATIONS_DIR))
    login_manager.init_app(app)
    csrf.init_app(app)

    # Initialize tables if database is available (supports serverless SQLite and fresh cloud DBs)
    with app.app_context():
        try:
            db.create_all()
        except Exception as err:
            app.logger.warning("Database schema auto-creation deferred or database unavailable: %s", err)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None
        except OperationalError:
            db.session.rollback()
            return None

    @login_manager.unauthorized_handler
    def handle_unauthorized():
        if request.path.startswith("/api/"):
            return jsonify(
                {
                    "success": False,
                    "errors": ["Authentication required."],
                    "prediction": None,
                }
            ), 401
        flash("Please log in to access this page.", "warning")
        return redirect(url_for("auth.login", next=request.path))

    @app.errorhandler(400)
    def handle_bad_request(error):
        if request.path.startswith("/api/"):
            return jsonify({
                "success": False,
                "errors": ["Bad Request. Please verify parameters and request syntax."],
            }), 400
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def handle_forbidden(error):
        if request.path.startswith("/api/"):
            return jsonify({
                "success": False,
                "errors": ["Access Forbidden. Administrator privileges required."],
            }), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def handle_not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({
                "success": False,
                "errors": ["Endpoint or resource not found."],
            }), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        if request.path.startswith("/api/"):
            return jsonify({
                "success": False,
                "errors": [f"HTTP method '{request.method}' is not allowed on this endpoint."],
            }), 405
        return render_template("errors/400.html"), 405

    @app.errorhandler(500)
    def handle_internal_server_error(error):
        app.logger.exception("Internal Server Error encountered")
        if request.path.startswith("/api/"):
            return jsonify({
                "success": False,
                "errors": ["Internal Server Error. Please contact system administrator."],
            }), 500
        return render_template("errors/500.html"), 500

    @app.errorhandler(OperationalError)
    def handle_operational_error(error):
        app.logger.exception("Database connection failed")
        if request.path.startswith("/api/"):
            return jsonify(
                {
                    "status": "error",
                    "application": "NIDARS",
                    "message": "Database unavailable",
                }
            ), 503
        flash(
            "Database connection failed. Check your database settings and try again.",
            "danger",
        )
        return redirect(url_for("main.index"))

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app


app = create_app()


def apply_migrations():
    """Apply Alembic migrations to the database configured in .env."""
    with app.app_context():
        try:
            bind = db.session.execute(text("SELECT DATABASE()")).scalar()
            print(f"Connected database: {bind}")
        except Exception:
            bind = "sqlite_or_other"
            print("Connected database: SQLite/External")

        alembic_upgrade(directory=str(MIGRATIONS_DIR))
        db.create_all()
        tables = inspect(db.engine).get_table_names()
        print("Migrations applied.")
        print("Tables:", ", ".join(tables) if tables else "(none)")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "db-upgrade":
        apply_migrations()
    else:
        apply_migrations()
        app.run(host="127.0.0.1", port=5000, debug=app.config.get("DEBUG", False))
