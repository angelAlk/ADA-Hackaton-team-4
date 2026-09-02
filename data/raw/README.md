# Source data

Place the four Parquet files in this directory before running the pipeline:

- `transactions.parquet`
- `customer_mtu.parquet`
- `policy_events.parquet`
- `scam_reports.parquet`

The Parquet files are excluded from Git. Do not place processed data here; the
pipeline generates it under `data/processed/`.
