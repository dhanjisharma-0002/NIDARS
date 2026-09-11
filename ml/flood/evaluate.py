"""Model evaluation helpers for flood classification."""

from __future__ import annotations

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def evaluate_classifier(model, x_test, y_test):
    y_pred = model.predict(x_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }
    if hasattr(model, "predict_proba") and len(set(y_test)) > 1:
        y_score = model.predict_proba(x_test)[:, 1]
        metrics["roc_auc"] = float(roc_auc_score(y_test, y_score))
    else:
        metrics["roc_auc"] = None
    return metrics


def selection_score(metrics):
    """
    Primary criterion: recall (missed flood-risk events are costly).
    Ties: F1, then ROC-AUC (missing AUC treated as 0).
    Accuracy is reported but not used to pick the model.
    """
    recall = metrics.get("recall") or 0.0
    f1 = metrics.get("f1") or 0.0
    auc = metrics.get("roc_auc") or 0.0
    return (recall, f1, auc)
