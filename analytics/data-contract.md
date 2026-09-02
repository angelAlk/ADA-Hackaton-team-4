# Data Contract

**Team 4 · Front B — MTU Policy**

This document defines **what is passed between the three areas, under what
names, what each thing means, and what is forbidden**. Its purpose is for
Product, BA, and Engineering to report the same numbers, and for no one to
have to guess the meaning of a column.

**Golden rule:** if a number appears in the pitch, the dashboard, or a
document, its definition is here. If it isn't here, it isn't reported.

---

## 1. Parties and responsibilities

| Area | Owners | Produces | Consumes |
| :---- | :---- | :---- | :---- |
| **Engineering** | Marco Polo Aguilar, Ricardo Ruelas, Angel Alcántara | `master` and `model_data` tables, ingestion pipeline | Feature specification (BA) |
| **Business Analyst** | Ricardo Alfredo Montes, Luis Antonio Domínguez, Francisco Bosch | Score, metrics, candidate thresholds | `model_data` (Eng.), business parameters (Product) |
| **Product** | Denisse Dix Cedeño | Cost parameters, final threshold decision | Metrics and trade-offs (BA) |

---

## 2. Sources of truth

Canonical location: `/Volumes/usr/<user>/<folder>/`

| File | Expected rows | Grain | Primary key |
| :---- | :---- | :---- | :---- |
| `transactions.parquet` | 901,286 | Transaction | `txn_id` |
| `customer_mtu.parquet` | 90,000 | Customer | `customer_id` |
| `policy_events.parquet` | 37,925 | Policy event | `event_id` |
| `scam_reports.parquet` | 4,272 | Report | `report_id` |

**Join keys:** `txn_id` (transaction ↔ policy ↔ report), `customer_id`
(transaction ↔ customer).

### 2.1 Load contract (mandatory)

The Parquet files contain `TIMESTAMP(NANOS)`, which is incompatible with
Databricks Runtime 11.3+. **Every load must go through truncation to
microseconds**:

```py
pdf = pd.read_parquet(path)
for col in pdf.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
    pdf[col] = pdf[col].dt.floor("us")
sdf = spark.createDataFrame(pdf)
```

Loading directly with `spark.read.parquet()` **fails**. This is not
optional.

### 2.2 Ingestion validations

Engineering guarantees, before delivering `master`:

- [ ] All four row counts match the table in §2
- [ ] 100% of `policy_events.txn_id` exists in `transactions`
- [ ] 100% of `scam_reports.txn_id` exists in `transactions`
- [ ] `txn_id` is unique in `transactions`; `customer_id` is unique in `customer_mtu`
- [ ] Joins do not duplicate rows (`master` must have exactly 901,286 rows)

---

## 3. Engineering → BA deliverable: `master` table

**Grain:** one row per transaction. **Rows:** 901,286. Construction:
`transactions` ⟕ `customer_mtu` ⟕ `policy_events` ⟕ `scam_reports`.

### 3.1 Derived features — normative definitions

These formulas are **the only valid definition**. If a number doesn't add
up between areas, it is checked against this table.

| Feature | Formula | Interpretation |
| :---- | :---- | :---- |
| `mtu_ratio` | `(mtd_volume_before_mxn + amount_mxn) / mtu_declared_mxn` | Fraction of the monthly ceiling that would be consumed **if** this transaction is authorized |
| `ticket_ratio` | `amount_mxn / avg_ticket_90d_mxn` | How many times the customer's usual ticket size |
| `mtu_gap_ratio` | `mtu_declared_mxn / mtu_observed_p95_mxn` | How inflated the declared ceiling is vs. actual behavior |
| `is_scam` | `coalesce(confirmed_scam, false)` | Target label |

**Conventions:**

- Every denominator is protected with `when(denominator > 0, ...)`; if it is
  zero or null, the result is `null`, **never 0**.
- `mtu_ratio` includes the current transaction **on purpose** — the
  decision happens before authorization, and the resulting state is what's
  evaluated.
- Nulls are imputed at the modeling layer (median + indicator), **not** when
  building `master`.

