# NIDARS — User Guide & System Walkthrough

Welcome to the **NIDARS** (North India Disaster Awareness & Route System) User Guide.

---

## 1. Getting Started & Account Access

### Registration (`/register`)
1. Open your browser and navigate to `http://127.0.0.1:5000/register`.
2. Enter your Full Name, valid Email address, and secure Password (minimum 8 characters).
3. Click **Register**. Your account will be created with standard `user` privileges.

### Login (`/login`)
1. Navigate to `http://127.0.0.1:5000/login`.
2. Enter your registered email and password.
3. Click **Login** to enter the NIDARS dashboard.

---

## 2. Main Dashboard (`/dashboard`)
* View quick navigation shortcuts to all platform features.
* Access recent weather advisories, model statistics, and operational links.

---

## 3. Local Flood Risk Predictor (`/flood-prediction`)
1. Click **Flood** in the main navigation menu.
2. Select a preset meteorological scenario or enter:
   * 24h, 72h, and 7-day cumulative rainfall (mm)
   * Temperature (°C), Surface Wind Speed (m/s), Barometric Pressure (hPa)
   * Elevation (meters) and geographic coordinates
3. Click **Predict Flood Risk**.
4. The system evaluates the Random Forest ML model and displays:
   * Flood Probability percentage (e.g. `82.4%`)
   * Risk Classification (`LOW`, `MODERATE`, `HIGH`, `CRITICAL`)
   * Safety recommendations and prototype disclaimer.

---

## 4. Interactive GIS Risk Map (`/map`)
1. Click **Map** in the main navigation menu.
2. Filter stations by:
   * **Hazard Mode:** Combined Hazard, Flood Risk Only, or Landslide Risk Only
   * **State:** All, Jammu & Kashmir, Himachal Pradesh, Uttar Pradesh, Bihar
   * **Hazard Weights:** Adjust sliders for flood vs. landslide relative weights.
3. Click on any colored map marker to view detailed meteorological station observations and ML probabilities.

---

## 5. Safe Route Optimizer (`/route-optimizer`)
1. Click **Safe Route** in the navigation bar.
2. Choose a preset corridor (e.g. *Delhi to Shimla*, *Chandigarh to Manali*) or input custom Origin and Destination coordinates.
3. Click **Compute Safe Route**.
4. The system queries OSRM driving routes, overlays flood/landslide risk along the highway corridor, and highlights:
   * **Recommended Route** (minimum combined distance + hazard cost)
   * **Shortest Route** vs. **Safest Route** comparison cards
   * Station hazard coverage percentage and driving travel time.

---

## 6. Emergency Mode & Facility Discovery (`/emergency`)
1. Click **🚨 Emergency** in the top navigation bar.
2. Click **📍 Use My Location** to auto-detect GPS coordinates, or manually enter Latitude and Longitude.
3. Click **🚨 Find Nearby Help**.
4. The system discovers genuine OpenStreetMap emergency amenities within 15 km:
   * 🏥 **Hospitals & Clinics**
   * 👮 **Police Stations**
   * 🏠 **Shelters & Relief Centers**
5. View the **Risk-Aware Recommendation** (the safest facility considering localized flood/landslide danger).
6. Click **🧭 Safe Route** on any facility card to draw an immediate evacuation path on the map.

---

## 7. Admin Control Center (`/admin`)
*(Restricted to Administrator accounts, e.g. `admin@nidars.gov.in`)*
1. Click **🛡️ Admin** in the navigation bar.
2. Monitor real-time system metrics:
   * Registered users, total ML inquiries, flood vs. landslide query distribution.
   * Emergency request volumes and cached OpenStreetMap facilities.
3. View interactive Chart.js analytics graphs for operational risk distribution.
4. Inspect audit tables for recent emergency inquiries and hazard predictions.
