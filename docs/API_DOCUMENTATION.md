# NIDARS — REST API Documentation

All REST API endpoints return JSON. Endpoints requiring authentication return `HTTP 401 Unauthorized` if unauthenticated. Admin endpoints return `HTTP 403 Forbidden` if accessed by non-admin users.

---

## 1. Authentication Endpoints

### `POST /login`
Authenticates user sessions.
* **Headers:** `Content-Type: application/x-www-form-urlencoded`
* **Parameters:** `email` (string), `password` (string), `csrf_token` (string)
* **Response:** Redirect to next URL or HTTP 200/400.

### `POST /register`
Registers a new standard user account.
* **Parameters:** `name` (string), `email` (string), `password` (string), `password_confirm` (string), `csrf_token` (string)
* **Response:** Redirect to login or HTTP 400 with validation errors.

### `GET /logout`
Terminates user session.
* **Response:** Redirect to home page.

---

## 2. Machine Learning Prediction Endpoints

### `POST /api/predict/flood`
Predicts localized flood risk from meteorological parameters.
* **Auth:** Required (`@login_required`)
* **Request Body:**
```json
{
  "rainfall_24h": 120.0,
  "rainfall_72h": 210.0,
  "rainfall_7d": 350.0,
  "temperature": 26.0,
  "wind_speed": 4.5,
  "air_pressure": 1008.2,
  "elevation": 450.0,
  "latitude": 28.6139,
  "longitude": 77.2090
}
```
* **Success Response (HTTP 200):**
```json
{
  "success": true,
  "probability": 0.782,
  "risk_level": "HIGH",
  "risk_class": 1,
  "confidence": "high",
  "disclaimer": "Prototype decision support only. Official government warnings remain authoritative."
}
```
* **Error Response (HTTP 400):**
```json
{
  "success": false,
  "errors": ["Missing required field 'rainfall_24h'."],
  "prediction": null
}
```

---

## 3. GIS & Spatial Hazard Endpoints

### `GET /api/gis/risk`
Returns a GeoJSON FeatureCollection of meteorological stations with live model-predicted hazard scores.
* **Auth:** Required (`@login_required`)
* **Query Parameters:**
  * `hazard`: `'flood'`, `'landslide'`, or `'combined'` (default: `'combined'`)
  * `state`: Optional filter (`'JK'`, `'HP'`, `'UP'`, `'BR'`)
  * `limit`: Optional maximum station limit
  * `flood_weight`: Float (default 0.50)
  * `landslide_weight`: Float (default 0.50)
