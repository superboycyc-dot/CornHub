# CornHub 当前分析范围：2022–2025

本轮按用户指令扩大 D 的目标年份。旧合同和 A/B/C 实际来源仍覆盖 2021–2023；本次扩大接入接口和输出窗口，不伪造新年度数据，不修改模型或前端。

| 年份 | 状态 | 已确认样本数 | 样本面积 ha | 预期青贮 ha | 预期籽粒 ha | 样本预测覆盖率 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2022 | computed | 7 | 44.65081 | 18.66017 | 25.99064 | 100% |
| 2023 | computed | 19 | 123.08977 | 40.63679 | 82.45297 | 100% |
| 2024 | pending | 未知 | null | null | null | null |
| 2025 | pending | 未知 | null | null | null | null |

2022/2023 是选定有标签样本的 OOF 概率加权结果，概率未校准。100% 只指各自选定样本，不是全部 83 块田、全 BARC 或加州。所有年份、角色分别统计，不生成“四年总面积”。

## 1. 2024/2025 为什么是待计算

当前固定 A/B/C 快照没有这两年的年度标签、特征或预测记录，也没有确认的年度目标集合。缺少的输入为：

- A：年度目标田块集合及稳定 ID；用于 OOF 验证的真实用途标签和划分。
- B：对应年份、按既定窗口/掩膜/质量规则生成的真实特征。
- C：对应年份、明确角色的真实概率及模型/折来源。

旧 83 块边界不能自动当作每年的玉米范围。未知年度的总面积、覆盖面积、覆盖率和预期面积均为 null，不是 0；空 field_ids 和核查表表示尚未确认范围，不表示没有玉米。全局缺项见 period_status.json，不编造 field_id 填入逐田缺测表。

## 2. 按此前步骤完成的处理

1. 读取并验证 A/B/C 固定来源，检查唯一键和输入 SHA-256。
2. 明确选择单个 year 和 prediction_role=oof 后按年度合并。
3. 2022/2023 计算 Σ(area_ha×p_silage) 与 Σ(area_ha×(1−p_silage))，保留覆盖率。
4. 2024/2025 无真实年度集合和预测，输出 pending、null 面积和仅表头核查表。
5. 核查继续使用 area_ha×4p(1−p)，只允许 usable 进入队列；预算 3 块、种子 42、随机重复 200 次。
6. 更新四年汇总、变化分解、缺项记录及来源说明；没有外推、插值或复制上一年的概率。

每年目录均有 summary.json、merge_audit.json、feature_coverage.json、review_queue.csv、data_needed.csv 和 review_simulation.json。

## 3. 年度变化及核查解释

2022→2023 的样本数由 7 到 19，样本面积由 44.65081 到 123.08977 ha。预期青贮面积上升涉及不同样本范围和概率占比，不能直接解释成地区种植增长。2023→2024、2024→2025 缺真实估计，不计算趋势；相应 CSV 数值留空。

2022 同预算核查的面积绝对误差为 11.46035→2.61794 ha；2023 为 3.05772→4.00931 ha，后者变差。2023 三块田净上调约 7.06703 ha，原先少估变为多估，说明移除误差抵消可能让总量误差上升。负结果保留，不宣称排序普遍有效。新年份不运行虚构的核查效果评估。

经济参数缺少本地对应年份的单产、价格、口径、单位、含水基准、转换和来源，情景结果继续为 null；青贮鲜重与籽粒重量不直接比较，总产值不叫利润。

## 4. 历史数据和参考资料

2021/oof 保留不变，当前批处理和汇总排除 2021。旧完整报告见 [历史 2021–2023 汇总](archive/barc_2021_2023_all_data_summary_zh.md)，其中的模型指标、USDA/CDL 资料仅对应固定旧快照。

根目录单年 summary 现为 2022/labeled，而非原先的 2021 smoke；A 官方 barc_1/2021 smoke_sample.json 未修改。C 模型仍是其已交付的模型，不因扩大 D 的输出年份而重训，也不能宣称完成了 2022–2025 的全时段或独立年份验证。

加州 2024/2025 CDL 和 USDA 参考表不能替代马里兰 BARC 的年度边界、田块真值、NDVI 或预测。两份加州 2025 统计差异仍未解决，不混用、不平均。

## 5. 运行、来源和实际验证

运行：
```sh
python3 -m unittest discover -s src/analysis -p 'test_*.py' -v
python3 src/analysis/run_period.py --start-year 2022 --end-year 2025 --prediction-role oof
python3 src/analysis/report_results.py --c-ref a867e4e19c431754e7b07ee8a260f48761d83d81 --prediction-role oof
```

实际四年运行使用 --input-root 指向只读固定快照；来源 A=df7ce8cd63039e90de7ca78ba95f4f3259ee15c5、B=05a81a7d1634c80d3c56b66cf9eb9acb9527fc9b、C=a867e4e19c431754e7b07ee8a260f48761d83d81。换上游数据前须先更新 handoff_validation.json 的来源验收，不能把新内容仍标成旧提交。

20 项测试及四年流程已在执行环境断开前完成；状态为 partial_pending，2022/2023 computed、2024/2025 pending。断开后通过 GitHub 整理提交内容和核对范围，未再次运行 Python。上传后的入口和文档未做额外本地执行；详见 period_validation.json、validation.txt。

历史 summarize_data.py 被保护，不能覆盖带有 period_status.json 的当前四年汇总。新输入到齐后继续逐年运行，pending 才能转为真实计算结果。
