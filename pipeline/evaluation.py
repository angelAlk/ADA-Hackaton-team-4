from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    roc_auc_score,
)

from .config import BusinessConfig


WARN_GRID = np.concatenate([np.arange(5, 100, 5), np.arange(100, 1001, 25)])
DELAY_GRID = np.concatenate([np.arange(50, 500, 25), np.arange(500, 5001, 100)])


def actions_from_thresholds(
    scores: np.ndarray,
    amounts: pd.Series | np.ndarray,
    warn_threshold: float,
    delay_threshold: float,
) -> tuple[np.ndarray, np.ndarray]:
    peso_risk = np.asarray(scores) * np.asarray(amounts)
    actions = np.where(
        peso_risk >= delay_threshold,
        "delay",
        np.where(peso_risk >= warn_threshold, "warn", "allow"),
    )
    return actions, peso_risk


def current_policy_actions(frame: pd.DataFrame) -> np.ndarray:
    mtu_ratio = frame["mtu_ratio"].fillna(0).to_numpy()
    amount = frame["amount_mxn"].to_numpy()
    declared = frame["mtu_declared_mxn"].fillna(np.inf).to_numpy()
    channel = frame["channel"].to_numpy()
    hour = frame["hour_of_day"].to_numpy()
    new_counterparty = frame["new_counterparty"].fillna(0).astype(bool).to_numpy()

    p01 = mtu_ratio >= 1.00
    p02 = (mtu_ratio >= 0.85) & (mtu_ratio < 1.00)
    p03 = amount >= 0.50 * declared
    p04 = new_counterparty & (amount >= 0.30 * declared)
    p05 = (channel == "cash_out") & (hour >= 0) & (hour <= 5)
    actions = np.full(len(frame), "allow", dtype="<U5")
    actions[p02 | p03 | p04] = "warn"
    actions[p01 | p05] = "delay"
    return actions


def mtu_policy_actions(frame: pd.DataFrame) -> np.ndarray:
    ratio = frame["mtu_ratio"].fillna(0).to_numpy()
    return np.where(ratio >= 1.0, "delay", np.where(ratio >= 0.85, "warn", "allow"))


def evaluate_policy(
    actions: np.ndarray,
    frame: pd.DataFrame,
    name: str,
    business: BusinessConfig,
) -> dict:
    labels = frame["label"].astype(bool).to_numpy()
    losses = frame["loss_amount_mxn"].fillna(0).to_numpy()
    base_rate = float(labels.mean())
    delayed = actions == "delay"
    warned = actions == "warn"
    allowed = actions == "allow"
    scam_delayed = delayed & labels
    scam_warned = warned & labels
    scam_allowed = allowed & labels
    legit_delayed = int((delayed & ~labels).sum())
    legit_warned = int((warned & ~labels).sum())
    delayed_count = int(delayed.sum())
    warned_count = int(warned.sum())

    precision_delay = float(scam_delayed.sum() / delayed_count) if delayed_count else 0.0
    precision_warn = float(scam_warned.sum() / warned_count) if warned_count else 0.0
    exposure_delay = float(losses[scam_delayed].sum())
    exposure_warn = float(losses[scam_warned].sum())
    prevented = (
        business.delay_effectiveness * exposure_delay
        + business.warning_effectiveness * exposure_warn
    )
    cost = (
        legit_delayed
        * (
            business.blocked_hours * business.hour_value_mxn
            + business.ops_contact_probability * business.ops_cost_mxn
        )
        + legit_warned * business.warning_cost_mxn
    )
    positives = int(labels.sum())
    legit_hours = legit_delayed * business.blocked_hours
    return {
        "policy": name,
        "rows": len(frame),
        "base_rate": base_rate,
        "scams_delayed": int(scam_delayed.sum()),
        "scams_warned": int(scam_warned.sum()),
        "scams_through": int(scam_allowed.sum()),
        "recall": float((scam_delayed.sum() + scam_warned.sum()) / positives)
        if positives
        else 0.0,
        "recall_effective": float(
            (
                business.delay_effectiveness * scam_delayed.sum()
                + business.warning_effectiveness * scam_warned.sum()
            )
            / positives
        )
        if positives
        else 0.0,
        "precision_delay": precision_delay,
        "precision_warn": precision_warn,
        "lift_delay": precision_delay / base_rate if base_rate else 0.0,
        "lift_warn": precision_warn / base_rate if base_rate else 0.0,
        "loss_exposure_delayed_mxn": exposure_delay,
        "loss_exposure_warned_mxn": exposure_warn,
        "loss_prevented_est_mxn": prevented,
        "loss_through_mxn": float(losses[scam_allowed].sum()),
        "legit_delayed": legit_delayed,
        "legit_warned": legit_warned,
        "legit_hours_blocked": legit_hours,
        "cost_mxn": cost,
        "net_value_mxn": prevented - cost,
        "north_star_mxn_per_legit_hour": prevented / legit_hours if legit_hours else 0.0,
        "pct_delayed": delayed_count / len(frame),
        "pct_warned": warned_count / len(frame),
        "guardrails": {
            "delay_at_or_above_base_rate": delayed_count == 0
            or precision_delay >= base_rate,
            "warn_at_or_above_base_rate": warned_count == 0 or precision_warn >= base_rate,
            "warn_share_at_or_below_10pct": warned_count <= 0.10 * len(frame),
        },
    }


