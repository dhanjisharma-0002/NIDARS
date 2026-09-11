import sys
import traceback

try:
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

        from werkzeug.middleware.proxy_fix import ProxyFix

        class _VercelPathMiddleware:
            """WSGI middleware to normalize PATH_INFO when running behind Vercel rewrites."""

            def __init__(self, wsgi_app):
                self.wsgi_app = wsgi_app

            def __call__(self, environ, start_response):
                # 1. Check direct URI / path headers from Vercel edge reverse proxy
                for key in (
                    "RAW_URI",
                    "REQUEST_URI",
                    "HTTP_X_FORWARDED_URI",
                    "HTTP_X_FORWARDED_PATH",
                    "HTTP_X_INVOKE_PATH",
                    "HTTP_X_REAL_PATH",
                ):
                    val = environ.get(key)
                    if val:
                        clean = val.split("?")[0].strip()
                        if clean and not (clean.startswith("/api/index") or clean in ("/api", "/api/")):
                            if not clean.startswith("/"):
                                clean = "/" + clean
                            environ["PATH_INFO"] = clean
                            return self.wsgi_app(environ, start_response)

                # 2. Check route matches if Vercel passed captured regex group (e.g. 1=dashboard)
                matches = environ.get("HTTP_X_NOW_ROUTE_MATCHES", "")
                if matches:
                    import urllib.parse
                    parsed = urllib.parse.parse_qs(matches)
                    if "1" in parsed and parsed["1"]:
                        captured = parsed["1"][0]
                        if not captured.startswith("/"):
                            captured = "/" + captured
                        environ["PATH_INFO"] = captured
                        return self.wsgi_app(environ, start_response)

                # 3. Check HTTP_X_MATCHED_PATH
                matched = environ.get("HTTP_X_MATCHED_PATH")
                if matched:
                    clean = matched.split("?")[0].strip()
                    if clean and not (clean.startswith("/api/index") or clean in ("/api", "/api/")):
                        if not clean.startswith("/"):
                            clean = "/" + clean
                        environ["PATH_INFO"] = clean
                        return self.wsgi_app(environ, start_response)

                # 4. Normalize if PATH_INFO still points to the serverless function path
                path_info = environ.get("PATH_INFO", "")
                for prefix in ("/api/index.py", "/api/index"):
                    if path_info == prefix or path_info == f"{prefix}/":
                        environ["PATH_INFO"] = "/"
                        break
                    elif path_info.startswith(prefix + "/"):
                        environ["PATH_INFO"] = path_info[len(prefix):]
                        break

                return self.wsgi_app(environ, start_response)

        app.wsgi_app = _VercelPathMiddleware(
            ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
        )

        return app

    app = create_app()

except Exception as _startup_err:
    _traceback_str = traceback.format_exc()
    print(f"CRITICAL APP STARTUP FAILURE IN app.py:\n{_traceback_str}", file=sys.stderr)
    from flask import Flask

    app = Flask(__name__)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def _startup_diagnostic_page(path):
        return (
            "<!DOCTYPE html><html><head><title>NIDARS Initialization Exception</title></head>"
            "<body style='font-family:monospace;background:#0d1117;color:#c9d1d9;padding:2rem;'>"
            "<h2 style='color:#f85149;'>Serverless Function Initialization Exception in app.py</h2>"
            "<p>An uncaught exception occurred while loading <code>app.py</code>:</p>"
            f"<pre style='background:#161b22;padding:1.5rem;border-radius:8px;border:1px solid #30363d;color:#ff7b72;overflow:auto;font-size:14px;'>{_traceback_str}</pre>"
            f"<p style='color:#8b949e;'>Python Version: {sys.version}</p>"
            "</body></html>",
            500,
            {"Content-Type": "text/html; charset=utf-8"},
        )

# Export handler for Vercel Python runtime compatibility
handler = app


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
