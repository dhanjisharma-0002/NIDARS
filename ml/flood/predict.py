"""Load the persisted flood model and score a validated feature row."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ml.flood.feature_schema import FEATURE_COLUMNS, risk_level_from_probability


def model_files_exist(model_path, preprocessor_path):
    return Path(model_path).is_file() and Path(preprocessor_path).is_file()


def _ensure_real_artifact(file_path):
    """Ensure artifact is actual binary data; downloads from GitHub LFS media storage if pointer."""
    p = Path(file_path)
    if not p.is_file():
        return p
    try:
        with open(p, "rb") as f:
            header = f.read(40)
        if header.startswith(b"version https://git-lfs") or p.stat().st_size < 300:
            import tempfile
            import urllib.request

            tmp_dir = Path(tempfile.gettempdir())
            cached_file = tmp_dir / f"lfs_{p.name}"
            if cached_file.is_file() and cached_file.stat().st_size > 300:
                return cached_file

            parts = list(p.parts)
            if "ml" in parts:
                rel_parts = parts[parts.index("ml") :]
                rel_url_path = "/".join(rel_parts)
            else:
                rel_url_path = f"ml/flood/model/{p.name}"

            media_url = f"https://media.githubusercontent.com/media/dhanjisharma-0002/NIDARS/main/{rel_url_path}"
            req = urllib.request.Request(media_url, headers={"User-Agent": "NIDARS-ML-Loader/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            with open(cached_file, "wb") as f_out:
                f_out.write(data)
            return cached_file
    except Exception:
        pass
    return p


def load_artifacts(model_path, preprocessor_path):
    if not model_files_exist(model_path, preprocessor_path):
        return None, None
    import joblib

    resolved_model = _ensure_real_artifact(model_path)
    resolved_prep = _ensure_real_artifact(preprocessor_path)

    model = joblib.load(resolved_model)
    preprocessor = joblib.load(resolved_prep)
    return model, preprocessor


def predict_flood_probability(cleaned_features, model, preprocessor):
    frame = pd.DataFrame([cleaned_features], columns=FEATURE_COLUMNS)
    transformed = preprocessor.transform(frame)
    if hasattr(model, "predict_proba"):
        probability = float(model.predict_proba(transformed)[0][1])
    else:
        probability = float(model.predict(transformed)[0])
    probability = min(1.0, max(0.0, probability))
    return probability


def format_prediction(probability, low_max, moderate_max, high_max):
    return {
        "flood_probability": round(probability, 4),
        "risk_level": risk_level_from_probability(
            probability, low_max=low_max, moderate_max=moderate_max, high_max=high_max
        ),
    }
