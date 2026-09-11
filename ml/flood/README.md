# NIDARS flood prediction module

This is a **college/research prototype and decision-support system**. It is **not** an official disaster warning system. Official government warnings and advisories remain authoritative.

Do not claim that the model predicts real-world floods with guaranteed accuracy. It has not been scientifically validated as an operational flood forecast.

## Dataset

**This repository does not include a trained model or a flood CSV.** Training will not invent samples.

Place a legitimate CSV at:

`data/raw/flood_data.csv`

See `data/README.md` for column definitions and source guidance. The training script **will not** create synthetic samples.

Target `flood_risk`:

- `0` = no / low flood event
- `1` = flood / risk event

If source columns differ, map them in `feature_schema.py`.

## Preprocessing

- Load with pandas
- Alias mapping, numeric coercion, duplicate drop
- Drop rows with invalid/missing target
- Median imputation **fit on the training split only** (no test leakage)
- No standardization (tree ensembles)

## Models

- Random Forest Classifier
- Gradient Boosting Classifier
- XGBoost is evaluated only if the package is already installed (optional, not required)

Selection criterion (in order): **recall**, then F1, then ROC-AUC. Accuracy is reported, not used for selection. Recall is prioritized because missed flood-risk events are more serious than extra warnings in this prototype.

## Training

From `C:\Users\DELL\NIDARS`:

```powershell
.\venv\Scripts\python.exe -m ml.flood.train
```

Artifacts:

- `ml/flood/model/flood_model.pkl`
- `ml/flood/model/flood_preprocessor.pkl`
- `ml/flood/model/evaluation.json`

## Prediction API

`POST /api/predict/flood` (login required)

Risk bands are **application UI thresholds**, not IMD/NDMA warning categories:

- 0.00–0.24 LOW
- 0.25–0.49 MODERATE
- 0.50–0.74 HIGH
- 0.75–1.00 CRITICAL

If artifacts are missing, the API returns `model_status: not_trained` and does not invent a probability.

## UI

`/flood-prediction` — authenticated form that calls the API.

## Limitations

- No dataset is bundled with the repository
- No GIS overlay or routing in this phase
- History rows store inputs and scores in `prediction_history.result_json` when a trained model actually scores a request
