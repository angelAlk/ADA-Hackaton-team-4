# EDA — Exploratory Data Analysis

**Team 4 · Front B — Fraud, alert, and delay** **Challenge:** MTU policy to decide between allow, warn, or apply a delay **Dataset:** 4 Parquet files · ~1M rows · 120 days of transactions

---

## 1. Executive summary

| Finding | Evidence |
| :---- | :---- |
| The current policy catches 4.7% of scams | 135 of 2,872 confirmed |
| 99.8% of delays are false positives | 24,420 of 24,462 |
| The delay rules are **worse than chance** | Lift 0.62x and 0.41x vs. base rate |
| MTU is not the discriminating signal | `mtu_ratio` lift 1.5x vs. `device_new_flag` 10.2x |
| There is a regime change in weeks 24–27 | 44.5% of scams in 4 of ~20 weeks |
| "Captured loss" is **realized** loss | 100% of confirmed scams were completed |

---

## 2. Data inventory

| File | Rows | Columns | Grain | Key |
| :---- | :---- | :---- | :---- | :---- |
| `transactions.parquet` | 901,286 | 14 | One row per transaction | `txn_id` |
| `customer_mtu.parquet` | 90,000 | 9 | One row per customer | `customer_id` |
| `policy_events.parquet` | 37,925 | 12 | One row per policy event | `event_id`, FK `txn_id` |
| `scam_reports.parquet` | 4,272 | 6 | One row per report | `report_id`, FK `txn_id` |

### Referential integrity

| Join | Result | Reading |
| :---- | :---- | :---- |
| `transactions` ∩ `policy_events` | 37,925 / 37,925 | 100% of events have a transaction |
| `transactions` ∩ `scam_reports` | 4,272 / 4,272 | 100% of reports have a transaction |
| `policy_events` ∩ `scam_reports` | 161 | Transactions with a rule triggered AND a report |

No orphans. Joins on `txn_id` and `customer_id` are complete.

### Coverage

- **4.21%** of transactions triggered some policy rule (37,925 / 901,286)
- **0.47%** of transactions have an associated report (4,272 / 901,286)
- **2.32%** of transactions did not complete (20,902 / 901,286)

---

## 3. Schemas

### `transactions`

| Column | Type | Notes |
| :---- | :---- | :---- |
| `txn_id` | integer | PK |
| `customer_id` | integer | FK to `customer_mtu` |
| `txn_ts` | timestamp_ntz | Transaction time |
| `amount_mxn` | float | Amount |
| `channel` | string | `spei_out`, `card_online`, `cash_out`, `p2p_nu`, `card_present` |
| `counterparty_id` | integer | Destination — **not exploited, see §8** |
| `counterparty_first_seen_flag` | boolean | First time this customer transfers to this destination |
| `device_id` | integer | Device |
| `device_new_flag` | boolean | Device new to the customer |
| `geo_state` | string | Transaction state |
| `hour_of_day` | byte | 0–23 |
| `is_weekend` | boolean |  |
| `mtd_volume_before_mxn` | float | Month-to-date cumulative **before** this transaction |
| `completed_flag` | boolean | Whether the transaction completed |

### `customer_mtu`

| Column | Type | Notes |
| :---- | :---- | :---- |
| `customer_id` | long | PK |
| `tenure_months` | long | Account age |
| `income_band` | string | Income band |
| `mtu_declared_mxn` | double | **Declared monthly ceiling** — denominator of `mtu_ratio` |
| `mtu_observed_p95_mxn` | double | p95 of actual behavior |
| `avg_ticket_90d_mxn` | double | Average ticket, 90 days |
| `prior_scam_report_flag` | boolean | Prior report |
| `risk_segment` | string | `low`, `medium`, `high` |
| `home_state` | string | State of residence |

### `policy_events`

Contains `rule_id`, `rule_description`, `action_taken` (`delay` / `scam_alert` / `none`), `policy_holdout_flag`, `minutes_blocked`, `ops_contact_flag`, `customer_proceeded`, `bypass_requested`, `bypass_granted`, `mtu_breach_flag`.

> ⚠️ The last five are **post-action**. See §7.

### `scam_reports`

Contains `confirmed_scam` (boolean), `loss_amount_mxn` (double), `reported_ts` (timestamp), `report_channel` (`app` / `phone` / `chat`).

---

## 4. The target variable

| `confirmed_scam` | Count | Average loss | Total loss |
| :---- | :---- | :---- | :---- |
| `true` | 2,872 | $2,675.38 | $7,683,695.99 |
| `false` | 1,400 | $0.00 | $0.00 |

