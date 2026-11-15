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

## National candidate layer and prediction slots

Added an independent white-marker layer with an explicit show/hide checkbox (off by default). It covers all 6,112,209 CSB and 15,939 CropSight objects in A's pinned handoff, without merging overlapping sources. Locations are bounding-box-center display points, not surveyed boundary polygons. Counted clusters are used at low zoom or dense views; individual IDs load on demand. Annual crop eligibility is preserved for 2021–2023; 2024/2025 are not populated from older data.

Every object retains its original candidate_id, source_field_id and source_dataset_id, including ID string length. A prediction adapter is available for all of them, keyed by source, ID, year, role and model version. A configured endpoint may return separately calculated outputs; empty configuration/results show Not computed. IDs, model versions, roles, years, duplicate records and probability ranges are validated. BARC remains independent. No national probabilities or crop confidence were fabricated or borrowed from BARC.

The builder checked all 1,232 upstream shard hashes and counts and packed 6,128,148 objects into 170 compressed display tiles (~40.7 MB). Source geometry-valid flags and annual eligibility are preserved, including flagged-invalid source objects. Data provenance and a rebuild command are in web/national/README.md and national-index-validation.json. 10 Node tests and production build passed; supported browser tools remain unavailable, so visual/hover QA is not claimed.
## 集成验收 2026-11-14（America/Los_Angeles）

- 合入 main 的 A/B/C/D 交接后，通过 27 个发布输入核验、9 个 Node 测试及生产构建。
- 修复全国 external_corn 候选分片进入 BARC 网页发布目录的问题，并验证旧副本会清理。
- 修复浏览器检查的旧概率定位器；真实数据桌面/手机、键盘田块选择、2024 pending 与 inference 队列隔离均通过本地 Chromium 检查。截图见 integration-real-*，详细证据见 integration-browser-verification.json。外部底图部分瓦片加载失败时提示正常，未验证生产部署。
- 显示概率最多六位小数，避免浮点尾数挤出面板；原始预测文件不变。

## National polygon outlines and small-scale points

Replaced close-up national center markers with actual source Polygon/MultiPolygon geometry, white outline and translucent fill. Source geometries are simplified for display with topology preservation (0.0001 degrees), not replaced by rectangles. Source invalid-geometry flags remain explicit. At zoom 12 and closer polygons are displayed; farther out white points/clusters remain visible, including at a roughly 50 km ruler. No minimum national visibility cutoff was added. All source IDs, annual crop flags and prediction interfaces remain unchanged. Polygon tiles are selected by true geometry extents to retain edge-crossing shapes. Browser visual QA is still not claimed.
