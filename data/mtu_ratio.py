#!/usr/env python

# Validate/reconstruct MTD and add the guarded MTU ratio.

from pathlib import Path
import json
import sys

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.config import PipelineConfig
from pipeline.features import reconstruct_mtd, validate_mtd


def add_mtu_ratio() -> tuple[Path, dict]:
    config = PipelineConfig()
    transactions = pd.read_parquet(config.cleaned_dir / "transactions.parquet")
    customer_mtu = pd.read_parquet(config.cleaned_dir / "customer_mtu.parquet")
    variant, report = validate_mtd(transactions)
    transactions["mtd_volume_before_mxn"] = reconstruct_mtd(
        transactions, completed_only=variant == "completed_only"
    )

    df = transactions.merge(
        customer_mtu[["customer_id", "mtu_declared_mxn"]],
        on="customer_id",
        how="left",
        validate="many_to_one",
    )
    df["mtu_ratio"] = (
        (df["mtd_volume_before_mxn"] + df["amount_mxn"])
        / df["mtu_declared_mxn"].where(df["mtu_declared_mxn"] > 0)
    )

    aggregated_dir = config.aggregated_dir
    aggregated_dir.mkdir(exist_ok=True)
    out_path = aggregated_dir / "transactions_mtu_ratio.parquet"
    df.to_parquet(out_path, index=False)
    (aggregated_dir / "mtu_validation.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return out_path, report


def main():
    out_path, report = add_mtu_ratio()
    print(f"{out_path.name}: {out_path}")
    print(f"MTD variant: {report['selected_variant']}")


if __name__ == "__main__":
    main()
