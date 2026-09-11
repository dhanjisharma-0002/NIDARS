# Landslide Machine Learning Module

This package implements the data schema, preprocessing, feature validation, and inference pipeline for Landslide Risk Prediction in NIDARS.

## Accepted Dataset Location

Place the raw landslide dataset at:
`data/raw/landslide_data.csv`

## Required Canonical Features

| Column | Description | Unit / Range |
| :--- | :--- | :--- |
| `rainfall_24h` | Daily / 24-hour rainfall | mm (≥ 0) |
| `rainfall_72h` | 3-day / 72-hour cumulative antecedent rainfall | mm (≥ 0) |
| `rainfall_7d` | 7-day cumulative antecedent rainfall | mm (≥ 0) |
| `slope` | Slope gradient | degrees (0–90°) |
| `elevation` | Topographic altitude | meters (-100 to 9000) |
| `aspect` | Slope orientation / compass direction | degrees (0–360°) |
| `soil_moisture` | Volumetric soil moisture fraction | 0.0–1.0 |
| `distance_to_road` | Distance to nearest road network | meters (≥ 0) |
| `distance_to_river` | Distance to nearest stream / drainage line | meters (≥ 0) |
| `vegetation_index` | Normalized Difference Vegetation Index (NDVI) | -1.0 to 1.0 |
| `landslide_risk` | Target binary indicator | 0 = No event / Low susceptibility, 1 = Landslide occurrence / High risk |

## Workflow

1. Place legitimate landslide inventory / susceptibility dataset at `data/raw/landslide_data.csv`.
2. Execute model training:
   ```powershell
   .\venv\Scripts\python.exe -m ml.landslide.train
   ```
3. Generated artifacts:
   - `ml/landslide/model/landslide_model.pkl`
   - `ml/landslide/model/landslide_preprocessor.pkl`
   - `ml/landslide/model/evaluation.json`
