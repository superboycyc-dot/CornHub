# CornHub 数据目录与集成状态

2026-11-14（America/Los_Angeles）。本次接手时的 11 个 PR 均已合入 main：原已合并 #1/#8/#9，本次合并 #6/#5/#4/#7/#11/#3/#10/#2。保留成员分支与原始来源提交。此次整理不重新下载卫星、不发布网站、不改变标签或模型结果。

## 从哪里读取

| 层次 | 入口 | 当前内容与用途 |
| --- | --- | --- |
| 官方材料 | `04_Evaluation/`、`challenge_statement.md` | BARC 官方原件；历史材料与原始文件保留 |
| A 核心数据 | `data/processed/core/README.md` | 83 个 EPSG:4326 边界；44 标签年、34 独立田、32 grain/12 silage；5 农场留出折；面积 ha |
| B 卫星 | `data/processed/satellite/features.csv`、`timeseries.csv` | 44 特征、4,524 场景记录；26 usable、18 limited；质量不等于预测可靠性 |
| C 模型 | `data/processed/model/metrics.json`、`predictions.csv` | 44 OOF + 44 inference；按 field_id/year/role 关联，不能当 88 独立样本 |
| D 年度分析 | `data/processed/analysis/period_status.json`、`annual_data_summary.csv` | 2022/2023 computed，2024/2025 pending；逐年逐 role 子目录为正式入口 |
| D NDMI | `reports/d_analysis/ndmi/README.md` | Maryland Corn 4/60 月已计算，56 月 pending；不等于 BARC 逐田增强特征已接入模型 |
| E 网站 | `web/README.md` | BARC 真实交接已集成；构建时同步发布副本，不手改 public/data |
| 全国候选库 | `data/processed/external_corn/README.md` | CSB 6,112,209 多年度对象；CropSight 15,939 对象年；1,232 个 GeoParquet 分片，不能当 S/G 真值 |
| 历史政策 | `reports/a_data/policy_2022_2025/README.md` | 来源与资格口径；不当作用途标签或全国统一青贮补贴 |
| v2 计划 | `notebooks/c_model/v2/模型方案与ABC提示词.md` | 2018–2025 逐田跨年方案；计划不等于数据已补齐 |
| 历史资料 | `data/usda_nass_cdl/california/`、`data/processed/usda_nass/` | 加州历史参考，不并入当前 BARC 验证样本 |

## 可直接使用的年度结果

| 年份 | 选定田块年 | 预期青贮 ha | 预期籽粒 ha | 状态 |
| --- | ---: | ---: | ---: | --- |
| 2022 | 7 | 18.66016901 | 25.99064119 | computed / OOF |
| 2023 | 19 | 40.63679195 | 82.45297313 | computed / OOF |
| 2024 | 未知 | null | null | pending |
| 2025 | 未知 | null | null | pending |

不同年份不能加成一年面积；null 不是零。2021 的历史 OOF 目录保留，但不属于 D 当前 2022–2025 活动窗口。根 summary/review_queue 是明确选定的 2022/labeled 副本。

## 本次真实检查

- A：独立回读 83 边界、面积回投影、44 标签/划分、唯一键、5 农场及原件 SHA-256，通过。
- B：34 个测试通过；从已交付场景汇总重新核验 44 行特征。没有重新获取影像或核验地面真值。
- C：10 个测试通过；在 Python 3.12.14 重训，混淆矩阵及 F1/召回一致。原报告环境为 Python 3.13；Brier 从 0.1627309156 到 0.1627347749，差 0.0000038593，概率不逐字节一致，保留原交付、不覆盖结果。
- D：20 个核心测试通过；NDMI 8 通过、1 因无 CuPy/CUDA 跳过。四年流程实际重跑，四个 summary JSON 与已提交数据相同。
- 全国候选库：1,232 分片全部重新读入，逐片大小/SHA-256/行数、ID 唯一、CRS、面积样本及几何标记通过；CSB 209,931 个无效几何显式保留，不静默修复；全部 harvest_type 为空。
- E：27 个发布输入核验、9 个 Node 测试、生产构建通过；真实数据和隔离夹具浏览器检查通过，包含手机、键盘田块选择、缺失年度和角色隔离。外部底图部分瓦片不可达时有降级提示。未重新部署。
- 修复 #3 文档冲突，保留最新 BARC/农场五折约定，旧状态标为历史快照。修复网站复制全国候选库的问题，防止约 2.15 GB 研究分片进入 BARC 网站发布目录。

## 使用限制与下一步

模型概率未校准，OOF macro F1 约 0.650794，青贮 recall 1/3，12 条青贮漏掉 8 条。农场与独立田数量有限，不宣称全国精度。2023 核查模拟使面积误差增加，该负结果保留。

下一轮按 v2 方案：A 提供有版本与时点的年度田块/玉米资格和跨年对应，B 提供真实对应年度的观测与增强特征，C 在冻结农场折上做配对比较；D 才能更新缺失年份，E 再同步。全国候选库没有 S/G 标签，不能直接扩充监督真值。GPU/远程配置尚未验证，NDMI 未完成月份继续标 pending。

## 审计证据

[本次汇总与限制](../reports/integration/pr-management-2026-11-14/summary.json) · [全部 PR 状态与提交](../reports/integration/pr-management-2026-11-14/pull-requests.json) · [核心交接逐文件 SHA-256/行数](../reports/integration/pr-management-2026-11-14/handoff-files.json) · [全国分片 SHA-256 清单](../reports/integration/pr-management-2026-11-14/external-shards.json) · [浏览器证据](../reports/e_web/integration-browser-verification.json)。同目录保留本次实际测试和复跑输出。
