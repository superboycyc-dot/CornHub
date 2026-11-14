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

同步脚本逐字节复制仓库 `data/processed` 下已有常规文件到 `web/public/data`，保留相对路径和全部字段；每次清理旧发布副本，生成文件状态 manifest，缺文件继续。发布目录已忽略，不手改、不提交副本。源目录应由团队维护，不存凭据或未获许可的原件；同步不会过滤其已有文件。

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

真实样本截图尚未完成：A/B/C/D 的合同文件当前全缺。数据到齐后运行同步并打开共同样本，核实来源后截图，存 `reports/e_web/real-sample.png`。不能用已有加州州级统计或测试夹具代替 BARC 真实样本。

最新主线 `51d5989` 已包含官方材料，已同步到本地，无需再次手工下载：

- `04_Evaluation/BARC_Corn.2021-2023.gpkg`
- `04_Evaluation/barc_fields_explorer.ipynb`
- 根目录 `challenge_statement.md`
- `03_Geospatial_References/sentinel-2_starter_notebook.ipynb`（实际文件名与合同示例不同）

另有 `data/processed/barc_field_year_labels.csv`：列为原始 field_id、year、harvest_type、acres，不是合同的 core/labels.csv。E 不自行给原 ID 加前缀、不转换标签及面积；需 A 统一提供 core 与不可变 ID 映射，再由 B/C/D 按该 ID 交付。现有 notebook 原型不代表合同路径的数据已经生成。

若其他电脑缺少这些文件，先 `git pull` 获取最新主线。仅当主线也没有时，才从 https://hacktheharvest.farmgpu.net/anaheim04-8892/lab 下载合同列出的原件，交给 A/B 保留上述实际路径。原件许可及训练/评估用途由 A 核实，E 不复制原件到公开数据目录。

## Full-screen interface

The English interface uses a fixed full-viewport satellite map. Year, field and prediction-role selectors float above it. The bottom navigation opens Field, Observations, Analysis, Review, and Data status panels; Escape or the close button dismisses a panel. The page itself does not scroll; long panel contents scroll within their overlay. Esri imagery provides geographic context and is not used to fabricate NDVI observations.