def optimize_thresholds(
    frame: pd.DataFrame,
    scores: np.ndarray,
    business: BusinessConfig,
) -> tuple[dict, pd.DataFrame]:
    candidates: list[dict] = []
    for warn_threshold in WARN_GRID:
        for delay_threshold in DELAY_GRID:
            if delay_threshold <= warn_threshold:
                continue
            actions, _ = actions_from_thresholds(
                scores, frame["amount_mxn"], warn_threshold, delay_threshold
            )
            metrics = evaluate_policy(actions, frame, "candidate", business)
            guardrails = metrics["guardrails"]
            if not all(guardrails.values()):
                continue
            candidates.append(
                {
                    "warn_threshold_mxn": float(warn_threshold),
                    "delay_threshold_mxn": float(delay_threshold),
                    "net_value_mxn": metrics["net_value_mxn"],
                    "loss_prevented_est_mxn": metrics["loss_prevented_est_mxn"],
                    "pct_warned": metrics["pct_warned"],
                    "pct_delayed": metrics["pct_delayed"],
                }
            )
    if not candidates:
        raise ValueError("no threshold configuration satisfies the policy guardrails")
    results = pd.DataFrame(candidates).sort_values(
        "net_value_mxn", ascending=False
    ).reset_index(drop=True)
    best = results.iloc[0].to_dict()
    best["grid_edge"] = bool(
        best["warn_threshold_mxn"] in {float(WARN_GRID.min()), float(WARN_GRID.max())}
        or best["delay_threshold_mxn"]
        in {float(DELAY_GRID.min()), float(DELAY_GRID.max())}
    )
    best["deployment_ready"] = bool(
        not best["grid_edge"] and best["net_value_mxn"] > 0
    )
    return best, results


def model_score_metrics(frame: pd.DataFrame, scores: np.ndarray) -> dict:
    labels = frame["label"].astype(int).to_numpy()
    predicted = scores >= 0.5
    tn, fp, fn, tp = confusion_matrix(labels, predicted, labels=[0, 1]).ravel()
    base_rate = float(labels.mean())
    return {
        "pr_auc": float(average_precision_score(labels, scores)),
        "roc_auc": float(roc_auc_score(labels, scores)),
        "brier_score": float(brier_score_loss(labels, scores)),
        "mean_score": float(np.mean(scores)),
        "mean_score_to_base_rate": float(np.mean(scores) / base_rate)
        if base_rate
        else None,
        "confusion_at_0_5": {
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
            "true_positive": int(tp),
        },
    }


def evaluate_all(
    frame: pd.DataFrame,
    scores: np.ndarray,
    thresholds: dict,
    business: BusinessConfig,
    output_dir: Path,
) -> dict:
    proposed, peso_risk = actions_from_thresholds(
        scores,
        frame["amount_mxn"],
        thresholds["warn_threshold_mxn"],
        thresholds["delay_threshold_mxn"],
    )
    current = current_policy_actions(frame)
    mtu = mtu_policy_actions(frame)
    comparisons = [
        evaluate_policy(proposed, frame, "proposed_model", business),
        evaluate_policy(current, frame, "current_p01_p05", business),
        evaluate_policy(mtu, frame, "mtu_only", business),
    ]
    report = {
        "model": model_score_metrics(frame, scores),
        "thresholds_selected_on_validation": thresholds,
        "policy_comparison": comparisons,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "evaluation.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    pd.json_normalize(comparisons).to_csv(output_dir / "policy_comparison.csv", index=False)
    predictions = frame[["txn_id", "txn_ts", "label", "amount_mxn"]].copy()
    predictions["fraud_score"] = scores
    predictions["peso_risk_mxn"] = peso_risk
    predictions["proposed_action"] = proposed
    predictions["current_policy_action"] = current
    predictions["mtu_only_action"] = mtu
    predictions.to_parquet(output_dir / "test_predictions.parquet", index=False)
    return report
