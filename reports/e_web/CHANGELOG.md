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

## 2026-11-15 — MD/CA outlines, US points

- Limit published source outlines to MD (49,902 objects) and CA (18,434); keep all 6,128,148 national object IDs and position points. Source inventories can overlap.
- Restore individual point loading elsewhere, keep low-zoom count clusters, and preserve all future prediction slots. No national probabilities are available or generated.
- Enable the national checkbox on opening and label its outline scope explicitly. Keep the 83 green BARC boundaries and Maryland opening view.
- Add repeatable scope reducer and byte-level verification against the prior complete point inventory. Deployment verification is recorded in national-scope-verification.json and deployment verification report.

- Deployment: Sites v13 succeeded at the existing public URL. Live HTTP verification without cache-busting matched release manifest, homepage, JS bundle, national indexes, MD/CA outline samples and US point samples byte-for-byte. Evidence: deployment-scope-verification.json. Browser visual verification was unavailable.

## 2026-11-15 — V9 confidence integration

- Pin the latest inspected CA/MD snapshot d7648e0c81b0c59a494d44d8309684ba84ef2da6 (a new update arrived during integration). All 10 annual CSVs retain original columns and values in byte-exact gzip transport, with local processed files taking precedence. No teammate scripts or outputs changed.
- Color existing field outlines and fills by confidence_score: >80 green, >60–80 yellow, ≤60 red; missing/uncomputed stays white. Preserve color on hover/selection; no confidence assigned to low-zoom clusters.
- Add hover details, legend and separate V9 field card. Default to inference, disable V9 colors for OOF, and retain original BARC baseline and D analysis as separate outputs. Surface experimental calibration, California transfer, conditional crop eligibility and training overlap.
- Validate strict thresholds, probability/score separation, state/year/source identity, duplicate rows, null values and repeatable synchronization. Check all upstream CSV bytes and scored map joins; see v9-integration-verification.json. Supported browser tools unavailable, so browser visual QA is not claimed.

- Deployment: Sites v14 succeeded at the existing URL. Without cache-busting, live homepage, JS/CSS bundles, release/manifest/index and all 10 annual gzip CSVs matched the local build byte-for-byte. All live CSVs were parsed again: 341,550 rows, 56 red +11 yellow scored annual records, zero >80 green records; others remain white. Evidence: v9-live-verification.json.

## 2026-11-15 — Maryland detail only, confidence >90 green

- Refresh V9 pin to cf612d37d762392068056f0c6cb2e132bf16f4cf; publish/load only Maryland 2021–2025 CSVs (249,485 field-year rows, 128 scored records). California annual prediction files are excluded and stale generated copies removed. Upstream snapshot is still partial.
- Remove California polygon assets from web publication, retain all 6,128,148 US display-point identities, and keep 49,902 Maryland candidate outlines plus independent BARC boundaries. All other regions, including California, use points; overview counts remain white.
- Change confidence threshold to >90 green, >60–90 yellow, ≤60 red, unavailable white. Test exact 90 and adjacent values; preserve year/role/source isolation. Existing confidence scores are unchanged.
- 2024/2025 national dots are explicitly historical reference locations, not verified current-year corn fields. Maryland conditional predictions retain source eligibility and training-overlap notes.

- Deployment: Sites v15 succeeded at the existing public URL. Live homepage, JS/CSS, release manifest, Maryland-only prediction manifest, all five MD annual CSVs, Maryland-only polygon index/sample and California point tile matched local build bytes without cache-busting. Live parse confirmed 249,485 Maryland annual records (93 red, 35 yellow, zero >90 green predictions; remaining records white). Evidence: v9-live-verification.json. 16 tests passed; browser visual QA remains unavailable.

## 2026-11-14 (America/Los_Angeles) — color by original model probability

- Replace confidence-driven colors with original V9 p_silage: >0.9 green, >0.6–0.9 yellow, ≤0.6 red, unavailable white. Keep confidence and raw selected-class probability separately labeled in details.
- Apply the same rule to outline/fill, hover/selection, legend and field card. Missing confidence no longer blocks a valid model probability. Test boundaries and deliberately conflicting/missing confidence values.
- Preserve Maryland-only detailed data, other-state points, original IDs, source probabilities, selected year, inference/OOF isolation and existing upstream pin.

- Sites v16 deployed successfully. Live homepage, JS/CSS, release metadata, MD-only manifest, all five MD annual CSVs and geometry/point samples matched local build bytes without cache-busting. Color basis verified as p_silage; 128 scored annual records yield 43 red, 12 yellow and 73 green records. Original data bytes unchanged. Evidence: v9-live-verification.json. Browser visual verification remains unavailable.

## Map-first layout

- Prioritize year, model role and a readable silage-probability legend; move coverage and technical status into expandable details. Remove decorative headline and redundant telemetry.
- Force the US candidate layer on, hide BARC reference polygons by default and label their optional toggle explicitly. Preserve Maryland outline/other-state point scope.
- Separate primary left controls from right evidence panel; mobile evidence replaces the legend card to avoid overlapping controls.

## Review overview and field lists

Restore BARC reference layer by default. Move silage-probability legend to lower right with 48% opaque background. Add current-year Maryland available-prediction percentages and clickable red First review, orange Suggested review and green lists. Counts describe user-requested probability buckets, not validated error/review requirements or D area summaries. Missing predictions excluded; conditional predictions included and labeled. Each list shows original field ID (no supplied names), boundary-center coordinates, predicted silage/grain use and original probability. Harvest dates are unavailable. Location index is generated from existing source geometries during sync.

## Black-screen hotfix

Reproduced ReferenceError: React is not defined by rendering ReviewOverview with the production classic JSX transform. Added the missing React import. Added a component render regression check for loading, populated and OOF states; compilation and HTTP checks alone had missed this runtime failure.

## Compact review rows

Move review summaries into three compact vertical rows at upper right, with a fourth white Unavailable row counting selected-year records without predictions. Missing counts include pending, non-corn and invalid-geometry statuses; cross-year rows are excluded. Preserve clickable color lists and percentages among available predictions. Remove lower-right explanatory card while preserving visible data-load failures.