### 3.2 Reconstructing the monthly cumulative

`mtd_volume_before_mxn` is given in the Parquet file but **must be
validated** by reconstructing it. Specification:

```
val w = Window
  .partitionBy($"customer_id", year($"txn_ts"), month($"txn_ts"))  // resets each calendar month
  .orderBy($"txn_ts")                                              // respects temporal order
  .rowsBetween(Window.unboundedPreceding, -1)                      // EXCLUDES the current row
```

All three elements are mandatory. Using the default window would include the
current row and inflate the ratio.

**Open point:** it is not resolved whether transactions with
`completed_flag = false` should count toward the cumulative. Run both
variants and adopt the one that reproduces the original column. Document in
`decision-log.md`.

---

## 4. Engineering → BA deliverable: `model_data` table

**Grain:** one row per transaction. **Use:** score training and evaluation.

### 4.1 Allowed features (18)

**Continuous (6)** — median imputation + `<name>_missing` column:

| Feature | Source |
| :---- | :---- |
| `amount_mxn` | `transactions` |
| `mtu_ratio` | Derived §3.1 |
| `ticket_ratio` | Derived §3.1 |
| `mtu_gap_ratio` | Derived §3.1 |
| `hour_of_day` | `transactions` |
| `tenure_months` | `customer_mtu` |

**Binary (12)** — nulls filled with 0 (flag absence):

| Group | Features |
| :---- | :---- |
| Behavioral novelty | `new_counterparty`, `new_device` |
| Context | `geo_mismatch_flag`, `is_weekend_flag`, `prior_scam` |
| Channel (one-hot) | `ch_spei_out`, `ch_card_online`, `ch_cash_out`, `ch_p2p_nu`, `ch_card_present` |
| Segment | `risk_high`, `risk_medium` |

### 4.2 Carry-along columns (NOT features)

Needed to evaluate policies, forbidden as model input:

| Column | Purpose |
| :---- | :---- |
| `txn_id` | Traceability |
| `txn_ts`, `txn_week` | Temporal split |
| `label` | Target |
| `loss_amount_mxn` | Loss calculation during evaluation |
| `completed` | Context |
| `channel`, `mtu_declared_mxn`, `mtd_volume_before_mxn` | Replicating the current policy as a baseline |

> ⚠️ `loss_amount_mxn` is in the table but **not in `feature_cols`**.
> Including it would be direct target leakage.

### 4.3 Columns FORBIDDEN as features

These are **post-action**. Using them as score input is information leakage
and disqualifies the work:

| Column | Why |
| :---- | :---- |
| `customer_proceeded` | Only exists after showing the warning |
| `bypass_requested` | Only exists after imposing the delay |
| `bypass_granted` | Same |
| `ops_contact_flag` | Consequence of the action |
| `minutes_blocked` | Consequence of the action |
| `action_taken`, `rule_id` | Current policy's decision |

**Explicit and sole exception:** these columns **are** used to calibrate the
effectiveness coefficients in §6. They feed the **cost function**, never the
**model**. The distinction must be recorded in `decision-log.md`.

### 4.4 Discarded feature

`geo_mismatch_flag` is kept in the schema but **documented as having no
signal**: 5.0% in scams vs. 6.3% in legitimate transactions (slightly
inverted). Its exclusion from the final set is defensible and demonstrates
evidence-based selection.

---

## 5. Partition contract: temporal split

**Mandatory for all training and evaluation.** No one uses a random split.

| Set | Criterion | Rows | Scams | Base rate |
| :---- | :---- | :---- | :---- | :---- |
| Train | `txn_week <= 23` | 742,446 | 1,623 | **0.219%** |
| Test | `txn_week >= 24` | 158,840 | 1,249 | **0.786%** |

**Reason:** weeks 24–27 concentrate 44.5% of the scams (regime change). A
random split would leak the future into training and make "detecting" the
emerging pattern trivial.

> ⚠️ **The test base rate (0.786%) is NOT the global one (0.319%).** Any
> lift or guardrail calculation evaluated on test must use `y_test.mean()`.
> Using the global rate inflates lifts by 2.5x and hides that the current
> delay rules are below chance.

