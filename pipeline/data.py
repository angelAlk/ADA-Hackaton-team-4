from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


class DataValidationError(ValueError):
    """Raised when a source violates the training data contract."""


@dataclass(frozen=True)
class TableSpec:
    primary_key: str
    required_columns: tuple[str, ...]
    timestamp_columns: tuple[str, ...] = ()
    expected_rows: int | None = None


TABLE_SPECS = {
    "transactions": TableSpec(
        "txn_id",
        (
            "txn_id", "customer_id", "txn_ts", "amount_mxn", "channel",
            "counterparty_id", "counterparty_first_seen_flag", "device_id",
            "device_new_flag", "geo_state", "hour_of_day", "is_weekend",
            "mtd_volume_before_mxn", "completed_flag",
        ),
        ("txn_ts",),
        901_286,
    ),
    "customer_mtu": TableSpec(
        "customer_id",
        (
            "customer_id", "tenure_months", "income_band", "mtu_declared_mxn",
            "mtu_observed_p95_mxn", "avg_ticket_90d_mxn",
            "prior_scam_report_flag", "risk_segment", "home_state",
        ),
        expected_rows=90_000,
    ),
    "policy_events": TableSpec(
        "event_id",
        (
            "event_id", "txn_id", "rule_id", "rule_description", "action_taken",
            "policy_holdout_flag", "mtu_breach_flag", "customer_proceeded",
            "bypass_requested", "bypass_granted", "ops_contact_flag",
            "minutes_blocked",
        ),
        expected_rows=37_925,
    ),
    "scam_reports": TableSpec(
        "report_id",
        (
            "report_id", "txn_id", "reported_ts", "confirmed_scam",
            "loss_amount_mxn", "report_channel",
        ),
        ("reported_ts",),
        4_272,
    ),
}


def _clean_table(
    frame: pd.DataFrame,
    name: str,
    *,
    enforce_expected_counts: bool,
) -> tuple[pd.DataFrame, dict]:
    spec = TABLE_SPECS[name]
    missing = sorted(set(spec.required_columns) - set(frame.columns))
    if missing:
        raise DataValidationError(f"{name}: missing required columns: {missing}")

    source_rows = len(frame)
    frame = frame.drop_duplicates().copy()
    exact_duplicates_removed = source_rows - len(frame)

    null_counts = frame.loc[:, spec.required_columns].isna().sum()
    null_counts = {column: int(count) for column, count in null_counts.items() if count}
    if null_counts:
        raise DataValidationError(f"{name}: nulls in required columns: {null_counts}")

    if frame[spec.primary_key].duplicated().any():
        examples = frame.loc[
            frame[spec.primary_key].duplicated(keep=False), spec.primary_key
        ].head(5).tolist()
        raise DataValidationError(
            f"{name}: duplicate primary key {spec.primary_key}; examples={examples}"
        )

    for column in spec.timestamp_columns:
        try:
            frame[column] = pd.to_datetime(frame[column]).dt.floor("us")
        except (TypeError, ValueError) as exc:
            raise DataValidationError(f"{name}: invalid timestamp column {column}") from exc

    if enforce_expected_counts and spec.expected_rows is not None and len(frame) != spec.expected_rows:
        raise DataValidationError(
            f"{name}: expected {spec.expected_rows:,} rows, found {len(frame):,}"
        )

    return frame, {
        "source_rows": source_rows,
        "clean_rows": len(frame),
        "exact_duplicates_removed": exact_duplicates_removed,
        "primary_key": spec.primary_key,
        "primary_key_unique": True,
        "required_nulls": 0,
    }


def validate_foreign_keys(tables: dict[str, pd.DataFrame]) -> dict:
    txn_ids = set(tables["transactions"]["txn_id"])
    customer_ids = set(tables["customer_mtu"]["customer_id"])
    missing_policy = int((~tables["policy_events"]["txn_id"].isin(txn_ids)).sum())
    missing_reports = int((~tables["scam_reports"]["txn_id"].isin(txn_ids)).sum())
    missing_customers = int((~tables["transactions"]["customer_id"].isin(customer_ids)).sum())
    failures = {
        "policy_events_missing_transactions": missing_policy,
        "scam_reports_missing_transactions": missing_reports,
        "transactions_missing_customers": missing_customers,
    }
    if any(failures.values()):
        raise DataValidationError(f"foreign-key validation failed: {failures}")
    return failures


def clean_sources(
    source_dir: Path,
    output_dir: Path,
    *,
    enforce_expected_counts: bool = True,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables: dict[str, pd.DataFrame] = {}
    report: dict = {"tables": {}}

    for name in TABLE_SPECS:
        source = source_dir / f"{name}.parquet"
        if not source.exists():
            raise FileNotFoundError(f"missing source table: {source}")
        tables[name], report["tables"][name] = _clean_table(
            pd.read_parquet(source),
            name,
            enforce_expected_counts=enforce_expected_counts,
        )

    report["foreign_keys"] = validate_foreign_keys(tables)
    for name, frame in tables.items():
        frame.to_parquet(output_dir / f"{name}.parquet", index=False)

    report_path = output_dir / "quality_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report
