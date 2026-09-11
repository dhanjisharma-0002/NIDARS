from routes.auth import auth_bp
from routes.main import api_bp, main_bp
from routes import flood as flood_routes  # noqa: F401  — registers flood page and API
from routes import gis as gis_routes  # noqa: F401  — registers GIS endpoints
from routes import routing as routing_routes  # noqa: F401  — registers safe route optimization page and API
from routes import emergency as emergency_routes  # noqa: F401  — registers emergency mode page and API
from routes import admin as admin_routes  # noqa: F401  — registers admin dashboard and API
from routes import weather as weather_routes  # noqa: F401  — registers weather monitoring page and API
from routes import alerts as alert_routes  # noqa: F401  — registers early warning & advisory page and API
from routes import simulator as simulator_routes  # noqa: F401  — registers what-if risk simulator page and API
from routes import incidents as incident_routes  # noqa: F401  — registers citizen incident reporting page and API
from routes import analytics as analytics_routes  # noqa: F401  — registers advanced analytics dashboard and API
from routes import reports as report_routes  # noqa: F401  — registers PDF disaster report generation API
from routes import notifications as notification_routes  # noqa: F401  — registers notification and alert API

__all__ = ["main_bp", "api_bp", "auth_bp"]



