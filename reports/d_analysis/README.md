# D: area and review interfaces

[中文全量数据汇总与变化解释](all_data_summary_zh.md)：包括 A/B/C/D、USDA/CDL、年度面积变化分解和逐田核查修正。

Contract baseline: docs/team-contract.md, main commit 51d59890b04c6b0d7c1dce8186f2992352a32a1c (contract blob 1749344f5a6a2911a8327927eabbdb549e951adb).
The user explicitly assigns this round to that contract: BARC 2021-2023, not
the older California/2022-2026 README scope. Root README also retains an older
A^2*p*(1-p) ranking. This implementation uses the contract's A*4*p*(1-p).
No model/frontend/shared configuration files are changed.

## Run from repository root

```sh
python3 -m unittest discover -s src/analysis -p 'test_*.py' -v
python3 src/analysis/analysis.py --year 2021 --prediction-role oof --cohort smoke --review-budget 1
```

Inputs (read only): data/processed/core/fields.geojson,
data/processed/satellite/features.csv, data/processed/model/predictions.csv.
Labeled/smoke selection reads core/labels.csv; smoke also reads core/smoke_sample.json.
Optional simulation reads core/validation_folds.csv unchanged from A.
Python 3.9+; no third-party dependencies. Missing prediction/feature files produce
pending output; malformed files fail with exit 2. Explicit labeled/smoke selection
requires the corresponding A inputs and fails rather than inventing a cohort. No fallback probabilities or prices exist.

## Output contract

Default output folder is data/processed/analysis. summary.json contains exactly
status, year, scope, prediction_role, total_area_ha, covered_area_ha,
coverage_fraction, expected_silage_area_ha, expected_grain_area_ha,
economic_scenario, notes. Status is pending or computed. Scope is an object:
dataset=BARC, field_ids (explicit selected IDs), cohort (inventory/labeled/smoke),
representative_of_county_or_state=false.
Numbers not computable are null. Missing inventory means total/coverage are null;
known nonempty cohort with no probabilities means covered area=0, coverage=0,
expected crop areas=null. An empty known cohort has total=0 and coverage=null. No fields are assumed to have zero area or to be grain.

review_queue.csv columns: field_id,year,prediction_role,rank,review_score,reason.
No probabilities means header only. Score=A*4*p*(1-p), descending, ties by field_id.
Only usable features enter this heuristic queue. data_needed.csv separately lists
missing predictions/features and all non-usable quality categories, preserving B's
missing_reason. Low-quality fields with real probabilities remain included in
area totals (the contract says all predicted area); they do not enter the queue.
Satellite quality is not model accuracy or confidence.

merge_audit.json reports input row counts, selection exclusions, matches, missing
files, unmatched IDs and records requiring data. Duplicate keys, orphan IDs (when
inventory exists), invalid probabilities and inconsistent labels fail explicitly.
All duplicate checks precede year/role filtering. Leading zeros in IDs are kept.
Area_ha is trusted from A, who owns source CRS verification and EPSG:26918 area
calculation; D never recomputes area from EPSG:4326 coordinates.

The total denominator is the explicitly selected cohort. --cohort inventory
(default for API compatibility) covers supplied boundaries and is not verified
annual corn acreage. --cohort labeled selects only IDs with a real label in the
requested year. --cohort smoke selects exactly A smoke_sample ID/year and requires
a matching real label. The run still requires an explicit year and role; a smoke
year mismatch fails. Cohort selection never substitutes truth for probabilities.
All upstream keys and orphan IDs are validated before cohort exclusions; valid
outside-cohort records and other-year/role exclusions are reported separately.
These are sample/cohort estimates, not county/state estimates or a census.

One run selects exactly one year and role. The default files are the active
handoff snapshot. To retain several runs without overwriting snapshots, pass
--output-root data/processed/analysis/2023/oof (and the corresponding selectors).
Never concatenate years/roles into one area estimate. The active root snapshot
now selects A official smoke sample barc_1 / 2021, role oof. Annual labeled
cohorts are separate under 2021/oof, 2022/oof and 2023/oof.

## Review simulation