**Global base rate: 0.319%** (2,872 / 901,286) — imbalance of **313:1**.

### Loss distribution

| Statistic | Value |
| :---- | :---- |
| Mean | $2,675.38 |
| p25 | $731.89 |
| Median | $1,820.19 |
| p75 | $3,544.78 |
| p95 | $7,804.63 |
| Max | $35,175.18 |

| Loss range | Cases | Total loss | % of total |
| :---- | :---- | :---- | :---- |
| $0–500 | 495 | $139,360 | 1.8% |
| $500–1K | 445 | $329,238 | 4.3% |
| $1K–2K | 604 | $899,427 | 11.7% |
| $2K–5K | 891 | $2,828,409 | 36.8% |
| $5K–10K | 358 | $2,362,319 | 30.7% |
| $10K+ | 79 | $1,124,943 | 14.6% |

**15.2% of cases (≥$5K) concentrate 45.3% of losses.** This justifies
designing the policy around **expected loss** rather than probability
alone.

### Critical finding: loss equals amount

`avg_amount` of fraudulent transactions = **$2,675.38** `avg_loss` of
confirmed reports = **$2,675.38**

They are identical. The loss is the full transaction amount, so:

```
expected_loss = P(scam | x) × amount_mxn
```

A separate severity model is not required.

### Report channel

| Channel | Cases | Average loss |
| :---- | :---- | :---- |
| `app` | 1,641 | $2,678.42 |
| `phone` | 789 | $2,780.69 |
| `chat` | 442 | $2,476.10 |

No relevant differential signal between channels.

---

## 5. Diagnosis of the current policy

### By rule

| Rule | Description | Triggers | Action | Scams | Exposure | Min. blocked | Ops contacts |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| P-01 | `mtu_ratio` > 1.00 | 20,685 | delay | 41 | $300,673 | 11,232,671 | 6,607 |
| P-02 | `mtu_ratio` 0.85–1.00 | 9,802 | scam_alert | 68 | $335,451 | 0 | 0 |
| P-03 | Txn > 50% of MTU | 1,320 | scam_alert | 9 | $168,759 | 0 | 0 |
| P-04 | New counterparty + >30% MTU | 806 | scam_alert | 10 | $94,161 | 0 | 0 |
| P-05 | Cash out 00h–05h | 5,312 | delay | 7 | $4,829 | 2,862,777 | 1,734 |
| **Total** |  | **37,925** |  | **135** | **$903,873** | **14,095,448** | **8,341** |

### Precision and lift by rule

Base rate = 0.319%

| Rule | Precision | Lift | Action |
| :---- | :---- | :---- | :---- |
| P-04 | 1.241% | **3.89x** | warn |
| P-02 | 0.694% | 2.18x | warn |
| P-03 | 0.682% | 2.14x | warn |
| P-01 | 0.198% | **0.62x** | **delay** |
| P-05 | 0.132% | **0.41x** | **delay** |

**The inversion is total:** the three most precise rules only warn; the two
worst impose the 12-hour block. P-01 and P-05 have lift **below 1** — a
transaction flagged by them is *less* likely to be fraud than one picked at
random.

### Efficiency in the North Star currency

| Rule | Hours blocked | Exposure touched | MXN per hour blocked |
| :---- | :---- | :---- | :---- |
| P-01 | 187,211 | $300,673 | $1.61 |
| P-05 | 47,713 | $4,829 | **$0.10** |
| P-02/03/04 | 0 | $598,371 | — (no blocking) |

P-05 consumes 20% of all system friction to touch $4,829.

### Total friction cost

| Metric | Value |
| :---- | :---- |
| Legitimate customers delayed | 24,420 |
| Legitimate customers warned | 11,062 |
| **Hours of blocking to legitimate customers** | **234,831** (~26.8 customer-years) |
| Contacts to operations | 8,299 |
| Bypass requested / granted | 8,299 / 5,912 |
| Customers who proceeded despite the warning | 8,668 |

### Real effectiveness of the actions

| Action | Rate | Effectiveness |
| :---- | :---- | :---- |
| Warning | 78.5% proceed anyway | **21.5%** deterrence |
| Delay | 24.2% obtain a bypass | **75.8%** retention |
| Actual block duration | 543 min average | **9 hours**, not 12 |

### The holdout counterfactual

| Group | n | Scams | Rate |
| :---- | :---- | :---- | :---- |
| Holdout (rule triggered, no action) | 2,320 | 12 | 0.517% |
| Treated | 35,605 | 123 | 0.345% |

Implies a ~33% relative reduction: **~61 scams and ~$410K prevented**.

