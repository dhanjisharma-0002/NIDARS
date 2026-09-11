# NIDARS

**North India Disaster Awareness & Route System**  
*AI-Based North India Flood and Landslide Prediction with Disaster-Aware Safe Route Optimization Using Machine Learning and GIS*

---

## 🚨 Disclaimer & Advisory
> **ACADEMIC RESEARCH PROTOTYPE DISCLAIMER:**  
> NIDARS is developed as an MCA Major Project and research decision-support prototype. Hazard probabilities, spatial risk maps, nearest/safest facility rankings, and evacuation route optimizations are experimental computational estimates.  
> **For active emergency situations, life safety operations, and evacuation directives, always strictly follow official government alerts, National Disaster Response Force (NDRF), State Disaster Management Authorities (SDMA), District Emergency Operation Centers (DEOC), and local law enforcement.**

---

## 📖 Project Overview
The Himalayan and riverine terrain of North India—encompassing Jammu & Kashmir, Himachal Pradesh, Uttar Pradesh, and Bihar—faces recurring seasonal hazards from monsoon-induced flash floods, riverine flooding, and slope instability landslides. 

**NIDARS** is an end-to-end disaster intelligence and evacuation routing platform. It couples real-time meteorological observations, trained machine learning classifiers, spatial GIS hazard modeling across 64 North Indian meteorological stations, live OpenStreetMap (OSM) amenity discovery, and OSRM (Open Source Routing Machine) network optimization to compute risk-penalized, disaster-aware travel corridors and emergency evacuation routes.

---

## 🎯 Problem Statement
Traditional navigation systems (such as standard GPS or turn-by-turn routing engines) optimize travel exclusively for the shortest distance or travel duration. During extreme weather events, this frequently leads travelers, emergency responders, and evacuees directly through flooded river basins, inundated lowlands, or active landslide hazard zones. 

Furthermore, existing disaster warnings are frequently disseminated at broad administrative scales (state/district) without localized spatial resolution, and lack actionable integration with ground transportation networks and critical emergency amenities (hospitals, police stations, evacuation shelters).

---

## 🎯 Objectives
1. **Accurate Hazard Modeling:** Implement machine learning pipelines to evaluate localized flood and landslide hazards using genuine meteorological and geophysical features.
2. **Spatial Risk Mapping:** Construct a GIS hazard foundation over 64 North India stations to compute multi-hazard risk indices (Low, Moderate, High, Severe).
3. **Disaster-Aware Navigation:** Formulate an intelligent path-cost algorithm that incorporates spatial hazard exposure into road network routing via OSRM.
4. **Emergency Decision Support:** Enable rapid GPS-based discovery of verified OSM emergency amenities and compute safest vs. nearest evacuation routes.
5. **Administrative Governance:** Provide role-protected analytics, prediction auditing, and system monitoring for emergency management administrators.

---

## ✨ Key Features
- **Role-Based Access Control:** Secure user registration, authentication, session handling, and admin privilege gates (`User` vs. `Admin`).
- **Interactive Multi-Hazard GIS:** Leaflet.js map visualizing 64 meteorological stations across J&K, HP, UP, and Bihar with spatial buffer overlays, risk level badges, and configurable hazard weightings (Flood vs. Landslide).
- **Flood Risk Prediction:** Standalone machine learning risk scoring based on localized 24h, 72h, and 7-day cumulative rainfall, temperature, pressure, wind, and elevation.
- **Landslide Probability Analysis:** Calibrated Gradient Boosting probability scoring trained on verified NASA Global Landslide Catalog occurrences.
- **Safe Route Optimization:** Multi-alternative driving route evaluation comparing standard shortest routes against disaster-minimized safe routes using waypoint hazard sampling and route risk penalties.
- **Emergency Evacuation Mode:** One-click GPS location detection, real-time Overpass OSM querying for genuine emergency facilities (hospitals, police stations, shelters), nearest vs. safest ranking, and direct evacuation routing.
- **Admin Analytics Dashboard:** System KPI summaries, prediction volume breakdowns, hazard level distributions, and real-time Chart.js visual analytics.

---

## 🏗️ System Architecture

