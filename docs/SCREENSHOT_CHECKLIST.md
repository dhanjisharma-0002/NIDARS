# NIDARS — Recommended Screenshots Checklist for MCA Report

The following screenshots should be captured from the live application running on `http://127.0.0.1:5000` for inclusion in the MCA Final Project Report and Presentation:

---

## Screenshot Checklist

1. **Home / Landing Page (`/`)**
   * View: Hero section, system introduction, live hazard indicators, and quick navigation cards.
2. **User Registration Page (`/register`)**
   * View: Registration form with client/server validation fields and security notes.
3. **User Login Page (`/login`)**
   * View: Clean dark-mode login card with CSRF protection and access credentials.
4. **User Dashboard (`/dashboard`)**
   * View: Welcome banner, system shortcuts, quick links to Flood, Map, Route, and Emergency.
5. **Flood Prediction Form (`/flood-prediction`)**
   * View: 9-feature meteorological input form with preset corridor selection.
6. **Flood Prediction Results (`/flood-prediction`)**
   * View: Evaluated flood probability badge (e.g. `82.4% HIGH RISK`) and advisory card.
7. **Interactive GIS Risk Map (`/map`)**
   * View: Full North India Leaflet map rendering colored station markers across JK, HP, UP, BR.
8. **GIS Station Popup & Filter Controls (`/map`)**
   * View: Station details popup with flood/landslide risk breakdown and state dropdown filter.
9. **Safe Route Optimizer View (`/route-optimizer`)**
   * View: Preset route selection (e.g. *Delhi to Shimla*), parameter sliders, and driving mode.
10. **Safe Route Comparison & Polylines (`/route-optimizer`)**
    * View: Map with computed driving route polyline, Recommended vs. Shortest cards, and risk penalty scores.
11. **Emergency Mode Main View (`/emergency`)**
    * View: Top red warning banner with Research Prototype advisory, geolocation button, and coordinate inputs.
12. **Emergency Facilities Discovery (`/emergency`)**
    * View: Rendered verified OpenStreetMap cards for Hospitals, Police Stations, and Shelters.
13. **Emergency Evacuation Route (`/emergency`)**
    * View: Active evacuation corridor polyline to safest facility and summary metric card.
14. **Admin Dashboard Control Center (`/admin`)**
    * View: Top KPI metric cards (Total Users, Predictions, Emergency Queries, Cached Facilities).
15. **Admin Analytics Charts (`/admin`)**
    * View: Chart.js Doughnut (Prediction Types), Bar (Risk Levels), and Pie (Facilities) graphs.
16. **Admin Activity Logs (`/admin`)**
    * View: Real-time tables for Recent Emergency Operations and Hazard Predictions.
17. **Database Migration Output in Terminal**
    * View: `python app.py db-upgrade` confirming `nidars_db` migration success.
18. **Automated Pytest Suite Execution**
    * View: Terminal output showing `107 passed in 39.72s`.
