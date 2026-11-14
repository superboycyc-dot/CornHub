# Data directory

## USDA NASS corn benchmarks

`raw/usda_nass/crop_production_2025_summary.pdf` is the official USDA National Agricultural Statistics Service (NASS) *Crop Production 2025 Summary*, released January 12, 2026. The report contains state and national planted/harvested area, yield, and production tables.

`processed/usda_nass/corn_state_benchmarks_2025.csv` is a compact, machine-readable extract for the United States and California. It is for unit checks, aggregate sanity checks, and the California example in the project brief. It is **not** a field-level training set and must not be used as if it supplied field labels.

`processed/usda_nass/california_corn_acreage_annual_reference_2012_2025.csv` is a California-only extract from the Quick Stats download in `01_QuickStats/`. It retains the three annual corn acreage series used by the project (all-purpose planted, grain harvested, silage harvested), filters to total-domain annual records, and uses county/Census records for 2012, 2017, and 2022 and state/Survey records for other years. The original NASS columns are retained for provenance. Suppressed values such as `(D)` remain text and should not be treated as zero.

### Units and interpretation

- Area columns are thousand acres.
- Grain yield is bushels per acre; grain production is thousand bushels.
- Silage yield is tons per acre; silage production is thousand tons.
- `corn_planted_all_purpose` includes corn planted for all uses. Grain and silage harvested acres are reported separately; do not assume they must sum exactly to planted acres.
- USDA NASS estimates are annual aggregate reference values. They are not near-real-time supply measurements.

### Provenance

- Official NASS report: <https://release.nass.usda.gov/reports/cropan26.pdf>
- California state overview: <https://www.nass.usda.gov/Quick_Stats/Ag_Overview/stateOverview.php?state=California&year=2025>
- Data are attributed to USDA NASS. Consult the linked source for publication notes, revisions, definitions, and reuse terms.

All values in the CSV are from the same January 2026 NASS summary report and preserve its published rounding.

### Quick Stats acreage extract

Rebuild the California Quick Stats extract from the committed source CSV with:

```sh
python3 scripts/curate_quickstats.py
```

This table is an aggregate reference, not ground truth for individual fields. Annual publication and revision timing means it cannot serve as a real-time supply feed.

**Source-vintage discrepancy to resolve before reporting totals:** for California 2025, this Quick Stats extract reports 450 thousand planted acres, 75 thousand grain-harvested acres, and 370 thousand silage-harvested acres. The separate January 2026 *Crop Production 2025 Summary* extract in `processed/usda_nass/corn_state_benchmarks_2025.csv` reports 420, 50, and 365 thousand acres, respectively. Both retain their source and publication context; do not average or silently substitute between them. Confirm definitions, reference vintage, and later revisions with NASS before using either as the project’s calibration target.

## USDA NASS California Cropland Data Layer

[加州 2022–2025 年 CDL 数据与来源说明](usda_nass_cdl/california/README.md)：四个原始年度 ZIP、文件清单与 SHA-256 校验记录。实测 30 米像元；2026 年本次未找到已发布数据。

## 外部全国玉米候选库（2021–2023）

[CSB / CropSight-US 处理后数据与读取方式](processed/external_corn/README.md)。全国原始包仅本地缓存，GitHub 保存玉米筛选分片、来源校验和复现脚本；两套数据均不提供 silage/grain 收获用途真值，不替换 BARC core。2022–2025 美国相关支持政策及适用边界见 [政策研究](../reports/a_data/policy_2022_2025/README.md)。
