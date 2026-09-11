import numpy as np
import pandas as pd

INPUT_FILE = "data/processed/flood_labeled_weather.csv"
OUTPUT_FILE = "data/processed/flood_training.csv"

print("=" * 70)
print("NIDARS FLOOD TRAINING DATA PREPARATION (CALENDAR TIME ROLLING)")
print("=" * 70)

# 1. Load labeled dataset
df = pd.read_csv(INPUT_FILE)
print("\nOriginal shape:", df.shape)

# 2. Parse date and ensure numeric rainfall
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df["rainfall"] = pd.to_numeric(df["rainfall"], errors="coerce")

# Drop any rows with invalid dates if present
valid_date_mask = df["date"].notna()
if not valid_date_mask.all():
    print(f"Dropping {(~valid_date_mask).sum()} rows with invalid dates.")
    df = df[valid_date_mask].copy()

# 3. Sort chronologically within each station time-series
group_cols = ["state_full", "district_key", "station_name"]
df = df.sort_values(group_cols + ["date"]).reset_index(drop=True)

# 4. Compute calendar-time based rainfall features
# Daily rainfall observation (24-hour observation)
df["rainfall_24h"] = df["rainfall"]

# Previous 72-hour (3-day) and 7-day accumulated rainfall using actual calendar time window.
# Using datetime index with '3D' and '7D' rolling windows ensures that only observations
# within the exact preceding calendar window are aggregated. Gaps (e.g. 10 to 317 days)
# are strictly respected and past data outside the window is excluded.
# sort=False maintains the already sorted station-date sequence.
rolling_72h = (
    df.set_index("date")
    .groupby(group_cols, sort=False)["rainfall"]
    .rolling("3D", min_periods=1)
    .sum()
    .reset_index()
)

rolling_7d = (
    df.set_index("date")
    .groupby(group_cols, sort=False)["rainfall"]
    .rolling("7D", min_periods=1)
    .sum()
    .reset_index()
)

# Assign aligned calendar rolling values
df["rainfall_72h"] = rolling_72h["rainfall"].values
df["rainfall_7d"] = rolling_7d["rainfall"].values

# 5. Map real available meteorological & geospatial features
df["temperature"] = pd.to_numeric(df["avg_temp"], errors="coerce")
df["wind_speed"] = pd.to_numeric(df["wind_speed"], errors="coerce")
df["air_pressure"] = pd.to_numeric(df["air_pressure"], errors="coerce")
df["elevation"] = pd.to_numeric(df["elevation"], errors="coerce")
df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

# 6. Select feature columns and target (no fabricated features)
feature_columns = [
    "rainfall_24h",
    "rainfall_72h",
    "rainfall_7d",
    "temperature",
    "wind_speed",
    "air_pressure",
    "elevation",
    "latitude",
    "longitude",
    "flood_risk",
]

training = df[feature_columns].copy()

# Replace infinite values with NaN
training = training.replace([np.inf, -np.inf], np.nan)

# Ensure valid target
training = training.dropna(subset=["flood_risk"])
training["flood_risk"] = training["flood_risk"].astype(int)

# 7. Verification & Summary Output
print("\n" + "-" * 40)
print("DATASET VERIFICATION & STATISTICS")
print("-" * 40)

print("\nFinal training shape:", training.shape)

print("\nColumns:")
for col in training.columns:
    print(f"  - {col}")

print("\nMissing values per column:")
print(training.isna().sum())

print("\nRainfall 24h statistics (mm):")
print(training["rainfall_24h"].describe())

print("\nRainfall 72h statistics (mm):")
print(training["rainfall_72h"].describe())

print("\nRainfall 7d statistics (mm):")
print(training["rainfall_7d"].describe())

print("\nFlood Risk class distribution:")
print(training["flood_risk"].value_counts().sort_index())

flood_pct = training["flood_risk"].mean() * 100
print(f"\nFlood positive rate: {flood_pct:.4f}%")

# 8. Save final dataset
training.to_csv(OUTPUT_FILE, index=False)

print("\n" + "=" * 70)
print(f"SUCCESS: Saved corrected dataset to {OUTPUT_FILE}")
print("=" * 70)