# NIDARS — GIS & Spatial Hazard Methodology

**Geospatial Standards:** RFC 7946 GeoJSON, WGS84 (EPSG:4326), Leaflet.js  
**Spatial Monitoring Grid:** 64 Meteorological Stations across North India  
**Routing Engine:** OSRM (Open Source Routing Machine)

---

## 1. Meteorological Station Spatial Grid

NIDARS establishes a genuine 64-station meteorological monitoring network spanning 4 critical northern states:

| State | Stations | Example Major Stations |
| :--- | :--- | :--- |
| **Jammu & Kashmir (JK)** | 14 | Srinagar, Jammu, Anantnag, Baramulla, Leh, Kargil |
| **Himachal Pradesh (HP)** | 12 | Shimla, Manali, Dharamshala, Kullu, Mandi, Solan |
| **Uttar Pradesh (UP)** | 24 | Lucknow, Varanasi, Prayagraj, Gorakhpur, Kanpur, Agra |
| **Bihar (BR)** | 14 | Patna, Muzaffarpur, Gaya, Bhagalpur, Darbhanga, Purnia |

---

## 2. Spatial Risk Scoring & Classification

### A. Combined Risk Formulation
The overall disaster risk score at any spatial station combines flood and landslide probabilities using user-configurable or default hazard weights:

$$\text{Combined Risk} = (w_{\text{flood}} \times P_{\text{flood}}) + (w_{\text{landslide}} \times P_{\text{landslide}})$$

where $w_{\text{flood}} + w_{\text{landslide}} = 1.0$ (Default: $w_{\text{flood}} = 0.50$, $w_{\text{landslide}} = 0.50$).

### B. Hazard Classification Bands
| Risk Level | Combined Risk Score ($R$) | Visual Marker Color | Operational Advisory |
| :--- | :--- | :--- | :--- |
| **LOW** | $R < 0.25$ | Green (`#198754`) | Normal driving conditions. |
| **MODERATE** | $0.25 \le R < 0.50$ | Yellow (`#ffc107`) | Elevated caution advised along mountain passes. |
| **HIGH** | $0.50 \le R < 0.75$ | Orange (`#fd7e14`) | High hazard exposure. Consider alternate routes. |
| **CRITICAL** | $R \ge 0.75$ | Red (`#dc3545`) | Severe hazard danger. Evacuation / avoidance recommended. |

---

## 3. Corridor Discretization & Route Risk Analysis

### A. Polyline Sampling
Driving routes retrieved from OSRM are represented as continuous GeoJSON `LineString` geometries. NIDARS samples the polyline at 1.0 km intervals to create discrete evaluation waypoints:

$$\Delta s = 1.0\text{ km}$$

### B. Spatial Association Rule
For every waypoint $p_i = (\text{lat}_i, \text{lon}_i)$, NIDARS computes the Haversine great-circle distance to all 64 stations:

$$d(p_i, s_j) = 2 R \arcsin \sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos \phi_1 \cos \phi_2 \sin^2\left(\frac{\Delta \lambda}{2}\right)}$$

* **Within 50.0 km:** Point $p_i$ is mapped to the nearest station's live hazard risk.
* **Beyond 50.0 km:** Point $p_i$ is categorized as **Uncovered** ($P = 0.0$ penalty, confidence coverage adjusted).

### C. Route Cost Optimization Formula
The total disaster-aware route cost penalizes hazardous segments while preserving total driving efficiency:

$$\text{Risk Penalty} = \text{Distance (km)} \times 10.0 \times \text{Average Combined Risk}$$
$$\text{Route Cost} = \text{Distance (km)} + \text{Risk Penalty}$$

The route minimizing $\text{Route Cost}$ is labeled as **RECOMMENDED**.
