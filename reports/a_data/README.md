# A 第一轮数据交接与验收

日期：2026-11-14。负责人：成员 A（当前 Codex 会话）。从最新已获取 `origin/main=51d5989` 开始，原工作区干净，使用 `work/a-data`；其他角色的远端分支存在，本次没有切换、合并或修改它们。PR：https://github.com/superboycyc-dot/CornHub/pull/6 。

## 先交共同样本

核心数据已在报告完成前以 `6b9f09f` 推送，B 不需要等最终验收文档才开始。按规范化 field_id 的**字符串顺序**、然后年份数值排序，第一条为：

- field_id：`barc_1`；source_field_id：`1`（GeoPackage OBJECTID）；year：2021。
- 真实类别：`grain`，原始值 `Grain`；来源 `barc_corn_2021_2023_challenge`。
- 边界：`data/processed/core/fields.geojson`，筛选 properties.field_id；EPSG:4326，经度在前。
- 面积：`6.63739333 ha`，由原件 CRS 转 EPSG:26918 后面积除以 10,000 得出。
- 窗口：`[2021-04-01, 2021-12-01)`；合同选择规则，没有根据影像效果挑样本。
- 定位记录：`data/processed/core/smoke_sample.json`；真实类别来自 labels.csv，没有向样本 JSON 增加下游必须读取的新字段。

## 原件与使用规则核验

原件 `04_Evaluation/BARC_Corn.2021-2023.gpkg` 和旧 `data/processed/barc_field_year_labels.csv` 均保留、未覆盖。来源/许可、引用和核验时间见 sources.csv、source_metadata.json；SHA-256 见 acceptance.json。

本仓库 challenge_statement.md 的 Data Rules 与 Evaluation、官方 barc_fields_explorer.ipynb 的说明要求：只用公开资料；只评估有效 Grain/Silage 年度；空白不是 Grain；保留原始标签、预测另存；报告混淆矩阵、两类 precision/recall、年份/类别数量、划分和不确定性；避免邻近田块的简单随机拆分。没有找到主办方指定固定测试田块或禁止训练的明确条款，也没有找到独立隐藏测试清单。这里据此发布可用于分组 OOF 的输入，不宣称收到主办方关于训练用途的额外书面确认。C 必须把评估折留出，不能把完整标签训练后的训练内分数当验证。

官方 explorer 指向 Dulaney 等（2024，doi:10.1002/agg2.20474）、Kraatz 等（2023，doi:10.3390/s23208595）及两个公开数据集，并要求使用/再分发时引用。已核验 Ag Data Commons 页面显示 U.S. Public Domain，Zenodo API 显示 CC-BY-4.0、版本 1.0.0。这些是**上游数据集许可**；比赛组装的 2021–2023 标签 GeoPackage 没有独立机器可读许可证，登记为 unknown，不把上游任一个许可擅自套给整个原件。现有官方 notebook 明确提及使用/再分发时引用，本 PR 按用户授权提供其派生交接并保留引用，不重新复制原始包。若后续确认更细许可，应更新来源记录。

## 交付文件和关联

| 文件（均在 data/processed/core） | 行数/要素数 | 唯一键与内容 |
| --- | ---: | --- |
| fields.geojson | 83 | field_id；source_field_id、source_dataset_id、area_ha；增加只用于验证分组的 farm_group |
| labels.csv | 44 | field_id+year；小写 label、保留 label_raw、source_dataset_id |
| smoke_sample.json | 1 | 合同六个字段；共同样本不是独立测试集 |
| validation_folds.csv | 44 | field_id+year；fold_id 为 0–4，仅有标签记录 |
| field_id_map.csv | 83 | field_id 与 source_field_id 一对一；源 ID 列 OBJECTID、farm_group、source_acres、原几何 WKB SHA-256 |

源 OBJECTID 为整数，没有前导零信息可保留；统一 ID 固定为 `barc_<OBJECTID>`，不用行号、fid、FIELD_ID 重新生成。映射是此版源文件的持久注册表；生成器检测现有映射不一致就失败。上游更换数据版本时需显式审核映射，不能假定 OBJECTID 跨所有外部版本永远不变。

