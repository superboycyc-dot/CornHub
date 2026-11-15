> 历史快照：本文记录首轮交接时点。后续 BARC 范围、农场五折及真实 A/B/C/D 交付已更新；当前状态以根 README、团队合同顶部及各角色最新报告为准。原始审计记录保留。

# 五人和各自 agent 的接手说明

先读 [进度台账](project-status.md)、[现有团队合同](team-contract.md)、[本会话工作日志](worklog-2026-11-14.md)。本页补充交接，不建立第二套 schema。成员姓名、账号、agent 身份尚未确认；A–E 是角色占位，不能宣称有人已接单。具体列定义以 team-contract 为准，发现与本页冲突先由 A 记录决定。

## 1. 所有权、首项任务和可并行工作

| 角色/分支 | 接手输入 | 首项交付与验收 | 依赖 | 推荐 PR 范围 |
| --- | --- | --- | --- | --- |
| A 数据/集成，work/a-data | 04_Evaluation 原件、两个整理脚本、挑战书 | core/fields.geojson、labels.csv、smoke_sample.json、validation_folds.csv；来源与几何/面积/关联报告 | 先解决 SCOPE-01/EVAL-01；无需等卫星 | core 四件套和生成器；共享合同改动单独说明 |
| B 遥感/特征，work/b-satellite | A 的 fields/sample；官方 starter 和本会话原型 | 一田一年真实 timeseries/features/曲线；再扩 44 个标签年度 | 没有 A 时先写读取和质量接口 | src/satellite、notebooks/b_satellite、processed/satellite、reports/b_satellite |
| C 模型/验证，work/c-model | A 的 labels/folds，B 的 features | 最多类/简单收割时间规则对照、RF、OOF 概率、合同指标；先可交 pending 接口 | 实际训练等 A+B；先锁定 split | src/model、notebooks/c_model、processed/model、reports/c_model |
| D 面积/核查，work/d-analysis | A 面积、B 质量、C OOF | 逐年/role summary、review_queue、缺测清单；真实标签上的同预算随机核查对照 | 先写函数与 null/pending 状态；真实效果等 C | src/analysis、notebooks/d_analysis、processed/analysis、reports/d_analysis |
| E 网页/演示，work/e-web | A 边界、B 时序、C 概率、D 汇总 | 同步脚本、地图/年度/田块详情/曲线/核查表；空状态能运行 | 先做无数据界面；真实联调依次接 A/B/C/D | web、reports/e_web |

A 维护根目录依赖、共享配置和合同。B/C 应把 notebook 中各自可复用的逻辑迁入各自目录，避免多人同时改同一 ipynb。D 不重复实现 C 的概率；E 不另写一套区域统计。每个角色自己维护 reports 下来源与日志。

## 2. 已有成果如何适配合同

| 现有成果 | 与合同的差异 | 适配负责人/要求 |
| --- | --- | --- |
| processed/barc_field_year_labels.csv | field_id 是 OBJECTID 的字符串；Grain/Silage 大写；ACRES；无来源/fold | A：保存原 ID 映射，统一 barc_<ID>、label 小写和 label_raw；面积按合同投影计算并与原 ACRES 比较，不能只换列名 |
| prepare_barc_labels.py | 仅导出有标签年度，不产 GeoJSON/fold/sample | A：保留原提取器及原表，新增 core 生成器，不把“44 行已提取”称为 core 已完成 |
| 05_Model 原型 ROOT=Path.cwd() | 从 notebook 目录启动可能找不到原件 | B/C：确定统一启动入口或可靠 repo-root 定位；记录完整运行命令 |
| 原型窗口 July–Nov | 合同 April 1 至 Dec 1（右端不含） | B：显式配置合同日期；日志记录 query，不偷偷改窗口 |
| 原型 SCL=[4,5]，10 m 网格，像元中心判定 | 合同要求记录掩膜/重采样/分母 | B：记录 SCL 最近邻、田块内总像元作分母；核对边界像元、nodata、缩放/offset |
| 原型用 solar_day 合成后算田块中位数 | 合同保留逐 scene_id，按有效比例择日，保留低覆盖观测 | B：先产逐场景原始表，再日聚合；不要编造合成结果的单一 scene_id |
| 原型无 >=0.5 有效比例特征门槛 | 可能用少量晴空像元作为整田特征 | B：按合同保留低覆盖原始记录但排除其特征贡献 |
| 原型特征名/定义与合同不同 | 没有完整 max_drop_per_day、边界感知 max_gap_days 和 quality_flag | B：以合同定义重新计算、记录缺失原因；不能仅列名替换 |
| 原型直接按 FARM_ID GroupKFold | 合同文件 fold_id 尚未生成，方案也不同 | A+C：冻结评估设计和计数，C 读取 A 的 folds；farm ID 不作输入特征 |
| 原型 OOF 字段为 silage_probability_oof 等 | 没有合同 role/model_version 格式，也无 pending metrics | C：导出 p_silage/predicted_label/role/fold/version；不混训练内预测 |
| 原型计算所有年度面积总和误差 | 合同要求一个 year、一个 role | D：用逐年输出；跨年度和不是某年收获面积，不得作为首页数字 |
| Quick Stats 2012–2025 文件 | 多年、县/州不同粒度；可能含抑制值 | A/D：保留文本值和源列，明确筛地区/年/层级；不能用作田块真值或把 (D) 当 0 |

