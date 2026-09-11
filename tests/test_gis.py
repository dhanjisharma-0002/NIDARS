"""Comprehensive Tests for NIDARS Phase 11 Advanced GIS Intelligence."""

from __future__ import annotations

import pytest

from app import create_app
from config import TestConfig
from extensions import db
from gis.processing import get_spatial_risk_engine, load_station_latest_observations
from gis.risk_zones import (
    calculate_combined_risk,
    classify_combined_risk,
    classify_flood_risk,
    classify_landslide_risk,
    to_feature_collection,
    to_geojson_feature,
    validate_geojson,
)
from services.gis_service import (
    get_district_boundaries_geojson,
    get_emergency_facilities_geojson,
    get_gis_summary_statistics,
    get_north_india_rivers_geojson,
    get_spatial_risk_data,
)
from tests.conftest import login, make_user


@pytest.fixture
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(app, client):
    make_user(app)
    login(client)
    return client


# --- 1. Risk Formulas & Classification Tests ---


def test_combined_risk_equal_weights():
    score = calculate_combined_risk(flood_prob=0.40, landslide_prob=0.20, flood_weight=0.50, landslide_weight=0.50)
    assert score == pytest.approx(0.30, rel=1e-4)


def test_combined_risk_custom_weights():
    score = calculate_combined_risk(flood_prob=0.80, landslide_prob=0.20, flood_weight=0.70, landslide_weight=0.30)
    assert score == pytest.approx(0.62, rel=1e-4)


def test_combined_risk_boundary_clamping():
    assert calculate_combined_risk(-0.5, 1.5) == 0.5
    assert calculate_combined_risk(0.0, 0.0) == 0.0
    assert calculate_combined_risk(1.0, 1.0) == 1.0


def test_combined_risk_zero_weight_raises():
    with pytest.raises(ValueError):
        calculate_combined_risk(0.5, 0.5, flood_weight=0.0, landslide_weight=0.0)


def test_landslide_risk_classification_phase_4_1_thresholds():
    """Preserve validated Phase 4.1 thresholds: <0.02 LOW, 0.02-0.10 MODERATE, >=0.10 HIGH."""
    assert classify_landslide_risk(0.005) == "LOW"
    assert classify_landslide_risk(0.0199) == "LOW"
    assert classify_landslide_risk(0.02) == "MODERATE"
    assert classify_landslide_risk(0.05) == "MODERATE"
    assert classify_landslide_risk(0.099) == "MODERATE"
    assert classify_landslide_risk(0.10) == "HIGH"
    assert classify_landslide_risk(0.20) == "HIGH"
    assert classify_landslide_risk(0.35) == "CRITICAL"


def test_flood_risk_classification():
    assert classify_flood_risk(0.10) == "LOW"
    assert classify_flood_risk(0.30) == "MODERATE"
    assert classify_flood_risk(0.60) == "HIGH"
    assert classify_flood_risk(0.85) == "CRITICAL"


def test_combined_risk_classification():
    assert classify_combined_risk(0.15) == "LOW"
    assert classify_combined_risk(0.35) == "MODERATE"
    assert classify_combined_risk(0.65) == "HIGH"
    assert classify_combined_risk(0.80) == "CRITICAL"


# --- 2. GeoJSON Structure & RFC 7946 Compliance ---


def test_geojson_feature_creation():
    props = {"station": "Shimla", "state": "HP", "risk_level": "LOW"}
    feat = to_geojson_feature(latitude=31.1048, longitude=77.1734, properties=props, feature_id=1)
    assert feat["type"] == "Feature"
    assert feat["id"] == 1
    assert feat["geometry"]["type"] == "Point"
    # RFC 7946 coordinates: [longitude, latitude]
    assert feat["geometry"]["coordinates"] == [77.1734, 31.1048]
    assert feat["properties"]["station"] == "Shimla"


def test_geojson_validation():
    feat = to_geojson_feature(latitude=31.1048, longitude=77.1734, properties={"station": "Shimla"})
    fc = to_feature_collection([feat], metadata={"total": 1})
    valid, errors = validate_geojson(fc)
    assert valid is True
    assert len(errors) == 0


