# NIDARS — GIS Risk Map Foundation (Phase 5)

## 1. Overview & Objectives

The GIS module in NIDARS provides geospatial data processing, spatial hazard risk scoring, and interactive Leaflet map visualization for North India (Jammu & Kashmir, Himachal Pradesh, Uttar Pradesh, and Bihar).

It bridges the trained Machine Learning models (Flood Random Forest and Landslide Gradient Boosting) with spatial observation stations across North India and exposes standardized GeoJSON layers to the web frontend.

---

## 2. Spatial Data Sources Used

NIDARS uses **only legitimate, verified spatial information** available in the project data sources:

1. **North India Hydrometeorological Observation Network**:
   - Total stations: **64 real observation stations**
   - States covered:
     - Uttar Pradesh (`UP`): 31 stations
     - Bihar (`BR`): 16 stations
     - Himachal Pradesh (`HP`): 11 stations
     - Jammu & Kashmir (`JK`): 6 stations
   - Geospatial variables:
     - Real Latitude: $22.8167^{\circ}\text{N}$ to $34.0833^{\circ}\text{N}$
     - Real Longitude: $74.4000^{\circ}\text{E}$ to $87.4667^{\circ}\text{E}$
     - Real Elevation: $0\text{ m}$ to $2,652\text{ m}$ above sea level
     - State, District, and Station identifiers
     - Hydrometeorological observations: 24h, 72h, and 7d rolling precipitation, temperature, wind speed, and air pressure.

2. **NASA Global Landslide Catalog (GLC)**:
   - Ground truth coordinates of historical landslide events across India and the Himalayan belt ($546$ Himalayan events).

### Scientific Integrity & Non-Fabrication Policy
- **NO synthetic GIS rasters**: We do NOT fabricate slope, aspect, NDVI, or satellite soil moisture layers.
- **NO fake road closures**: We do NOT create synthetic traffic or route obstruction polygons.
- **NO fake flood inundation polygons**: Points are mapped to real physical monitoring stations.

---

## 3. GIS Architecture & Modules

```
gis/
├── __init__.py           # Package exports for core risk functions
├── processing.py         # Station aggregation & ML prediction scoring engine
├── risk_zones.py         # Risk formulas, classification bands & RFC 7946 GeoJSON builder
├── geojson/              # Directory for GeoJSON layer artifacts
│   └── .gitkeep
└── README.md             # Technical documentation & research disclaimer
```

Supporting Services & Routes:
- `services/landslide_service.py`: Landslide model application service.
- `services/gis_service.py`: Spatial risk query orchestration.
- `routes/gis.py`: API endpoint `GET /api/gis/risk`.
- `templates/map.html`: Responsive Leaflet UI with hazard selector, state filter, risk filter, and legend.
- `static/js/map.js`: Leaflet map client script.

---

## 4. Mathematical Risk Representation

The spatial risk engine supports standalone hazard probabilities as well as a joint combined risk score:

$$\text{combined\_risk} = \frac{w_{\text{flood}} \cdot P(\text{flood}) + w_{\text{landslide}} \cdot P(\text{landslide})}{w_{\text{flood}} + w_{\text{landslide}}}$$

### Configurable Weights
- Default Flood Weight ($w_{\text{flood}}$): **`0.50`**
- Default Landslide Weight ($w_{\text{landslide}}$): **`0.50`**
- Configurable via `config.py` (`Config.GIS_FLOOD_WEIGHT`, `Config.GIS_LANDSLIDE_WEIGHT`) and API query parameters.
- Both individual model probabilities ($P(\text{flood})$ and $P(\text{landslide})$) are preserved separately in the GeoJSON feature properties.

---

## 5. Risk Classification & Thresholds

### Landslide Risk (Phase 4.1 Validated Thresholds)
Adheres strictly to the optimal operating thresholds determined in Phase 4.1 ROC/PR analysis:
- **`LOW`**: $P(\text{landslide}) < 0.02$ (Below advisory threshold)
- **`MODERATE`**: $0.02 \le P(\text{landslide}) < 0.10$ (Advisory threshold reached)
- **`HIGH`**: $0.10 \le P(\text{landslide}) < 0.25$ (Action/Warning threshold reached)
- **`CRITICAL`**: $P(\text{landslide}) \ge 0.25$

