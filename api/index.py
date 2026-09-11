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
