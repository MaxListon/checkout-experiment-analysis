# Explain this project in an interview

## Your 60-second walkthrough

“I built a reproducible analysis of a simulated 24,000-user randomized checkout experiment. I created the assignment, event, order and refund data, then used SQL to build one row per assigned user. I retained nonbuyers, handled duplicate ingestion and split refunds, and defined mature purchase and refund windows.

“The new checkout converted 13.45% versus 12.86% for control, about +0.59 percentage points. But the confidence interval included no improvement. Revenue was slightly lower, and refund safety was unresolved. I recommended retaining the current checkout and making further testing conditional on feasibility.

“The useful extra finding was that a conversion-only test needed about 50,000 users per arm, while the proposed revenue safety margin could need roughly 645,000 even under no true loss. That changed the next step from ‘just test longer’ to agreeing on economic tolerance and whether the test is worth running.”

## A five-minute walkthrough

1. **Business decision:** launch, continue or redesign. Explain the primary metric, refund guardrail and after-refund revenue safety criterion.
2. **Measurement:** show `sql/01_user_analysis.sql`. Explain the assigned-user denominator, seven-day paid-order window and complete 30-day refund follow-up.
3. **Data quality:** demonstrate one failed crossover fixture and one successful nonbuyer/split-refund fixture. Explain why a clean SRM alone does not validate tracking.
4. **Evidence:** show absolute vs relative conversion lift, the user bootstrap and the three decision gates.
5. **Business judgment:** show the revenue decomposition and the safety sample-size scenarios. Explain why no real traffic or budget means you cannot claim testing is worthwhile.

## Questions a reviewer may ask

**Why simulate?** To disclose the random assignment process and demonstrate realistic multi-table analysis without presenting observational public data as randomized. The project demonstrates a method, not a real product effect.

**Why not analyze only checkout starters?** Starting checkout occurs after assignment. Restricting to starters could select different populations by treatment. Intention-to-treat keeps the assignment policy comparison intact.

**What was the important SQL trap?** Split refunds form a one-to-many join. Joining them directly to orders duplicates order value. Aggregate refund entries to orders first, then aggregate to users, then left join to assignments.

**Why are purchases counted even if later refunded?** Purchase conversion measures whether a paid order occurred. Refunds are separate outcomes that affect the refund guardrail and revenue after refunds. Changing conversion retrospectively would change the estimand.

**Why user-level bootstrapping?** Assignment is by user. Resampling that unit preserves zero-revenue users and clusters their orders and refunds. Resampling orders would overrepresent frequent buyers and lose the intended denominator.

**Can a bootstrap handle anything?** No. It relies on the observed sample and independence assumptions. It cannot recover unseen tails or fix tracking errors. I retained high spenders and also checked a normal mean-difference interval.

**Why not call +4.57% a success?** It is the relative point estimate. The absolute interval spans about −0.27 to +1.44 percentage points, and the safety criteria also matter. An attractive point estimate is insufficient.

**Why more buyers but less revenue?** Gross revenue per assigned user is conversion × orders per buyer × average order value. In this sample, lower order frequency and value offset the conversion contribution. Additional refunds reduce the after-refund total. The decomposition is descriptive; it does not prove separate causal mechanisms.

**Why not 50,000 users per arm?** That is conversion-only planning. The revenue outcome is noisy and the proposed $0.25 safety margin is tight. Under no true loss, revenue safety needs about 645,000 per arm for 80% marginal power. This is approximate and not a guarantee of passing the whole launch rule.

**Would you loosen the safety limit?** Only if business economics independently justify a different tolerance before the new test. I would not change it just to obtain a favorable conclusion.

**Why not keep running until significant?** Optional stopping with ordinary fixed-horizon inference increases false positives. Use a new independent fixed-horizon run or a prospectively specified valid sequential design.

**What if a mobile subgroup looks great?** Test a prespecified interaction and account for multiple comparisons. A lucky subgroup does not override an uncertain overall result. I report balance summaries, not segment launch claims.

**What would you add with real company data?** Assignment/exposure audits, identity coverage, payments reconciliation, technical failure metrics, costs and margin, long-term customer outcomes, realistic traffic forecasts and the operating characteristics of the full decision rule.

## Honest resume wording

Built a reproducible SQL/Python analysis of a simulated 24,000-user checkout experiment; validated assignment and transaction data, estimated conversion and revenue uncertainty with 10,000 user bootstrap resamples, and evaluated launch criteria and next-test feasibility.

## What to demonstrate live

- Run `python -m unittest discover -s tests -v` and explain the failed-data scenarios it protects against.
- Open the executed notebook and explain one confidence interval without reading the prose.
- Show how the decision function changes under clear success, clear harm and inconclusive evidence.
- Walk through why the revenue bridge adds up but is not causal mediation.

Keep “simulated” visible in the portfolio and resume. Review and understand the code before presenting it as your work; describe AI assistance honestly if asked.