## 3. 原型运行前的技术待查项

下列由静态阅读发现或提示，不代表已经做了遥感运行实验。B/C 接手后应记录实际结论。

1. 红光/NIR 目前直接做加减；若加载仍为无符号整数，减法有回绕风险。先确认实际 dtype、STAC 的 scale/offset、nodata 和库的处理行为，再显式转浮点并按产品规则计算反射率。不得认为共同乘法比例抵消就能忽略加性 offset。
2. 原型已把传入 load 的 AOI 从无 CRS 的投影坐标改成 WGS84 GeoJSON；但库版本、geopolygon 接口和实际下载仍未执行核验。
3. timeseries 全空时原型直接 sort_values 可能报列不存在；需输出明确 no_data 状态。
4. groupby.apply 默认是否保留 year 随 pandas 版本变化；函数当前读取 group.year，需改成显式传入分组键或固定兼容实现，并锁定环境。
5. 当前对整个 AOI 多次按田掩膜、compute，可能重复读取大块影像。先量一田一年耗时/下载量，再加缓存/批次与断点续跑，遵守团队工作区上限。
6. 5 个农场的训练/测试类别分布尚未实际生成；若训练折只剩一类，应报告不可评估并调整已记录的设计，不能悄悄退回随机拆分。
7. RF 概率未校准；OOF 只解决训练泄漏的一部分，不自动给出可靠概率或面积置信区间。Brier、校准证据、跨年/空间泛化仍需 C 交付。
8. 原型的输出目录没有已提交结果；“保存了代码”不表示代码生成的文件已经存在。

## 4. 每个 agent 的工作循环

1. 检查 git status 和当前分支；先记录已有未提交文件归属。不要 reset --hard、不要删除他人改动、不要共用同一可写 checkout。
2. fetch main，阅读最新合同与本角色 reports。已有角色分支则沿用；不存在才从最新 main 创建。更新前确认工作区干净或先把自己的改动安全提交。
3. 在角色报告写输入 commit、输入文件路径/哈希、预期 schema、计划输出和阻塞。缺输入时实现 pending 接口，不能造业务样本当真数据。
4. 执行最小真实样本；记录实际命令、依赖版本、UTC 时间、数据源/查询参数、输出位置、失败消息。重试或调整阈值要写明原因。
5. 检查唯一键、单位、范围、缺失和关联数；记录真实输出与未匹配项。任何统计必须说明 year、scope、prediction_role。
6. 提交自己负责的文件。PR 写问题、最终行为、输入输出接口、已运行检查、未运行部分、限制、依赖的 PR/commit。PR 提交不等于合并，合并不等于通过科学验证。
7. A 审查共享格式及空间/标签问题；下游成员复核能否直接读取。按 A 核心→B 时序→C 预测→D 汇总→E 联调合并；独立接口可提前合并。
8. 合并后更新本角色日志与进度台账，给下游“commit + 文件 + 命令 + 缺口”。群聊里的口头状态不能替代仓库记录。

本轮使用独立文档分支提交，通过 PR 供团队审查。之前本会话确实直接推送过 main（用户先前已授权），现在团队协作采用 team-contract 的 PR 工作流；历史事实保留在工作日志中。

## 5. 交付日志模板

复制到 reports/<角色>/YYYY-MM-DD-handoff.md；不要填未执行命令的想象结果。

```text
角色、成员、agent：
任务 ID、分支、PR：
基于 main commit：
输入文件、来源、SHA-256、schema 版本：
本次改变了什么、为什么：
执行环境与依赖版本：
实际运行命令与 UTC 时间：
输出文件、记录数、覆盖年份与范围：
唯一键/缺失/关联/单位检查结果：
实际验证结果及证据文件：
没有运行或没有完成的内容：
失败、重试与参数修改：
需哪个角色提供什么文件/决定：
已知限制及不可据此声称的结论：
交付 commit、PR 状态、下一步：
```

## 6. 集成人应首先确认的四个决定

- 第一阶段明确做 BARC 方法验证，还是仍严格只做加州？建议前者；加州保留扩展目标。把团队决定写进 README 和合同。
- 按农场/空间留出还是已有合同的田块 3 折作为主验证？查主办方指定规则，记录最终 folds 及每折类别数。
- 核查排序采用哪个公式及用途？D 给同预算比较，不把启发式称为最优策略。
- 角色账号和分支对应谁？未知先保留占位，不替成员接邀请、认领任务或发送外部消息。