> ⚠️ With only 12 events, the 95% confidence interval of the holdout rate
> spans approximately 0.27%–0.91%, which **includes values below the
> treated rate**. This is the only causal estimate available, but it is
> directional, not conclusive.

---

## 6. Signal analysis

### Scam vs. legitimate comparison (full population)

| Feature | Scam (n=2,872) | Legitimate (n=898,414) | Lift |
| :---- | :---- | :---- | :---- |
| `device_new_flag` | 37.9% | 3.7% | **10.2x** |
| `counterparty_first_seen_flag` | 68.0% | 11.4% | **6.0x** |
| `ticket_ratio` | 4.15 | 1.38 | 3.0x |
| `prior_scam_report_flag` | 7.0% | 2.8% | 2.5x |
| `amount_mxn` | $2,675 | $1,527 | 1.8x |
| `mtu_ratio` | 0.291 | 0.194 | 1.5x |
| `hour_of_day` | 14.9 | 13.2 | weak |
| `is_weekend` | 28.1% | 29.2% | none |
| `geo_mismatch` | 5.0% | 6.3% | **none (inverted)** |

**Conclusion:** behavioral novelty signals (device and counterparty)
discriminate 4 to 7 times better than MTU. `geo_mismatch` is discarded — it
adds no signal.

### Precision of individual signals (Bayes)

| Signal | Volume if triggered alone | Precision | Lift |
| :---- | :---- | :---- | :---- |
| `device_new_flag` | 34,615 | **3.14%** | 9.9x |
| `counterparty_first_seen_flag` | 104,375 | 1.87% | 5.9x |
| P-04 (best current rule) | 806 | 1.24% | 3.9x |

A raw boolean new-device flag is **2.5x more precise than the best rule in
the current policy**, over a volume comparable to the entire policy.

### `mtu_ratio` distribution

| Statistic | Value |
| :---- | :---- |
| Mean | 0.194 |
| Median | 0.096 |
| p95 | 0.717 |
| **Max** | **5.248** |

> The maximum of 5.25 confirms that **MTU does not operate as a hard
> limit** in this dataset. If the ceiling blocked automatically,
> `mtu_ratio > 1` should not exist; yet 20,685 transactions exceed it. MTU
> functions as a monitoring threshold that triggers policy, not as a cap.
> Documented premise.

---

## 7. Data quality and identified pitfalls

### 7.1 Nanosecond timestamps

The Parquet files contain `TIMESTAMP(NANOS)`, not supported by Databricks
Runtime 11.3+. Direct reading fails with
`Illegal Parquet type: INT64 (TIMESTAMP(NANOS,false))`.

**Solution adopted:** load with pandas and truncate to microseconds before
converting to Spark.

```py
pdf[col] = pdf[col].dt.floor("us")
```

### 7.2 Post-action columns — forbidden as features

| Column | Why |
| :---- | :---- |
| `customer_proceeded` | Only exists after the warning is shown |
| `bypass_requested` / `bypass_granted` | Only exist after imposing the delay |
| `ops_contact_flag` | Consequence of the action |
| `minutes_blocked` | Consequence of the action |

**Important distinction:** these columns **cannot enter the model**, but
**should be used to calibrate each action's effectiveness** (that's where
the 21.5% and 75.8% come from). They are inputs to the cost function, not
the score.

### 7.3 Censored population

Scams successfully prevented **never become a report**. By construction,
the positive label only contains fraud that occurred and was reported.
Consequences:

- The negative class contains unreported scams → the measured precision is
  a **floor**, not the true value
- The policy's success is **unobservable** in the label → the holdout is
  the only valid estimator

### 7.4 "Captured loss" is not avoided loss

Verification run:

```
completed_flag | n     | total_loss
true           | 2,872 | 7,683,695.99
```

**100% of confirmed scams completed.** The $903,873 of "exposure touched"
is money that **was lost** on transactions where the policy triggered and
failed, not money saved.

> This result is partly tautological (for a loss to exist, the money had
> to leave), but it confirms the column's interpretation and requires
> renaming the metric.

### 7.5 Nulls

Null count in key features after joins: **0** in `mtu_ratio`,
`ticket_ratio`, `mtu_gap_ratio`, `tenure_months`, `prior_scam`,
`hour_of_day`.

Even so, the pipeline implements **median imputation + missing indicator
column** for robustness, instead of `na.fill(0)` — filling `mtu_ratio` with
0 would mean "consumed 0% of its ceiling," the safest possible value
assigned to an unknown.

### 7.6 Temporal leakage check

Dimension-table features (`prior_scam_report_flag`, `avg_ticket_90d_mxn`,
`mtu_observed_p95_mxn`) could be snapshots computed at the end of the
period, which would leak the future.

