"""Create real landslide ground-truth labels by matching NASA Global Landslide Catalog events

with North India weather observations using exact date and spatial proximity.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WEATHER_FILE = "data/processed/north_india_weather.csv"
LANDSLIDE_FILE = "data/raw/landslide_data.csv"
OUTPUT_FILE = "data/processed/landslide_labeled_weather.csv"

# Spatial threshold: 50 km is chosen because mountainous weather stations in the Himalayas
# (HP and JK) have average spacing of 30-50 km, representing the local catchment/storm basin.
SPATIAL_THRESHOLD_KM = 50.0

STATE_MAP = {
    "UP": "UTTAR PRADESH",
    "BR": "BIHAR",
    "HP": "HIMACHAL PRADESH",
    "JK": "JAMMU & KASHMIR",
}


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate geodesic distance in kilometers between two coordinate pairs."""
    r = 6371.0  # Earth radius in kilometers
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2.0) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    return r * c


def main():
    print("=" * 70)
    print("NIDARS LANDSLIDE GROUND-TRUTH LABEL GENERATION")
    print("=" * 70)

    # 1. Load weather observations
    weather = pd.read_csv(WEATHER_FILE)
    print(f"\nLoaded {len(weather)} weather records from {WEATHER_FILE}")

    weather["state_full"] = weather["state"].map(STATE_MAP)
    weather["district_key"] = weather["district"].astype(str).str.strip().str.upper()
    weather["date"] = pd.to_datetime(weather["date_of_record"], errors="coerce")

    # 2. Load NASA Global Landslide Catalog
    landslides = pd.read_csv(LANDSLIDE_FILE)
    print(f"Loaded {len(landslides)} global landslide events from {LANDSLIDE_FILE}")

    # Filter to India
    india_mask = landslides["country_na"].astype(str).str.strip().str.upper() == "INDIA"
    landslides_in = landslides[india_mask].copy()

    landslides_in["date"] = pd.to_datetime(landslides_in["event_date"], errors="coerce")
    landslides_in = landslides_in[
        landslides_in["date"].notna()
        & landslides_in["latitude"].notna()
        & landslides_in["longitude"].notna()
    ].copy()

    w_min_date = weather["date"].min()
    w_max_date = weather["date"].max()

    # Filter landslides within the temporal range of the weather dataset
    ls_timeline = landslides_in[
        (landslides_in["date"] >= w_min_date) & (landslides_in["date"] <= w_max_date)
    ].copy()

    print(f"India landslide events within weather timeline ({w_min_date.date()} to {w_max_date.date()}): {len(ls_timeline)}")

    # Initialize all weather observations as non-landslide (0)
    weather["landslide_risk"] = 0

    matched_events = set()
    matched_records = 0
    matched_stations = set()

    # Match each landslide event to weather stations on the event date within spatial threshold
    for _, ls_event in ls_timeline.iterrows():
        event_id = ls_event["event_id"]
        event_date = ls_event["date"].date()
        event_lat = ls_event["latitude"]
        event_lon = ls_event["longitude"]

        # Weather observations on the exact event date
        day_mask = weather["date"].dt.date == event_date
        if not day_mask.any():
            continue

        day_subset = weather.loc[day_mask]
        dists = haversine_distance(
            event_lat,
            event_lon,
            day_subset["latitude"].values,
            day_subset["longitude"].values,
        )

        close_indices = day_subset.index[dists <= SPATIAL_THRESHOLD_KM]
        if len(close_indices) > 0:
            weather.loc[close_indices, "landslide_risk"] = 1
            matched_events.add(event_id)
            matched_records += len(close_indices)
            for idx in close_indices:
                matched_stations.add(weather.loc[idx, "station_name"])

    # Summary report
    print("\n" + "-" * 40)
    print("LABELING SUMMARY")
    print("-" * 40)
    print(f"Spatial Threshold Distance: {SPATIAL_THRESHOLD_KM} km")
    print(f"NASA Landslide Events Matched: {len(matched_events)} / {len(ls_timeline)}")
    print(f"Unique Weather Stations Affected: {len(matched_stations)}")
    print(f"Total Positive (Landslide Risk = 1) Records: {int(weather['landslide_risk'].sum())}")
    print(f"Total Negative (Landslide Risk = 0) Records: {int((weather['landslide_risk'] == 0).sum())}")
    pos_pct = weather["landslide_risk"].mean() * 100
    print(f"Positive Rate: {pos_pct:.4f}%")

    print("\nPositive Records by State:")
    print(weather[weather["landslide_risk"] == 1]["state_full"].value_counts().to_string())

    # Save labeled dataset
    weather.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved labeled dataset to: {OUTPUT_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()
