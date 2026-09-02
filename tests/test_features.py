import pandas as pd
import pytest

from pipeline.data import DataValidationError
from pipeline.features import _guarded_ratio, reconstruct_mtd, validate_mtd


def transactions_fixture():
    return pd.DataFrame(
        {
            "txn_id": [2, 1, 3, 5, 4],
            "customer_id": [10, 10, 10, 10, 10],
            "txn_ts": pd.to_datetime(
                [
                    "2026-03-01 10:00:00",
                    "2026-03-01 10:00:00",
                    "2026-03-02 10:00:00",
                    "2026-03-03 10:00:00",
                    "2026-04-01 10:00:00",
                ]
            ),
            "amount_mxn": [20.0, 10.0, 30.0, 50.0, 40.0],
            "completed_flag": [True, True, False, True, True],
        }
    )


def test_mtd_excludes_current_resets_month_and_breaks_ties_by_id():
    frame = transactions_fixture()
    result = reconstruct_mtd(frame)
    assert result.tolist() == [10.0, 0.0, 30.0, 60.0, 0.0]


def test_mtd_validation_selects_all_transactions():
    frame = transactions_fixture()
    frame["mtd_volume_before_mxn"] = reconstruct_mtd(frame)
    variant, report = validate_mtd(frame)
    assert variant == "all_transactions"
    assert report["all_transactions"]["mismatch_rows"] == 0
    assert report["completed_only"]["mismatch_rows"] == 1


def test_mtd_validation_rejects_unexplained_values():
    frame = transactions_fixture()
    frame["mtd_volume_before_mxn"] = 999.0
    with pytest.raises(DataValidationError):
        validate_mtd(frame)


def test_ratios_return_null_for_nonpositive_denominators():
    result = _guarded_ratio(
        pd.Series([10.0, 10.0, 10.0]), pd.Series([2.0, 0.0, -1.0])
    )
    assert result.iloc[0] == 5.0
    assert result.iloc[1:].isna().all()
