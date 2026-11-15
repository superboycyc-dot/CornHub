# 官方 Sentinel-2 starter 实际代码审阅

已阅读 `03_Geospatial_References/sentinel-2_starter_notebook.ipynb`，来自 main `51d5989`，14 个 cell；完整 SHA256、导入和代码信号在 `starter_notebook_audit.json`。原件不修改。官方说明明确这是可选示例，不是指定数据源或强制模型。

| 原件 cell | 实际功能 | B 的合同适配 |
| --- | --- | --- |
| 4 | 读本地 `field_aoi.geojson`；写死 2022-07-01 到 2022-11-30、场景云量<40% | `load_sample` 读取 A 的 fields/smoke，严格 `[04-01,12-01)`；不另造 ID/标签 |
| 6 | Planetary Computer 的 Sentinel-2 L2A STAC 搜索 | 使用同一公开 L2A 数据类型的 Earth Search COG 访问；官方允许替代目录，省去签名步骤；保存完整产品和来源 |
| 8 | `planetary_computer.sign_inplace`，odc.stac 载入 B04/B08/SCL，写死 UTM 10N，10m、`groupby=solar_day` | 选择产品自己的投影 10m B04 网格，以田块窗口读取；SCL 最近邻；先保留场景，再按合同逐 UTC 日期有效比例选场景 |
| 10 | SCL 白名单 `[4,5,6,7]`；直接计算 band ratio，空间取 median | 沿用该 SCL 白名单和 NDVI 中位数；显式使用产品 scale/offset、nodata、中心像元规则和完整田块分母；不声称原件已经完成这些校验 |
| 12 | peak_date、peak_ndvi、09-01 后的 NDVI **median**、峰后观测次数 | 按合同输出 peak_doy、相邻有效日下降率、晚季 **mean**、有效日数、边界缺口和 quality_flag |

原件没有读取 A 的标准交接文件，没有导出合同两张 CSV，也没有 valid_pixel_fraction、同日质量排序、max_gap_days 或质量分级。不能把它直接运行后的基础特征当作合同交付。

源代码并未显式应用 BOA 缩放偏移，也未明确指定分类层重采样；本适配将这些步骤写成可测试函数。跨日期同一田不改 ID；不把影像、标签或时序结果伪造为示例。

选择独立 Python 入口是为保留原 notebook 的“单田边界 → L2A 搜索 → B04/B08/SCL → NDVI 中位数 → 时序特征”流程，同时满足合同精确格式、来源记录和无需全景下载的限制；不是声称复现了未执行的 odc.stac 结果。`notebooks/b_satellite/run_smoke.ipynb` 是该入口的 B 自有 notebook。

目前真实端到端执行仍由 A 的两个标准交接文件阻塞。已有 `data/processed/barc_field_year_labels.csv` 使用数字 ID 与不同列名，不能由 B 擅自替代 A 的 `barc_` ID 和共同样本选择。
