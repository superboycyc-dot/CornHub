# 美国逐周降水：来源、计算过程与输出合同

本批沿用前文的 2021–2025 年范围，实际计算 2021-01-01 至 2025-12-31。结果总结见 [summary_zh.md](summary_zh.md)。本批是单独的天气背景数据，不修改 NDMI、模型、前端或此前面积预测。

## 1. 官方来源

1. **NOAA CPC Global Unified Gauge-Based Analysis of Daily Precipitation**，由 NOAA PSL 分发，V1.0 RT。原始数据为全球 0.5°×0.5°、每日累计降水，单位 mm。2021–2025 文件分别为 `precip.YYYY.nc`，下载 URL、实际时间、字节数及 SHA-256 均在 `data/processed/analysis/precipitation/inputs/source_manifest.json`。
2. **US Census 2024 Cartographic Boundary / States / 1:20,000,000**，固定同一套简化边界用于五年。读取真实 .prj，从 NAD83 转到 EPSG:4326；不使用行号另造州 ID，使用官方州 FIPS 和邮政缩写。50 州加 DC，共 51 个范围；排除海外领地。

原始年度 NetCDF 约数百 MB，仅在缓存中；不进 Git。州界小型快照、完整格点权重及源元数据随结果交付。CPC 的使用限制为 none，按 NOAA PSL 要求登记来源；Census 属美国政府公开地理数据。

**降水不是纯降雨。** 输入只有 precipitation 总量，没有液态雨/雪的相态拆分。不能将本表标成纯雨量或直接认为是作物可利用水量。

## 2. 空间计算

经度从 0–360°规范化到 −180–180°，保留阿拉斯加在日期变更线两侧的岛屿。对每个源格点建立 0.5°方格，与每个州的简化边界求交集；使用 WGS84 椭球计算交集面积，单位 km²。并非对经纬度直接求平面面积，也不是把各州等权平均。

```text
A_s,i = area_ellipsoid(state_s ∩ grid_cell_i)
P_i,week = sum(该格点所需日期的每日累计降水)
P_s,week = sum(A_s,i × P_i,week) / sum(A_s,i)，仅在所需日期均有效的格点上
coverage_fraction = 有效格点相交面积之和 / 该范围全部格点相交面积之和
```

各区域的量是**平均累计水深（mm）**，不是把美国所有位置的 mm 相加，不是总水体积。`US50_DC` 权重为 51 个州/DC 的相交面积之和；`CONUS48_DC` 另外排除 AK、HI。网格仍是原始 0.5°，没有用插值伪造更高分辨率。

20m 指地图比例尺 1:20,000,000，**不是 20 米分辨率**。这些边界为制图而简化；未另行扣除全部内陆水体，其覆盖面积不等于官方 ALAND 或精确国土面积。小岛、沿海和山地的降水误差可能明显，不能作为田块、县或精细灌溉数据。

## 3. 周、缺测与年份

- 按 ISO 周：周一至周日。`iso_year` 可能与日期的公历年不同，唯一键使用 `scope_id+week_start`，避免跨年混淆。
- 输入日期是 NOAA 源文件的日期标签；不同地区的日累计观测时段可能不同，因此不宣称是全国统一 UTC 00:00–24:00 的精确同步窗口。
- 共 262 个周区间。2021-01-01–03 是第一周的三天子区间，2025-12-29–31 是最后一周的三天子区间，标记 `partial_week`。它们的数值仅是三天累计，不应作为 mm/完整周比较。其余 260 周是完整七天。
- 采用 NetCDF 缺测掩膜及源 `valid_range`。缺值、非有限值和越界值都不作为零。**0 mm 是有效的无降水值。**
- 每一格点必须在该周实际需计算的所有日期都有有效值，才能进入周累计；不会把缺一天的六天累计当七天累计。源日期缺失会在该日留空，进而降低完整格点覆盖率。
- 全范围没有完整有效格点时，`precip_total_mm` / `precip_total_in` 留空，状态为 `no_complete_cell`；有值为 `computed` 或边界 `partial_week`。`computed` 只表示计算非空，不表示覆盖率为 100%。
- 年度汇总使用**全年每天都有效**的格点。年度和逐周的有效范围可能不同，且跨年周有不同切分，因此年度不能通过按 iso_year 简单加周表来复现。

## 4. 已发现的实际缺口

