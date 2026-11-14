# Should we launch the new checkout?

**CONTINUE TESTING — CONDITIONAL ON FEASIBILITY.** Conversion is promising; revenue and refund safety remain unresolved. Retain the existing checkout. Treat this as an inconclusive pilot and assess whether a fresh, independently planned test is economically feasible.

**Clearly labeled simulation:** 24,000 fictional users, 50:50 random assignment, 7-day paid-order window and 30-day refund follow-up. All outcomes are mature.

| Metric | Control | New checkout | Difference [95% CI] |
|---|---:|---:|---:|
| Assigned users | 11,911 | 12,089 | SRM p = 0.251 |
| Purchase conversion | 12.86% | 13.45% | +0.59 pp [-0.27 pp to +1.44 pp] |
| Gross revenue / user | $14.87 | $14.81 | -$0.06 [-$1.45 to $1.27] |
| After-refund revenue / user | $13.58 | $13.30 | -$0.28 [-$1.59 to $0.98] |
| Refunded-user rate | 1.24% | 1.46% | +0.21 pp [-0.08 pp to +0.51 pp] |

## What the evidence means

Conversion rises by +0.59 pp, or +4.57% relative (relative 95% CI: -2.01% to +11.60%). Its interval includes no improvement. The refund estimate is higher, but that difference is also uncertain. Revenue and refund intervals do not rule out unacceptable harm at the illustrative margins.

The revenue bridge reconciles the after-refund difference: conversion contributes +$0.66/user, order frequency -$0.19, basket value -$0.53, and additional refunds -$0.22. This is descriptive arithmetic, not causal mediation; rounded contributions may not sum exactly.

## What would change the decision?

Launch candidate only when conversion lower 95% bound > 0, after-refund revenue/user lower bound > -$0.25, and refunded-user rate upper bound < +0.30 pp. All must clear at an agreed analysis. Current gates cleared: 0/3. These margins are illustrative and require stakeholder agreement; they were not historically preregistered.

Conversion planning needs approximately 49,838 users per arm for +0.60 pp at 80% power. **Revenue safety needs about 644,548 per arm under zero true loss**, using the $0.25 margin and pilot variance. At 50,000 per arm its approximate power is only 12%. If the true revenue difference equaled the observed -$0.28, it would be below the safety boundary; more data would not make it safe.

Agree on economic tolerance, test cost and available traffic. Use a fresh independent confirmatory test only if feasible; otherwise retain the existing checkout and redesign. The planning calculations are approximate powers for each individual criterion, not a joint 80% probability of passing all gates. Do not extend the pilot until a favorable unadjusted interval appears.

## Trust and limitations

Assignment counts are 11,911 vs 12,089; SRM p=0.251. 24 exact duplicate deliveries are removed. No conflicting assignments; all 20,842 nonbuyers remain. Independent Python reconciles every SQL analysis row, including order windows, refunds and checkout events.

Proportions use Wilson/Newcombe intervals; revenue uses 10,000 within-arm user bootstrap resamples. Individual 95% intervals do not have joint 95% coverage. Repeated checking and many subgroup comparisons can inflate false positives. Buyer-only refund rates are descriptive because treatment changes who buys. After-refund revenue is not profit. The simulation omits real-world instrumentation errors, fraud, seasonality, spillovers and long-term effects.

See [the two-page PDF](experiment-readout.pdf), [visual readout](readout.html), [methodology](docs/METHODOLOGY.md), and [reproduction guide](README.md).
