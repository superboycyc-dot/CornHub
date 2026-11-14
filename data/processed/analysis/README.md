# Analysis handoff

Active snapshot: official A smoke sample barc_1 / 2021, role oof, area 6.63739333 ha.
A core snapshot: df7ce8cd63039e90de7ca78ba95f4f3259ee15c5. B/C tables have headers
but no observations or predictions. Status pending; prediction coverage 0%; expected
silage/grain area and economics null. Review queues have headers only.

Annual labeled cohorts are separate under 2021/oof, 2022/oof, 2023/oof, selecting
18, 7, 19 fields respectively. All 83 boundaries are not assumed to be annual corn.
Every selected field has explicit missing feature/prediction reasons. These are
BARC selected samples, not representative county/state or California estimates.

Run from repository root after upstream inputs are available:
`python3 src/analysis/analysis.py --year 2021 --prediction-role oof --cohort smoke --review-budget 1`.
For annual labeled analysis use --cohort labeled and a separate --output-root.
See reports/d_analysis/README.md and handoff_validation.json for provenance,
validation, the full integration command, and remaining blockers.
