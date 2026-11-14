# Dataset and measurement contract

All data are simulated. Timestamps are UTC ISO 8601 without a suffix (`YYYY-MM-DDTHH:MM:SS`), with uniform second precision; this convention makes SQLite string comparisons safe here. Real pipelines should normalize timezones explicitly. Amounts are integer USD cents. All user and transaction IDs are synthetic.

| Table | Grain / intended key | Columns and meaning |
|---|---|---|
| users | One row / user_id | `user_id`; `device` (mobile/desktop); `customer_type` (new/returning), both measured before assignment |
| assignments | Raw assignment delivery; exact duplicates possible | `user_id`; `variant` (control/new); `assigned_at` |
| checkout_events | One tracked event / event_id | `event_id`; `user_id`; `event_type` (checkout_started/checkout_completed); `event_at` |
| orders | One order / order_id | `order_id`; `user_id`; `ordered_at`; `amount_cents`; `status` (paid/cancelled) |
| refunds | One ledger entry / refund_id | `refund_id`; `order_id`; `refunded_at`; `amount_cents`; multiple rows may represent one order's split refund |
| user_analysis | One assigned user / user_id | Assignment fields, user attributes and windowed outcomes below |

## Analysis fields

- `started_checkout`: any checkout_started event in the user's seven-day window, 0/1; descriptive, not the primary denominator.
- `converted`: at least one eligible paid order, 0/1.
- `order_count`: count of eligible paid orders, including repeat orders.
- `gross_cents`: sum of eligible paid order value, including subsequently refunded orders.
- `refund_cents`: sum of eligible refund ledger amounts on eligible orders.
- `net_cents`: gross minus observed refund cents; does not include other costs.
- `any_refund`: any positive eligible refund on an eligible order, 0/1.

## Windows and eligibility

All 24,000 unique assigned users are eligible, including those without checkout events or orders. Enrollment: January 1 at 00:00 through January 29 at 00:00 UTC, exclusive. Order window: assignment inclusive, assignment + 7 days exclusive. Refund window: order time inclusive, order + 30 days exclusive, and only for eligible orders. Administrative extract: March 7, 2026 00:00 UTC. Thus the latest possible user has fully mature purchase and refund windows.

Purchase conversion measures whether a paid purchase occurred, even if later refunded. Refunds affect the refund guardrail and revenue after refunds, not the binary purchase conversion.

## Designed data-quality cases

There are 24 exact duplicate assignment records, introduced as ingestion artifacts after generation. Orders also include paid records before assignment, paid records on day 8, and cancelled records inside the window. Some refunds have two ledger records. These cases test deduplication, temporal eligibility, payment status and join fan-out. The simulation contains no assignment conflicts; the analysis fails if a user appears in multiple variants or with multiple assignment times. The regression suite tests exactly day 7, exactly day 30, the last eligible second and inclusion at assignment. Source schemas enforce keys and allowed categories; Python also validates timestamps and ledger consistency.

## Synthetic data-generating process

Seed: 314159; 24,000 independent users. Device is mobile with probability 0.67 and customer type returning with probability 0.30. Independent Bernoulli randomization follows attribute generation; the checked-in treatment probability of 0.50 is in `measurement.expected_treatment_share`. Assignment time is uniform over 28 days.

Seven-day buyer probability is 0.112 + 0.026 × returning + 0.016 × desktop + 0.006 × treatment. Buyers always start checkout; nonbuyers start with probability 0.40. Buyers have one eligible order plus another with probability 0.08. Order value is lognormal with log-location log(78) and log-scale 0.75, rounded to cents. Eligible order times are uniform between 120 seconds and seven days after assignment. Per-order refund probability is 0.080 in control and 0.088 in treatment; 80% of refunds are full and 20% half value. Refund time is uniform within 30 days. Twenty percent of refunds split into two entries at the same timestamp.

The observed group rates need not equal these probabilities. The generation metadata are disclosed for reproducibility, not used as if they were observable business evidence. There are no external raw-data downloads or personal records.

## Configuration and derived exports (version 2)

`config.json` records simulation provenance, expected treatment share, observation windows, extract date, inference settings, illustrative margins and planning assumptions. SQLite `experiment_config` contains one row (id=1) with purchase_days, refund_days and extract_at used by the analysis SQL. The data generator uses the configured treatment share; with the checked-in 0.50 value, assignment is independent Bernoulli 50:50.

`results/bootstrap_draws.csv` contains 10,000 rows of gross and after-refund new-minus-control revenue differences, one row per resample. `results/window_sensitivity.csv` contains descriptive point estimates only for 1-, 3- and 7-day windows on the same assigned users; it has no confidence intervals or hypothesis tests and must not be used to select the best-looking window. `results/exploratory_balance.csv` contains pre-assignment attribute shares and standardized differences; it does not contain subgroup treatment-effect claims. `results/metrics.json` stores all unrounded estimates, the revenue bridge, planning scenarios and decision gates.
