# NIDARS — Machine Learning Methodology & Evaluation

**Research Scope:** Dual-Hazard Predictive Modeling (Flood & Landslide) for North India  
**Target Region:** Jammu & Kashmir, Himachal Pradesh, Uttar Pradesh, Bihar  
**Feature Standard:** Real Meteorological & Geographical Grounding (9 Observable Features)

---

## 1. Feature Schema & Engineering

Both Flood and Landslide models utilize an identical, physically validated 9-feature schema derived from genuine meteorological station records and digital elevation models:

| Feature Name | Description | Units | Range in Dataset |
| :--- | :--- | :--- | :--- |
| `rainfall_24h` | Cumulative 24-hour rainfall | mm | $0.0\text{ -- }425.0$ |
| `rainfall_72h` | Cumulative 72-hour antecedent rainfall | mm | $0.0\text{ -- }750.0$ |
| `rainfall_7d` | Cumulative 7-day antecedent rainfall | mm | $0.0\text{ -- }1200.0$ |
| `temperature` | 2-meter air temperature | °C | $-15.0\text{ -- }48.0$ |
| `wind_speed` | Surface wind speed | m/s | $0.0\text{ -- }35.0$ |
| `air_pressure` | Mean sea-level barometric pressure | hPa | $940.0\text{ -- }1040.0$ |
| `elevation` | Surface elevation above sea level | meters | $15.0\text{ -- }4500.0$ |
| `latitude` | Station geographic latitude | Decimal degrees | $24.0\text{ -- }37.0$ |
| `longitude` | Station geographic longitude | Decimal degrees | $73.0\text{ -- }89.0$ |

---

## 2. Flood Machine Learning Engine (Phase 3)

### Dataset & Labeling
* **Raw Sources:** Historical North India meteorological observations (`india_weather_rainfall_data.xlsx`) and IIT Delhi HydroSense Lab Flood Inventory.
* **Positive Ground-Truth Events:** Severe flood events labeled where cumulative precipitation exceeded regional critical flood thresholds ($> 100\text{ mm}$ 24h or extreme multi-day accumulation) cross-referenced with recorded flood occurrences.
* **Training Matrix:** 141,629 processed observations.

### Model Architecture & Training
* **Algorithm:** Random Forest Classifier (`RandomForestClassifier`, 100 estimators, balanced class weighting).
* **Preprocessing:** `StandardScaler` fitted on continuous variables with median imputation for missing values.

### Validated Test Metrics:
* **ROC-AUC:** `0.9421`
* **F1-Score:** `0.8845`
* **Precision:** `0.8610`
* **Recall:** `0.9100`
* **Accuracy:** `99.2%`

---

## 3. Landslide Machine Learning Engine (Phase 4 & 4.1)

### Dataset & Ground Truth Association
* **Positive Ground-Truth Source:** NASA Global Landslide Catalog / Cooperative Open Online Landslide Repository (COOLR).
* **Spatial-Temporal Association:**
  * Strict spatial tolerance: Within 50.0 km great-circle distance of genuine meteorological observation stations.
  * Strict temporal tolerance: Exact calendar date match with recorded antecedent rainfall.
* **Class Imbalance:** 56 confirmed positive landslide occurrences against 141,573 negative observations (extreme real-world class imbalance ratio of $\sim 1:2500$).

### Model Selection & Training
* **Algorithm:** Gradient Boosting Classifier (`GradientBoostingClassifier`, learning rate 0.05, max depth 4, subsample 0.8).
* **Preprocessing:** `LandslidePreprocessor` with feature standardization and strict temporal leakage prevention.

### Performance & Threshold Calibration:
* **ROC-AUC:** `0.9057`
* **PR-AUC (Precision-Recall AUC):** `0.0112` (reflecting extreme sparsity)
* **Threshold Analysis:**
  * Standard threshold ($0.50$): Recall = 0.00 (misses sparse occurrences).
  * **Phase 4.1 Advisory Threshold ($0.02$):** Balanced early warning advisory signal.
  * **Phase 4.1 Action Threshold ($0.10$):** High-confidence disaster routing and evacuation action threshold.

> **ACADEMIC NOTE ON LANDSLIDE MODEL:** Due to extreme rarity of ground-truth landslide records, the landslide model operates as an advisory hazard risk-scoring signal to penalize risky road corridors, and is not an autonomous warning siren.
