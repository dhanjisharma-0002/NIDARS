"""Train flood-risk classifiers and persist the selected model.

This is a college/research prototype. It is not an official disaster warning system.
"""

from __future__ import annotations

import json
from pathlib import Path

from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import train_test_split

from config import BASE_DIR, Config
from ml.flood.evaluate import evaluate_classifier, selection_score
from ml.flood.feature_schema import FEATURE_COLUMNS, MISSING_DATASET_MESSAGE, TARGET_COLUMN
from ml.flood.preprocess import (
    RANDOM_STATE,
    TEST_SIZE,
    FloodPreprocessor,
    load_raw_csv,
    prepare_training_frame,
    split_xy,
)

try:
    from xgboost import XGBClassifier
except ImportError:
    XGBClassifier = None


def _candidate_models():
    models = {
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        "gradient_boosting": GradientBoostingClassifier(
            random_state=RANDOM_STATE,
        ),
    }
    if XGBClassifier is not None:
        models["xgboost"] = XGBClassifier(
            random_state=RANDOM_STATE,
            eval_metric="logloss",
            n_estimators=200,
            n_jobs=-1,
        )
    return models


def _save_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def train(dataset_path=None):
    import joblib

    raw = load_raw_csv(dataset_path)
    frame = prepare_training_frame(raw)
    features, target = split_xy(frame)

    stratify = target if target.value_counts().min() >= 2 else None
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=stratify,
    )

    print(f"Train split: {len(x_train)} rows | Class 0: {(y_train == 0).sum()}, Class 1: {(y_train == 1).sum()}")
    print(f"Test split: {len(x_test)} rows | Class 0: {(y_test == 0).sum()}, Class 1: {(y_test == 1).sum()}")

    preprocessor = FloodPreprocessor()
    x_train_p = preprocessor.fit_transform(x_train)
    x_test_p = preprocessor.transform(x_test)

    results = {}
    fitted = {}
    for name, model in _candidate_models().items():
        print(f"Training {name}...")
        model.fit(x_train_p, y_train)
        metrics = evaluate_classifier(model, x_test_p, y_test)
        results[name] = metrics
        fitted[name] = model
        print(
            f"  recall={metrics['recall']:.4f}  f1={metrics['f1']:.4f}  "
            f"precision={metrics['precision']:.4f}  roc_auc={metrics['roc_auc']}  "
            f"accuracy={metrics['accuracy']:.4f}"
        )
        print(f"  confusion_matrix={metrics['confusion_matrix']}")

    best_name = max(results, key=lambda name: selection_score(results[name]))
    best_model = fitted[best_name]

    model_dir = Path(Config.FLOOD_MODEL_DIR)
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_model, Config.FLOOD_MODEL_PATH)
    joblib.dump(preprocessor, Config.FLOOD_PREPROCESSOR_PATH)

    processed_dir = BASE_DIR / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(processed_dir / "flood_clean.csv", index=False)

    summary = {
        "best_model": best_name,
        "selection_criterion": "Highest recall, then F1, then ROC-AUC. Accuracy is reported only.",
        "feature_columns": FEATURE_COLUMNS,
        "target": TARGET_COLUMN,
        "random_state": RANDOM_STATE,
        "test_size": TEST_SIZE,
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "xgboost_evaluated": XGBClassifier is not None,
        "metrics": results,
        "disclaimer": (
            "This is a college/research prototype and decision-support system. "
            "It is not an official disaster warning system. "
            "Official government warnings and advisories remain authoritative."
        ),
    }
    _save_json(Path(Config.FLOOD_EVALUATION_PATH), summary)

    print()
    print("Training summary")
    print(f"  Best model: {best_name}")
    print(f"  Saved model: {Config.FLOOD_MODEL_PATH}")
    print(f"  Saved preprocessor: {Config.FLOOD_PREPROCESSOR_PATH}")
    print(f"  Evaluation: {Config.FLOOD_EVALUATION_PATH}")
    print(summary["disclaimer"])
    return summary


def main():
    train()


if __name__ == "__main__":
    main()
