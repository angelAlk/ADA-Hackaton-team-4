# Pipeline Diagram

```mermaid
flowchart LR
    subgraph raw["Raw data (data/raw)"]
        T[transactions.parquet]
        C[customer_mtu.parquet]
        P[policy_events.parquet]
        S[scam_reports.parquet]
    end

    T --> clean
    C --> clean
    P --> clean
    S --> clean
    clean["clean (data.clean_sources)\nschema, PK/FK, null and row-count checks"] --> cleaned[(data/processed/cleaned)]

    cleaned --> prepare
    prepare["prepare (features.prepare_data)\nreconstruct_mtd -> build_master -> make_model_data"] --> model_data[(model_data.parquet)]
    prepare --> master[(master.parquet)]

    model_data --> split["temporal_split (split.py)"]
    split -->|train| train_set[(train)]
    split -->|validation| val_set[(validation)]
    split -->|test| test_set[(test)]

    train_set --> train
    val_set --> train
    train["train (model.train_model)\nfit preprocessing and GBM"] --> optimize["optimize_thresholds\nvalidation only"]
    optimize --> artifacts[(artifacts/\nfraud_model.joblib\nmodel_metadata.json\nthreshold_search.csv)]

    test_set --> evaluate
    artifacts --> evaluate
    evaluate["evaluate (evaluation.evaluate_all)\nmodel vs P-01–P-05 vs MTU-only"] --> report[(evaluation.json\npolicy_comparison.csv\ntest_predictions.parquet)]

    T -.->|new txns| predict
    C -.->|new customers| predict
    artifacts -.-> predict
    predict["predict (inference.predict_parquets)"] -.-> preds[(predictions.parquet)]
```

## Stages

- **clean** (`data.py::clean_sources`) — validates all four raw tables, including schemas, expected row counts, primary/foreign keys, required nulls, exact duplicates, and timestamp precision. Contract violations stop the pipeline; required nulls are not silently removed.
- **prepare** (`features.py::prepare_data`) — reconstructs and validates `mtd_volume_before_mxn`, calculates guarded ratios, joins all four tables into `master.parquet`, applies the feature allowlist, and writes `model_data.parquet`.
- **split** (`split.py::temporal_split`) — deterministically splits `model_data` into train (weeks 9–21), validation (22–23), and test (24–26). It persists row-ID manifests and SHA-256 checksums.
- **train** (`model.py::train_model`) — fits train-only median imputation, stable missing indicators, class weighting, and the gradient-boosted classifier with `random_state=42`.
- **threshold selection** (`evaluation.py::optimize_thresholds`) — chooses peso-risk warning and delay thresholds only on validation and records deployment guardrails.
- **evaluate** (`evaluation.py::evaluate_all`) — scores untouched test rows and compares the proposed model with both the current P-01–P-05 policy and the MTU-only baseline using identical business assumptions.
- **predict** (`inference.py::predict_parquets`) — separate, on-demand path: loads the saved model and scores fresh transactions/customers parquet files directly, without going through the train/evaluate split.

`run-all` in `cli.py` chains clean → prepare → train → evaluate.
