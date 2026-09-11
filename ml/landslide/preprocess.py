from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ml.landslide.feature_schema import (
    FEATURE_COLUMNS,
    MISSING_DATASET_MESSAGE,
    TARGET_COLUMN,
    LandslideSchemaError,
    apply_column_aliases,
)

RANDOM_STATE = 42
TEST_SIZE = 0.2


class LandslidePreprocessor:
    """Train-only median imputation. Fits only on training split."""

    def __init__(self):
        self.feature_columns_ = list(FEATURE_COLUMNS)
        self.fill_values_ = {}

    def fit(self, frame):
        numeric = frame[self.feature_columns_].apply(pd.to_numeric, errors="coerce")
        self.fill_values_ = numeric.median(numeric_only=True).to_dict()
        return self

    def transform(self, frame):
        data = frame[self.feature_columns_].copy()
        for column in self.feature_columns_:
            data[column] = pd.to_numeric(data[column], errors="coerce")
            fill = self.fill_values_.get(column, 0.0)
            data[column] = data[column].fillna(fill)
        return data

    def fit_transform(self, frame):
        return self.fit(frame).transform(frame)


def resolve_dataset_path(path=None):
    if path is None:
        from config import BASE_DIR, Config

        path = getattr(Config, "LANDSLIDE_DATASET_PATH", BASE_DIR / "data" / "processed" / "landslide_training.csv")
    return Path(path)


def load_raw_csv(path=None):
    csv_path = resolve_dataset_path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(MISSING_DATASET_MESSAGE)
    return pd.read_csv(csv_path)


def _map_target(series):
    mapped = series.copy()
    if mapped.dtype == object or str(mapped.dtype).startswith("str"):
        lowered = mapped.astype(str).str.strip().str.lower()
        mapped = lowered.replace(
            {
                "1": 1,
                "0": 0,
                "true": 1,
                "false": 0,
                "yes": 1,
                "no": 0,
                "landslide": 1,
                "no_landslide": 0,
                "risk": 1,
                "no_risk": 0,
                "high": 1,
                "low": 0,
            }
        )
    numeric = pd.to_numeric(mapped, errors="coerce")
    return numeric


def prepare_training_frame(raw_frame):
    if raw_frame.empty:
        raise LandslideSchemaError("The landslide dataset is empty.")

    renamed = raw_frame.rename(columns=apply_column_aliases(raw_frame.columns))
    missing = [col for col in FEATURE_COLUMNS + [TARGET_COLUMN] if col not in renamed.columns]
    if missing:
        raise LandslideSchemaError(
            "Landslide dataset is missing required columns after alias mapping: "
            + ", ".join(missing)
            + ". Expected features: "
            + ", ".join(FEATURE_COLUMNS)
            + f" and target {TARGET_COLUMN}."
        )

    frame = renamed[FEATURE_COLUMNS + [TARGET_COLUMN]].copy()
    for column in FEATURE_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame[FEATURE_COLUMNS] = frame[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)
    frame[TARGET_COLUMN] = _map_target(frame[TARGET_COLUMN])

    before = len(frame)
    frame = frame.drop_duplicates()
    frame = frame.dropna(subset=[TARGET_COLUMN])
    frame = frame[frame[TARGET_COLUMN].isin([0, 1, 0.0, 1.0])]
    frame[TARGET_COLUMN] = frame[TARGET_COLUMN].astype(int)

    feature_all_invalid = frame[FEATURE_COLUMNS].isna().all(axis=1)
    frame = frame.loc[~feature_all_invalid]

    if frame.empty:
        raise LandslideSchemaError("No valid rows remained after cleaning the landslide dataset.")
    if frame[TARGET_COLUMN].nunique() < 2:
        raise LandslideSchemaError("The landslide target must contain both classes (0 and 1) for training.")

    print(f"Loaded {before} rows; {len(frame)} remain after cleaning.")
    return frame


def split_xy(frame):
    features = frame[FEATURE_COLUMNS]
    target = frame[TARGET_COLUMN]
    return features, target
