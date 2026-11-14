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

字段、唯一键与空值定义见团队合同。CSV 保留字符串，不转换 ID。按 `field_id+year` 关联，再选择一个 `prediction_role`。CSV 缺字段、重复键、非法概率及非 4326 声明的边界会报错并隔离该文件。GeoJSON 使用经度在前；Leaflet 自身转换，不手动交换或用经纬度计算面积。无底图依赖，真实多边形到齐后自动缩放。

NDVI 图显示逐景真实观测点与来源，不插值、不补零；有效比例低于 0.5 或缺失用棕色。B 的日聚合和特征计算仍由 B 执行。质量来自 features，不从模型概率推断。零概率是合法结果，空预测显示未计算。

summary 必须与选择的 year 和 role 一致，直接显示 D 的数值、scope、notes 和经济情景，不另算面积。核查列表保留 D 的排序。页面另列无预测、卫星低质量/缺测的田块，不计算 review_score。输入行数和未匹配边界的记录可展开检查；无数据不宣称全链路通过。

## 截图与阻塞

`reports/e_web/empty-state.png` 和 `empty-state-mobile.png` 是当前仓库真实缺数据状态。浏览器检查中的临时测试数据仅存在请求拦截中，用于验证年份、用途和重复键；不写发布目录，不用作真实样本截图。

真实样本截图尚未完成：A/B/C/D 的合同文件当前全缺。数据到齐后运行同步并打开共同样本，核实来源后截图，存 `reports/e_web/real-sample.png`。不能用已有加州州级统计或测试夹具代替 BARC 真实样本。

A 需要从已登录团队 JupyterLab 下载原件：
https://hacktheharvest.farmgpu.net/anaheim04-8892/lab

- `04_Evaluation/BARC_Corn.2021-2023.gpkg` → `data/raw/barc/BARC_Corn.2021-2023.gpkg`
- `04_Evaluation/barc_fields_explorer.ipynb` → `data/raw/barc/barc_fields_explorer.ipynb`
- `01_Challenge/challenge_statement.md` → `data/raw/barc/challenge_statement.md`
- B 需要 `03_Geospatial_References/starter_notebook.ipynb`，建议交给 B 存 `notebooks/b_satellite/starter_notebook.ipynb`。

这些路径由对应负责人创建，本次 E 不修改它们。原件许可不明不提交公开仓库。E 应接 A 生成的 core 文件，不在前端从 GPKG 生成 ID/面积/标签。
