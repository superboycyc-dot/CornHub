# CornHub 成员 E：本地田块工作台

依据 `docs/team-contract.md`，范围为 BARC 2021–2023。根 README 仍记载旧的加州范围，待 A 协调；本页面遵循本轮合同。无数据也可以启动，不创建田块 ID 或预测，不公开部署。

需要 Node.js 20.19+ 或 22.12+（本轮 Node 24.22.1 / npm 11.9.0）。从仓库根目录：

```bash
cd web
npm ci
npm run sync:data
npm run dev
```

打开 http://localhost:5173 。`dev`、`build` 自动同步；运行中上游更新后执行 `npm run sync:data`，再点击“重新加载数据”。

```bash
npm test
npm run build
# 浏览器验收需先保持 npm run dev 运行
npx playwright install chromium
node scripts/browser-check.mjs
```

缓存目录受限时可设置 `npm_config_cache` 和 `PLAYWRIGHT_BROWSERS_PATH` 指向自己的可写目录。仅本地开发服务器，不是正式托管服务。

## 数据接入

同步脚本逐字节复制仓库 `data/processed` 下已有常规文件到 `web/public/data`，保留相对路径和全部字段。尚未合入主线的团队交接文件，可按 `data-handoffs.json` 中固定的完整提交 SHA 从本仓库 Git 对象只读提取；本地文件优先。每次清理旧发布副本，生成带来源的 manifest，缺文件继续，不修改队友目录。发布目录已忽略，不手改、不提交副本。源目录应由团队维护，不存凭据或未获许可的原件；同步不会过滤其已有文件。

页面读取合同十个路径：

- A：`core/fields.geojson`、`labels.csv`、`smoke_sample.json`、`validation_folds.csv`。
- B：`satellite/timeseries.csv`、`features.csv`。
- C：`model/predictions.csv`、`metrics.json`。
- D：`analysis/summary.json`、`review_queue.csv`。

字段、唯一键与空值定义见团队合同。CSV 保留字符串，不转换 ID。按 `field_id+year` 关联，再选择一个 `prediction_role`。CSV 缺字段、重复键、非法概率及非 4326 声明的边界会报错并隔离该文件。GeoJSON 使用经度在前；Leaflet 自身转换，不手动交换或用经纬度计算面积。背景使用在线 Esri World Imagery，保留署名；瓦片加载失败时显示提示，合同数据面板继续可用。Maryland 区域背景不代表已提供田块边界。真实多边形到齐后自动缩放。

NDVI 图显示逐景真实观测点与来源，不插值、不补零；有效比例低于 0.5 或缺失用棕色。B 的日聚合和特征计算仍由 B 执行。质量来自 features，不从模型概率推断。零概率是合法结果，空预测显示未计算。

summary 必须与选择的 year 和 role 一致，直接显示 D 的数值、scope、notes 和经济情景，不另算面积。核查列表保留 D 的排序。页面另列无预测、卫星低质量/缺测的田块，不计算 review_score。输入行数和未匹配边界的记录可展开检查；无数据不宣称全链路通过。

## 截图与阻塞

`reports/e_web/empty-state.png` 和 `empty-state-mobile.png` 是当前仓库真实缺数据状态。浏览器检查中的临时测试数据仅存在请求拦截中，用于验证年份、用途和重复键；不写发布目录，不用作真实样本截图。

已从 A/B/C/D 固定提交只读接入合同数据：83 块真实边界，44 个标签年，barc_1/2021 的 86 景 NDVI，模型/分析 pending。真实样本截图尚未完成：当前托管环境缺少支持的浏览器控制工具，因此未执行本轮截图，不把测试夹具或旧截图冒充已接通截图。

最新主线 `51d5989` 已包含官方材料，已同步到本地，无需再次手工下载：

- `04_Evaluation/BARC_Corn.2021-2023.gpkg`
- `04_Evaluation/barc_fields_explorer.ipynb`
- 根目录 `challenge_statement.md`
- `03_Geospatial_References/sentinel-2_starter_notebook.ipynb`（实际文件名与合同示例不同）

另有 `data/processed/barc_field_year_labels.csv`：列为原始 field_id、year、harvest_type、acres，不是合同的 core/labels.csv。E 不自行给原 ID 加前缀、不转换标签及面积；需 A 统一提供 core 与不可变 ID 映射，再由 B/C/D 按该 ID 交付。现有 notebook 原型不代表合同路径的数据已经生成。

若其他电脑缺少这些文件，先 `git pull` 获取最新主线。仅当主线也没有时，才从 https://hacktheharvest.farmgpu.net/anaheim04-8892/lab 下载合同列出的原件，交给 A/B 保留上述实际路径。原件许可及训练/评估用途由 A 核实，E 不复制原件到公开数据目录。

## Full-screen interface

The English interface uses a fixed full-viewport satellite map. Year, field and prediction-role selectors float above it. The bottom navigation opens Field, Observations, Analysis, Review, and Data status panels; Escape or the close button dismisses a panel. The page itself does not scroll; long panel contents scroll within their overlay. Esri imagery provides geographic context and is not used to fabricate NDVI observations.

## County and field overlays

县界：`reference/us-counties.geojson` 是 U.S. Census TIGERweb 的 2026-01-01 版本，3,235 个县及县级等价区域，EPSG:4326。可用 `python scripts/fetch-counties.py` 从官方服务刷新，来源、概化参数和 SHA-256 保存在 `reference/us-counties.source.json`。县界为概化背景，不用作地籍测量或年度农作物统计；地图只绘制视口附近县界。县界和田块均可独立开关。

真实田块仅为 A 的 BARC 样区，并非美国所有农田：zoom ≥ 13 才显示轮廓；点击 Zoom to fields 可放大。悬停高亮并读取当前 field_id + year + prediction_role 的模型青贮概率、类别、独立的卫星质量与面积；无预测显示 Not computed。点击或手机点按打开详情。键盘可聚焦已显示的田块，Enter 打开详情。

首次克隆如果缺固定交接提交，先执行：

```bash
git fetch origin work/a-data work/b-satellite work/c-model work/d-analysis
cd web
npm run sync:data
```

同步不自行 fetch，不偷偷合入队友分支，不创造字段 ID。固定 SHA 和逐文件字节核对见 `data-handoffs.json` 与 `reports/e_web/handoff-verification.json`。后续 A/B/C/D 更新后审查并修改对应 pin，或等其正式合入本地 data/processed；两种来源都逐字节保留。