* **Success Response (HTTP 200):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [77.1734, 31.1048]
      },
      "properties": {
        "station_name": "Shimla",
        "state": "HP",
        "district": "Shimla",
        "flood_probability": 0.05,
        "landslide_probability": 0.001,
        "combined_risk": 0.0255,
        "risk_level": "LOW"
      }
    }
  ]
}
```

---

## 4. Safe Route Optimization Endpoints

### `GET /api/routing/route`
Finds driving routes between start and end coordinates, evaluates spatial hazard exposure along the corridor, and returns risk-aware safety metrics.
* **Auth:** Required (`@login_required`)
* **Query Parameters:**
  * `start_lat`: Origin latitude (float, $[-90, 90]$)
  * `start_lon`: Origin longitude (float, $[-180, 180]$)
  * `end_lat`: Destination latitude (float, $[-90, 90]$)
  * `end_lon`: Destination longitude (float, $[-180, 180]$)
  * `flood_weight`: Optional float (default 0.50)
  * `landslide_weight`: Optional float (default 0.50)
* **Success Response (HTTP 200):**
```json
{
  "success": true,
  "origin": {"latitude": 28.6139, "longitude": 77.2090},
  "destination": {"latitude": 31.1048, "longitude": 77.1734},
  "routes": [
    {
      "route_index": 0,
      "summary": "NH 44",
      "geometry": {"type": "LineString", "coordinates": [[77.2090, 28.6139], [77.1734, 31.1048]]},
      "metrics": {
        "distance_km": 348.5,
        "duration_minutes": 420.0,
        "average_combined_risk": 0.12,
        "risk_coverage_percent": 88.5,
        "route_cost": 390.32
      },
      "tags": ["SHORTEST", "RECOMMENDED"]
    }
  ],
  "recommended_route_index": 0,
  "recommendation_note": "Recommended based on disaster-aware cost optimization."
}
```

---

## 5. Emergency Mode Endpoints

### `GET /api/emergency/risk`
Returns localized disaster risk for given coordinates.
* **Auth:** Required (`@login_required`)
* **Query Parameters:** `lat` (float), `lon` (float)
* **Success Response (HTTP 200):**
```json
{
  "success": true,
  "coordinates": {"latitude": 31.1048, "longitude": 77.1734},
  "risk_status": {
    "is_covered": true,
    "nearest_station": "Shimla",
    "station_distance_km": 0.5,
    "flood_probability": 0.05,
    "landslide_probability": 0.001,
    "combined_risk": 0.0255,
    "risk_level": "LOW"
  }
}
```

### `GET /api/emergency/facilities`
Discovers verified OpenStreetMap amenities within radius.
* **Auth:** Required (`@login_required`)
* **Query Parameters:** `lat`, `lon`, `radius_km` (default 15.0), `type` (`'hospital'`, `'police'`, `'shelter'`, `'all'`)
* **Success Response (HTTP 200):**
```json
{
  "success": true,
  "total_found": 12,
  "source": "OpenStreetMap (Live)",
  "facilities": [
    {
      "name": "IGMC Hospital",
      "facility_type": "hospital",
      "latitude": 31.108,
      "longitude": 77.175,
      "distance_km": 1.2,
      "address": "Circular Road",
      "phone": "+91-177-2804251",
      "opening_hours": "24/7",
      "source": "OpenStreetMap"
    }
  ]
}
```

### `GET /api/emergency/nearest`
Returns nearest facility by distance alongside risk-aware safest recommendation.
* **Auth:** Required (`@login_required`)
* **Query Parameters:** `lat`, `lon`, `type`, `radius_km`
* **Success Response (HTTP 200):**
```json
{
  "success": true,
  "nearest_by_distance": {"name": "Local Clinic", "distance_km": 1.2},
  "recommended_safest": {"name": "Regional Hospital", "distance_km": 1.8, "safety_cost": 1.84}
}
```

### `GET /api/emergency/route`
Calculates evacuation route to chosen emergency facility.
* **Auth:** Required (`@login_required`)
* **Query Parameters:** `start_lat`, `start_lon`, `facility_lat`, `facility_lon`, `facility_name`, `facility_type`
* **Success Response (HTTP 200):**
```json
{
  "success": true,
  "routes": [...],
  "recommended_route_index": 0,
  "recommendation_note": "Direct road corridor with minimum disaster risk exposure."
}
```

---

## 6. Admin REST Endpoints

### `GET /api/admin/stats`
Aggregates operational metrics across users, predictions, and emergency records.
* **Auth:** Admin Role Required (`@admin_required`)
* **Success Response (HTTP 200):**
```json
{
  "success": true,
  "metrics": {
    "total_users": 5,
    "total_predictions": 12,
    "flood_predictions": 8,
    "landslide_predictions": 4,
    "total_emergency_requests": 15,
    "total_facilities": 56,
    "facilities_by_type": {"hospitals": 32, "police": 14, "shelters": 10},
    "risk_distribution": {"LOW": 8, "MODERATE": 3, "HIGH": 1, "CRITICAL": 0}
  }
}
```

### `GET /api/admin/predictions`
Returns recent prediction history records without exposing password hashes.
* **Auth:** Admin Role Required (`@admin_required`)
* **Query Parameters:** `limit` (int, default 20)
* **Success Response (HTTP 200):** Returns array of sanitized prediction history objects.

### `GET /api/admin/emergency`
Returns recent emergency search and evacuation query logs.
* **Auth:** Admin Role Required (`@admin_required`)
* **Query Parameters:** `limit` (int, default 20)
* **Success Response (HTTP 200):** Returns array of emergency request records.

### `GET /api/admin/facilities`
Returns list of cached OpenStreetMap facilities stored in MySQL.
* **Auth:** Admin Role Required (`@admin_required`)
* **Query Parameters:** `limit` (int, default 50)
* **Success Response (HTTP 200):** Returns array of cached facility records.
