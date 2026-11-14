# C: 首轮真实农场分组 OOF 验证

负责人 C；分支 work/c-model；PR https://github.com/superboycyc-dot/CornHub/pull/4 。本轮替代此前 partial/pending 状态。

## 真实输入与交付

A PR #6 提交 `df7ce8cd63039e90de7ca78ba95f4f3259ee15c5`：44 标签年度、34 独立田、32 grain/12 silage、5 个农场固定 folds。B PR #5 提交 `05a81a7d1634c80d3c56b66cf9eb9acb9527fc9b`：44 行特征、4524 行真实逐场景观测，全部标签键已覆盖。读取固定提交的临时只读快照，输入提交与 SHA-256 见 merge_report.json，不修改或复制提交 A/B 目录。

labels/features/folds 按 field_id+year 一对一全部匹配；重复键、未知田块、schema 错误、未匹配和排除均 0。保留预先声明的 limited 可用策略：26 usable、18 limited；limited 不是概率可靠性类别。exclusions.csv 本轮仅表头，未静默丢行。

实际拟合 6 个模型：5 个外折模型与 1 个全量 inference 模型。predictions.csv 为 88 行，44 OOF + 44 inference，唯一键 field_id+year+prediction_role；inference 的 fold_id 留空。metrics.json 仅评估 OOF，全量 inference 含训练样本，不能拿来报验证成绩。未额外调参、选特征或改变划分。

## OOF 结果

| 指标 | Random Forest | 固定收获时间规则 |
| --- | ---: | ---: |
| 评估田块年 | 44 | 44 |
| macro F1 | 0.650794 | 0.429165 |
| silage precision | 0.666667 | 0.314286 |
| silage recall | 0.333333 | 0.916667 |
| Brier | 0.162731 | null（硬类别规则） |

RF 混淆矩阵：真实 grain→grain 30、grain→silage 2；真实 silage→grain 8、silage→silage 4。12 条青贮只识别 4 条，漏掉 8 条，不能称已解决分类问题。规则 DOY<=258 判青贮（缺 drop day 弃权），本批全有 drop day，故与 RF 同覆盖；其高 recall 伴随 24 条 grain 被错判为 silage，不能单看召回宣称更好。规则阈值未按本批数据优化；无概率或 Brier 可靠性声明。

| fold | 测试 grain/silage | 训练 grain/silage | macro F1 | silage recall |
| --- | --- | --- | ---: | ---: |
| 0 | 11/1 | 21/11 | 0.700000 | 1.000000 |
| 1 | 2/0 | 30/12 | null | null |
| 2 | 14/11 | 18/1 | 0.603175 | 0.272727 |
| 3 | 4/0 | 28/12 | null | null |
| 4 | 1/0 | 31/12 | null | null |

总体指标由所有 OOF 行汇总，未平均包含 null 的单折 F1。fold 1/3/4 的测试真值缺青贮，macro F1 与 silage recall 无定义；precision 在无预测正类时也为 null。逐折 Brier、混淆计数与解释见 merge_report.json。fold 2 训练仅 1 条青贮，承担 11/12 条青贮的测试，样本结构严重限制学习与外推。固定使用 A 农场 5 折（A 已记录组长批准的原合同田块三折例外），没有重拆来追求好成绩。

误判清单 oof_errors.csv 包含 10 条真实 OOF 错误、概率、fold 与数据质量，仅作观察，不把缺口直接认定为错误原因。例如 barc_382/2023（usable，max_gap=30）真实 grain、OOF p_silage=0.564167，被错判为 silage；说明 usable 卫星质量不等于预测正确。

## 实际运行与独立检查

在仓库根目录运行：

```sh
python3 -m venv /tmp/cornhub-c-model-venv
/tmp/cornhub-c-model-venv/bin/python -m pip install -r src/model/requirements.txt
/tmp/cornhub-c-model-venv/bin/python -m src.model.from_refs --core-ref df7ce8cd63039e90de7ca78ba95f4f3259ee15c5 --satellite-ref 05a81a7d1634c80d3c56b66cf9eb9acb9527fc9b --train --inference
python3 -m src.model.review_features --satellite-ref 05a81a7d1634c80d3c56b66cf9eb9acb9527fc9b
PYTHONDONTWRITEBYTECODE=1 /tmp/cornhub-c-model-venv/bin/python -m unittest src.model.test_pipeline -v
```

实际执行全部成功。review_features 独立校验 4524 行时序唯一键、年份窗口、范围、传感器与来源字段，并重做同日聚合、有效比例门槛和 7 个数值特征/质量类别；44/44 一致，容差 1e-9。全部 44 行均有晚季有效日，不再沿用旧样本“缺晚季”结论。结果与哈希见 upstream_review.json；这只是场景汇总与特征一致性，不是重新读取影像验证缩放/SCL/像元计算。B 的 pc_batch_report.json 引用的 A 边界与标签 SHA-256 与 C 输入一致。几何/面积核验沿用 A，不由 C 重跑。

整体 OOF 指标和各折 Brier 与 sklearn.metrics 独立对照一致；核验角色唯一性、44/44 OOF/inference、阈值、fold 映射、有限概率及缺类 null。acceptance.json 记录运行环境与结果（Python 3.13、numpy 2.5.4、sklearn 1.9.1）。10 项内部测试全部通过，包括折内填补、田块/农场泄漏拒绝、附加列不得覆盖标签、缺类与单条 partial 弃权。合成输入与结果在 TemporaryDirectory 自动清理，未发布。git diff --check 通过。

## 方法与限制

RF 固定 100 trees、depth 4、leaf minimum 2、balanced class weights、seed 42、单 CPU，无调参。特征仅 ndvi_peak、peak_doy、max_drop_per_day、drop_doy、ndvi_late_mean、valid_obs_count、max_gap_days；ID/year/fold/farm/标签及派生变量不入 X。每折独立 median imputer 仅拟合训练行，不用测试统计；全缺失训练列按既定 keep_empty_features 处理。输入元数据只用于核验与审计。

未校准，不能据 p_silage 宣称可靠概率、真实误判概率或面积置信区间。34 独立田、5 农场不足以证明广泛迁移；同田跨年固定分组，未做独立年份或加州验证。固定 DOY 规则可能捕获其他季节变化，并不证明检测到了实际收获。18 个 limited 样本保留可能影响结果；未因结果追加质量筛选或调参。

数据阻塞已解除。后续 D 可按单个 year 和显式 role 消费预测；验证/核查模拟只用 OOF。E 可同步真实输出，概率仍需标注未校准。C 未修改 D/E、合同或根配置，未运行面积经济结论、网站部署或赛事提交。模型接口与详细约定见 notebooks/c_model/README.md。