源文件日期 1,826 天齐全，但 Hawaii 的格点存在缺值：148 周没有完整有效格点；另有 5 周有效面积不足 90%。2021/2022 Hawaii 的全年有效区域约 14.28%，2023–2025 无全年连续有效格点。不能说 50 州每周均已完整取得。低于 90% 是本交付的筛查门槛，不代表经过验证的精度阈值。

已核查 NASA/ORNL Daymet 作为潜在独立补源；2025 HI 文件直接访问返回 HTTP 401。需要数据使用者自己的 Earthdata 授权，不能索要管理员 token。测试的 NOAA PSL GPCP 年文件路径返回 404。两者均未被接入，不以另一个产品悄悄填补 CPC 缺项，也不把源缺值解释成干旱或无雨。核查记录见 `alternative_source_checks.json`。

全国有效区域的覆盖率约 99.64%–99.96%；高全国覆盖率不代表 Hawaii 完整，也不代表预测准确率。各周有效范围可能略有变化，年际比较不可只看一个全国平均数。

## 5. 输出合同

目录：`data/processed/analysis/precipitation/`。CSV UTF-8、snake_case、空数值留空。

| 文件/字段 | 内容 |
| --- | --- |
| `weekly_us50_2021_2025.csv` | 全国 50 州＋DC，262 行，可直接查看 |
| `weekly_conus48_2021_2025.csv` | 本土48州＋DC，262 行 |
| `weekly_all_scopes_2021_2025.csv.gz` | 全部53个范围、13,886行，解压后是标准 CSV |
| `weekly_maryland_2021_2025.csv` | 马里兰州周表；不是 BARC 田块雨量 |
| `weekly_ak_2021_2025.csv`, `weekly_hi_2021_2025.csv` | AK、HI 的单独周表，保留缺项 |
| `annual_summary_2021_2025.csv` | 53范围×5年，265行，全年完整格点口径 |
| `coverage_below_90pct.csv` | 153行需要注意的低覆盖/无完整格点记录 |
| `inputs/grid_state_weights.csv` | 每州、每格点坐标索引与真实相交面积 |
| `inputs/scopes.json` | 范围名、FIPS、边界面积与网格划分面积 |
| `inputs/source_manifest.json`, `inputs/netcdf_metadata.json` | 来源、哈希、日期、单位和原始元数据 |
| `week_start`, `week_end` | 完整 ISO 周边界 |
| `period_start`, `period_end` | 本次请求范围内实际累计的日期边界 |
| `days_expected`, `days_in_requested_range`, `source_days` | 7天、请求范围内天数、源中实际日期数 |
| `precip_total_mm`, `precip_total_in` | 空间面积加权累计水深；1 inch=25.4 mm |
| `covered_area_km2`, `total_area_km2`, `coverage_fraction` | 完整有效格点覆盖范围与分母 |
| `status` | computed / partial_week / no_complete_cell |

## 6. 运行和检查

从仓库根目录执行；依赖仅在 D 子目录声明。

```sh
python3.12 -m venv /tmp/cornhub-rain-venv
/tmp/cornhub-rain-venv/bin/python -m pip install -r src/analysis/precipitation/requirements.txt
/tmp/cornhub-rain-venv/bin/python -m unittest discover -s src/analysis/precipitation -p 'test_*.py' -v
/tmp/cornhub-rain-venv/bin/python src/analysis/precipitation/weekly.py
MPLCONFIGDIR=/tmp/cornhub-mpl /tmp/cornhub-rain-venv/bin/python src/analysis/precipitation/report.py
```

`weekly.py`、`report.py` 均支持 `--cache`、`--output`、`--report`；默认缓存 `/tmp/cornhub_weekly_precip`。实际本次在已有 Python 3.12 隔离环境中执行了上述代码，5 项单元检查通过，批处理和报告生成 exit 0。没有使用 GPU 或声称在 NVIDIA 实例运行。

核查包括：日期/网格/单位/州集合；唯一键、非负值、覆盖率、英寸转换；以州结果和有效面积独立重建全国周均值，最大差异约 1.8e-14 mm。另直接回读原始 NetCDF 的 Maryland 某格点七天值，检查与缓存完全一致，再验证州面积加权结果。实例见 `calculation_example.json`，逐日格点周累计约 27.3688 mm，该周 Maryland 区域均值约 30.8683 mm；格点值与区域均值不同是正常的。

来源归属：NOAA PSL 提供 CPC 全球逐日格点，US Census 提供州界；本仓库负责周聚合、面积权重、缺测规则与派生统计。该数据不能单独解释 NDMI 变化的因果，也未用于生成新的模型概率、收获用途或利润结论。