def test_geojson_validation_invalid_object():
    valid, errors = validate_geojson({"type": "InvalidType"})
    assert valid is False
    assert any("FeatureCollection" in e for e in errors)


# --- 3. Observation Data & Spatial Coordinates Integrity ---


def test_load_station_latest_observations_shape():
    df = load_station_latest_observations()
    # 64 weather stations in North India
    assert len(df) == 64
    assert "station_name" in df.columns
    assert "latitude" in df.columns
    assert "longitude" in df.columns
    assert "rainfall_24h" in df.columns
    assert "rainfall_72h" in df.columns
    assert "rainfall_7d" in df.columns


def test_station_coordinates_within_north_india():
    df = load_station_latest_observations()
    for _, row in df.iterrows():
        lat = float(row["latitude"])
        lon = float(row["longitude"])
        # North India latitude range: 22.0 to 36.0, longitude range: 73.0 to 89.0
        assert 22.0 <= lat <= 36.0, f"Station {row['station_name']} latitude {lat} out of expected range"
        assert 73.0 <= lon <= 89.0, f"Station {row['station_name']} longitude {lon} out of expected range"


# --- 4. Layer Filtering & Engine Features ---


def test_spatial_risk_engine_station_filter():
    engine = get_spatial_risk_engine()
    fc = engine.get_spatial_risk_features(station="Shimla")
    assert len(fc["features"]) >= 1
    for feat in fc["features"]:
        assert "shimla" in feat["properties"]["station"].lower() or "shimla" in feat["properties"]["district"].lower()


def test_spatial_risk_engine_risk_level_filter():
    engine = get_spatial_risk_engine()
    fc = engine.get_spatial_risk_features(risk_level="LOW")
    for feat in fc["features"]:
        assert feat["properties"]["risk_level"] == "LOW"


def test_spatial_risk_engine_empty_filter_results():
    engine = get_spatial_risk_engine()
    fc = engine.get_spatial_risk_features(district="NonExistentDistrictName")
    assert len(fc["features"]) == 0
    assert fc["type"] == "FeatureCollection"


def test_get_gis_summary_statistics_structure():
    stats = get_gis_summary_statistics()
    assert stats["success"] is True
    assert stats["monitored_stations"] == 64
    assert "risk_counts" in stats
    assert "low" in stats["risk_counts"]
    assert "moderate" in stats["risk_counts"]
    assert "high" in stats["risk_counts"]
    assert "critical" in stats["risk_counts"]
    assert sum(stats["risk_counts"].values()) == 64
    assert "state_breakdown" in stats
    assert "JK" in stats["state_breakdown"]
    assert "HP" in stats["state_breakdown"]
    assert "UP" in stats["state_breakdown"]
    assert "BR" in stats["state_breakdown"]


# --- 5. Authentic Emergency Facilities, Rivers & Boundaries Layers ---


def test_get_emergency_facilities_geojson():
    fc = get_emergency_facilities_geojson(facility_type="hospital")
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) > 0
    valid, errors = validate_geojson(fc)
    assert valid is True
    for feat in fc["features"]:
        assert feat["properties"]["facility_type"] == "hospital"
        lat, lon = feat["geometry"]["coordinates"][1], feat["geometry"]["coordinates"][0]
        assert 22.0 <= lat <= 36.0
        assert 73.0 <= lon <= 89.0


def test_get_north_india_rivers_geojson():
    fc = get_north_india_rivers_geojson()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) >= 5
    river_names = [feat["properties"]["name"] for feat in fc["features"]]
    assert any("Ganga" in name for name in river_names)
    assert any("Yamuna" in name for name in river_names)


def test_get_district_boundaries_geojson():
    fc = get_district_boundaries_geojson()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) >= 4
    state_codes = [feat["properties"]["state_code"] for feat in fc["features"]]
    assert "JK" in state_codes
    assert "HP" in state_codes
    assert "UP" in state_codes
    assert "BR" in state_codes


# --- 6. Backend GIS API Endpoints & Authorization Tests ---