```text
                                  +---------------------------------------+
                                  |       Web Browser (Bootstrap 5)       |
                                  |   Leaflet Maps & Chart.js Analytics   |
                                  +-------------------+-------------------+
                                                      |
                                                      | HTTP / REST API
                                                      v
                                  +---------------------------------------+
                                  |         Flask Web Application         |
                                  |   Auth / Session / Error Handlers     |
                                  +-------------------+-------------------+
                                                      |
                    +---------------------------------+---------------------------------+
                    |                                 |                                 |
                    v                                 v                                 v
+-----------------------------------+ +-------------------------------+ +-------------------------------+
|       ML Prediction Engine        | |          GIS Engine           | |        Routing Engine         |
|  - Flood ML (Random Forest)       | |  - 64 Met Stations Grid       | |  - OSRM Driving Network       |
|  - Landslide ML (Grad. Boosting)  | |  - Spatial Risk Interpolation | |  - Polyline Hazard Sampling   |
|  - Preprocessing & Scalers        | |  - Multi-Hazard Scoring       | |  - Route Penalty Scoring      |
+-----------------+-----------------+ +---------------+---------------+ +---------------+---------------+
                  |                                   |                                 |
                  +-----------------------------------+---------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |         Emergency & OSM Service       |
                                  |  - Overpass API Live Querying         |
                                  |  - Amenity Distance & Safety Ranking  |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |        MySQL Relational Storage       |
                                  |  - Users & Roles                      |
                                  |  - Prediction History                 |
                                  |  - Cached Facilities & Audit Logs     |
                                  +---------------------------------------+
```

---

## 🛠️ Technology Stack
- **Backend Framework:** Python 3.14, Flask, Flask-SQLAlchemy, Flask-Login, Flask-Migrate (Alembic)
- **Database:** MySQL 8.0+ (`nidars_db`)
- **Machine Learning:** scikit-learn, NumPy, Pandas, Joblib
- **Geospatial & GIS:** Leaflet.js, GeoJSON, OpenStreetMap, Overpass QL API, OSRM (Open Source Routing Machine)
- **Frontend / UI:** HTML5, Vanilla CSS3 (Custom Dark Glassmorphism), Bootstrap 5.3, Chart.js 4.4, Feather/FontAwesome Icons
- **WSGI / Production:** Gunicorn / Waitress WSGI server

---

## 🤖 Machine Learning
NIDARS deploys two specialized, frozen machine learning models trained on strictly validated datasets with a unified 9-feature input schema:

$$\text{Features} = [\text{rainfall\_24h}, \text{rainfall\_72h}, \text{rainfall\_7d}, \text{temperature}, \text{wind\_speed}, \text{air\_pressure}, \text{elevation}, \text{latitude}, \text{longitude}]$$

### 1. Flood Risk Classifier
- **Model:** Random Forest Classifier (`ml/flood/model/flood_model.pkl`)
- **Training Source:** North India Weather Dataset (153,873 rows) labeled against IIT Delhi HydroSense Flood Inventory and IMD rainfall standards.
- **Key Metrics:**
  - **Accuracy:** 98.41%
  - **ROC-AUC:** 0.9972
  - **Recall:** 94.61%
  - **Precision:** 87.89%
  - **F1 Score:** 91.12%

### 2. Landslide Hazard Classifier
- **Model:** Gradient Boosting Classifier (`ml/landslide/model/landslide_model.pkl`)
- **Training Source:** NASA Global Landslide Catalog (COOLR) events matched to North India stations within a 50 km spatial radius and matching calendar dates.
- **Key Metrics & Threshold Calibration:**
  - **ROC-AUC:** 0.9057 | **PR-AUC:** 0.0112
  - **Imbalance Ratio:** 1:2,528 (56 positive events among 141,573 non-event observations)
  - **Operational Calibrated Threshold:** $\tau = 0.02$ (Advisory), $\tau = 0.10$ (Warning)

---

## 🗺️ GIS & Spatial Risk Grid
NIDARS models geographic risk across 64 authentic meteorological stations across 4 North Indian states:
- **Jammu & Kashmir:** Srinagar, Gulmarg, Pahalgam, Jammu, Katra, Banihal, Batote, Bhaderwah, Qazigund, Kupwara, Kukernag, Leh, Kargil
- **Himachal Pradesh:** Shimla, Manali, Dharamshala, Kullu, Solan, Mandi, Bilaspur, Kangra, Chamba, Nahan, Kalpa, Una, Keylong, Dalhousie, Sundernagar
- **Uttar Pradesh:** Lucknow, Kanpur, Varanasi, Prayagraj, Agra, Meerut, Gorakhpur, Bareilly, Aligarh, Moradabad, Jhansi, Ayodhya, Mathura, Saharanpur, Muzaffarnagar, Firozabad, Noida, Ghaziabad
- **Bihar:** Patna, Gaya, Bhagalpur, Muzaffarpur, Purnia, Darbhanga, Bihar Sharif, Arrah, Begusarai, Katihar, Munger, Chhapra, Saharsa, Sasaram, Hajipur, Dehri, Bettiah, Motihari

### Multi-Hazard Calculation
$$\text{Combined Risk} = (w_f \times P_{\text{flood}}) + (w_l \times P_{\text{landslide}})$$
- **Low Risk:** $< 0.25$ (Green)
- **Moderate Risk:** $0.25 - 0.50$ (Yellow)
- **High Risk:** $0.50 - 0.75$ (Orange)
- **Severe Risk:** $\ge 0.75$ (Red)

