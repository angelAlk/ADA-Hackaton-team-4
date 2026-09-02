import pandas as pd
import pytest

from pipeline.data import DataValidationError
from pipeline.features import add_features_for_inference


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
