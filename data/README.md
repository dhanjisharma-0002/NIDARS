# Flood dataset

This folder is the **only** accepted location for the flood training file:

`data/raw/flood_data.csv`

NIDARS does **not** ship a fabricated flood dataset. Do not generate random rows and treat them as observational data.

## Required columns

Canonical names:

| Column | Meaning | Typical range |
|---|---|---|
| rainfall_24h | Rainfall in last 24 hours (mm) | ≥ 0 |
| rainfall_72h | Rainfall in last 72 hours (mm) | ≥ 0 |
| rainfall_7d | Rainfall in last 7 days (mm) | ≥ 0 |
| river_level | Observed river / gauge level (m) | ≥ 0 |
| danger_level | Gauge danger / warning level (m) | ≥ 0 |
| soil_moisture | Volumetric moisture fraction | 0–1 |
| temperature | Air temperature (°C) | about -20–55 |
| humidity | Relative humidity (%) | 0–100 |
| elevation | Site elevation (m) | ≥ -50 |
| previous_flood | Prior flood at site | 0 or 1 |
| flood_risk | Target label | 0 = no/low event, 1 = flood/risk event |

If your source file uses different headers, add a mapping in `ml/flood/feature_schema.py` (`COLUMN_ALIASES`) rather than renaming by guesswork in notebooks.

## Suggested public sources (place the file yourself)

Use records you are allowed to use for academic work, for example:

- India Meteorological Department (IMD) rainfall products
- Central Water Commission (CWC) gauge / flood bulletins
- State disaster management rainfall or inundation archives
- Peer-reviewed or openly licensed hydrology datasets covering North India

Export a CSV that matches the columns above (or map them explicitly), then run:

```powershell
.\venv\Scripts\python.exe -m ml.flood.train
```

Processed copies may be written to `data/processed/` after a successful training run.
