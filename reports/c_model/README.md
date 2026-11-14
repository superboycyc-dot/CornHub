# C: A/B 真实交付接入与模型就绪检查

负责人 C；分支 work/c-model；PR https://github.com/superboycyc-dot/CornHub/pull/4 。2026-11-14 更新，已接入 B 的真实 partial smoke，替代前轮“B 只有表头”的状态。

## 本轮真实输入与结果

A PR #6 / work/a-data 提交 `df7ce8cd63039e90de7ca78ba95f4f3259ee15c5` 已读取。B PR #5 / work/b-satellite 提交 `9ff56716c5584b25238c91398f306a17e7269762` 已交付 1 行真实特征，状态 partial_network_blocked。两分支尚未合入本模型工作树；使用只读 Git 快照在临时目录提取四份输入，避免复制或修改 A/B 目录，运行后清理。SHA-256 与完整提交号记录在 merge_report.json。未改合同、根配置、队友成果或旧 notebook。

实际预检通过：44 标签、34 独立田、32 grain / 12 silage；44 个标签键全部一对一匹配 folds；重复键 0、schema 错误 0。83 个田块的分组元数据包含 5 个有标签农场，同田跨年与同农场均不跨折；标签/folds 无未知田块。本轮独立检查键和分组，几何/投影/面积有效性沿用 A 验收，不声称重新做过几何核验。

年度 grain/silage：2021=14/4，2022=3/4，2023=15/4。特征 1 行，labels→features/folds 匹配 1，43 个标签年度仍 missing_features。barc_1/2021 为 grain，fold 3；limited 按首版既定策略保留在候选训练集，未悄悄改为质量排除。但它是唯一候选样本，留出 fold 3 后训练 0 行，无法做 OOF；全量训练也仅有 grain 一类，inference 明确弃权。exclusions.csv 记录 43 条缺特征及该 1 条无法验证原因；无任何训练内指标。

使用 A 唯一发布的农场 5 折（A 报告记录组长明确要求，作为旧合同田块 3 折的例外），不自行生成第二套划分。farm_group 仅校验分组，不进入特征。按全部标签预检：

| fold | 测试 grain/silage | 训练 grain/silage | 留出农场 |
| --- | --- | --- | --- |
| 0 | 11/1 | 21/11 | 22358 |
| 1 | 2/0 | 30/12 | 22359 |
| 2 | 14/11 | 18/1 | 22380 |
| 3 | 4/0 | 28/12 | 22381 |
| 4 | 1/0 | 31/12 | 22854 |

以上是标签结构，**不是已训练模型的验证成绩**。B 到齐后可能因质量排除改变有效样本数，训练入口会重新统计。fold 1/3/4 测试青贮缺类，macro F1 与 silage recall 将为 null 并说明；precision 取决于预测正类是否存在。fold 2 仅 1 条训练青贮，结果会高度不稳定。Brier 在有 OOF 时仍可定义，但不能证明概率可靠。全程未校准，无概率可靠性承诺；BARC 不能证明加州迁移性能。

## 实际运行

仓库根目录：

```sh
python3 -m src.model.from_refs --core-ref df7ce8cd63039e90de7ca78ba95f4f3259ee15c5 --satellite-ref 9ff56716c5584b25238c91398f306a17e7269762 --train --inference
PYTHONDONTWRITEBYTECODE=1 /tmp/cornhub-c-model-venv/bin/python -m unittest src.model.test_pipeline -v
```

真实输入命令 exit 0，状态 pending：未调用随机森林训练，没有 OOF/inference 预测。predictions.csv 只有合同表头；metrics.json 中 n_evaluated=0、评估类计数 0/0、指标与混淆矩阵 null；评估类计数不是上游标签总数。规则对照同样 pending。model_fit_count=0，OOF/inference 输出均 0 行。当前阻塞为真实特征只覆盖一个类别的一块田一年，而非数据文件缺失。

10 项内部检查通过：缺输入 pending、重复键与跨年田块泄漏拒绝、同农场跨折拒绝、农场结构报告与未知特征 ID 拒绝、未匹配与质量排除、缺类 null、折内填补与角色分离、训练缺类弃权、B 附加列不能覆盖 A 标签或划分、单条 partial 特征不得生成训练或 inference 结果。合成输入/预测/指标全部在 TemporaryDirectory 自动清理；未写入团队发布产物。临时环境 Python 3.13、numpy 2.5.4、scikit-learn 1.9.1。测试验证接口行为，不是真实世界精度。git diff --check 通过。

## 下步依赖

B 先补齐共同样本晚季窗口并完成 smoke 验收，再继续完整 44 个标签年度。至少需要跨农场的真实两类特征，且每个被评估留出折的剩余训练部分都包含两类；C 不重新划分来迁就现有数据。B 当前另有 141 个场景读取未完成（HTTP 503/格式失败），完整批处理尚被其 smoke 门槛阻止。收到更新后替换 satellite ref 重跑，继续报告未匹配、质量排除、各折实际类数与 OOF 覆盖。

A 已检查挑战说明与 explorer：未找到禁止训练或固定测试清单，要求公开来源、有效真实标签、分组留出、保留原标签和来源引用。此轮据其报告消费固定 folds，不宣称额外主办方书面确认。上游组装包许可仍按 A 记录，未复制原件。

模型命令、特征、规则阈值与限制详见 notebooks/c_model/README.md。没有运行真实模型训练、校准、地面核查、分析、网页、部署或赛事提交。

## 对 B 真实部分季节结果的独立检查

B 的 69 行实际场景记录按合同同日最大有效比例/scene_id 排序，得到 30 个已处理日期、14 个有效日；逐项重算 7 个数值特征，与 features.csv 一致（容差 1e-9）。B 引用的 A 提交及边界 SHA-256 与 C 输入一致。输入与结果摘要见 upstream_review.json；这项检查只核对交接一致性，不是重跑影像处理。

最后有效日 2021-06-07，最长缺口 177 天，9–11 月没有有效记录，ndvi_late_mean 为 null。峰值 DOY 108、最大下降 DOY 130 都只描述已覆盖的春季片段，不能当玉米完整季节峰值或收获日期。缺晚季不是 NDVI=0、全云或 grain 的证据。固定收获规则未在该单条数据上打分或发布预测；不把其春季下降套作青贮证据。无插值、伪观测、伪概率或单类硬编码预测。
