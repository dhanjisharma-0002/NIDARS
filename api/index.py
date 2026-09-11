"""Vercel Serverless Function entry point for NIDARS.

This module initializes the Flask WSGI application instance so Vercel's
Python runtime (@vercel/python) can route HTTP requests into the application.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the repository root directory is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Mark the environment as Vercel serverless
os.environ.setdefault("VERCEL", "1")

from app import create_app
from config import ProductionConfig, get_config

config_class = ProductionConfig if os.environ.get("FLASK_ENV") == "production" else get_config()
app = create_app(config_class)

# For direct execution / testing
if __name__ == "__main__":
    app.run()
