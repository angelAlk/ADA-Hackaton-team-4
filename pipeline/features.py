from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .data import DataValidationError


NUMERIC_FEATURES = [
    "amount_mxn",
    "mtu_ratio",
    "ticket_ratio",
    "mtu_gap_ratio",
    "hour_of_day",
    "tenure_months",
]

BINARY_FEATURES = [
    "new_counterparty",
    "new_device",
    "geo_mismatch_flag",
    "is_weekend_flag",
    "prior_scam",
    "ch_spei_out",
    "ch_card_online",
    "ch_cash_out",
    "ch_p2p_nu",
    "ch_card_present",
    "risk_high",
    "risk_medium",
]

FEATURE_COLUMNS = NUMERIC_FEATURES + BINARY_FEATURES

CARRY_COLUMNS = [
    "txn_id",
    "customer_id",
    "txn_ts",
    "txn_week",
    "label",
    "loss_amount_mxn",
    "completed",
    "channel",
    "mtu_declared_mxn",
    "mtd_volume_before_mxn",
]

FORBIDDEN_FEATURES = {
    "customer_proceeded",
    "bypass_requested",
    "bypass_granted",
    "ops_contact_flag",
    "minutes_blocked",
    "action_taken",
    "rule_id",
    "loss_amount_mxn",
    "reported_ts",
}


def reconstruct_mtd(
    transactions: pd.DataFrame,
    *,
    completed_only: bool = False,
) -> pd.Series:
    required = {"customer_id", "txn_id", "txn_ts", "amount_mxn", "completed_flag"}
    missing = required - set(transactions.columns)
    if missing:
        raise DataValidationError(f"cannot reconstruct MTD; missing columns: {sorted(missing)}")

    ordered = transactions.sort_values(
        ["customer_id", "txn_ts", "txn_id"], kind="mergesort"
    ).copy()
    ordered["_month"] = ordered["txn_ts"].dt.to_period("M")
    if completed_only:
        ordered["_mtd_amount"] = ordered["amount_mxn"].where(
            ordered["completed_flag"], 0.0
        )
    else:
        ordered["_mtd_amount"] = ordered["amount_mxn"]

    grouped = ordered.groupby(
        ["customer_id", "_month"], sort=False, observed=True
    )["_mtd_amount"]
    reconstructed = (grouped.cumsum() - ordered["_mtd_amount"]).round(2)
    reconstructed.index = ordered.index
    return reconstructed.reindex(transactions.index)


def validate_mtd(transactions: pd.DataFrame, tolerance: float = 0.10) -> tuple[str, dict]:
    if "mtd_volume_before_mxn" not in transactions:
        raise DataValidationError("transactions: mtd_volume_before_mxn is required")

    supplied = transactions["mtd_volume_before_mxn"].astype(float)
    report: dict[str, dict] = {}
    candidates: dict[str, pd.Series] = {}
    for name, completed_only in (("all_transactions", False), ("completed_only", True)):
        candidate = reconstruct_mtd(transactions, completed_only=completed_only)
        delta = (candidate - supplied).abs()
        report[name] = {
            "mismatch_rows": int((delta > tolerance).sum()),
            "max_absolute_difference": float(delta.max()),
        }
        candidates[name] = candidate

    matching = [name for name, result in report.items() if result["mismatch_rows"] == 0]
    if not matching:
        raise DataValidationError(f"MTD reconstruction did not match supplied values: {report}")

    selected = "all_transactions" if "all_transactions" in matching else matching[0]
    report["selected_variant"] = selected
    return selected, report


def _guarded_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.div(denominator.where(denominator > 0))