### Flood Risk (Project-defined UI Bands)
- **`LOW`**: $P(\text{flood}) < 0.25$
- **`MODERATE`**: $0.25 \le P(\text{flood}) < 0.50$
- **`HIGH`**: $0.50 \le P(\text{flood}) < 0.75$
- **`CRITICAL`**: $P(\text{flood}) \ge 0.75$

### Combined Risk (Project-defined UI Bands)
- **`LOW`**: $\text{combined\_risk} < 0.25$
- **`MODERATE`**: $0.25 \le \text{combined\_risk} < 0.50$
- **`HIGH`**: $0.50 \le \text{combined\_risk} < 0.75$
- **`CRITICAL`**: $\text{combined\_risk} \ge 0.75$

---

## 6. API Reference

### `GET /api/gis/risk`
Exposes spatial disaster risk data in RFC 7946 GeoJSON `FeatureCollection` format.

**Authentication**: Required (`@login_required`). Unauthenticated requests return `401 Unauthorized`.

**Query Parameters**:
| Parameter | Type | Default | Description |
|---|---|---|---|
| `hazard` | `string` | `combined` | Hazard mode: `combined`, `flood`, or `landslide` |
| `state` | `string` | `None` | Filter by state code or name (`JK`, `HP`, `UP`, `BR`) |
| `district` | `string` | `None` | Filter by district name |
| `limit` | `integer` | `None` | Max number of station points to return |
| `flood_weight` | `float` | `0.50` | Custom flood weighting factor |
| `landslide_weight` | `float` | `0.50` | Custom landslide weighting factor |

**Sample GeoJSON Feature Output**:
```json
{
  "type": "Feature",
  "id": 1,
  "geometry": {
    "type": "Point",
    "coordinates": [74.4, 34.05]
  },
  "properties": {
    "station": "Gulmarg",
    "district": "Baramulla",
    "state": "JK",
    "state_name": "Jammu & Kashmir",
    "elevation_m": 2652.0,
    "observation_date": "2025-02-10",
    "flood_probability": 0.0000,
    "landslide_probability": 0.0000,
    "combined_risk": 0.0000,
    "risk_level": "LOW",
    "risk_score": 0.0000,
    "hazard": "combined",
    "rainfall_24h": 0.1,
    "rainfall_72h": 0.1,
    "rainfall_7d": 0.1,
    "temperature": -4.2,
    "wind_speed": 4.1,
    "air_pressure": 750.0
  }
}
```

---

## 7. Leaflet Frontend Features

- **OpenStreetMap Basemap**: Full pan, zoom, and spatial context over North India.
- **Interactive Hazard Selector**: Seamless switching between Combined Risk, Flood Risk, and Landslide Risk.
- **Multi-Level Risk Filtering**: Filter markers by All, Low, Moderate, High, Critical with real-time UI counters.
- **State Filtering & Live Search**: Instant filtering by state (`JK`, `HP`, `UP`, `BR`) or station/district name query.
- **Color-Coded Circle Markers**:
  - Green (`#22c55e`): Low Risk
  - Amber / Yellow (`#f59e0b`): Moderate Risk
  - Coral Red (`#ef4444`): High Risk
  - Deep Purple (`#a855f7`): Critical Risk
- **Interactive Popup Cards**: Shows station name, district, state, elevation, probability breakdown bars, meteorological observations, and coordinates.
- **Dynamic Legend**: Explains current hazard mode, colors, and thresholds.

---

## 8. Limitations & Future Scope

1. **Station Spatial Sparsity**: Station spacing in mountainous regions (HP, JK) averages 30–50 km.
2. **Safe Route Optimization**: Route pathfinding and nearest-facility emergency routing will be implemented in future phases.

---

## 9. Important Disclaimer

> **ACADEMIC & RESEARCH PROTOTYPE DISCLAIMER**
>
> NIDARS is a Master of Computer Applications (MCA) major project prototype. The risk scores, hazard classifications, and spatial mappings are research-driven estimates and **NOT** an official government early-warning system.
>
> For official, legally authoritative weather warnings, flood advisories, and landslide alerts, consult:
> - **India Meteorological Department (IMD)**
> - **National Disaster Management Authority (NDMA)**
> - **Central Water Commission (CWC)**
> - **Geological Survey of India (GSI)**
