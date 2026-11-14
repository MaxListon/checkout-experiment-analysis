# Measurement, inference and decision specification

This accompanies a **simulated pilot**. It is not historical preregistration. Seed 314159, the draw sequence and source data are preserved from version 1. Thresholds are illustrative business assumptions to agree with stakeholders before any real confirmation.

## 1. Design and estimands

Unit of assignment, analysis and resampling: user. Independent Bernoulli assignment at the configured 50:50 treatment share; 24,000 users enrolled January 1–28, 2026. Attributes precede assignment. The estimand compares assignment policies (intention-to-treat), not treatment completers or successful buyers.

Primary: probability of at least one paid order in [assignment, assignment + 7 days). Secondary economic outcomes: gross paid-order value per assigned user and that value minus eligible refunds. Refund safety: probability of any positive refund on an eligible order per assigned user. Refunds count in [order, order + 30 days); full windows mature by the March 7 00:00 UTC extract. A later refund does not erase the original purchase conversion.

All assigned users remain. Conditioning on checkout starts, exposure completion or purchases can create post-treatment selection. The buyer-only refund rate is therefore descriptive. Stable identities, independent units, full logging and no spillovers are assumed; production audits must assess these.

## 2. Data contracts and SQL

`00_schema.sql` enforces keys, non-null values, allowed categories, positive integer cents and referential integrity. `quality.py` validates normalized timestamps, extract boundaries, complete follow-up, refunds after paid orders and total refunds no greater than their order amount. Exact duplicate assignment deliveries are allowed; conflicting variants or assignment timestamps stop the analysis.

The SQL also fails closed on assignment conflicts, missing user records and incomplete maturity. It deduplicates with `SELECT DISTINCT` after the gate, rather than resolving conflicts with `MIN`. Refunds aggregate to orders before orders aggregate to users. The final left joins and zero-filled outcomes retain nonbuyers. A unique index enforces user grain.

A separate Python implementation reconstructs order, refund and checkout-start outcomes for every user and reconciles with SQL. The behavioral tests cover exact cutoff timestamps, before-assignment orders, cancellation, repeat orders, split refunds, duplicated ingestion, crossed assignments, missing keys, malformed timestamps, post-extract records and over-refunds. These checks raise exceptions even if Python is run with optimization flags; they do not depend on removable assertions.

## 3. Proportion inference

Group conversion intervals use 95% Wilson score limits. For count x, sample size n, proportion p=x/n and z=1.9599639845:

- center = (p + z²/(2n)) / (1 + z²/n)
- half-width = z × sqrt(p(1−p)/n + z²/(4n²)) / (1 + z²/n)

Absolute conversion and assigned-user refund differences use Newcombe's hybrid-score method for independent proportions (method 10). Let p1−p0=d and Wilson limits be [L1,U1], [L0,U0]:

- lower = d − sqrt((p1−L1)² + (U0−p0)²)
- upper = d + sqrt((U1−p1)² + (p0−L0)²)

Relative conversion change is p1/p0−1. Use SE(log RR)=sqrt(1/x1−1/n1+1/x0−1/n0), form the normal log-scale interval, then exponentiate and subtract one. Zero-event relative intervals are reported as unavailable rather than dividing by zero; absolute intervals still work.

Confidence intervals describe long-run coverage, not a 95% probability assigned to a fixed parameter. A zero-crossing interval does not establish no effect, equivalence or safety. The individual intervals do not have simultaneous 95% coverage.

## 4. Revenue inference and sensitivity

Use 10,000 independent within-arm user bootstrap resamples (seed 271828). Each resample has the arm's original sample size; each selected user carries their complete aggregate outcome, including zero revenue and repeat orders. Gross and after-refund revenue share sampled indices within each arm. Take the 2.5th and 97.5th percentiles of new-minus-control mean differences.

This accommodates skew without assuming normally distributed individual revenue. It remains an approximate, sample-dependent interval and does not resolve unseen-tail or dependence problems. No trimming or winsorization was performed. `results/bootstrap_draws.csv` makes intervals independently reconstructible. An unpooled normal mean-difference interval is included as a sensitivity check, using sqrt(s0²/n0+s1²/n1); it reaches the same qualitative conclusion on this pilot.

The top 1% of users account for roughly a quarter of gross revenue, illustrating why uncertainty is substantial. Outliers are retained because they are legitimate synthetic orders, not known errors.

## 5. Allocation and exploratory diagnostics

Pearson chi-square goodness-of-fit uses unique assigned users, with expected counts from 50:50 allocation. For one degree of freedom, the survival probability is erfc(sqrt(chi-square/2)). Flag p < 0.001 for investigation. SRM is a quality diagnostic, not an outcome test; an unflagged result does not prove correct exposure delivery or tracking.

Device and customer-type summaries use pre-assignment attributes. Standardized difference for each binary attribute is (p1−p0)/sqrt((p0(1−p0)+p1(1−p1))/2). No subgroup efficacy claims are made.

The 1-, 3- and 7-day tables reuse the same frozen source data and denominator. They report point estimates only, without confidence intervals or hypothesis tests. Treat them as exploratory measurement-window diagnostics, not sequential interim looks or candidate windows to select after viewing outcomes. In the simulation, order timing is simplified, so do not infer real checkout timing behavior from these differences. The configured purchase window remains the primary definition.