---

## 🛣️ Safe Route Optimization
Standard routing optimizes strictly for distance. NIDARS implements a risk-penalized cost function across candidate driving paths:

$$\text{Risk Penalty} = \text{Distance (km)} \times \alpha \times \text{Average Combined Risk}$$
$$\text{Route Cost} = \text{Distance (km)} + \text{Risk Penalty}$$

Where $\alpha = 2.0$ (penalty factor). Along the polyline trajectory, waypoints are sampled every 5–10 km and spatially correlated with the nearest meteorological hazard zones. The system evaluates alternative routes from OSRM and identifies the safest navigation corridor.

---

## 🚨 Emergency Evacuation Module
- **GPS Location Detection:** Acquires live coordinates via HTML5 Geolocation API with manual coordinate fallback.
- **Verified OpenStreetMap Discovery:** Direct spatial queries via Overpass QL for verified `hospital`, `police`, and `shelter` nodes.
- **Zero Fabrication Policy:** All emergency facilities are genuine OSM records; no simulated phone numbers or synthetic facilities are generated.
- **Nearest vs. Safest Ranking:** Compares raw Haversine proximity against hazard-weighted safety costs to recommend facilities outside active disaster zones.

---

## 🛡️ Admin Dashboard & Governance
- **Access Control:** Restricted via `@admin_required` decorator verifying `current_user.is_admin`.
- **System Metrics:** Live counts for registered users, hazard predictions, flood vs. landslide queries, and emergency operations.
- **Interactive Visualizations:** Chart.js graphs showing prediction volume distribution, risk tier breakdowns, and emergency facility queries.
- **Privacy & Security:** Password hashes, secret tokens, and sensitive credentials are never serialized in API responses.

---

## 🗄️ Database Architecture
MySQL Database (`nidars_db`) schema managed via Flask-Migrate (Alembic):
- `users`: User profiles, email, role (`user`/`admin`), PBKDF2 password hashes, timestamps.
- `locations`: Meteorological stations, state, latitude, longitude, baseline elevation.
- `prediction_history`: Historical user-submitted predictions, weather parameters, model probabilities, and risk levels.
- `emergency_facilities`: Cached OpenStreetMap amenities (OSM ID, amenity type, name, latitude, longitude).
- `emergency_requests`: Audit log of emergency operations, user coordinates, selected facilities, and hazard scores.

---

## 📡 REST API Reference

| Endpoint | Method | Auth | Description |
| :--- | :---: | :---: | :--- |
| `/api/health` | `GET` | Public | System status, database check, and ML model loading state |
| `/api/predict/flood` | `POST` | User | Execute standalone Flood ML prediction |
| `/api/gis/risk` | `GET` | User | Get spatial GeoJSON hazard grid for 64 North India stations |
| `/api/routing/route` | `POST` | User | Compute OSRM driving routes with disaster risk scoring |
| `/api/emergency/risk` | `GET` | User | Localized hazard assessment for given coordinate point |
| `/api/emergency/facilities`| `GET` | User | Query nearby verified OSM hospitals, police, and shelters |
| `/api/emergency/nearest` | `GET` | User | Compute nearest and risk-aware safest emergency facility |
| `/api/emergency/route` | `GET` | User | Generate safe evacuation driving route to emergency facility |
| `/api/admin/stats` | `GET` | Admin | Administrative analytics, counts, and hazard distributions |
| `/api/admin/predictions` | `GET` | Admin | Recent prediction audit logs |
| `/api/admin/emergency` | `GET` | Admin | Emergency operation audit logs |
| `/api/admin/facilities` | `GET` | Admin | Cached OpenStreetMap emergency facility records |

*(Complete API payloads, requests, and response schemas are documented in [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md).)*

---

## 📊 Data Sources & References
1. **Weather Observations:** IMD historical meteorological datasets (153,873 daily records across North India).
2. **Flood Inventory:** IIT Delhi HydroSense Lab India Flood Inventory ground-truth records.
3. **Landslide Catalog:** NASA Global Landslide Catalog (COOLR) open scientific repository.
4. **Road Network & Routing:** OpenStreetMap road network accessed via OSRM public API.
5. **Emergency Amenities:** OpenStreetMap amenities queried via the Overpass QL API.

---

## 💻 Installation & Setup

### Prerequisites
- Python 3.10 to 3.14 (Verified on Python 3.14.3 x64)
- MySQL Server 8.0+
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/nidars.git
cd NIDARS
```

### 2. Create and Activate Virtual Environment
**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**On Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip check
```

---

## ⚙️ Environment Variables
Copy `.env.example` to `.env` and configure your credentials:

```bash
cp .env.example .env
```

