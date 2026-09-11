import os
from pathlib import Path
import tempfile
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))


def _resolve_database_uri() -> str:
    """Resolve database URI supporting PostgreSQL, MySQL, and serverless database configuration."""
    db_url = (
        os.environ.get("DATABASE_URL", "").strip()
        or os.environ.get("MYSQL_URL", "").strip()
        or os.environ.get("POSTGRES_URL", "").strip()
    )
    if db_url:
        # Standardize PostgreSQL URLs (Vercel Postgres, Neon, Supabase often use postgres://)
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+pg8000://", 1)
        elif db_url.startswith("postgresql://") and "+pg8000" not in db_url and "+psycopg2" not in db_url:
            db_url = db_url.replace("postgresql://", "postgresql+pg8000://", 1)
        elif db_url.startswith("mysql://") and "+pymysql" not in db_url and "+mysqldb" not in db_url:
            db_url = db_url.replace("mysql://", "mysql+pymysql://", 1)
        return db_url

    user = os.environ.get("DB_USER", "").strip()
    host = os.environ.get("DB_HOST", "").strip()
    password = quote_plus(os.environ.get("DB_PASSWORD", ""))
    port = os.environ.get("DB_PORT", "3306").strip() or "3306"
    name = os.environ.get("DB_NAME", "nidars_db").strip() or "nidars_db"

    # If DB credentials and remote host are explicitly provided
    if user and host and host not in ("127.0.0.1", "localhost"):
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"

    is_serverless = bool(
        os.environ.get("VERCEL")
        or os.environ.get("VERCEL_ENV")
        or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        or os.environ.get("LAMBDA_TASK_ROOT")
    )

    # In local environment with local MySQL configured
    if not is_serverless and user:
        host_str = host or "127.0.0.1"
        return f"mysql+pymysql://{user}:{password}@{host_str}:{port}/{name}?charset=utf8mb4"

    if is_serverless:
        temp_db_path = Path(tempfile.gettempdir()) / "nidars.db"
        return f"sqlite:///{temp_db_path.as_posix()}"

    local_db_path = BASE_DIR / "nidars.db"
    return f"sqlite:///{local_db_path.as_posix()}"


def _get_float_env(name: str, default: float) -> float:
    """Safely parse float from environment variable, handling None, empty strings, and invalid inputs."""
    raw = os.environ.get(name, "")
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(raw)
    except (ValueError, TypeError):
        return default


def _get_int_env(name: str, default: int) -> int:
    """Safely parse int from environment variable, handling None, empty strings, and invalid inputs."""
    raw = os.environ.get(name, "")
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default


def _resolve_secret_key() -> str:
    """Resolve a secure, stable SECRET_KEY from environment or stable deterministic fallback."""
    key = os.environ.get("SECRET_KEY", "").strip()
    if key:
        return key
    return "nidars-stable-production-secret-key-v1-2026"


