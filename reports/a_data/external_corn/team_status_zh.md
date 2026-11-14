# 本轮团队状态快照

读取时间及固定分支 SHA 见 team_snapshot.json。通过 fetch、各角色报告和 PR #2/#4/#5/#6/#7/#8/#9 检查；没有重新运行队友的卫星、模型、分析或网站。main 当前 2f28056 已合入范围统一说明，A–E 产物仍主要在各角色分支。

| 角色 | 远端证据 | 当前结论 |
|---|---|---|
| A / PR #6 | df7ce8c；83边界、44标签、农场5折及独立验收 | 第一轮核心数据已交付 |
| B / PR #5 | 05a81a7；44特征、4524时序，26 usable/18 limited | 全部有标签年度已提取；本轮没有重读影像 |
| C / PR #4 | a867e4e；44 OOF+44 inference，metrics evaluated | OOF macro F1=0.650794，青贮 precision=.666667、recall=.333333；12条青贮漏8条，概率未校准 |
| D / PR #7 | 91ddbff；2022–2025 输出 | 2022/2023 computed；2024/2025 缺 A/B/C 真实输入而 pending；与 main 的 BARC 2021–2023 范围仍需协调 |
| E / PR #2 | 9a1dec7；真实边界、公开站点 | 已发布页面但其说明仍使用旧 C pending/单田 B 快照，需集成最新 B/C/D；新版交互视觉验收仍有缺口 |

C 的混淆矩阵：真实 grain 30判grain/2判silage；真实silage 8判grain/4判silage。这是小样本探索结果，不能改写成全国准确率。E 页面：https://cornhub-field-evidence.feistydegu3.chatgpt.site 。本轮没有浏览器验收该页面。

本次新增 CSB/CropSight 为独立外部候选库，不替换 A 的 core、B 的特征、C 的真值或 D 的目标年度。main 的本轮方法验证仍是主办方 BARC；全国扩展需另有用途真值和验收。政策研究供 D/团队理解背景，不将补助金额写入已有经济输出或模型标签。
