# Active analysis: 2022–2025

Requested years 2022/2023/2024/2025, explicit role oof; see period_status.json.
2022/2023 are computed sample estimates. 2024/2025 are pending: annual targets,
features, real predictions and OOF labels/folds are absent. Unknown areas/coverage
are null, never zero or copied from another year.

Root files are the single 2022 labeled cohort. Each requested year has its own
folder. 2021/oof is historical and excluded from active CSV summaries; A's
official smoke sample is not modified. No years/roles are summed together.

annual_data_summary.csv has four rows; year_change_decomposition.csv computes
only 2022→2023. The remaining pairs are pending. Six real 2022/2023 field
corrections are retained. Global missing inputs are listed in period_status.json;
unresolved-cohort field-level tables contain headers only.

Run: python3 src/analysis/run_period.py --start-year 2022 --end-year 2025 --prediction-role oof
Current report and contract: reports/d_analysis/all_data_summary_zh.md and README.md.
No newly acquired 2024/2025 source data is claimed.
