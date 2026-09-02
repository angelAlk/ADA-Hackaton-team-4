import numpy as np
import pandas as pd

from pipeline.config import BusinessConfig
from pipeline.evaluation import (
    actions_from_thresholds,
    current_policy_actions,
    evaluate_policy,
    mtu_policy_actions,
)


def policy_frame():
    return pd.DataFrame(
        {
            "mtu_ratio": [1.0, 0.85, 0.2, 0.2, 0.2],
            "amount_mxn": [100, 100, 60, 31, 10],
            "mtu_declared_mxn": [100, 100, 100, 100, 100],
            "channel": ["p2p_nu", "p2p_nu", "p2p_nu", "p2p_nu", "cash_out"],
            "hour_of_day": [12, 12, 12, 12, 5],
            "new_counterparty": [0, 0, 0, 1, 0],
            "label": [1, 0, 1, 0, 1],
            "loss_amount_mxn": [100, 0, 60, 0, 10],
        }
    )


def test_policy_boundaries_and_delay_precedence():
    frame = policy_frame()
    assert current_policy_actions(frame).tolist() == [
        "delay", "warn", "warn", "warn", "delay"
    ]
    assert mtu_policy_actions(frame).tolist() == [
        "delay", "warn", "allow", "allow", "allow"
    ]


def test_expected_loss_thresholds_are_inclusive():
    actions, risk = actions_from_thresholds(
        np.array([0.5, 0.5, 0.5]), np.array([20, 40, 10]), 10, 20
    )
    assert risk.tolist() == [10, 20, 5]
    assert actions.tolist() == ["warn", "delay", "allow"]


def test_policy_metrics_report_cost_and_guardrails():
    frame = policy_frame()
    metrics = evaluate_policy(
        mtu_policy_actions(frame), frame, "mtu", BusinessConfig()
    )
    assert metrics["scams_delayed"] == 1
    assert metrics["legit_warned"] == 1
    assert metrics["cost_mxn"] > 0
    assert set(metrics["guardrails"]) == {
        "delay_at_or_above_base_rate",
        "warn_at_or_above_base_rate",
        "warn_share_at_or_below_10pct",
    }