def test_gis_api_requires_login(client):
    response = client.get("/api/gis/risk")
    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_gis_api_combined_mode(auth_client):
    response = auth_client.get("/api/gis/risk?hazard=combined")
    assert response.status_code == 200
    data = response.get_json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 64
    assert data["metadata"]["hazard_mode"] == "combined"

    first = data["features"][0]
    assert "properties" in first
    props = first["properties"]
    assert "flood_probability" in props
    assert "landslide_probability" in props
    assert "combined_risk" in props
    assert "risk_level" in props
    assert props["hazard"] == "combined"


def test_gis_api_flood_mode(auth_client):
    response = auth_client.get("/api/gis/risk?hazard=flood")
    assert response.status_code == 200
    data = response.get_json()
    assert data["metadata"]["hazard_mode"] == "flood"
    for feat in data["features"]:
        assert feat["properties"]["hazard"] == "flood"
        assert feat["properties"]["risk_score"] == feat["properties"]["flood_probability"]


def test_gis_api_landslide_mode(auth_client):
    response = auth_client.get("/api/gis/risk?hazard=landslide")
    assert response.status_code == 200
    data = response.get_json()
    assert data["metadata"]["hazard_mode"] == "landslide"
    for feat in data["features"]:
        assert feat["properties"]["hazard"] == "landslide"
        assert feat["properties"]["risk_score"] == feat["properties"]["landslide_probability"]


def test_gis_api_state_filter(auth_client):
    response = auth_client.get("/api/gis/risk?state=HP")
    assert response.status_code == 200
    data = response.get_json()
    # Himachal Pradesh has 11 stations
    assert len(data["features"]) == 11
    for feat in data["features"]:
        assert feat["properties"]["state"] == "HP"


def test_gis_api_district_filter(auth_client):
    response = auth_client.get("/api/gis/risk?district=Patna")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["features"]) >= 1
    for feat in data["features"]:
        assert feat["properties"]["district"].upper() == "PATNA"


def test_gis_api_station_search(auth_client):
    response = auth_client.get("/api/gis/risk?station=Srinagar")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["features"]) >= 1
    for feat in data["features"]:
        assert "srinagar" in feat["properties"]["station"].lower() or "srinagar" in feat["properties"]["district"].lower()


def test_gis_api_limit(auth_client):
    response = auth_client.get("/api/gis/risk?limit=5")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["features"]) == 5


def test_gis_api_invalid_hazard(auth_client):
    response = auth_client.get("/api/gis/risk?hazard=earthquake")
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert any("Invalid hazard" in err for err in data["errors"])


def test_gis_api_invalid_limit(auth_client):
    response = auth_client.get("/api/gis/risk?limit=-3")
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False


def test_gis_api_invalid_weights(auth_client):
    response = auth_client.get("/api/gis/risk?flood_weight=-1.0")
    assert response.status_code == 400
    assert response.get_json()["success"] is False

    response2 = auth_client.get("/api/gis/risk?landslide_weight=invalid")
    assert response2.status_code == 400
    assert response2.get_json()["success"] is False


def test_gis_api_geojson_compliance(auth_client):
    response = auth_client.get("/api/gis/risk")
    assert response.status_code == 200
    data = response.get_json()
    valid, errors = validate_geojson(data)
    assert valid is True, f"GeoJSON validation failed with errors: {errors}"


def test_gis_stats_api(auth_client):
    response = auth_client.get("/api/gis/stats")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["monitored_stations"] == 64
    assert "risk_counts" in data
    assert "state_breakdown" in data


def test_gis_facilities_api(auth_client):
    response = auth_client.get("/api/gis/facilities?type=police")
    assert response.status_code == 200
    data = response.get_json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
    for feat in data["features"]:
        assert feat["properties"]["facility_type"] == "police"


def test_gis_facilities_api_invalid_type(auth_client):
    response = auth_client.get("/api/gis/facilities?type=airport")
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_gis_rivers_api(auth_client):
    response = auth_client.get("/api/gis/rivers")
    assert response.status_code == 200
    data = response.get_json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0


def test_gis_boundaries_api(auth_client):
    response = auth_client.get("/api/gis/boundaries")
    assert response.status_code == 200
    data = response.get_json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
