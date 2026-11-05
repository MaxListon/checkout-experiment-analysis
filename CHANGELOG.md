# Version 2 review

## Material improvements

1. Replaced the fixed recommendation with tested interval-based launch, continue, redesign and SRM-investigation logic.
2. Calculated revenue and refund safety sample-size scenarios. Revealed that the default revenue limit requires about 645,000 users per arm under no true loss; conversion-only planning was insufficient.
3. Added an exact descriptive revenue decomposition and explicit separation from causal explanations.
4. Split data simulation, quality contracts, statistics, analysis and reporting into readable modules. Analysis uses existing CSVs unless regeneration is requested.
5. Added source keys, constraints, indexes and fail-closed SQL assignment/maturity checks. Replaced removable assert-based data gates with exceptions.
6. Added 22 behavioral regression tests covering SQL edge cases, invalid data, statistical behavior, bootstrap batching and decision changes.
7. Built and executed the notebook with actual saved outputs, including independent reconstruction of the reported bootstrap intervals.
8. Added exploratory pre-assignment balance and measurement-window diagnostics without selecting a favorable subgroup or outcome window.
9. Rebuilt the visual case study with six charts and added a two-page PDF, rendered and visually reviewed.
10. Added one-command rebuilding, offline verification, an updated interview guide and a packaged ZIP.

## What the review did not change

The original simulated users, assignments, events, orders, refunds and user-analysis CSV are byte-for-byte preserved, including their random seeds. Headline estimates and confidence intervals agree to floating-point tolerance. The findings remain inconclusive; no seed or outcome was tuned to create a win.

## Final review refinements

- Changed the revenue headline to describe the near-zero gross revenue point estimate and its wide interval without implying a certain outcome.
- Marked alternate-window results as exploratory, added an explicit no-inference CSV column, and warned against choosing a window after viewing results.
- Made the simulated assignment probability follow the same configuration value used by the sample-ratio diagnostic; the default seed and 0.50 setting preserve the original source data.
- Removed duplicate sensitivity rows when the primary window is one or three days.

## Review limits

The PDF was visually inspected at full-page resolution. HTML source, links and shared charts were validated, but the environment blocked local-file browser preview. The HTML appearance has not been verified in a browser. The supplied tests and reconciliation validate this dataset and documented behaviors, not every possible production data source.
