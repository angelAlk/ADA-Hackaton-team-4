from __future__ import annotations

from pathlib import Path

import pandas as pd

from .data import DataValidationError
from .evaluation import actions_from_thresholds
from .features import FEATURE_COLUMNS, add_features_for_inference
from .model import load_model


def predict(
    transactions: pd.DataFrame,
    customers: pd.DataFrame,
    artifacts_dir: Path,
) -> pd.DataFrame:
    estimator, metadata = load_model(artifacts_dir)
    thresholds = metadata.get("decision_thresholds")
    if not thresholds:
        raise DataValidationError("model metadata has no validation-selected thresholds")

    model_data = add_features_for_inference(transactions, customers)
    scores = estimator.predict_proba(model_data[FEATURE_COLUMNS])[:, 1]
    actions, peso_risk = actions_from_thresholds(
        scores,
        model_data["amount_mxn"],
        thresholds["warn_threshold_mxn"],
        thresholds["delay_threshold_mxn"],
    )
    result = model_data[["txn_id", "txn_ts", "amount_mxn"]].copy()
    result["fraud_score"] = scores
    result["peso_risk_mxn"] = peso_risk
    result["decision"] = actions
    return result


def predict_parquets(
    transactions_path: Path,
    customers_path: Path,
    artifacts_dir: Path,
    output_path: Path,
) -> pd.DataFrame:
    transactions = pd.read_parquet(transactions_path)
    customers = pd.read_parquet(customers_path)
    result = predict(transactions, customers, artifacts_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output_path, index=False)
    return result


def predict_one(transaction: dict, customer: dict, artifacts_dir: Path) -> dict:
    transactions = pd.DataFrame([transaction])
    customers = pd.DataFrame([customer])
    result = predict(transactions, customers, artifacts_dir)
    row = result.iloc[0]
    return {
        "txn_id": int(row["txn_id"]),
        "txn_ts": row["txn_ts"].isoformat(),
        "amount_mxn": float(row["amount_mxn"]),
        "fraud_score": float(row["fraud_score"]),
        "peso_risk_mxn": float(row["peso_risk_mxn"]),
        "decision": str(row["decision"]),
    }
