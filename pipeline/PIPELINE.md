# Pipeline Diagram

```mermaid
flowchart LR
    subgraph raw["Raw data (data/raw)"]
        T[transactions.parquet]
        C[customer_mtu.parquet]
    end

    T --> clean
    C --> clean
    clean["clean (data.clean_sources)\nvalidate + dedup + FK checks"] --> cleaned[(cleaned/*.parquet)]

    cleaned --> prepare
    prepare["prepare (features.prepare_data)\nreconstruct_mtd -> build_master -> make_model_data"] --> model_data[(model_data.parquet)]

    model_data --> split["temporal_split (split.py)"]
    split -->|train| train_set[(train)]
    split -->|validation| val_set[(validation)]
    split -->|test| test_set[(test)]

    train_set --> train
    val_set --> train
    train["train (model.train_model)\nbuild_estimator + optimize_thresholds"] --> artifacts[(artifacts/\nmodel.pkl, metadata.json,\nthreshold_search.csv)]

    test_set --> evaluate
    artifacts --> evaluate
    evaluate["evaluate (evaluation.evaluate_all)\nmodel vs current policy"] --> report[(evaluation report)]

    T -.->|new txns| predict
    C -.->|new customers| predict
    artifacts -.-> predict
    predict["predict (inference.predict_parquets)"] -.-> preds[(predictions.parquet)]
```

## Stages

- **clean** (`data.py::clean_sources`) — validates schemas/foreign keys, dedups, and removes nils from the raw `transactions` and `customer_mtu` tables.
- **prepare** (`features.py::prepare_data`) — reconstructs `mtu_ratio` from `mtd_volume_before_mxn` (`reconstruct_mtd`), joins the tables into a master frame (`build_master`), and derives the model-ready `model_data.parquet` (`make_model_data`).
- **split** (`split.py::temporal_split`) — splits `model_data` into train/validation/test by time, so no future transaction leaks into training.
- **train** (`model.py::train_model`) — fits the estimator (`build_estimator`) on `train`, then picks decision thresholds against `validation` (`evaluation.py::optimize_thresholds`); estimator + metadata are persisted under `artifacts/`.
- **evaluate** (`evaluation.py::evaluate_all`) — scores `test` with the saved model and compares the resulting policy actions against the current rule-based policy (`current_policy_actions` / `mtu_policy_actions`).
- **predict** (`inference.py::predict_parquets`) — separate, on-demand path: loads the saved model and scores fresh transactions/customers parquet files directly, without going through the train/evaluate split.

`run-all` in `cli.py` chains clean → prepare → train → evaluate.