--review-budget is a whole-field count. Seed defaults to 42; random-repeats=200.
Requires complete, sourced labels for every covered field, and OOF rows whose
fold IDs agree with A's validation_folds.csv. Inference, incomplete labels/folds
or an oversized budget return pending with null errors. Zero budget is allowed.
The true total and initial estimate cover the same complete labeled OOF cohort.
Both strategies select from the identical usable queue and use the same budget.
Each reviewed field's A*p is replaced by A for silage or zero for grain. Output
reports initial/heuristic absolute error and seeded random median/min/max error.
The input contract cannot independently prove that C excluded a field from
training; that OOF provenance remains C/A's responsibility. Real results require
documented label use permission. Synthetic unittest fixtures are temporary and
are not released as analysis data or evidence of heuristic effectiveness.

## Economics

economic_parameters.template.json contains null values only. For each yield and
price, record value, source_dataset_id, source_url, source_table, publication_year,
data_year, region, unit, price_basis, moisture_basis, conversion_description,
conversion_factor, retrieved_at_utc and license. Sources.csv distinguishes the
contract actually read from possible economic sources not yet acquired.
Obtain year/region-matched BARC-relevant yields and prices before computing.
Record farm-gate versus delivered price, currency, fresh/dry basis, grain moisture,
and any bushel/short-ton/metric-ton/acre/hectare conversion explicitly.
Fresh silage and grain weight are different products; do not compare their mass
directly. Gross crop value is not profit; costs are absent. No economic calculation
is released in phase one, and summary.economic_scenario stays null.

## Current real A/B/C integration