**Test:** scam rate among customers with `prior_scam = 1`, by week block:

| Block | Transactions | Scam rate |
| :---- | :---- | :---- |
| Weeks 1–12 | 4,696 | 0.0070 |
| Weeks 13–18 | 8,941 | 0.0068 |
| Weeks 19–23 | 7,456 | 0.0080 |

Stable. No evidence of leakage.

**Control test:** model trained without `prior_scam` or `tenure_months` →
ROC-AUC 0.9358 vs. 0.9458 for the full model. The drop is marginal,
confirming that the signal does not depend on those columns.

---

## 8. The emerging pattern: weeks 24–27

### Volume and severity by week

| Week | Reports | Total loss | Average loss |
| :---- | :---- | :---- | :---- |
| 9–23 (15 wks) | 1,592 | $3,146,564 | ~$1,977 |
| **24** | 314 | $1,063,553 | **$3,387** |
| **25** | 422 | $1,511,784 | **$3,582** |
| **26** | 425 | $1,560,274 | **$3,671** |
| **27** | 118 | $396,733 | **$3,362** |

**4 of ~20 weeks concentrate 44.5% of scams and 59% of losses.**

### Behavioral signature of the outbreak

| Metric | Weeks 9–23 | Weeks 24–27 |
| :---- | :---- | :---- |
| New counterparty | ~0.50 | **0.86–0.88** |
| New device | ~0.32 | **0.43–0.47** |
| Average hour | ~12.3 | **17.3–17.9** |
| Average amount | ~$1,900 | **$3,362–$3,671** |

The pattern is **behavioral, not volumetric**: near-universal use of
never-before-seen counterparties, shifted to afternoon-evening, at double
the usual ticket size.

### Why the current policy is blind

Rules P-01 through P-05 are **static thresholds on cumulative volume**. They
have no temporal or behavioral-novelty component, so they are structurally
incapable of detecting a regime change. Over these same weeks they capture
**6.9%** of the scams.

### High-value scams

| Metric | Value |
| :---- | :---- |
| Scams ≥ $5K | 437 |
| Caught by the policy | 69 (15.8%) |
| **Undetected** | **368** |
| Undetected loss | $2,760,571 |
| Concentration in `app` channel | 202 cases, $1,503,724 |

### Pending line of investigation

`counterparty_id` **has not been exploited**. The natural hypothesis for
the outbreak is **shared mule accounts** — multiple victims transferring to
the same counterparties. None of the five current rules look at that field.

Proposed query:

```
scamConfirmed
  .join(transactions.select("txn_id", "counterparty_id", "txn_ts"), Seq("txn_id"), "inner")
  .groupBy("counterparty_id")
  .agg(count("*").as("n_scams"), sum("loss_amount_mxn").as("total_loss"))
  .filter($"n_scams" > 1)
  .orderBy($"n_scams".desc)
```

> ⚠️ Any counterparty-history feature must be built with a **strictly
> causal** window (only reports available at the time of the transaction).
> `reported_ts` arrives with delay; using it without restriction produces
> leakage.

---

## 9. Modeling decisions derived from the EDA

| Decision | Justification (section) |
| :---- | :---- |
| **Temporal** split (weeks ≤23 / ≥24), not random | §8 — the regime change would make detection trivial with a random split |
| Thresholds on **expected loss**, not probability | §4 — loss equals the amount; 45% of losses in 15% of cases |
| Discard `geo_mismatch` | §6 — no signal, slightly inverted |
| Class weighting of 456:1 | §4 — global imbalance of 313:1, 456:1 on train |
| Exclude post-action columns from the model | §7.2 |
| Use post-action columns to calibrate effectiveness | §7.2, §5 |
| Report **PR-AUC**, not only ROC-AUC | §4 — extreme minority class |
| Guardrail: no zone below the base rate | §5 — P-01 and P-05 violate this today |

---

## 10. Known limitations

1. **The label is not "fraud," it is "fraud reported and confirmed."** The
   model learns propensity to report mixed with propensity to be scammed.
2. **`tenure_months` is the 3rd most important feature** — it has not been
   verified whether it is real risk or reporting behavior.
3. **The score is not calibrated.** Class weighting inflates the predicted
   probabilities. The ranking is valid (the transformation is monotonic),
   the peso-value interpretation is not.
4. **The causal estimate rests on 12 events.** Wide interval.
5. **`counterparty_id` unexploited.** Mule detection pending.
6. **Synthetic data** with intentional nulls and possible leakage declared
   by the challenge.

---

*Living document. Last updated after running on the full dataset (901,286
transactions).*
