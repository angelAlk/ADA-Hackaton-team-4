# Quality controls

| Control | Rule | Result | Action on failure |
| --- | --- | --- | --- |
| Schema | Required columns present | Met in 4 sources | Stop execution |
| Completeness | Required fields with no nulls | 0 nulls | Stop execution and report by column |
| Exact duplicates | Identical rows | 0 removed | Remove before validating keys |
| Primary keys | `txn_id`, `customer_id`, `event_id`, `report_id` unique | Met | Stop execution |
| Foreign keys | Events/reports exist in transactions; customers exist | 100% coverage | Stop execution |
| Master grain | One record per `txn_id` | 901,286 rows and unique IDs | Stop execution |
| MTU cumulative | Reconstruction excludes the current row and resets monthly | Variant using all transactions matches; maximum float32 difference MXN 0.0625 | Stop if it exceeds MXN 0.10 |
| Temporal split | Each ID belongs to exactly one set | 637,487 train; 104,959 validation; 158,840 test | Stop execution |
| Repeatability | SHA-256 of IDs per split is stable | Logged in `split_manifest.json` | Stop on unexpected change |
| Leakage | Features checked against allowlist | 18 allowed sources; post-action excluded | Stop tests |

Machine-readable details are written to
`data/processed/cleaned/quality_report.json`,
`data/processed/prepared/feature_report.json`, and
`artifacts/splits/split_manifest.json`.