A: df7ce8cd63039e90de7ca78ba95f4f3259ee15c5 (PR #6).
B: 05a81a7d1634c80d3c56b66cf9eb9acb9527fc9b (PR #5).
C: a867e4e19c431754e7b07ee8a260f48761d83d81 (PR #4).
These are pinned read-only inputs. D does not merge their unapproved changes or
copy their data into this PR. Sources are recorded in sources.csv. Contract blob
remains 1749344f5a6a2911a8327927eabbdb549e951adb; no AGENTS.md appears in inspected trees.

83 boundaries, 44 labels on 34 fields, 44 matching features and 88 predictions
(44 OOF + 44 inference) have been consumed. Four A core files match A acceptance
SHA-256. C training input hashes and A/B source refs match D inputs. Prediction
keys are unique; OOF fold IDs match A. A explicitly documents five farm folds
as an authorized exception to the older three-field-fold contract. D reads them,
checks same-field/farm separation and does not re-split or retrain models.
A owns geometry/CRS/area checks; D does not independently reproject or ground-survey.
A's label-use and licensing findings still apply; no extra organizer approval is claimed.

Published runs explicitly select OOF. Inference rows are excluded from area sums
and all review evaluation. C probabilities are uncalibrated, so probability-weighted
areas below are exploratory sample estimates, not validated county/state totals.
The 83 boundary inventory is not assumed to be corn in each year. Annual labeled
cohorts remain selected samples; different years are never added together.

| Year | Fields | Covered area ha | Expected silage ha | Expected grain ha | Prediction coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2021 | 18 | 130.11089599 | 32.66385589 | 97.44704010 | 100% |
| 2022 | 7 | 44.65081020 | 18.66016901 | 25.99064119 | 100% |
| 2023 | 19 | 123.08976508 | 40.63679195 | 82.45297313 | 100% |

Root snapshot is only the official smoke barc_1/2021 OOF. Full annual scopes are
in 2021/oof, 2022/oof and 2023/oof. Label-derived areas are never passed off as
predicted areas. No extrapolation to California or annual BARC census is claimed.

## Feature availability and quality sidecar

report_results.py adds feature_coverage.json in each output folder, without changing
the summary.json top-level contract. Fields include selected scope/year, feature
match count/area, area of fields with at least one valid day, usable-feature area
and fractions, quality counts/areas, and min/max valid days and maximum gaps.
Unknown/empty denominators are null. All fractions use the explicit cohort area.
Field-level feature availability is not complete seasonal/pixel coverage, model
accuracy, prediction coverage or probability reliability.

| Year | Feature matches | limited | usable | Valid-day range | Longest-gap range days |
| --- | ---: | ---: | ---: | --- | --- |
| 2021 | 18 | 18 | 0 | 21-52 | 33-45 |
| 2022 | 7 | 0 | 7 | 25-43 | 20-28 |
| 2023 | 19 | 0 | 19 | 21-51 | 15-30 |

Every selected field has features and valid days. All 2021 rows remain limited,
so 2021 usable-feature area is zero while its predicted area is fully covered.
Its 18 data_needed.csv records preserve quality_limited;gap_exceeds_30_days.
2022/2023 data-needed tables are empty. B reports 4,524 scene observations; D
checked consumed interfaces, not imagery processing or ground truth. C separately
reports time-series/feature consistency checks. Early peak/drop features are not
established harvest dates or S/G labels. Quality rules are not relaxed.

## Real fixed-budget review simulation

Budget=3 whole fields per annual cohort, seed=42, random repeats=200. Root smoke
uses budget=1. Same usable candidate pool, same budget and same OOF labeled cohort
for heuristic and random methods. Reviewed A*p is replaced by its true silage
area (A or zero). This assumes perfect manual label revelation, not a field survey.

| Year | Initial abs error ha | Heuristic abs error ha | Random median ha | Random range ha |
| --- | ---: | ---: | ---: | --- |
| 2021 | null | null | null | null |
| 2022 | 11.46034856 | 2.61793608 | 7.23108338 | 1.07524082-16.14943826 |
| 2023 | 3.05772217 | 4.00930710 | 4.77900320 | 0.47201898-11.75730767 |

2021 and smoke simulations remain pending: zero usable candidates, so the budget
cannot be executed. No budget reduction or quality promotion is performed.
2022 review IDs: barc_252, barc_278, barc_279. 2023: barc_292, barc_230, barc_323.
2023 error increases from 3.05772217 to 4.00930710 ha: revealing correct labels can
remove cancellation between field errors. Keep this negative result. Being below
the random median in two small runs is not a significance test or proof of general
ranking effectiveness. No threshold, budget or model choices were tuned to results.

review_comparison.csv and prediction_handoff_review.json record comparisons and
independent direct recomputation of weighted areas, area conservation, queue rank,
whole-field label replacement and seed-42 random error summaries (agreement 1e-10).
D relies on C's OOF training provenance and does not retrain or calibrate its models.

## Reproduce and remaining limitations

Python 3.9+ standard library. Tests: 18 passing; internal synthetic fixtures stay
in temporary directories. Main real integration and independent audit commands:

```sh
python3 src/analysis/validate_handoff.py \
  --a-ref df7ce8cd63039e90de7ca78ba95f4f3259ee15c5 \
  --b-ref 05a81a7d1634c80d3c56b66cf9eb9acb9527fc9b \
  --c-ref a867e4e19c431754e7b07ee8a260f48761d83d81 \
  --acceptance reports/a_data/acceptance.json --prediction-role oof
python3 src/analysis/report_results.py \
  --c-ref a867e4e19c431754e7b07ee8a260f48761d83d81 --prediction-role oof
```

Actual execution used staged read-only snapshots via --core-root, --features,
--predictions and --acceptance for the integration runner, and --input-root plus
--model-report for the result audit. Default paths above work after upstream PRs
are integrated. The scripts do not download or modify upstream files. Record the
actual immutable source refs when inputs change. Actual run evidence: validation.txt.

A/B/C inputs are available for this selected BARC cohort. Remaining limitations:
2021 has no usable review candidates; C probabilities are uncalibrated, only 34
independent fields/5 farms exist, one training fold has a single silage example,
and no independent-year/California validation exists. No general effectiveness,
confidence interval, deployment or field survey is claimed.

Economic inputs remain absent. Parameter template values and economic_scenario
stay null. Need local year-matched yields/prices, source table/URL, publication and
data year, region, currency, units, farm-gate/delivered price basis, moisture/fresh-
dry basis, conversions, retrieval time and license. Do not compare silage fresh
mass directly with grain mass or call gross crop value profit. No default prices.
