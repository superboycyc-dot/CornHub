# D: active 2022–2025 period

[当前中文报告](all_data_summary_zh.md)。

The user explicitly extends D's requested window to 2022–2025. The shared contract
and A/B/C files are unchanged. Readers retain 2021 source compatibility; active
outputs exclude 2021. Source data currently remains 2021–2023.

| Year | Status | Selected fields | Expected silage ha | Expected grain ha |
| --- | --- | ---: | ---: | ---: |
| 2022 | computed | 7 | 18.66016901 | 25.99064119 |
| 2023 | computed | 19 | 40.63679195 | 82.45297313 |
| 2024 | pending | unknown | null | null |
| 2025 | pending | unknown | null | null |

## Run and outputs

Python 3.9+ standard library:
```sh
python3 -m unittest discover -s src/analysis -p 'test_*.py' -v
python3 src/analysis/run_period.py --start-year 2022 --end-year 2025 --prediction-role oof
python3 src/analysis/report_results.py --c-ref a867e4e19c431754e7b07ee8a260f48761d83d81 --prediction-role oof
```

Use --input-root for staged read-only handoffs and --model-report for C's report.
Input SHA-256 must match handoff_validation.json. Validate updated sources before
changing the provenance manifest. The historical summarizer refuses to overwrite
an active period. Source validator validate_handoff.py can enumerate historical
labels; rerun run_period.py to restore the explicit active window after it.

Every requested year has summary, merge audit, feature coverage, data-needed,
review queue and simulation files. period_status.json lists all four years and
global blockers. The root copies one explicit cohort: 2022/labeled. A's official
2021 smoke sample is unchanged. Historical 2021/oof files are untouched.

summary.json top-level keys are unchanged. For a labeled year without an annual
target cohort, scope.cohort_status=pending_no_annual_cohort and field_ids=[].
Total area, covered area, coverage and expected crop areas are null. Empty IDs
are unresolved scope, not zero corn acreage. Both field-level CSVs have headers
only; global blockers are in period_status, not fake field IDs. A known nonempty
cohort without predictions still has 0 coverage; an unknown cohort has null.

annual_data_summary.csv has four year-separated rows. Unknown CSV values are
blank, JSON values null. Only 2022→2023 in year_change_decomposition.csv is
computed; later pairs are pending. review_field_corrections.csv retains six real
2022/2023 corrections. No four-year area total is produced. Root/annual data is
OOF only; inference is never mixed into evaluation.

## Provenance, checks and limits

A=df7ce8cd63039e90de7ca78ba95f4f3259ee15c5,
B=05a81a7d1634c80d3c56b66cf9eb9acb9527fc9b,
C=a867e4e19c431754e7b07ee8a260f48761d83d81.
The fixed source files still contain 44 labels/features and 44 OOF+44 inference
rows across 2021–2023. The new window does not acquire missing 2024/2025 records.

20 core tests and a real four-year execution completed before the local execution
environment disconnected. The result was partial_pending. Files were subsequently
assembled/verified through GitHub; no post-disconnection Python execution occurred.
Current evidence: period_validation.json and validation.txt. The supplemental
auditor follows period_status and never evaluates missing-year predictions.

Use the existing A farm folds, same usable pool, budget 3, seed 42 and 200 random
repeats. 2022 error decreases; 2023 increases. Keep the negative result. C model
probabilities are uncalibrated; no model retraining, regional representativeness,
California validation, ground review or general ranking benefit is claimed.

2024/2025 need A-confirmed annual targets and sourced labels/folds for OOF, real
B features and real C predictions with provenance. The old 83 boundaries and
California CDL do not supply these inputs. Economic parameters/results stay null;
fresh silage and grain weights are not directly comparable; gross value is not
profit. D does not edit models, frontend or shared rules.

Historical reports: archive/barc_2021_2023_all_data_summary_zh.md and
archive/README_2021_2023.md. Old summary validation is archived as well; it does not
describe the current active output files.
