#!/usr/env python

# Dedup and drop rows with nulls from the four d4_mtu parquet files,
# writing the cleaned result into data/d4_mtu/data/cleaned/. Originals
# are left untouched.

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "d4_mtu" / "data"
CLEANED_DIR = DATA_DIR / "cleaned"

FILES = [
    "customer_mtu.parquet",
    "policy_events.parquet",
    "scam_reports.parquet",
    "transactions.parquet",
]


def clean_file(name):
    path = DATA_DIR / name
    df = pd.read_parquet(path)
    before = len(df)
    df = df.drop_duplicates().dropna()
    after = len(df)

    CLEANED_DIR.mkdir(exist_ok=True)
    out_path = CLEANED_DIR / name
    df.to_parquet(out_path, index=False)

    print(f"{name}: {before} -> {after} rows -> {out_path.relative_to(DATA_DIR.parent)}")


def main():
    for name in FILES:
        clean_file(name)


if __name__ == "__main__":
    main()