---

## 6. Shared parameters

### 6.1 Data-derived — owned by BA

Computed from `policy_events`. Not modified without recalculating.

| Parameter | Value | Source |
| :---- | :---- | :---- |
| `E_DELAY` | 0.758 | 1 − `bypass_granted` rate |
| `E_WARN` | 0.215 | 1 − `customer_proceeded` rate |
| `HRS` | 9.0 | Observed mean of `minutes_blocked` (543 min) |
| `P_OPS` | 0.34 | `ops_contact_flag` rate given delay |
| `BASE_RATE` | `y_test.mean()` | **Computed, never hardcoded** |

> `HRS = 9.0`, not 12. The nominal block is 12 hours but the actual average
> is lower because bypasses interrupt it.

### 6.2 Business judgments — owned by Product

These **do not come from the data**. Product sets and defends them.

| Parameter | Provisional value | Status |
| :---- | :---- | :---- |
| `V_HORA` | 10.0 MXN | ⏳ Pending confirmation |
| `C_WARN` | 2.0 MXN | ⏳ Pending confirmation |
| `C_OPS` | 50.0 MXN | ⏳ Pending confirmation |

**Reference for calibrating `V_HORA`:** the current policy delivers $3.76 of
prevented loss per hour of blocking a legitimate customer. If the business
values an hour above that figure, the current policy destroys net value.

**Constraint on `C_WARN`:** it must be strictly positive. With zero cost,
the optimizer degenerates to warning the entire population — confirmed
experimentally (it reached 88% of transactions).

---

## 7. Metrics dictionary

**Single source of truth.** Any reported figure uses these exact
definitions.

### 7.1 Loss terminology — critical

| Term | Definition | What it is NOT |
| :---- | :---- | :---- |
| `loss_exposure_*` | Sum of `loss_amount_mxn` in transactions where the policy acted | **Not** money saved |
| `loss_prevented_est` | `E_DELAY × delayed_exposure + E_WARN × warned_exposure` | An estimate, not a measurement |
| `loss_through` | Loss on transactions that were allowed |  |

> **Why it matters:** 100% of confirmed scams have `completed_flag = true`.
> "Exposure" is money **that was lost**, not money that was avoided.
> Confusing the two inflates the current policy's performance by 2.2x. Using
> "captured" or "saved" to refer to exposure is forbidden.

### 7.2 Performance metrics

| Metric | Formula |
| :---- | :---- |
| `recall` | (delayed scams + warned scams) / total scams |
| `recall_eff` | `(E_DELAY × delayed + E_WARN × warned) / total` |
| `prec_delay` | delayed scams / total delayed |
| `prec_warn` | warned scams / total warned |
| `lift_*` | `prec_* / BASE_RATE` — using the base rate **of the evaluated set** |
| `PR-AUC` | Primary model metric (not ROC-AUC — extreme minority class) |

### 7.3 Friction and value metrics

| Metric | Formula | Unit |
| :---- | :---- | :---- |
| `legit_delayed` | Legitimate customers delayed | people |
| `legit_hours_blocked` | `legit_delayed × HRS` | **hours** (never with a $ sign) |
| `cost` | `legit_delayed × (HRS × V_HORA + P_OPS × C_OPS) + legit_warned × C_WARN` | MXN |
| `net_value` | `loss_prevented_est − cost` | MXN |
| **North Star** | `loss_prevented_est / legit_hours_blocked` | **MXN per hour blocked** |

> **The North Star is a reporting metric, NOT the objective function.**
> Optimizing a ratio allows improving it by shrinking the denominator, which
> degenerates into warning everyone and blocking no one. Optimization is
> done on `net_value`.

---

## 8. Policy contract

### 8.1 Decision rule

```
risk_in_pesos = fraud_score × amount_mxn

risk < WARN_THRESHOLD                    → allow
WARN_THRESHOLD ≤ risk < DELAY_THRESHOLD   → warn
risk ≥ DELAY_THRESHOLD                    → delay
```

**Current values:** `WARN_THRESHOLD = 925 MXN`, `DELAY_THRESHOLD = 2,300 MXN`.

