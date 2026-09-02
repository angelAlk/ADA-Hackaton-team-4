# Architecture

```text
Raw Parquet
  → clean (schema, PK/FK, timestamps)
  → prepare (MTD, joins, features)
  → temporal split (train/validation/test + manifests)
  → train (imputer + GBM + artifact)
  → validation (thresholds and guardrails)
  → test evaluation (model vs P-01–P-05 vs MTU)
  → predict (score, MXN risk, decision)
```

## Components
- **`pipeline/data.py`:** validates and cleans without modifying sources.
- **`pipeline/features.py`:** rebuilds MTD, builds `master` and
  `model_data`, and applies the allowlist.
- **`pipeline/split.py`:** cuts by ISO week and persists IDs/checksums.
- **`pipeline/model.py`:** fits preprocessing and GBM; serializes with joblib.
- **`pipeline/evaluation.py`:** selects thresholds on validation and compares
  policies on test.
- **`pipeline/inference.py`:** validated batch API.
- **`pipeline/cli.py`:** orchestrates local stages via `python -m pipeline`.

Prepared data and run artifacts are git-ignored; code, lockfile, contract,
tests, and decisions are version-controlled.
