# Decision log

| Date | Decision | Context | Impact | Owner |
| --- | --- | --- | --- | --- |
| 2026-09-01 | Structure deliverables by area | Ease jury evaluation | Clear repository navigation | Team 4 |
| 2026-09-02 | Local pipeline in pandas and scikit-learn | The notebook depends on Databricks and personal paths | Training and inference runnable from CLI | Engineering |
| 2026-09-02 | Temporal split: train 9–21, validation 22–23, test 24–26 | Validation needed without contaminating the final regime shift | Hyperparameters and thresholds do not use test | Engineering/BA |
| 2026-09-02 | Reproducibility via cuts and IDs, not random sampling | A seed does not correctly define a temporal split | Manifests with IDs, counts, and SHA-256; seed 42 only for the model | Engineering |
| 2026-09-02 | All transactions add to the MTD | This variant reproduces the Parquet; excluding non-completed ones differs by up to MXN 241,882.60 | The reconstruction uses all amounts and excludes only the current row | Engineering |
| 2026-09-02 | MTU tolerance of MXN 0.10 | The source float32 cumulative differs by up to MXN 0.0625 due to representation | Storage-level differences are accepted, not semantic changes | Engineering |
| 2026-09-02 | Imputation fit exclusively on train | The notebook computed medians before the split | Prevents validation/test leakage and persists medians | Engineering |
| 2026-09-02 | Post-action columns excluded from the model | They only exist after the current policy is applied | Used only when deriving cost/effectiveness | Engineering/BA |
| 2026-09-02 | Thresholds selected on validation by net value | Optimizing on test produces an overly optimistic comparison | Test remains reserved for the final comparison | BA |
| 2026-09-02 | Inference requires causal `mtd_volume_before_mxn` | A partial batch cannot correctly reconstruct monthly history | Explicit failure when history is missing | Engineering |