**Guaranteed property:** since `fraud_score ≤ 1`, no transaction under
$2,300 can be delayed, and none under $925 can be warned. The floor is
structural and does not depend on model quality.

> ⚠️ `fraud_score` **is not calibrated** (class weighting inflates the
> predicted probabilities). The ranking is valid; the "expected loss in
> pesos" reading is approximate. See `decision-log.md`.

### 8.2 Non-negotiable guardrails

Every proposed configuration must satisfy:

1. **No active zone falls below the base rate** of the evaluated set
2. **The warning zone does not exceed 10%** of transactions
3. **The optimum does not land at the edge of the search grid**
4. **Hours of blocking legitimate customers** are always reported; if they
   rise relative to the current policy, it is explicitly declared as a
   quantified trade-off

### 8.3 Mandatory comparison

Every proposal is evaluated against **two** references, on **the same test
rows** and with **the same effectiveness coefficients**:

1. Current policy (replica of P-01 through P-05)
2. MTU-only baseline (delay if `mtu_ratio ≥ 1`, warn if ≥ 0.85)

**Replica validation:** the reconstructed rules trigger on 4.9% of test
transactions vs. 4.2% observed in `policy_events`. Acceptable match.

---

## 9. Handoffs

| \# | From → To | Deliverable | Acceptance criterion |
| :---- | :---- | :---- | :---- |
| 1 | Eng → BA | `master` (901,286 rows) | Validations in §2.2 pass |
| 2 | BA → Eng | Feature specification §4.1 | Formulas in §3.1 implemented |
| 3 | Eng → BA | `model_data` with `txn_ts` and `txn_week` | No `na.fill(0)`; forbidden columns absent from `feature_cols` |
| 4 | BA → Product | Metrics §7 + comparison table §8.3 | Terminology in §7.1 respected |
| 5 | Product → BA | `V_HORA`, `C_WARN`, `C_OPS` | Values justified in writing |
| 6 | BA → Product | Optimal thresholds + frozen friction variant | Guardrails in §8.2 verified |
| 7 | All → repo | Documentation in `/docs` and `/analytics` | Numbers consistent between notebook and markdown |

---

## 10. Reproducibility rules

1. **Fixed seeds.** `random_state=42` in every stochastic component.
2. **No hand-written numbers in code.** Every figure is computed from
   variables. `caughtScams.toDouble / 4` is forbidden.
3. **Markdown summaries are updated after every re-run.** A summary that
   contradicts the cell above it is worse than no summary at all.
4. **Every assumption is documented in `decision-log.md`**, especially: MTU
   as the declared monthly limit, loss = transaction amount, and the
   exclusion of post-action columns.
5. **Changes to this contract are logged in §11.**

---

## 11. Change log

| Date | Change | Reason |
| :---- | :---- | :---- |
| Day 1 | Initial version | — |
| Day 1 | Load via pandas with truncation to µs | `TIMESTAMP(NANOS)` incompatible with Spark |
| Day 2 | Random split → temporal | Regime change in weeks 24–27 |
| Day 2 | Hardcoded `BASE_RATE` → `y_test.mean()` | Was hiding that the delay rules are below chance |
| Day 2 | Thresholds on probability → on expected loss | The decision must scale with the amount at risk |
| Day 2 | Ratio objective → net value | The ratio degenerated into warning 88% of the population |
| Day 2 | Terminology `captured` → `exposure` / `prevented_est` | Exposure is realized loss, not avoided loss |

---

## 12. Open points

| \# | Question | Owner |
| :---- | :---- | :---- |
| 1 | How much is an hour of blocking a legitimate customer worth? | Product |
| 2 | Do non-completed transactions count toward the monthly cumulative? | Engineering |
| 3 | Does `tenure_months` measure risk or propensity to report? | BA |
| 4 | Is blocking on an MTU breach a regulatory obligation (Art. 287 Bis) or discretionary? | Product |
| 5 | Are there counterparties that concentrate multiple victims (mule accounts)? | BA |
| 6 | Does isotonic score calibration improve net value? | BA |