fields 包含全部 83 个原始田块，方便展示无标签状态；有标签的是 34 块。**83 块不代表它们每年都种植/收获玉米**，D 不应把全部 83 块面积当作每年的玉米总面积；年份估计的目标集合应显式选择，缺少当年种植范围真值时仅报告指定集合。labels→fields 全部匹配；labels→folds 全部一对一。CSV 的 year、fold_id 解析为整数，field_id、source_field_id、farm_group 保持字符串。

农场字段来源为原始 `FARM_ID`，不是 FARM 名称、FIELD_ID 或模型特征；在 GeoJSON properties 和 ID 映射中用 `farm_group` 提供。labels/folds 保持合同字段头。B 的场景 source_dataset_id 应描述其卫星产品来源，不要当作与 BARC 标签来源相同的 join key；跨表 join 使用 field_id/year。

## 实际验收结果

| 检查 | 实际结果 |
| --- | --- |
| 原件 GeoPackage | 83 要素、5 个不同 FARM_ID；自定义 srs_id=100000，其定义为 NAD83 / Maryland (ftUS)，不是 EPSG:100000 |
| 标签计数 | 2021 grain/silage=14/4；2022=3/4；2023=15/4；合计 32/12 |
| 缺失标签 | 2021=65、2022=76、2023=64；249 个候选田块年度中 205 个空白；没有额外非标准标签 |
| 唯一键/缺失 | OBJECTID 和农场 ID 无缺失；83 个 field_id 唯一；44 个标签键唯一；旧表无重复且标签集合完全一致 |
| 原几何 | 83 个 Polygon/MultiPolygon 有效、非空；转换后输出 83 个有效、非空多边形；经纬度范围落在 BARC |
| 面积 | 全部有限且 >0；EPSG:26918 投影计算，无经纬度直接求面积 |
| 面积对照 | 对照源 ACRES×0.40468564224，差异为约 -0.291584% 至 -0.001462%；无一超过 1%；只报告差异，不缩放几何凑英亩 |
| 序列化回读 | exported GeoJSON 重投影后面积与 area_ha 最大差 4.9746e-9 ha（容差 0.0001 ha），字段/单位/关联检查通过 |
| 验证泄漏 | 同田跨年同折、同农场跨年同折；5 折农场不交叉；各折训练集均含两类 |
| 复现 | 重跑生成器后所有交付与报告 SHA-256 一致；原件 SHA 不变；验证器实际执行通过 |

### 显式几何修复

原始几何均通过有效性检查，但 `barc_301` 的微小组件在投影变换后退化，EPSG:26918 和 EPSG:4326 几何均出现 Too few points。生成器对**派生几何**执行 make_valid，保留多边形组件、移除退化的非面积部分，没有简化或修补原件。投影面积变化绝对值为 `1.74623e-10 m²`；经纬度面积变化为 `3.38813e-21 degree²`（后者仅记录拓扑修复数值，不用来计算 ha）。修复原因、方法和前后数值见 acceptance.json 的 geometry_repairs。该田仍保留并映射，不删除记录。

## 唯一发布的验证方案

依组长本轮指令，保留现有按农场分组基线；发布**一套**留一农场 5 折。编号按原 FARM_ID 字符串排序冻结，从 0 开始；与原 notebook GroupKFold(5) 的留出农场集合相同，但不承诺 sklearn 的 fold 编号顺序相同。C 应读取文件，不再次随机拆分；不并发发布另一份三折结果。这里只生成划分，没有训练或指标。

| fold_id | 留出 farm_group | 测试 grain/silage | 训练 grain/silage | 测试独立田 |
| --- | --- | --- | --- | ---: |
| 0 | 22358 | 11/1 | 21/11 | 10 |
| 1 | 22359 | 2/0 | 30/12 | 2 |
| 2 | 22380 | 14/11 | 18/1 | 19 |
| 3 | 22381 | 4/0 | 28/12 | 2 |
| 4 | 22854 | 1/0 | 31/12 | 1 |

