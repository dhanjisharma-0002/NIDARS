"""Prepare landslide training dataset using calendar-time rolling rainfall features

and real available meteorological / topographic features from labeled weather data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

INPUT_FILE = "data/processed/landslide_labeled_weather.csv"
OUTPUT_FILE = "data/processed/landslide_training.csv"

# Unavailable features in the current weather/tabular dataset (no fabrication):
UNAVAILABLE_SCHEMA_FEATURES = [
    "slope",
    "aspect",
    "soil_moisture",
    "distance_to_road",
    "distance_to_river",
    "vegetation_index",
]


def main():
    print("=" * 70)
    print("NIDARS LANDSLIDE TRAINING DATA PREPARATION")
    print("=" * 70)

    # 1. Load labeled dataset
    df = pd.read_csv(INPUT_FILE)
    print(f"\nOriginal shape: {df.shape}")

    # 2. Parse date and ensure numeric rainfall
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["rainfall"] = pd.to_numeric(df["rainfall"], errors="coerce")

    # Drop any invalid dates
    valid_date_mask = df["date"].notna()
    if not valid_date_mask.all():
        print(f"Dropping {(~valid_date_mask).sum()} invalid date rows.")
        df = df[valid_date_mask].copy()

    # 3. Sort chronologically within each station time-series
    group_cols = ["state_full", "district_key", "station_name"]
    df = df.sort_values(group_cols + ["date"]).reset_index(drop=True)

    # 4. Compute calendar-time rolling rainfall features (same as Flood ML)
    df["rainfall_24h"] = df["rainfall"]

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

    df["rainfall_72h"] = rolling_72h["rainfall"].values
    df["rainfall_7d"] = rolling_7d["rainfall"].values

    # 5. Map real available meteorological & geospatial features
    df["temperature"] = pd.to_numeric(df["avg_temp"], errors="coerce")
    df["wind_speed"] = pd.to_numeric(df["wind_speed"], errors="coerce")
    df["air_pressure"] = pd.to_numeric(df["air_pressure"], errors="coerce")
    df["elevation"] = pd.to_numeric(df["elevation"], errors="coerce")
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    # 6. Populate legitimately available feature columns
    available_feature_columns = [
        "rainfall_24h",
        "rainfall_72h",
        "rainfall_7d",
        "temperature",
        "wind_speed",
        "air_pressure",
        "elevation",
        "latitude",
        "longitude",
        "landslide_risk",
    ]

    training = df[available_feature_columns].copy()

    # Replace infinite values with NaN
    training = training.replace([np.inf, -np.inf], np.nan)

    # Ensure valid target
    training = training.dropna(subset=["landslide_risk"])
    training["landslide_risk"] = training["landslide_risk"].astype(int)

    # 7. Verification & Summary Output
    print("\n" + "-" * 40)
    print("DATASET VERIFICATION & STATISTICS")
    print("-" * 40)

    print(f"\nFinal training shape: {training.shape}")

    print("\nAvailable Real Features:")
    for col in training.columns:
        print(f"  - {col}")

    print("\nUnavailable Schema Features (NOT fabricated):")
    for col in UNAVAILABLE_SCHEMA_FEATURES:
        print(f"  - {col} (Requires external GIS/DEM layers)")

    print("\nMissing values per available column:")
    print(training.isna().sum())

    print("\nRainfall 24h statistics (mm):")
    print(training["rainfall_24h"].describe())

    print("\nRainfall 72h statistics (mm):")
    print(training["rainfall_72h"].describe())

    print("\nRainfall 7d statistics (mm):")
    print(training["rainfall_7d"].describe())

    print("\nLandslide Risk class distribution:")
    print(training["landslide_risk"].value_counts().sort_index())

    pos_pct = training["landslide_risk"].mean() * 100
    print(f"\nLandslide positive rate: {pos_pct:.4f}%")

    # 8. Save final dataset
    training.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved landslide training dataset to: {OUTPUT_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()
