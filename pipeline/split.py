from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from .config import SplitConfig
from .data import DataValidationError


def _id_checksum(ids: pd.Series) -> str:
    ordered = ids.astype("int64").sort_values().astype(str)
    return hashlib.sha256("\n".join(ordered).encode()).hexdigest()


def temporal_split(
    model_data: pd.DataFrame,
    config: SplitConfig,
    output_dir: Path,
) -> tuple[dict[str, pd.DataFrame], dict]:
    if model_data["txn_id"].duplicated().any():
        raise DataValidationError("model_data txn_id must be unique before splitting")

    masks = {
        "train": model_data["txn_week"] <= config.train_max_week,
        "validation": model_data["txn_week"].between(
            config.validation_min_week, config.validation_max_week
        ),
        "test": model_data["txn_week"] >= config.test_min_week,
    }
    membership_count = sum(mask.astype(int) for mask in masks.values())
    if not (membership_count == 1).all():
        bad = model_data.loc[membership_count != 1, ["txn_id", "txn_week"]].head()
        raise DataValidationError(f"split cutoffs overlap or leave gaps:\n{bad}")

    output_dir.mkdir(parents=True, exist_ok=True)
    splits: dict[str, pd.DataFrame] = {}
    metadata: dict = {
        "strategy": "deterministic_temporal_iso_week",
        "random_seed_used_for_membership": False,
        "cutoffs": {
            "train_max_week": config.train_max_week,
            "validation_min_week": config.validation_min_week,
            "validation_max_week": config.validation_max_week,
            "test_min_week": config.test_min_week,
        },
        "splits": {},
    }

    for name, mask in masks.items():
        frame = model_data.loc[mask].sort_values(
            ["txn_ts", "txn_id"], kind="mergesort"
        ).reset_index(drop=True)
        if frame.empty:
            raise DataValidationError(f"{name} split is empty")
        splits[name] = frame
        frame.to_parquet(output_dir / f"{name}.parquet", index=False)
        frame[["txn_id"]].to_parquet(output_dir / f"{name}_txn_ids.parquet", index=False)
        metadata["splits"][name] = {
            "rows": len(frame),
            "positives": int(frame["label"].sum()),
            "base_rate": float(frame["label"].mean()),
            "min_week": int(frame["txn_week"].min()),
            "max_week": int(frame["txn_week"].max()),
            "min_timestamp": frame["txn_ts"].min().isoformat(),
            "max_timestamp": frame["txn_ts"].max().isoformat(),
            "txn_id_sha256": _id_checksum(frame["txn_id"]),
        }

    (output_dir / "split_manifest.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    )
    return splits, metadata
