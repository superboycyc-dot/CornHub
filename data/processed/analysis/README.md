# Analysis handoff

Root: official smoke barc_1 / 2021 / OOF only. Annual labeled OOF scopes are separate
under 2021/oof, 2022/oof and 2023/oof. They select 18/7/19 fields, not all 83 boundaries.
Source commits and input hashes: reports/d_analysis/handoff_validation.json.

Real C OOF probabilities now provide 100% selected-cohort prediction coverage.
Inference is excluded. Expected areas are exploratory uncalibrated sample estimates,
not BARC annual census/county/state/California totals; years are not added together.
feature_coverage.json separates feature availability and quality from predictions.
2021 has 18 limited records (gaps 33-45 days), with reasons in data_needed.csv;
2022/2023 have 7/19 usable records. 2021 and smoke review simulations remain pending
because no usable candidates meet the unchanged quality gate.

2022/2023 review simulations use real OOF and sourced labels, seed 42, 200 random
repeats and the same budget of three fields. 2023 heuristic error increases after
review; no general ranking benefit is claimed. Economic scenarios remain null.

Run after upstream files are available:
python3 src/analysis/analysis.py --year 2021 --prediction-role oof --cohort smoke --review-budget 1
Use --cohort labeled and a distinct --output-root for annual scopes. Full contracts,
commands, source refs, independent checks and limitations: reports/d_analysis/README.md.