def build_master(cleaned_dir: Path, output_dir: Path) -> tuple[pd.DataFrame, dict]:
    transactions = pd.read_parquet(cleaned_dir / "transactions.parquet")
    customers = pd.read_parquet(cleaned_dir / "customer_mtu.parquet")
    policy = pd.read_parquet(cleaned_dir / "policy_events.parquet")
    reports = pd.read_parquet(cleaned_dir / "scam_reports.parquet")

    if policy["txn_id"].duplicated().any() or reports["txn_id"].duplicated().any():
        raise DataValidationError("policy_events and scam_reports must be unique by txn_id")

    selected_variant, mtd_report = validate_mtd(transactions)
    reconstructed = reconstruct_mtd(
        transactions, completed_only=selected_variant == "completed_only"
    )
    transactions["mtd_volume_before_mxn"] = reconstructed

    expected_rows = len(transactions)
    master = transactions.merge(
        customers, on="customer_id", how="left", validate="many_to_one"
    )
    master = master.merge(policy, on="txn_id", how="left", validate="one_to_one")
    master = master.merge(
        reports, on="txn_id", how="left", validate="one_to_one", suffixes=("", "_report")
    )
    if len(master) != expected_rows or master["txn_id"].nunique() != expected_rows:
        raise DataValidationError("master join changed transaction grain")

    master["mtu_ratio"] = _guarded_ratio(
        master["mtd_volume_before_mxn"] + master["amount_mxn"],
        master["mtu_declared_mxn"],
    )
    master["ticket_ratio"] = _guarded_ratio(
        master["amount_mxn"], master["avg_ticket_90d_mxn"]
    )
    master["mtu_gap_ratio"] = _guarded_ratio(
        master["mtu_declared_mxn"], master["mtu_observed_p95_mxn"]
    )
    master["is_scam"] = master["confirmed_scam"].fillna(False).astype(bool)
    master["loss_amount_mxn"] = master["loss_amount_mxn"].fillna(0.0)

    output_dir.mkdir(parents=True, exist_ok=True)
    master.to_parquet(output_dir / "master.parquet", index=False)
    report = {
        "master_rows": len(master),
        "master_unique_transactions": int(master["txn_id"].nunique()),
        "mtd_validation": mtd_report,
    }
    (output_dir / "feature_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return master, report


def make_model_data(master: pd.DataFrame) -> pd.DataFrame:
    model_data = pd.DataFrame(index=master.index)
    model_data["txn_id"] = master["txn_id"]
    model_data["customer_id"] = master["customer_id"]
    model_data["txn_ts"] = pd.to_datetime(master["txn_ts"])
    model_data["txn_week"] = model_data["txn_ts"].dt.isocalendar().week.astype(int)
    model_data["label"] = master["is_scam"].astype(int)
    model_data["loss_amount_mxn"] = master["loss_amount_mxn"].fillna(0.0)
    model_data["completed"] = master["completed_flag"].astype(bool)
    model_data["channel"] = master["channel"]
    model_data["mtu_declared_mxn"] = master["mtu_declared_mxn"]
    model_data["mtd_volume_before_mxn"] = master["mtd_volume_before_mxn"]

    for column in NUMERIC_FEATURES:
        model_data[column] = master[column]
    model_data["new_counterparty"] = master["counterparty_first_seen_flag"].astype(int)
    model_data["new_device"] = master["device_new_flag"].astype(int)
    model_data["geo_mismatch_flag"] = (master["geo_state"] != master["home_state"]).astype(int)
    model_data["is_weekend_flag"] = master["is_weekend"].astype(int)
    model_data["prior_scam"] = master["prior_scam_report_flag"].astype(int)
    for channel in ("spei_out", "card_online", "cash_out", "p2p_nu", "card_present"):
        model_data[f"ch_{channel}"] = (master["channel"] == channel).astype(int)
    model_data["risk_high"] = (master["risk_segment"] == "high").astype(int)
    model_data["risk_medium"] = (master["risk_segment"] == "medium").astype(int)

    unexpected = FORBIDDEN_FEATURES.intersection(FEATURE_COLUMNS)
    if unexpected:
        raise AssertionError(f"forbidden model features configured: {sorted(unexpected)}")
    return model_data[CARRY_COLUMNS + FEATURE_COLUMNS].sort_values(
        ["txn_ts", "txn_id"], kind="mergesort"
    ).reset_index(drop=True)


def prepare_data(cleaned_dir: Path, output_dir: Path) -> tuple[pd.DataFrame, dict]:
    master, report = build_master(cleaned_dir, output_dir)
    model_data = make_model_data(master)
    model_data.to_parquet(output_dir / "model_data.parquet", index=False)
    report["model_data_rows"] = len(model_data)
    report["model_features"] = FEATURE_COLUMNS
    (output_dir / "feature_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return model_data, report


def add_features_for_inference(
    transactions: pd.DataFrame,
    customers: pd.DataFrame,
) -> pd.DataFrame:
    required_transactions = {
        "mtd_volume_before_mxn", "txn_id", "customer_id", "txn_ts", "amount_mxn",
        "channel", "counterparty_first_seen_flag", "device_new_flag", "geo_state",
        "hour_of_day", "is_weekend", "completed_flag",
    }
    required_customers = {
        "customer_id", "tenure_months", "mtu_declared_mxn",
        "mtu_observed_p95_mxn", "avg_ticket_90d_mxn",
        "prior_scam_report_flag", "risk_segment", "home_state",
    }
    missing_transactions = required_transactions - set(transactions.columns)
    missing_customers = required_customers - set(customers.columns)
    if missing_transactions:
        raise DataValidationError(
            "inference requires authoritative transaction history columns; "
            f"missing {sorted(missing_transactions)}"
        )
    if missing_customers:
        raise DataValidationError(
            f"inference customer table is missing {sorted(missing_customers)}"
        )
    if transactions["txn_id"].duplicated().any():
        raise DataValidationError("inference txn_id values must be unique")
    enriched = transactions.merge(
        customers, on="customer_id", how="left", validate="many_to_one"
    )
    if enriched["mtu_declared_mxn"].isna().any():
        raise DataValidationError("inference contains customers absent from customer_mtu")
    enriched["mtu_ratio"] = _guarded_ratio(
        enriched["mtd_volume_before_mxn"] + enriched["amount_mxn"],
        enriched["mtu_declared_mxn"],
    )
    enriched["ticket_ratio"] = _guarded_ratio(
        enriched["amount_mxn"], enriched["avg_ticket_90d_mxn"]
    )
    enriched["mtu_gap_ratio"] = _guarded_ratio(
        enriched["mtu_declared_mxn"], enriched["mtu_observed_p95_mxn"]
    )
    enriched["is_scam"] = False
    enriched["loss_amount_mxn"] = 0.0
    return make_model_data(enriched)
