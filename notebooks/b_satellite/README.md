# B 的 notebook

官方原件现已在仓库 `03_Geospatial_References/sentinel-2_starter_notebook.ipynb`，无需再下载；CLI 自动优先读取它。已逐 cell 阅读，差异说明见 `reports/b_satellite/notebook_review.md`。原件保持不变。

`run_smoke.ipynb` 是 B 自有的合同适配入口，读取 A 的 `fields.geojson` 和 `smoke_sample.json`，不包含自造 ID、标签或虚构观测。

若其他 checkout 缺原件，从团队 JupyterLab 下载 `03_Geospatial_References/starter_notebook.ipynb`，保存为本目录 `starter_notebook.ipynb`；该本地回退文件默认不入 Git，等待许可核查。

依赖、CLI 参数和正式命令见 `src/satellite/README.md`。
