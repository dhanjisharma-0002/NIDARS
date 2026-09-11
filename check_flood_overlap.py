import pandas as pd
import re

WEATHER_FILE = "data/processed/north_india_weather.csv"
FLOOD_FILE = "data/raw/India_Flood_Inventory_v3.csv"

STATE_MAP = {
    "UP": "UTTAR PRADESH",
    "BR": "BIHAR",
    "HP": "HIMACHAL PRADESH",
    "JK": "JAMMU & KASHMIR",
}

# Load weather data
weather = pd.read_csv(
    WEATHER_FILE,
    usecols=["date_of_record", "state", "district"]
)

weather["state_full"] = weather["state"].map(STATE_MAP)
weather["district_key"] = (
    weather["district"]
    .astype(str)
    .str.strip()
    .str.upper()
)
weather["date"] = pd.to_datetime(
    weather["date_of_record"],
    errors="coerce"
)

# Load flood inventory
flood = pd.read_csv(
    FLOOD_FILE,
    usecols=["Start Date", "End Date", "Districts", "State"]
)

flood["state_full"] = (
    flood["State"]
    .astype(str)
    .str.strip()
    .str.upper()
)

flood["start"] = pd.to_datetime(
    flood["Start Date"],
    dayfirst=True,
    errors="coerce"
)

flood["end"] = pd.to_datetime(
    flood["End Date"],
    dayfirst=True,
    errors="coerce"
)

flood = flood[
    flood["Districts"].notna()
    & flood["start"].notna()
    & flood["end"].notna()
    & (flood["end"] >= flood["start"])
].copy()

flood["districts_key"] = (
    flood["Districts"]
    .astype(str)
    .str.upper()
)

matched_records = 0
matched_pairs = set()
matched_districts = set()
matched_states = set()

weather_groups = weather.groupby(
    ["state_full", "district_key"]
)

for _, row in flood.iterrows():

    state = row["state_full"]

    if state not in STATE_MAP.values():
        continue

    state_weather = weather[
        weather["state_full"] == state
    ]

    districts = state_weather["district_key"].unique()

    for district in districts:

        if district in ("NAN", ""):
            continue

        pattern = (
            r"(?<![A-Z])"
            + re.escape(district)
            + r"(?![A-Z])"
        )

        if re.search(pattern, row["districts_key"]):

            mask = (
                (weather["state_full"] == state)
                & (weather["district_key"] == district)
                & (weather["date"] >= row["start"])
                & (weather["date"] <= row["end"])
            )

            count = int(mask.sum())

            if count > 0:
                matched_records += count
                matched_pairs.add((state, district))
                matched_districts.add(district)
                matched_states.add(state)

print()
print("=" * 60)
print("NIDARS FLOOD EVENT OVERLAP CHECK")
print("=" * 60)
print()

print("Weather records:", len(weather))
print("Flood events with valid dates:", len(flood))
print()

print(
    "Weather records falling inside real flood events:",
    matched_records
)

print(
    "Unique matched districts:",
    len(matched_districts)
)

print(
    "State-district pairs with flood events:",
    len(matched_pairs)
)

print(
    "States with matched flood records:",
    len(matched_states)
)

print()
print("Matched states:")

for state in sorted(matched_states):
    print(" -", state)

print()
print("Sample matched districts:")

for state, district in sorted(matched_pairs)[:30]:
    print(" -", state, "|", district)

print()
print("=" * 60)