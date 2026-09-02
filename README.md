# ADA Hackathon — Team 4

## Objective
Build a data-driven solution for the MTU policy challenge.

## Challenge
Document the problem, implement the pipeline, and analyze the results to
propose a measurable solution that can be presented to the jury.

## How to run the pipeline

### Requirements

- Python 3.14
- [`uv`](https://docs.astral.sh/uv/)
- Place the four source files, not version-controlled, in `data/raw/`:
  `transactions.parquet`, `customer_mtu.parquet`,
  `policy_events.parquet`, and `scam_reports.parquet`

Install the dependencies:

```bash
uv sync --default-index https://pypi.org/simple
```

### Full run

From the repository root:

```bash
uv run --frozen python -m pipeline run-all
```

This command cleans and validates the data, rebuilds the features, creates the
temporal split, trains the model, selects thresholds via validation, and runs
the final comparison on the test set.

### Staged run

```bash
# 1. Validate and clean the four Parquet files
uv run --frozen python -m pipeline clean

# 2. Rebuild MTD, enrich transactions, and create model_data
uv run --frozen python -m pipeline prepare

# 3. Create splits, train the model, and select thresholds on validation
uv run --frozen python -m pipeline train

# 4. Evaluate the test set against P-01–P-05 and the MTU-only baseline
uv run --frozen python -m pipeline evaluate
```

Each stage reuses the previous stage's output. To start from scratch, use
`run-all`.

### Outputs

The flow preserves the original Parquet files and writes:

- `data/processed/cleaned/`: validated sources and quality report.
- `data/processed/prepared/`: `master.parquet`, `model_data.parquet`, and MTU validation.
- `artifacts/splits/`: train (weeks 9–21), validation (22–23), test (24–26), IDs and checksums.
- `artifacts/fraud_model.joblib`: trained preprocessing and model.
- `artifacts/model_metadata.json`: features, medians, versions, metrics, and thresholds.
- `artifacts/evaluation.json`, `policy_comparison.csv`, and test predictions.

Split membership is deterministic by time; rows are not assigned at random.
`random_state=42` controls only the model's stochastic operations.

## Batch inference

The input must contain the transaction columns from the contract, including
the causal cumulative `mtd_volume_before_mxn`. The command rejects batches
lacking that history rather than reconstructing it from an incomplete window.

```bash
uv run --frozen python -m pipeline predict \
  --transactions data/processed/cleaned/transactions.parquet \
  --customers data/processed/cleaned/customer_mtu.parquet \
  --output artifacts/predictions.parquet
```

The output contains `fraud_score`, estimated risk in MXN, and the
`allow`/`warn`/`delay` decision.

## Verification

```bash
uv run --frozen pytest -q
```

## Index
- [`docs/`](docs/): architecture, decision log, and AI usage.
- [`pipeline/`](pipeline/): ingestion, training, evaluation, and inference code.
- [`analytics/`](analytics/): data contract, EDA, model, metrics, and data quality.
- [`dashboard/`](dashboard/): Amazon QuickSight link or screenshots.
- [`pitch/`](pitch/): material for the final presentation.
