# C: A 交付接入与实际预检

负责人 C；分支 work/c-model；PR https://github.com/superboycyc-dot/CornHub/pull/4 。2026-11-14 更新，替代第一轮“三份输入均缺失”的状态。

## 本轮真实输入与结果

A PR #6 / work/a-data 提交 `df7ce8cd63039e90de7ca78ba95f4f3259ee15c5` 已读取。B PR #5 / work/b-satellite 提交 `e107fea4a539a6a9f973263f6a1be23158438304` 的 features.csv 仍只有表头。两分支尚未合入本模型工作树；使用只读 Git 快照在临时目录提取四份输入，避免复制或修改 A/B 目录，运行后清理。SHA-256 与完整提交号记录在 merge_report.json。未改合同、根配置、队友成果或旧 notebook。

实际预检通过：44 标签、34 独立田、32 grain / 12 silage；44 个标签键全部一对一匹配 folds；重复键 0、schema 错误 0。83 个田块的分组元数据包含 5 个有标签农场，同田跨年与同农场均不跨折；标签/folds 无未知田块。本轮独立检查键和分组，几何/投影/面积有效性沿用 A 验收，不声称重新做过几何核验。

年度 grain/silage：2021=14/4，2022=3/4，2023=15/4。特征 0 行，labels→features 匹配 0，合并可用记录 0。44 个标签年度逐项记录 missing_features，详见 exclusions.csv 与 merge_report.json。没有错误地继续报告 A 文件缺失。

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
python3 -m src.model.from_refs --core-ref df7ce8cd63039e90de7ca78ba95f4f3259ee15c5 --satellite-ref e107fea4a539a6a9f973263f6a1be23158438304 --train
PYTHONDONTWRITEBYTECODE=1 /tmp/cornhub-c-model-venv/bin/python -m unittest src.model.test_pipeline -v
```

真实输入命令 exit 0，状态 pending：未调用随机森林训练，没有 OOF/inference 预测。predictions.csv 只有合同表头；metrics.json 中 n_evaluated=0、评估类计数 0/0、指标与混淆矩阵 null；评估类计数不是上游标签总数。规则对照同样 pending。当前阻塞仅为 B 的真实特征尚未生成。

9 项内部检查通过：缺输入 pending、重复键与跨年田块泄漏拒绝、同农场跨折拒绝、农场结构报告与未知特征 ID 拒绝、未匹配与质量排除、缺类 null、折内填补与角色分离、训练缺类弃权、B 附加列不能覆盖 A 标签或划分。合成输入/预测/指标全部在 TemporaryDirectory 自动清理；未写入团队发布产物。临时环境 Python 3.13、numpy 2.5.4、scikit-learn 1.9.1。测试验证接口行为，不是真实世界精度。git diff --check 通过。

## 下步依赖

B 提交同 field_id/year 的真实特征与缺测原因，优先共同样本 barc_1/2021，再覆盖完整 44 个标签年度；单个真实样本只能验证读入，不足以做跨农场 RF OOF。收到后更新 satellite ref 重跑同一入口，记录质量排除、实际训练/测试类数、OOF 覆盖和逐折/整体指标；仅在显式 --inference 时生成全量推断。

A 已检查挑战说明与 explorer：未找到禁止训练或固定测试清单，要求公开来源、有效真实标签、分组留出、保留原标签和来源引用。此轮据其报告消费固定 folds，不宣称额外主办方书面确认。上游组装包许可仍按 A 记录，未复制原件。

模型命令、特征、规则阈值与限制详见 notebooks/c_model/README.md。没有运行真实模型训练、校准、地面核查、分析、网页、部署或赛事提交。