fold 1/3/4 没有测试青贮，单折该类 recall 无定义；不能用零或高 accuracy 隐藏这一点。fold 2 训练青贮仅 1 条，小样本和强农场聚集会严重限制可靠性。建议 C 汇报整体 OOF、逐折样本数与无定义项，同时保留未校准说明；本任务不做模型实验。同农场验证不等于独立年份验证，也不证明迁移到加州。

旧合同写固定种子 42、按田块三折，与此文件不同；这是本轮组长明确指定保留农场基线后的**显式例外**。A 在此记录，供团队统一合同；没有修改 C 的实现、旧 notebook 或合同文件，也没有把两个验证方案混用。

## 可复现命令与环境

Python 3.13.0；确切依赖见 src/data/requirements.txt（Shapely 2.2.0、PyProj 3.8.0 等），PROJ 版本见 acceptance.json。下列命令在仓库根目录运行，无需卫星网络访问：

```sh
python3 -m venv /tmp/cornhub-a-data-venv
/tmp/cornhub-a-data-venv/bin/python -m pip install -r src/data/requirements.txt
/tmp/cornhub-a-data-venv/bin/python src/data/prepare_core.py
/tmp/cornhub-a-data-venv/bin/python src/data/validate_core.py
```

本轮实际命令输出、版本与重复生成检查见 run_log.txt。第一次普通网络安装失败；使用执行环境授权后临时 venv 安装成功。首次几何处理主动报 barc_301 无效，查明退化原因后加了显式修复日志；后续真实检查通过。生成器对核心条件失败即停止，输出不能使用失败批次。

未执行：地面核查、人工逐点制图复核、跨田边界重叠的语义纠正、GPS 精度评估、卫星读取、模型训练/精度/校准、分析、网页、加州验证、赛事正式提交。这些不包含在 A 本轮验收结论中。

## README 与合同差异及建议

| 项目 | README/现有实现 | team-contract | 本轮处理/建议 |
| --- | --- | --- | --- |
| 研究范围 | 加州 2022–2026 | BARC 2021–2023 首轮 | 依组长指令先 BARC 方法验证；加州待有真值后扩展。建议后续共享文档同步此阶段口径；不声称加州效果 |
| 分支 | member/01–05 | work/a-data 等 A–E | 本轮 work/a-data；保留旧分支，建议下轮 README 统一 |
| ID | 旧 CSV 数字字符串 | barc_<原稳定ID> | 新增 ID 映射，旧表保留，供 B/C/D/E 适配 |
| 面积 | acres；有些 NASS 为千英亩 | area_ha | core 用投影 ha，映射保留 source_acres；不同文件明确换算 |
| 输出路径 | 05_Model 和 processed/sentinel2 草稿 | core/satellite/model/analysis | 本轮只生成 core；原型仍保留，由 B/C 在各自目录适配 |
| 卫星窗口 | 原型 July–Nov | April 1–Dec 1 右端不含 | smoke_sample 按合同；不改 B 的查询代码 |
| 验证 | 原型 FARM_ID 分组 | 田块 3 折种子 42 | 本轮只发农场 5 折，依本任务明确指令；C 与团队统一合同后读取本表 |
| 核查公式 | A²p(1-p) | area_ha×4p(1-p) | 两者排序可能不同；建议 D 当前接口继续合同公式，并由组长另行确认；A 未改分析 |

## 转发给 B/C/D/E

> A 已交付 PR #6，分支 work/a-data（首次可用数据提交 6b9f09f）。从 data/processed/core 读取 fields.geojson、labels.csv、smoke_sample.json、validation_folds.csv、field_id_map.csv。共同样本 barc_1 / 2021 / grain，6.63739333 ha；窗口 [2021-04-01, 2021-12-01)。边界 EPSG:4326 经度在前；关联用 field_id 或 field_id+year；ID 保持字符串、标签小写、面积 ha。83 边界/44 标签/34 有标签田已核验，无重复键或孤立标签，导出几何有效。fold_id=0–4 按 farm_group=原 FARM_ID 留一农场；只有一套划分，与旧合同 3 折田块规则不同；不要自行再拆。fold 2 训练青贮仅 1 条，其余部分测试折缺青贮，模型结果须说明。全部 83 块不等于各年全是玉米；仅代表 BARC，不代表加州。来源、差异、修复和验收见 reports/a_data/README.md。
