#!/usr/env python

# Merge cleaned transactions with cleaned customer_mtu and add mtu_ratio,
# writing the result into data/d4_mtu/data/aggregated/transactions_mtu_ratio.parquet.
# mtu_ratio = (mtd_volume_before_mxn + amount_mxn) / mtu_declared_mxn

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "d4_mtu" / "data"
CLEANED_DIR = DATA_DIR / "cleaned"
AGGREGATED_DIR = DATA_DIR / "aggregated"

TRANSACTIONS_FILE = "transactions.parquet"
CUSTOMER_MTU_FILE = "customer_mtu.parquet"
OUT_FILE = "transactions_mtu_ratio.parquet"


def add_mtu_ratio():
    transactions = pd.read_parquet(CLEANED_DIR / TRANSACTIONS_FILE)
    customer_mtu = pd.read_parquet(CLEANED_DIR / CUSTOMER_MTU_FILE)

    df = transactions.merge(
        customer_mtu[["customer_id", "mtu_declared_mxn"]],
        on="customer_id",
        how="left",
    )
    df["mtu_ratio"] = (df["mtd_volume_before_mxn"] + df["amount_mxn"]) / df["mtu_declared_mxn"]

    AGGREGATED_DIR.mkdir(exist_ok=True)
    out_path = AGGREGATED_DIR / OUT_FILE
    df.to_parquet(out_path, index=False)

    print(f"{OUT_FILE}: {len(df)} rows -> {out_path.relative_to(DATA_DIR.parent)}")


def main():
    add_mtu_ratio()


if __name__ == "__main__":
    main()
