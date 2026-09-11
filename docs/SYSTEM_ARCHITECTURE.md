# NIDARS — System Architecture Document

## 1. High-Level Architectural Flow

```text
                                [ User / Client ]
                                        │
                                        ▼
                            [ Nginx Reverse Proxy / WSGI ]
                                        │
                                        ▼
                             [ Flask Application Core ]
                                        │
                 ┌──────────────────────┼──────────────────────┐
                 ▼                      ▼                      ▼
        [ Authentication & RBAC ]  [ Route Controllers ]   [ Jinja2 & Static Assets ]
        - Flask-Login              - main_bp / api_bp       - Bootstrap 5 Dark UI
        - Password Hashing (Werkzeug) auth_bp               - Leaflet.js Maps
        - Role Check (@admin_required)                       - Chart.js Dashboards
                 │                      │                      │
                 ▼                      ▼                      ▼
        [ MySQL 8.0 Storage ]   [ Business Logic Services ]    [ Interactive Views ]
        - users                 - weather_service              - GIS Hazard Map
        - locations             - flood_service                - Route Optimizer
        - prediction_history    - landslide_service            - Emergency Mode
        - emergency_facilities  - gis_service                  - Admin Control Center
        - emergency_requests    - route_risk_service
                                - emergency_service
                                        │
                        ┌───────────────┴───────────────┐
                        ▼                               ▼
            [ Machine Learning Pipelines ]   [ External Geospatial APIs ]
            - Flood: Random Forest           - OSRM Routing Engine
            - Landslide: Gradient Boosting   - OpenStreetMap / Overpass QL
            - 9 Real Feature Preprocessors
```

---

## 2. Component Descriptions

### A. Presentation Layer (Frontend)
* **Design Philosophy:** Responsive dark-mode user interface using Bootstrap 5, curated HSL color schemes, dynamic micro-interactions, and accessible typography.
* **Map Visualizations:** Leaflet.js with OpenStreetMap standard cartographic tiles, rendering GeoJSON hazard layers, colored facility icons, and route polylines.
* **Analytical Dashboards:** Chart.js 4.4 rendering Doughnut, Bar, and Pie charts dynamically populated from backend REST endpoints.

### B. Application & Routing Layer (Backend)
* **Framework:** Flask with application factory pattern (`create_app`) supporting pluggable environments (`DevelopmentConfig`, `ProductionConfig`, `TestConfig`).
* **REST API Layer:** Clean, version-ready JSON endpoints (`/api/*`) enforcing input boundary checks, authentication tokens, and standardized status codes.
* **Security & Session Layer:** Session cookies configured with `HttpOnly` and `SameSite=Lax`. CSRF protection enabled across all state-modifying requests.

### C. Analytical & Machine Learning Layer
* **Spatial Hazard Engine:** Aggregates 64 genuine meteorological monitoring stations across Jammu & Kashmir, Himachal Pradesh, Uttar Pradesh, and Bihar.
* **Flood ML Engine:** Preprocessed Random Forest model estimating precipitation-driven inundation probabilities.
* **Landslide ML Engine:** Preprocessed Gradient Boosting model trained on NASA Global Landslide Catalog occurrences.
* **Corridor Risk Analyzer:** Discretizes road geometries into 1.0 km interval coordinates, performs spatial station lookups within a strict 50 km radius, and evaluates route hazard penalties.

### D. Data & Storage Layer
* **Database Engine:** MySQL 8.0 with SQLAlchemy ORM and Alembic migration control.
* **Cache Architecture:** Local database caching of verified OpenStreetMap amenities to prevent external service downtime dependencies.

---

## 3. Emergency & Admin Data Flow

### Emergency Mode Flow:
1. User supplies coordinates via Browser Geolocation or manual numeric input.
2. `services/emergency_service.py` validates coordinates ($-90 \le \text{lat} \le 90$, $-180 \le \text{lon} \le 180$).
3. Spatial risk engine calculates localized flood and landslide probabilities from nearest station.
4. Overpass QL queries authentic OpenStreetMap amenities (hospitals, police, shelters) within the chosen radius ($5\text{--}50\text{ km}$).
5. Facilities are ranked by distance (nearest) and disaster risk cost (safest):
   $$\text{Safety Cost} = \text{Distance} \times (1 + 2.0 \times \text{Combined Risk})$$
6. User triggers evacuation route -> Phase 6 OSRM routing calculates driving path with disaster penalty exposure metrics.
7. Operational metrics logged to `emergency_requests` table without storing sensitive PII.

### Admin Dashboard Flow:
1. Authenticated user requests `/admin` or `/api/admin/*`.
2. `@admin_required` decorator validates `current_user.is_admin()`. If non-admin, aborts with HTTP 403 Forbidden.
3. System aggregates live MySQL metrics (total users, prediction counts, risk distribution, emergency logs, cached facilities).
4. Data serialized to JSON with passwords, password hashes, and sensitive tokens strictly excluded.
5. Chart.js visualizes live metrics in the browser.