class Config:
    """Base configuration. Credentials and secrets come from the environment only."""

    SECRET_KEY = _resolve_secret_key()
    DEBUG = os.environ.get("FLASK_DEBUG", "true").lower() in {"1", "true", "yes"}

    _RESOLVED_DB_URI = _resolve_database_uri()
    SQLALCHEMY_DATABASE_URI = _RESOLVED_DB_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = (
        {}
        if _RESOLVED_DB_URI.startswith("sqlite")
        else {
            "pool_pre_ping": True,
            "pool_recycle": 280,
        }
    )

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SSL_STRICT = False
    WTF_CSRF_TIME_LIMIT = None

    FLOOD_DATASET_PATH = BASE_DIR / "data" / "processed" / "flood_training.csv"
    FLOOD_MODEL_DIR = BASE_DIR / "ml" / "flood" / "model"
    FLOOD_MODEL_PATH = FLOOD_MODEL_DIR / "flood_model.pkl"
    FLOOD_PREPROCESSOR_PATH = FLOOD_MODEL_DIR / "flood_preprocessor.pkl"
    FLOOD_EVALUATION_PATH = FLOOD_MODEL_DIR / "evaluation.json"
    # Application UI thresholds only — not official IMD/NDMA warning bands.
    FLOOD_RISK_LOW_MAX = 0.25
    FLOOD_RISK_MODERATE_MAX = 0.50
    FLOOD_RISK_HIGH_MAX = 0.75

    LANDSLIDE_DATASET_PATH = BASE_DIR / "data" / "processed" / "landslide_training.csv"
    LANDSLIDE_MODEL_DIR = BASE_DIR / "ml" / "landslide" / "model"
    LANDSLIDE_MODEL_PATH = LANDSLIDE_MODEL_DIR / "landslide_model.pkl"
    LANDSLIDE_PREPROCESSOR_PATH = LANDSLIDE_MODEL_DIR / "landslide_preprocessor.pkl"
    LANDSLIDE_EVALUATION_PATH = LANDSLIDE_MODEL_DIR / "evaluation.json"
    # Validated Phase 4.1 thresholds (advisory: 0.02, warning: 0.10)
    LANDSLIDE_RISK_LOW_MAX = 0.02
    LANDSLIDE_RISK_MODERATE_MAX = 0.10
    LANDSLIDE_RISK_HIGH_MAX = 0.25

    # GIS configuration & spatial risk mapping
    NORTH_INDIA_WEATHER_PATH = BASE_DIR / "data" / "processed" / "north_india_weather.csv"
    GIS_GEOJSON_DIR = BASE_DIR / "gis" / "geojson"
    GIS_FLOOD_WEIGHT = 0.50
    GIS_LANDSLIDE_WEIGHT = 0.50
    GIS_COMBINED_RISK_LOW_MAX = 0.25
    GIS_COMBINED_RISK_MODERATE_MAX = 0.50
    GIS_COMBINED_RISK_HIGH_MAX = 0.75

    # Phase 6: Safe Route Optimization configuration
    OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL") or "https://router.project-osrm.org"
    ROUTE_PROFILE = os.environ.get("ROUTE_PROFILE") or "driving"
    ROUTE_STATION_RADIUS_KM = _get_float_env("ROUTE_STATION_RADIUS_KM", 50.0)
    ROUTE_SAMPLE_INTERVAL_KM = _get_float_env("ROUTE_SAMPLE_INTERVAL_KM", 1.0)
    ROUTE_RISK_PENALTY_FACTOR = _get_float_env("ROUTE_RISK_PENALTY_FACTOR", 10.0)
    ROUTE_MIN_CONFIDENCE_COVERAGE = _get_float_env("ROUTE_MIN_CONFIDENCE_COVERAGE", 30.0)
    OSRM_TIMEOUT_SECONDS = _get_float_env("OSRM_TIMEOUT_SECONDS", 10.0)

    # Phase 7: Emergency Mode & Facility Discovery configuration
    OVERPASS_BASE_URL = os.environ.get("OVERPASS_BASE_URL") or "https://overpass-api.de/api/interpreter"
    EMERGENCY_SEARCH_RADIUS_KM = _get_float_env("EMERGENCY_SEARCH_RADIUS_KM", 15.0)
    EMERGENCY_MAX_RESULTS = _get_int_env("EMERGENCY_MAX_RESULTS", 25)
    OVERPASS_TIMEOUT_SECONDS = _get_float_env("OVERPASS_TIMEOUT_SECONDS", 12.0)

    # Phase 14: Emergency Evacuation & Safe Zone Analysis configuration
    EVACUATION_MAX_CANDIDATES = _get_int_env("EVACUATION_MAX_CANDIDATES", 5)
    EVACUATION_MAX_DISTANCE_KM = _get_float_env("EVACUATION_MAX_DISTANCE_KM", 25.0)
    EVACUATION_WEIGHT_DEST_RISK = _get_float_env("EVACUATION_WEIGHT_DEST_RISK", 0.40)
    EVACUATION_WEIGHT_ROUTE_RISK = _get_float_env("EVACUATION_WEIGHT_ROUTE_RISK", 0.35)
    EVACUATION_WEIGHT_DISTANCE = _get_float_env("EVACUATION_WEIGHT_DISTANCE", 0.20)
    EVACUATION_WEIGHT_TYPE = _get_float_env("EVACUATION_WEIGHT_TYPE", 0.05)

    # Phase 9: Real-Time Weather Monitoring configuration
    WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")
    WEATHER_PROVIDER = os.environ.get("WEATHER_PROVIDER") or "open-meteo"
    WEATHER_API_BASE_URL = os.environ.get("WEATHER_API_BASE_URL") or "https://api.open-meteo.com/v1/forecast"
    WEATHER_TIMEOUT_SECONDS = _get_float_env("WEATHER_TIMEOUT_SECONDS", 8.0)

    # Phase 15: Incident Reporting Upload configuration
    INCIDENT_UPLOAD_DIR = (
        Path(tempfile.gettempdir()) / "uploads" / "incidents"
        if IS_VERCEL
        else BASE_DIR / "static" / "uploads" / "incidents"
    )
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max request size
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}



class DevelopmentConfig(Config):

    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestConfig(Config):
    TESTING = True
    DEBUG = False
    SECRET_KEY = "nidars-test-secret"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}


def get_config():
    env = os.environ.get("FLASK_ENV", "development").lower()
    if env == "production":
        return ProductionConfig
    if env == "testing":
        return TestConfig
    return DevelopmentConfig
