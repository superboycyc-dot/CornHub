# 成员 E 第一阶段交付与验收

负责人：E。分支：`work/e-web`。基线 `b603997`（main 的团队合同）。本轮仅新增 web 和 reports/e_web，无前端可沿用，无 AGENTS.md。没有公开部署、改动队友目录或根配置。

交付：React + Vite + Leaflet 本地页面；重复执行的逐字节数据同步；README；输入检查与浏览器验收脚本；桌面和手机空状态截图；来源记录。

## 实际检查

- `npm install --cache <可写缓存目录>` 成功；Node 24.22.1，npm 11.9.0，依赖版本已锁定。
- `npm test`：3 项通过。同步字节保真与删除上游后的旧副本清理；CSV 引号/ID/空值/零值；重复键、用途区分、概率范围、投影拒绝。
- `npm run build`：Vite 构建成功。`npm run dev` 成功，本地端口 5173。
- `PLAYWRIGHT_BROWSERS_PATH=<本地浏览器目录> node scripts/browser-check.mjs`：通过。实际截图 1440×1100 桌面、390×844 手机；手机无页面横向溢出；清单 HTTP 500 提示；按田块+年份+用途切换；不同用途的 summary 不显示；重复预测键拒绝；无浏览器异常。
- 年份和用途关联检查使用仅存在浏览器请求拦截中的隔离测试数据，不落发布目录，不作为演示数字或真实截图。
- 空状态截图已目视检查：`empty-state.png`、`empty-state-mobile.png`。页面无伪造曲线、概率、验证指标和经济结果。
- `git diff --check` 通过。发布副本、node_modules、dist 均忽略。

## 当前真实数据验收

实际输入：`data/processed/usda_nass/corn_state_benchmarks_2025.csv` 已同步，未接入 BARC 视图。合同 core 4 文件、satellite 2 文件、model 2 文件、analysis 2 文件全缺。故真实边界数、匹配数和真实模型结果均无法验收，不报告为零田块或成功联通。

页面显示尚未提供/缺测/未计算；读取失败显示具体文件和原因。边界未交付时无默认伪造样区。地图坐标按 GeoJSON 经度在前交由 Leaflet 转换，面积仅显示 A 的 area_ha。数据质量与模型概率单列；summary 使用 D 结果，不复制统计算法。不会混合 OOF 与 inference。

真实样本接通截图 **阻塞**，没有生成替代截图。A 的边界到齐后即可同步查看；完整闭环仍需要 B/C/D。待共同样本到齐，按 smoke_sample.json 的 field_id/year 打开页面、核实来源，再保存 `real-sample.png` 并补验收结果。

## 后续字段与负责人

|负责人|交付路径（前缀 data/processed/）|页面使用|
|---|---|---|
|A|core/fields.geojson|field_id、source_field_id、source_dataset_id、area_ha、真实几何|
|A|core/labels.csv、smoke_sample.json、validation_folds.csv|标签关联、共同样本选择、划分检查；后两者目前只载入与文件检查|
|B|satellite/timeseries.csv|按田块年展示 date/scene_id/ndvi/有效比例/来源|
|B|satellite/features.csv|quality_flag、valid_obs_count、max_gap_days、missing_reason|
|C|model/predictions.csv、metrics.json|p_silage、类别、role、模型版本、真实验证指标|
|D|analysis/summary.json、review_queue.csv|选定年和 role 的 scope/面积/覆盖率/经济情景、原始核查顺序与理由|

官方原件的准确下载位置与建议落盘位置见 `web/README.md`。由 A 核实官方使用限制、CRS、标签与许可；E 不生成 ID。由 B 按官方 notebook 提取真实观测。C 未训练维持空值，D 无参数维持经济情景 null。

需要 A 处理的文档冲突：根 README 的加州 2022–2026/英亩/旧核查公式与新合同的 BARC 2021–2023/公顷规则不同。本次依用户要求遵循团队合同，未越权修改根文件。
