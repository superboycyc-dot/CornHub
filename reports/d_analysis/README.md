# D: area and review interfaces

Contract baseline: docs/team-contract.md, main commit 51d59890b04c6b0d7c1dce8186f2992352a32a1c (contract blob 1749344f5a6a2911a8327927eabbdb549e951adb).
The user explicitly assigns this round to that contract: BARC 2021-2023, not
the older California/2022-2026 README scope. Root README also retains an older
A^2*p*(1-p) ranking. This implementation uses the contract's A*4*p*(1-p).
No model/frontend/shared configuration files are changed.

## Run from repository root

```sh
python3 -m unittest discover -s src/analysis -p 'test_*.py' -v
python3 src/analysis/analysis.py --year 2022 --prediction-role oof --review-budget 3
```

Inputs (read only): data/processed/core/fields.geojson,
data/processed/satellite/features.csv, data/processed/model/predictions.csv.
Optional simulation also reads core/labels.csv and core/validation_folds.csv.
Python 3.9+; no third-party dependencies. Missing files produce pending output;
malformed files fail with exit 2. No fallback probabilities or prices exist.

## Output contract

Default output folder is data/processed/analysis. summary.json contains exactly
status, year, scope, prediction_role, total_area_ha, covered_area_ha,
coverage_fraction, expected_silage_area_ha, expected_grain_area_ha,
economic_scenario, notes. Status is pending or computed. Scope is an object:
dataset=BARC, field_ids (explicit inventory), representative_of_county_or_state=false.
Numbers not computable are null. Missing inventory means total/coverage are null;
known inventory with no probabilities means covered area=0, coverage=0, expected
crop areas=null. No fields are assumed to have zero area or to be grain.

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

The total denominator is the supplied static field inventory, not verified annual
corn acreage; coverage describes predictions over that inventory only. These are
sample/cohort estimates, not representative county/state estimates or a census.

One run selects exactly one year and role. The default files are the active
handoff snapshot. To retain several runs without overwriting snapshots, pass
--output-root data/processed/analysis/2023/oof (and the corresponding selectors).
Never concatenate years/roles into one area estimate. The published pending
snapshot selects 2022/oof as an explicitly identified interface run, not a chosen
official smoke sample; A has not yet supplied smoke_sample.json.

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

## Actual checks and blockers

The test command above covers pending inputs, weighted sums and area conservation,
year/role separation, duplicate/orphan rejection, probability limits, quality queue
separation, tie-breaking, fixed-seed equal-budget simulation and CLI selectors.
See validation.txt for the actual run result.

A: supply fields.geojson, labels.csv, validation_folds.csv, smoke_sample.json and
official label-use restrictions. B: supply contract features.csv. C: supply real
OOF/inference predictions with version and fold provenance. Until then no true
area estimates, review performance claims or economic conclusions are available.

## Repository verification for this delivery

Read current README, docs/team-contract.md, 01 - Working together.md, and
02 - Submitting your work.md via the connected GitHub account. No AGENTS.md
exists in the inspected main/branch tree. The branch had only requirements.txt;
its history is retained, and current main is included as a merge parent.
The raw BARC GeoPackage and legacy label CSV are now on main, but A has not
published the normalized core handoff. D does not create replacement IDs or
reinterpret those raw labels. No canonical core, satellite or model inputs exist
on the inspected main snapshot. Pending outputs therefore remain appropriate.
