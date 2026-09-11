# NIDARS — Phase 8 Complete Project Audit

**Project:** NIDARS (North India Disaster Awareness & Route System)  
**Full Title:** AI-Based North India Flood and Landslide Prediction with Disaster-Aware Safe Route Optimization Using Machine Learning and GIS  
**Audit Date:** September 8, 2026  
**Auditor:** NIDARS Development Team  
**Status:** ALL PHASES 1–7 VERIFIED & INTEGRATED

---

## 1. System Architecture Overview
NIDARS is built as a multi-tier, modular Flask-based web and GIS platform designed for spatial hazard prediction, disaster-aware route optimization, emergency facility discovery, and administrative monitoring across North India (Jammu & Kashmir, Himachal Pradesh, Uttar Pradesh, Bihar).

```text
                                [ User / Web Client ]
                                         │
                                         ▼
                               [ Flask Web Framework ]
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
             [ Auth & RBAC ]     [ RESTful APIs ]     [ Jinja2 Templates ]
             (Flask-Login)       (/api/* endpoints)    (Bootstrap 5/Leaflet)
                    │                    │                    │
                    ▼                    ▼                    ▼
           [ MySQL Database ]   [ Services & Engines] [ Interactive Visuals ]
             - users              - weather_service     - Leaflet GeoJSON
             - locations          - flood_service       - OSRM Route Polylines
             - prediction_history - landslide_service   - Chart.js Dashboards
             - emergency_fac      - spatial_risk_engine
             - emergency_req      - route_risk_service
                                  - emergency_service
```

---

## 2. Directory and Module Breakdown

| Directory / File | Description | Status |
| :--- | :--- | :--- |
| `app.py` | Application factory (`create_app`), error handlers (400, 403, 404, 405, 500), blueprint registration, and migration runner. | Audited & Verified |
| `config.py` | Environment-aware hierarchical configurations (`DevelopmentConfig`, `ProductionConfig`, `TestConfig`). | Audited & Verified |
| `wsgi.py` | Production WSGI entry point for Gunicorn / Waitress. | Audited & Verified |
| `extensions.py` | Shared extensions (`db`, `migrate`, `login_manager`, `csrf`). | Audited & Verified |
| `routes/` | Blueprint controllers: `auth.py`, `main.py`, `flood.py`, `gis.py`, `routing.py`, `emergency.py`, `admin.py`. | Audited & Verified |
| `models/` | SQLAlchemy models: `User`, `Location`, `PredictionHistory`, `EmergencyFacility`, `EmergencyRequest`. | Audited & Verified |
| `services/` | Business logic services: `weather_service.py`, `flood_service.py`, `landslide_service.py`, `gis_service.py`, `routing_service.py`, `route_risk_service.py`, `emergency_service.py`. | Audited & Verified |
| `ml/flood/` | Random Forest flood prediction pipeline, feature schema (9 meteorological features), preprocessing, model artifacts. | Audited & Intact |
| `ml/landslide/` | Gradient Boosting landslide prediction pipeline, NASA catalog grounding, preprocessing, model artifacts. | Audited & Intact |
| `gis/` | Meteorological station aggregator, spatial risk scoring engine, GeoJSON serializers. | Audited & Verified |
| `templates/` | Jinja2 templates (responsive dark theme, Bootstrap 5, Leaflet containers, Chart.js views, error templates). | Audited & Verified |
| `static/` | Vanilla CSS tokens/utilities and JavaScript controllers (`flood.js`, `map.js`, `routing.js`, `emergency.js`, `admin.js`). | Audited & Verified |
| `tests/` | Pytest test suites across all 8 modules (107 automated tests). | Audited & 100% Passing |

---

## 3. Database Schema Audit

| Table Name | Primary Key | Foreign Keys | Indexed Columns | Record Count / Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `users` | `id` (INT) | None | `email` (Unique) | User accounts, authentication hashes, and roles (`user`, `admin`). |
| `locations` | `id` (INT) | None | `state`, `district` | Named geospatial coordinates and meteorological stations. |
| `prediction_history` | `id` (INT) | `user_id` -> `users.id`, `location_id` -> `locations.id` | `user_id`, `location_id`, `prediction_type` | Audit trail of flood & landslide ML predictions. |
| `emergency_facilities`| `id` (INT) | None | `facility_type`, `latitude`, `longitude`, `external_id` | Verified OpenStreetMap emergency amenities (hospitals, police, shelters). |
| `emergency_requests` | `id` (INT) | `user_id` -> `users.id` | `user_id`, `request_type`, `created_at` | Audit logs of emergency risk checks, facility queries, and evacuation routes. |
| `alembic_version` | `version_num` | None | None | Alembic migration tracking table (`002_phase7_emergency_tables`). |

---

## 4. Machine Learning & Spatial Intelligence Audit

### Flood Model (`ml/flood/model/`)
* **Algorithm:** Random Forest Classifier (`RandomForestClassifier`)
* **Features (9 Real Attributes):** `rainfall_24h`, `rainfall_72h`, `rainfall_7d`, `temperature`, `wind_speed`, `air_pressure`, `elevation`, `latitude`, `longitude`.
* **Preprocessing:** Standard scaling and median imputation fitted on historical rainfall/weather data.
* **Integrity:** Frozen artifacts (`flood_model.pkl`, `flood_preprocessor.pkl`, `evaluation.json`).

### Landslide Model (`ml/landslide/model/`)
* **Algorithm:** Gradient Boosting Classifier (`GradientBoostingClassifier`)
* **Features (9 Real Attributes):** Identical real meteorological and geographical feature schema anchored to NASA Global Landslide Catalog ground-truth events within 50 km.
* **Validated Operational Thresholds:**
  * Advisory threshold: $\ge 0.02$
  * Warning/Action threshold: $\ge 0.10$
* **Integrity:** Frozen artifacts (`landslide_model.pkl`, `landslide_preprocessor.pkl`, `evaluation.json`, `threshold_analysis.json`).

---

## 5. Routing & Safe Corridor Optimization Audit
* **Routing Engine:** OpenStreetMap / Project OSRM driving HTTP service.
* **Corridor Geometry Sampling:** Fixed interval spatial sampling (1.0 km interval) along route polylines.
* **Hazard Association:** Nearest-station spatial lookup within a strict 50 km meteorological radius. Points outside radius are categorized as uncovered without fabricated risk.
* **Cost Optimization Formula:**
  $$\text{Risk Penalty} = \text{Distance (km)} \times 10.0 \times \text{Average Combined Risk}$$
  $$\text{Route Cost} = \text{Distance (km)} + \text{Risk Penalty}$$

---

## 6. Emergency & Admin Modules Audit
* **Emergency Mode:** Real-time geolocation, Overpass QL facility discovery, distance ranking, risk-aware safety ranking, and emergency evacuation route calculation.
* **Admin Dashboard:** Role-based access control (`@admin_required`), real-time MySQL operational metrics, Chart.js analytics, and complete exclusion of password hashes or sensitive user data.

---

## 7. Known Architectural Limitations
1. **Research Prototype Status:** NIDARS is an MCA Major Project decision support tool and not an authorized disaster warning authority.
2. **Station Density:** High-confidence hazard scoring depends on the 50 km coverage grid around the 64 genuine meteorological monitoring stations in North India.
3. **External Network Availability:** Upstream routing (OSRM) and live amenity discovery (Overpass API) require internet connectivity; cached records and fallback error states are implemented to prevent system crashes.