## 6. Revenue bridge

Gross revenue per assigned user = conversion × orders per buyer × average order value. Replacing all three control factors with treatment factors exactly reconstructs the observed gross difference. To avoid privileging one replacement order, average each factor's marginal contribution over all six orders (a three-factor Shapley arithmetic decomposition). Subtract the difference in refund dollars per assigned user to reconcile the after-refund difference.

These components are descriptive accounting contributions. They have no separate significance claims and are not causal mediation effects: the experiment can change the composition of buyers, and factor estimates are correlated. Rounded dollar labels may not add exactly; unrounded values reconcile to machine precision.

## 7. Decision rule

Default illustrative criteria:

1. Conversion lower two-sided 95% bound > 0.
2. After-refund revenue/user lower 95% bound > −$0.25.
3. Refunded-user risk-difference upper 95% bound < +0.30 percentage points.

All pass → **launch candidate**, subject to operational readiness. If the conversion upper bound is ≤0, the revenue upper bound is below −$0.25, or the refund lower bound is above +0.30 pp → **reject or redesign**. Otherwise → **continue testing, conditional on feasibility**. An SRM flag overrides outcome interpretation with an allocation investigation. Data-contract violations stop result generation.

Requiring all gates is a conjunctive rule rather than choosing whichever metric looks positive. It does not provide simultaneous interval coverage or guarantee 80% joint power. Approximate bootstrap coverage also limits exact error-control claims. In production, agree on the rule and economic margins in advance, not after seeing which thresholds are convenient.

## 8. Next-test feasibility, not just conversion power

All figures below are first-order normal-approximation scenarios based on pilot estimates. No traffic, budget or cost estimate is invented.

Conversion planning uses p0=0.12862, p1=p0+0.006, two-sided alpha .05 and power .80. Per-arm sample:

`ceil((z(.975)*sqrt(2*pbar*(1-pbar)) + z(.80)*sqrt(p0*(1-p0)+p1*(1-p1)))**2 / effect**2)`

This gives **49,838 per arm**. It addresses conversion alone.

For safety, a two-sided 95% CI boundary corresponds to one-sided alpha .025. With equal n per arm, variance sum V and assumed true effect at distance D from the unsafe boundary:

`n ≈ ceil((z(.975)+z(.80))**2 * V / D**2)`

For revenue, V=s0²+s1² in USD² and D=assumed treatment effect + loss margin. Pilot V is about 5,132.48. Under zero true revenue change, the $0.25 margin needs **644,548 per arm**. At 50,000 per arm, power is only **11.9%**, using `Phi(D/sqrt(V/n) − z(.975))`. At a true effect equal to the pilot's −$0.2815, D≤0; no finite sample provides 80% power to establish the proposed safety claim.

For refunds, V=p0(1−p0)+p1(1−p1), using the control pilot risk and an assumed new risk; D=allowed increase − assumed increase. The +0.30 pp margin needs about **21,404 per arm** under no increase, **50,069** under +0.10 pp, and **278,063** under the pilot point estimate. This simple Wald planning approximation does not exactly invert the Newcombe analysis test. A real design should simulate its operating characteristics, including the full launch rule, after assumptions and margins are fixed.

The safety scenarios are not retrospective “observed power” presented as additional evidence for or against an effect. They are explicit future-design assumptions. Current uncertainty is conveyed by confidence intervals. Pilot effects and variances are uncertain, so scenario precision must not be mistaken for known traffic requirements.

Agree on economic loss tolerance, implementation/test cost, traffic capacity and a sample cap. If confirmation is unaffordable, retain the existing checkout and redesign. Loosening a margin solely to make a test pass is not a valid business justification.

## 9. Repeated checking and subgroup fishing

A fresh independent confirmatory experiment is recommended if feasible. Do not append users to this inspected pilot until an ordinary fixed-horizon interval becomes positive. If continuous efficacy monitoring is required, choose a valid sequential design with defined error control before starting. Operational data-quality monitoring is distinct from optional efficacy stopping.

Searching many device/customer/date slices raises the chance of accidental positives. A significant result in one slice and a non-significant result in another is not evidence of an interaction. Specify a small hypothesis family, test interactions, apply suitable multiplicity control and confirm selected patterns independently. No subgroup is used to rescue this inconclusive overall result.

## 10. Limitations and references

Simulation omits missing logs, identity loss, bots/fraud, failures, seasonality, novelty, interference, chargebacks, profit margin, taxes, implementation costs and long-term customer outcomes. After-refund revenue is not profit. There is no actual retailer or production launch.

- [NIST: difference of proportions confidence intervals](https://itl.nist.gov/div898/software/dataplot/refman1/auxillar/diffprop.htm) — independent proportion-difference inference.
- [NIST: confidence intervals for a proportion](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm) — Wilson score intervals.
- [Microsoft Research: diagnosing sample ratio mismatch](https://www.microsoft.com/en-us/research/articles/diagnosing-sample-ratio-mismatch-in-a-b-testing/) — assignment-quality diagnostics.
- [Efron: the jackknife, bootstrap and other resampling plans](https://statistics.stanford.edu/technical-reports/jackknife-bootstrap-and-other-resampling-plans-0) — resampling foundations.

The sources inform methodology; all experiment records are generated locally.