**Configuration Reference (`.env`):**
```ini
FLASK_ENV=development
DEBUG=True
SECRET_KEY=your_secure_random_secret_key_here

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=nidars_user
MYSQL_PASSWORD=nidars_password
MYSQL_DATABASE=nidars_db
DATABASE_URL=mysql+pymysql://nidars_user:nidars_password@localhost:3306/nidars_db

OSRM_BASE_URL=https://router.project-osrm.org
OVERPASS_BASE_URL=https://overpass-api.de/api/interpreter
```

---

## 🗄️ Database Setup & Migrations
1. Create the database in MySQL:
```sql
CREATE DATABASE nidars_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. Run Flask-Migrate database upgrade:
```powershell
python app.py db-upgrade
```

---

## 🚀 Running the Application

### Development Server
```powershell
python app.py
```
Access the application at `http://127.0.0.1:5000`.

### Production Server (WSGI)
**On Windows (Waitress):**
```powershell
waitress-serve --listen=127.0.0.1:5000 wsgi:app
```

**On Linux (Gunicorn):**
```bash
gunicorn --workers 4 --bind 0.0.0.0:5000 wsgi:app
```

---

## 🧪 Testing & Verification
Execute the automated regression test suite:
```powershell
python -m pytest -v
```
**Test Results:** **107/107 passed (100% pass rate)** in `~40 seconds`.

---

## 🚀 Deployment Guide
Comprehensive production deployment instructions—including Nginx reverse proxy configuration, Gunicorn systemd service setup, SSL certificates via Certbot, and Render/Cloud deployment—are available in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

---

## ⚠️ Known Limitations
1. **Station Spatial Resolution:** Hazard interpolations represent approximations calculated from 64 representative meteorological stations; microclimate and unmonitored valley variations may not be fully captured.
2. **Upstream External Dependencies:** OSRM routing and Overpass API emergency facility queries depend on third-party OpenStreetMap server availability and network connectivity.
3. **Landslide Dataset Imbalance:** The landslide classifier is trained on extreme class imbalance (56 historical NASA positive events) and serves as an advisory prioritization signal rather than a localized warning system.

---

## 🔮 Future Scope
- **IoT & Live Sensor Telemetry:** Direct ingestion of live telemetry from IMD radar, river water level gauges, and soil moisture sensors.
- **Multimodal Routing:** Support for heavy disaster relief convoy vehicles and helicopter landing zone (helipad) discovery.
- **Offline Mesh Caching:** Local spatial vector tile caching for disconnected disaster response operations.

---

## 📁 Project Structure
```text
NIDARS/
├── app.py                      # Flask Application Factory & Entrypoint
├── config.py                   # Environment & Configuration Management
├── wsgi.py                     # Production WSGI Entrypoint
├── requirements.txt            # Python Dependencies
├── .env.example                # Template Environment Variables
├── docs/                       # Comprehensive MCA Project Documentation Suite
│   ├── API_DOCUMENTATION.md    # REST API Specification
│   ├── DATABASE.md             # Schema, Migrations & Backup Guide
│   ├── DEPLOYMENT.md           # Production Deployment Manual
│   ├── FINAL_TEST_MATRIX.md    # End-to-End Verification Matrix
│   ├── GIS_METHODOLOGY.md      # Spatial Grid & Hazard Formulas
│   ├── MCA_PROJECT_REPORT.md   # Academic Major Project Report
│   ├── ML_METHODOLOGY.md       # ML Classifiers & Threshold Calibrations
│   ├── SCREENSHOT_CHECKLIST.md # UI & Demo Capture Checklist
│   ├── SECURITY_CHECKLIST.md   # Security & Hardening Audit
│   ├── SYSTEM_ARCHITECTURE.md  # Architectural Blueprint & Diagrams
│   └── USER_GUIDE.md           # Step-by-Step Operator Manual
├── gis/                        # GIS Data, Stations & Spatial Engine
├── ml/                         # Frozen ML Models, Preprocessors & Schemas
│   ├── flood/                  # Flood Model Artifacts & Evaluation
│   └── landslide/              # Landslide Model Artifacts & Evaluation
├── models/                     # SQLAlchemy Database Models
├── routes/                     # Flask Route Blueprints (Auth, Predict, GIS, Route, Emergency, Admin)
├── services/                   # Business Logic (GIS, Routing, Overpass, Admin, Prediction)
├── static/                     # CSS, JavaScript & Static Assets
├── templates/                  # Jinja2 HTML Templates (Pages & Error Views)
└── tests/                      # Automated Pytest Regression Test Suite (107 Tests)
```

---

## 👨‍💻 Project Information
- **Project Title:** AI-Based North India Flood and Landslide Prediction with Disaster-Aware Safe Route Optimization Using Machine Learning and GIS
- **Degree Program:** Master of Computer Applications (MCA) Major Project
- **Project Phase:** Phase 8 (Final Testing, Security Hardening, Deployment & Project Finalization)
- **Status:** Complete & Verified
