"""Vercel Serverless Function entry point for NIDARS.

This module initializes the Flask WSGI application instance so Vercel's
Python runtime (@vercel/python) can route HTTP requests into the application.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

# Ensure the repository root directory is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Mark the environment as Vercel serverless
os.environ.setdefault("VERCEL", "1")

try:
    from app import app as _app

    from werkzeug.middleware.proxy_fix import ProxyFix

    class _VercelPathMiddleware:
        """WSGI middleware to normalize PATH_INFO from Vercel rewrites."""

        def __init__(self, wsgi_app):
            self.wsgi_app = wsgi_app

        def __call__(self, environ, start_response):
            import urllib.parse

            # 1. Extract path from __vercel_path query parameter passed by vercel.json
            query = environ.get("QUERY_STRING", "")
            if "__vercel_path=" in query:
                qs = urllib.parse.parse_qs(query, keep_blank_values=True)
                if "__vercel_path" in qs and qs["__vercel_path"]:
                    target_path = "/" + qs["__vercel_path"][0].lstrip("/")
                    environ["PATH_INFO"] = target_path
                    # Reconstruct query string without the routing parameter
                    filtered = {k: v for k, v in qs.items() if k != "__vercel_path"}
                    environ["QUERY_STRING"] = urllib.parse.urlencode(filtered, doseq=True)
                    return self.wsgi_app(environ, start_response)

            # 2. Check direct URI / path headers from Vercel reverse proxy
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

            # 3. Fallback normalization for root serverless invocation
            path_info = environ.get("PATH_INFO", "")
            for prefix in ("/api/index.py", "/api/index"):
                if path_info == prefix or path_info == f"{prefix}/":
                    environ["PATH_INFO"] = "/"
                    break
                elif path_info.startswith(prefix + "/"):
                    environ["PATH_INFO"] = path_info[len(prefix):]
                    break

            return self.wsgi_app(environ, start_response)

    # Wrap WSGI app to catch any unhandled request exceptions and display readable diagnostics
    class _WSGIDiagnosticMiddleware:
        def __init__(self, wsgi_app):
            self.wsgi_app = wsgi_app

        def __call__(self, environ, start_response):
            try:
                return self.wsgi_app(environ, start_response)
            except Exception:
                tb = traceback.format_exc()
                body = (
                    "<!DOCTYPE html><html><head><title>500 Internal Error - NIDARS</title></head>"
                    "<body style='font-family:monospace;background:#0d1117;color:#c9d1d9;padding:2rem;'>"
                    "<h2 style='color:#f85149;'>500 Serverless Execution Error</h2>"
                    "<p>An unhandled exception occurred during request execution:</p>"
                    f"<pre style='background:#161b22;padding:1rem;border-radius:8px;border:1px solid #30363d;color:#ff7b72;overflow:auto;'>{tb}</pre>"
                    "</body></html>"
                ).encode("utf-8")
                start_response(
                    "500 Internal Server Error",
                    [
                        ("Content-Type", "text/html; charset=utf-8"),
                        ("Content-Length", str(len(body))),
                    ],
                )
                return [body]

    # Apply middleware chain: Diagnostic -> Path Normalization -> ProxyFix -> Flask WSGI
    _app.wsgi_app = _WSGIDiagnosticMiddleware(
        _VercelPathMiddleware(
            ProxyFix(_app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
        )
    )
    app = _app

except Exception:
    # Capture import or startup exceptions so Vercel doesn't show a blank FUNCTION_INVOCATION_FAILED
    startup_traceback = traceback.format_exc()
    from flask import Flask

    app = Flask(__name__)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def startup_error_handler(path):
        return (
            "<!DOCTYPE html><html><head><title>Startup Error - NIDARS</title></head>"
            "<body style='font-family:monospace;background:#0d1117;color:#c9d1d9;padding:2rem;'>"
            "<h2 style='color:#f85149;'>Serverless Function Startup Exception</h2>"
            "<p>An error occurred while importing or initializing NIDARS on Vercel:</p>"
            f"<pre style='background:#161b22;padding:1.5rem;border-radius:8px;border:1px solid #30363d;color:#ff7b72;overflow:auto;'>{startup_traceback}</pre>"
            f"<p style='color:#8b949e;'>Python Version: {sys.version}</p>"
            "</body></html>",
            500,
            {"Content-Type": "text/html; charset=utf-8"},
        )

# Export both 'app' and 'handler' to satisfy all Vercel Python runtime entrypoint conventions
handler = app

if __name__ == "__main__":
    app.run()
