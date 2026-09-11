"""WSGI production entry point for NIDARS.

Compatible with Gunicorn, uWSGI, Waitress, and other standard WSGI servers.
Usage:
    gunicorn wsgi:app
    waitress-serve --port=5000 wsgi:app
"""

import os
from app import create_app
from config import ProductionConfig, get_config

config_class = ProductionConfig if os.environ.get("FLASK_ENV") == "production" else get_config()
app = create_app(config_class)

if __name__ == "__main__":
    app.run()
