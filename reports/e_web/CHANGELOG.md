# E website integration log

## 2026-11-14 — Complete BARC handoff connected

- Scope confirmed by the user: BARC results only; national candidate parcels remain separate.
- A unchanged: df7ce8cd63039e90de7ca78ba95f4f3259ee15c5, 83 boundary features / 34 labeled fields / 44 labeled field-years.
- B updated 9d31ddf → 05a81a7d1634c80d3c56b66cf9eb9acb9527fc9b: 4,524 scene records and 44 features, 18 limited / 26 usable.
- C updated c3f432c → a867e4e19c431754e7b07ee8a260f48761d83d81: 44 OOF + 44 inference predictions; evaluated pooled OOF metrics. These are 44 field-years, not 88 independent samples. Probabilities are uncalibrated.
- D updated 25755b5 → b369af8fe673a2f384fb0462fc7e6bbb34a2eeaa: year/role-specific summary, queue, data-needed and review-simulation inputs. 2022/2023 computed; 2024/2025 pending with unknown cohort and null areas. Active D summaries exclude 2021.
- Render D’s exact outcomes, including increased error after heuristic review in 2023. Do not mix inference into OOF validation or review simulations.
- Added annual-file routing and checks; no reuse of another year’s summary or queue. Root files remain a matching year/role fallback. D has not supplied analysis/index.json; the pinned handoff manifest documents this directory-based compatibility path.
- Retained the Maryland 1 km opening view, field highlights, county layer and full-screen English interface.
- Verification: 8 Node tests; 27 source files byte-checked; annual/role/cohort and D input-hash checks; production build. No browser visual/hover check or real screenshot was performed because the supported browser tool is unavailable.
- Source changes are limited to web and reports/e_web. No teammate scripts, source IDs, model results, economic values or root configuration were changed.

## 集成验收 2026-11-14（America/Los_Angeles）

- 合入 main 的 A/B/C/D 交接后，通过 27 个发布输入核验、9 个 Node 测试及生产构建。
- 修复全国 external_corn 候选分片进入 BARC 网页发布目录的问题，并验证旧副本会清理。
- 修复浏览器检查的旧概率定位器；真实数据桌面/手机、键盘田块选择、2024 pending 与 inference 队列隔离均通过本地 Chromium 检查。截图见 integration-real-*，详细证据见 integration-browser-verification.json。外部底图部分瓦片加载失败时提示正常，未验证生产部署。
- 显示概率最多六位小数，避免浮点尾数挤出面板；原始预测文件不变。
