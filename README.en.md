# CornHub

[中文](README.md) | **English**

CornHub uses public satellite observations to identify whether a corn field was harvested for silage or grain. It reports data quality and prediction uncertainty and helps reviewers decide which fields to check.

The [data catalog](docs/data-catalog.md) lists the datasets, the outcome of each pull request, and outstanding work. All 11 pull requests covered by the handoff were merged into `main`. The core BARC deliverables and the nationwide candidate inventory have separate paths.

## Study scope

The organizers supplied 2021–2023 labels for the Beltsville Agricultural Research Center (BARC) in Maryland. The source data contains boundaries for 83 fields. Across 34 distinct fields, 44 field-years have a valid harvest-use label (32 grain and 12 silage). A blank label leaves both the crop planted that year and its harvest use unknown.

The first phase evaluates the method on those 44 labeled field-years. To extend the study, first verify that a candidate field grew corn in the year of interest, then extract its observations. Applying the model to all 83 fields in all three years would skip that check. The California Cropland Data Layer (CDL) and Quick Stats materials serve as historical references only. They provide neither training labels for this study nor evidence of performance elsewhere.

## What has been delivered

- **Observations and validation.** The pipeline produces Sentinel-2 NDVI time series and features for 44 field-years, evaluates a random forest using five folds that hold out farms, and estimates area and simulates field review separately for each year.
- **Outputs.** The release includes 4,524 field–scene records, 44 feature rows, 44 out-of-fold (OOF) predictions, and 44 inference predictions. Both prediction sets describe the same 44 field-years.
- **Integration.** The first-round outputs from teams A–E and the nationwide candidate inventory are on `main`. Subsequent updates are tracked through new pull requests and versioned sources. Model probabilities are uncalibrated.
- **Proposed moisture features.** The planned comparison would add NDMI moisture time series and combined NDVI–NDMI features, using the same 44 labels and farm splits as the NDVI baseline. This comparison is pending. Extra observations do not add independent labels, and any accuracy gain needs to be demonstrated.
- **Prediction timing.** Current inputs span the full season, so the results identify harvest use retrospectively. A pre-harvest forecast would require a fixed prediction date, observations available by that date, and a new validation run.

## Interpreting predictions and prioritizing field review

The model returns a class and `p_silage`, its estimated probability of silage harvest. Separate quality indicators describe valid observations, gaps, harvest-window coverage, and the number of pixels supporting each field estimate. A probability near 0.5, disagreement between models, or inputs outside the training distribution can flag uncertainty. Estimating accuracy requires held-out labels.

Review priority takes field area and observational evidence into account alongside uncertainty. The first version retains the team contract’s heuristic, `area_ha * 4p(1-p)`, where `p` is `p_silage`, and a separate list of data-quality issues to follow up. Compare future rules with random review using the same OOF samples and review budget. Repeatedly tuning rules on test results would compromise that comparison.

All 2021 records received the `limited` quality rating under the original thresholds. In the 2023 simulation, field review **increased the error in the estimated total area**. The simulation therefore does not establish that review consistently improves the aggregate estimate.

## Resources and collaboration

- [Official challenge statement](challenge_statement.md)
- [Team data contract and first-round prompts](docs/team-contract.md)
- [Second-round handoff review and role prompts](docs/round-2-prompts.md). Later deliverables supersede the C and D snapshots. Check the latest pull requests before acting on those instructions.
- [Source data notes](data/README.md)
- [Early NDVI prototype](05_Model/README.md)
- [Pull requests and deliverables](https://github.com/superboycyc-dot/CornHub/pulls)

| Team | Responsibility | Branch |
| --- | --- | --- |
| A | Data and integration | `work/a-data` |
| B | Remote sensing | `work/b-satellite` |
| C | Modeling | `work/c-model` |
| D | Analysis | `work/d-analysis` |
| E | Presentation | `work/e-web` |

Continue work on the existing branches and pull requests, preserving teammates’ changes. Team A integrates changes to the shared contract. When adding a metric, update downstream interfaces and retain the previous version.

Keep original labels, sources, and licenses traceable. Aggregate area for one year at a time, specifying the field set and `prediction_role`. Use OOF predictions for validation. Inference predictions on these fields do not constitute new fields or independent validation. Pricing, economic returns, and transport scheduling remain outside the delivered capabilities.

## Historical handoff records

These records document the first handoff. For the current study scope and validation splits, consult this README and the latest agreement at the top of the team contract.

- [First-round project status](docs/project-status.md)
- [First-round role handoff](docs/agent-handoff.md)
- [First-round work log](docs/worklog-2026-11-14.md)
