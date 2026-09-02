# Model

## Objective
Estimate the relative probability that a transaction ends up as a confirmed
scam report. The decision uses `fraud_score × amount_mxn` to express risk in
pesos and assign `allow`, `warn`, or `delay`.

## Approach
- Method: `GradientBoostingClassifier` with 300 estimators, depth 4,
  `learning_rate=0.05`, subsample 0.8, and `random_state=42`.
- Imbalance: positive-class weight computed exclusively on training data.
- Features: the 18 allowed by `data-contract.md`; each continuous feature
  gets median imputation fit on train plus a stable missingness indicator.
- Deterministic temporal split: train weeks 9–21, validation 22–23, and test
  weeks 24–26. IDs and checksums are kept in `artifacts/splits/`.
- Selection: risk thresholds in pesos are optimized only on validation. Test
  is opened a single time to compare the model, P-01–P-05, and the MTU
  baseline.

## Result
The metrics from the run are saved in `artifacts/model_metadata.json` and
`artifacts/evaluation.json`; PR-AUC is the primary metric. The
`artifacts/policy_comparison.csv` table applies the same costs and
effectiveness coefficients to all three policies.

Run from 2026-09-02:

| Set | PR-AUC | ROC-AUC | Base rate |
| --- | ---: | ---: | ---: |
| Train (9–21) | 0.1056 | 0.9297 | 0.2201% |
| Validation (22–23) | 0.1005 | 0.8705 | 0.2096% |
| Test (24–26) | 0.4133 | 0.9449 | 0.7863% |

Validation selected thresholds of MXN 1,000 to warn and MXN 4,300 to delay.
The result **is not ready for deployment**: the warning threshold landed at
the edge of the grid, the net value on validation was MXN -19,922, and on
test the warning rate reached 10.66%, above the 10% guardrail. The positive
net value observed on test is not used to retune thresholds because doing so
would contaminate the holdout.

On test, for reference:

| Policy | Recall | Estimated prevented loss | Net value |
| --- | ---: | ---: | ---: |
| Proposed model | 81.51% | MXN 2,115,898 | MXN 1,916,992 |
| P-01–P-05 | 6.89% | MXN 175,647 | MXN -384,689 |
| MTU only | 6.24% | MXN 168,526 | MXN -292,485 |

## Limitations

- The label means a scam that was completed, reported, and confirmed; it
  does not observe blocked fraud that was never reported.
- The weighted score preserves ranking quality but should not be
  interpreted as a calibrated probability without additional temporal
  calibration.
- Customer snapshots are static in the synthetic data. In production they
  must be replaced with point-in-time features to avoid future leakage.
- The `V_HORA`, `C_WARN`, and `C_OPS` costs are provisional, set by Product.
- The regime change in weeks 24–26 makes the test metrics a test of
  temporal generalization, not an i.i.d. estimate.
