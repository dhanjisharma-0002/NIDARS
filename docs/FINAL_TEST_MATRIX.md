# NIDARS — Final Test Matrix & Verification Results

All test cases listed below have been verified through automated regression tests (`pytest`) and live HTTP end-to-end testing against MySQL (`nidars_db`).

---

## Complete Test Matrix

| Module | Test Case | Test Description | Expected Behavior | Actual Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Auth** | `TC-AUTH-01` | Register new user | Creates account, hashes password | Account created in `users` | **PASS** |
| **Auth** | `TC-AUTH-02` | Valid login | Issues session cookie, redirects | HTTP 302 -> `/dashboard` | **PASS** |
| **Auth** | `TC-AUTH-03` | Invalid login credentials | Generic authentication error | Error displayed, no leak | **PASS** |
| **Auth** | `TC-AUTH-04` | Unauthenticated protected access | Redirects to login with `next` param | HTTP 302 -> `/login?next=...` | **PASS** |
| **Auth** | `TC-AUTH-05` | Unauthenticated API request | Rejects API query | HTTP 401 Unauthorized | **PASS** |
| **Flood** | `TC-FLD-01` | Valid flood prediction input | Runs Random Forest ML inference | Returns probability & risk level | **PASS** |
| **Flood** | `TC-FLD-02` | Missing meteorological feature | Schema validation triggers | HTTP 400 with missing field name | **PASS** |
| **Flood** | `TC-FLD-03` | Out-of-bounds numeric input | Validates physical bounds | HTTP 400 Bad Request | **PASS** |
| **Flood** | `TC-FLD-04` | Prediction history logging | Successful run logs to MySQL | Record created in `prediction_history` | **PASS** |
| **Landslide**| `TC-LND-01` | Feature schema validation | Validates 9 real features | Rejects ungrounded GIS attributes | **PASS** |
| **Landslide**| `TC-LND-02` | Gradient Boosting inference | Runs calibrated model prediction | Returns risk probability | **PASS** |
| **Landslide**| `TC-LND-03` | Threshold calibration | Verifies advisory ($0.02$) & action ($0.10$) | Risk bands correctly mapped | **PASS** |
| **GIS** | `TC-GIS-01` | Spatial risk GeoJSON API | Queries 64 stations | Returns RFC 7946 GeoJSON | **PASS** |
| **GIS** | `TC-GIS-02` | State filter query | Filters stations by state (`HP`, `UP`) | Returns subset FeatureCollection | **PASS** |
| **GIS** | `TC-GIS-03` | Hazard mode switching | Supports flood, landslide, combined | Custom weights applied cleanly | **PASS** |
| **Routing** | `TC-RTE-01` | Valid driving route query | OSRM road route calculated | Driving route polyline returned | **PASS** |
| **Routing** | `TC-RTE-02` | Discretization & sampling | Samples line at 1.0 km intervals | Generates sampled waypoints | **PASS** |
| **Routing** | `TC-RTE-03` | Station risk association | Associates within 50 km radius | Computes corridor hazard penalty | **PASS** |
| **Routing** | `TC-RTE-04` | Route cost optimization | Evaluates Distance + Risk Penalty | Identifies Recommended route | **PASS** |
| **Routing** | `TC-RTE-05` | Upstream OSRM failure | Simulates network error / timeout | Returns HTTP 502 gracefully | **PASS** |
| **Emergency**| `TC-EMG-01` | Geolocation / coordinate input | Validates decimal coordinates | Accepts valid lat/lon pairs | **PASS** |
| **Emergency**| `TC-EMG-02` | Invalid coordinates input | Out-of-bounds latitude/longitude | HTTP 400 Bad Request | **PASS** |
| **Emergency**| `TC-EMG-03` | Live OSM facility discovery | Overpass QL query | Returns verified amenities | **PASS** |
| **Emergency**| `TC-EMG-04` | Nearest vs Safest ranking | Haversine vs Risk Exposure Cost | Evaluates both metrics | **PASS** |
| **Emergency**| `TC-EMG-05` | Emergency safe evacuation | OSRM route to chosen facility | Generates route with hazard cost | **PASS** |
| **Emergency**| `TC-EMG-06` | Emergency request audit log | Logs search/routing activity | Record created in `emergency_requests` | **PASS** |
| **Admin** | `TC-ADM-01` | Non-admin user access | Regular user accesses `/admin` | HTTP 403 Forbidden | **PASS** |
| **Admin** | `TC-ADM-02` | Non-admin API access | Regular user calls `/api/admin/*` | HTTP 403 Forbidden | **PASS** |
| **Admin** | `TC-ADM-03` | Admin role access | Admin accesses `/admin` | HTTP 200 OK | **PASS** |
| **Admin** | `TC-ADM-04` | Operational stats API | Aggregates DB counts & risk metrics | Returns verified metrics JSON | **PASS** |
| **Admin** | `TC-ADM-05` | Sensitive data protection | Checks all API payloads | Zero password hashes exposed | **PASS** |
