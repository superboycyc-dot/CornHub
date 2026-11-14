# D: area and review interfaces

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

## Actual checks and blockers

The test command above covers pending inputs, weighted sums and area conservation,
year/role separation, duplicate/orphan rejection, probability limits, quality queue
separation, tie-breaking, fixed-seed equal-budget simulation and CLI selectors.
See validation.txt for the actual run result.

A core inputs have been received from PR #6 (work/a-data), but are not yet on
main at the inspected snapshot. A records five leave-one-farm-out folds as an
explicit authorized exception to the older three-field-fold contract; D reads
those folds and checks farm separation without re-splitting. A documents official
label-use findings and their limits in reports/a_data/README.md; no extra written
organizer approval is claimed. B and C have header-only tables, so real features
and probabilities remain blockers. Review effectiveness and economic conclusions
remain uncomputed; economic inputs and OOF provenance are still needed.

## Real A handoff integration

A snapshot: df7ce8cd63039e90de7ca78ba95f4f3259ee15c5 (PR #6).
B header snapshot: e107fea4a539a6a9f973263f6a1be23158438304.
C header snapshot: 6a799c1d4f3d0103c105d19cf880b52c68140901.
These branches are read-only inputs; D does not merge their unapproved changes or
copy core/model/satellite files into this PR. Stage the pinned source files in
separate input directories until the respective PRs are merged. Read current
README, contract and collaboration/submission rules; contract blob unchanged,
and no AGENTS.md appears in the inspected trees.

Validated 83 boundaries, 44 unique labels on 34 fields and 44 matching fold rows.
The four consumed A core files match A acceptance SHA-256 byte for byte. Same
field/farm never crosses a fold. D trusts A area/geometry preparation and does
not claim an independent geometric reprojection or ground survey. The 490.86427949
ha static boundary inventory is only an input integrity check, not annual corn
acreage and not an estimated S/G total.

| Selected cohort | Fields | Selected area (ha) | Prediction coverage | Status |
| --- | ---: | ---: | ---: | --- |
| Official smoke barc_1 / 2021 | 1 | 6.63739333 | 0% | pending |
| Labeled 2021 | 18 | 130.11089599 | 0% | pending |
| Labeled 2022 | 7 | 44.65081020 | 0% | pending |
| Labeled 2023 | 19 | 123.08976508 | 0% | pending |

All expected crop areas and economic scenarios remain null, every review queue
is header-only, and each selected field has missing_features;missing_prediction
in its data-needed table. B/C files exist but contain zero rows, which is different
from a missing file. No true-label area was used as a prediction. Years are never
summed into a single area.

Reproduce using a checkout containing A/B/C handoffs, or pass --core-root,
--features, --predictions and --acceptance pointing to staged read-only inputs:

```sh
python3 src/analysis/validate_handoff.py \
  --a-ref df7ce8cd63039e90de7ca78ba95f4f3259ee15c5 \
  --b-ref e107fea4a539a6a9f973263f6a1be23158438304 \
  --c-ref 6a799c1d4f3d0103c105d19cf880b52c68140901 \
  --acceptance reports/a_data/acceptance.json --prediction-role oof
```

The refs must identify the actual source snapshots; when inputs change, use their
new commits. The runner verifies core checksums against the supplied acceptance,
records all six input SHA-256 and Git blob hashes, validates core links and farm
folds, and writes smoke plus annual labeled-cohort outputs. It does not fetch or
change any upstream file. Full audit: handoff_validation.json. Actual execution
and staged-input command: validation.txt. Tests: 16 passing, including cohort
selection, exclusions, farm leakage rejection and the original calculation tests.
