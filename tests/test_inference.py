import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from pipeline.config import ModelConfig, PipelineConfig
from pipeline.data import DataValidationError
from pipeline.features import BINARY_FEATURES, NUMERIC_FEATURES, add_features_for_inference
from pipeline.inference import predict_one
from pipeline.model import save_model, train_model


def test_inference_rejects_missing_mtd_history():
    transactions = pd.DataFrame(
        {
            "txn_id": [1],
            "customer_id": [10],
            "txn_ts": pd.to_datetime(["2026-06-01"]),
        }
    )
    customers = pd.DataFrame({"customer_id": [10]})
    with pytest.raises(DataValidationError, match="authoritative transaction history"):
        add_features_for_inference(transactions, customers)


def _model_frame(rows=40):
    data = {}
    for index, column in enumerate(NUMERIC_FEATURES):
        data[column] = np.arange(rows, dtype=float) + index
    for index, column in enumerate(BINARY_FEATURES):
        data[column] = ((np.arange(rows) + index) % 2).astype(int)
    data["label"] = (np.arange(rows) % 5 == 0).astype(int)
    return pd.DataFrame(data)


def test_predict_one_returns_a_json_serializable_decision(tmp_path):
    config = replace(
        PipelineConfig(artifacts_dir=tmp_path),
        model=ModelConfig(n_estimators=3, max_depth=2, min_samples_leaf=1),
    )
    estimator, metadata = train_model(_model_frame(), _model_frame(20), config)
    metadata["decision_thresholds"] = {
        "warn_threshold_mxn": 100.0,
        "delay_threshold_mxn": 500.0,
    }
    save_model(estimator, metadata, tmp_path)

    transaction = {
        "txn_id": 1,
        "customer_id": 10,
        "txn_ts": "2026-06-01T10:00:00",
        "amount_mxn": 1500.0,
        "channel": "spei_out",
        "counterparty_first_seen_flag": True,
        "device_new_flag": True,
        "geo_state": "CDMX",
        "hour_of_day": 14,
        "is_weekend": False,
        "mtd_volume_before_mxn": 2000.0,
        "completed_flag": True,
    }
    customer = {
        "customer_id": 10,
        "tenure_months": 12,
        "mtu_declared_mxn": 5000.0,
        "mtu_observed_p95_mxn": 4000.0,
        "avg_ticket_90d_mxn": 800.0,
        "prior_scam_report_flag": False,
        "risk_segment": "medium",
        "home_state": "CDMX",
    }

    result = predict_one(transaction, customer, tmp_path)

    assert result["txn_id"] == 1
    assert result["decision"] in {"allow", "warn", "delay"}
    assert isinstance(result["fraud_score"], float)
    json.dumps(result)
