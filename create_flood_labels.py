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

weather = pd.read_csv(WEATHER_FILE)

flood = pd.read_csv(
    FLOOD_FILE,
    usecols=["Start Date", "End Date", "Districts", "State"]
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

# Start with all observations as non-flood
weather["flood_risk"] = 0

matched_pairs = set()
flood_records = 0

for _, row in flood.iterrows():

    state = row["state_full"]

    if state not in STATE_MAP.values():
        continue

    state_mask = weather["state_full"] == state

    districts = weather.loc[
        state_mask,
        "district_key"
    ].dropna().unique()

    for district in districts:

        if district == "NAN" or district == "":
            continue

        pattern = (
            r"(?<![A-Z])"
            + re.escape(district)
            + r"(?![A-Z])"
        )

        if not re.search(pattern, row["districts_key"]):
            continue

        mask = (
            (weather["state_full"] == state)
            & (weather["district_key"] == district)
            & (weather["date"] >= row["start"])
            & (weather["date"] <= row["end"])
        )

        count = int(mask.sum())

        if count > 0:
            weather.loc[mask, "flood_risk"] = 1
            flood_records += count
            matched_pairs.add((state, district))


print()
print("=" * 60)
print("NIDARS FLOOD LABEL GENERATION")
print("=" * 60)
print()

print("Total weather records:", len(weather))
print("Flood-risk records:", int(weather["flood_risk"].sum()))
print(
    "Non-flood records:",
    int((weather["flood_risk"] == 0).sum())
)

print()
print("Class distribution:")
print(
    weather["flood_risk"]
    .value_counts()
    .sort_index()
)

print()
print("Unique state-district pairs with flood records:")
print(len(matched_pairs))

print()
print("Flood records by state:")

print(
    weather[weather["flood_risk"] == 1]
    .groupby("state_full")
    .size()
    .sort_values(ascending=False)
)

print()
print("Saving labeled dataset...")

output_file = "data/processed/flood_labeled_weather.csv"

weather.to_csv(
    output_file,
    index=False
)

print()
print("Saved:", output_file)
print()
print("=" * 60)