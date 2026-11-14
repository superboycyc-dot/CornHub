# B：BARC 遥感与特征

仅维护 B 的目录，分支 `work/b-satellite`，通过 PR 交付。规则来源为 `docs/team-contract.md`（首次实现基于 main `b603997`）。本阶段采用合同明确的 BARC、2021–2023 年范围；根 README 的加州 2022–2026 范围是较早方案，未在 B 的目录中擅自修改。

## 当前真实执行状态

- 官方 notebook 已逐 cell 阅读；保留其单田 L2A/B04/B08/SCL/NDVI 中位数流程并适配合同。审阅见 reports。
- A 已交付，用 PR #6 / `df7ce8c` 的只读 worktree 校验 83 个边界和 44 个标签键。样本 **barc_1 / 2021，6.63739333 ha**。
- 实际检索 210 个场景条目；读取 69 条，合同聚合后 **14 个有效日**，已生成真实 CSV、特征和时序图。
- 其余 **141 个场景因上游 HTTP 503 未完成**。最长缺口 177 天，quality_flag=limited，晚季均值空；峰值和下降不能解释为完整季节或收获时点。
- CA 信任问题已修复，保留 TLS 验证；已验证离线重建，并在线重试全部缺失场景，最终仍为 **partial / exit 2**，不是全窗成功。
- 不将合成检查样本用作生产结果；原件与队友文件不改，B PR 不复制 A 的文件。

## 环境与运行

从仓库根目录运行，Python 3.11 及以上：

```sh
python -m venv src/satellite/.venv
src/satellite/.venv/bin/pip install -r src/satellite/requirements.txt
PYTHONPATH=src src/satellite/.venv/bin/python -m satellite preflight
PYTHONPATH=src src/satellite/.venv/bin/python -m pytest src/satellite/tests -q
```

`preflight` 缺交接文件时退出码为 **2**，同时写明确阻塞报告；它不查询任意虚构田块。`--help` 列出所有参数。目录参数均可覆盖，默认定位当前仓库，不依赖特定机器路径。

### 输入与官方原件

原件目前已在仓库 `03_Geospatial_References/sentinel-2_starter_notebook.ipynb`；CLI 自动优先使用它，**不需要再次手动下载**。以下仅为原件未随 checkout 提供时的回退步骤。

1. 用自己的团队账号登录 [官方 JupyterLab](https://hacktheharvest.farmgpu.net/anaheim04-8892/lab)。当前未登录请求会跳转到登录页。
2. 找到 **`03_Geospatial_References/starter_notebook.ipynb`**，右键 Download，保存为 **`notebooks/b_satellite/starter_notebook.ipynb`**。
3. notebook 原件默认被 B 目录的 `.gitignore` 忽略，先核查再分发许可，不提交输出中的 token。入口只做 AST/文本清点，不执行原 notebook、不存其代码或输出；清点不能替代阅读实际代码。
4. A 交付 `data/processed/core/fields.geojson` 和 `data/processed/core/smoke_sample.json`。B 不自行创建 ID、边界、标签或选择另一个样本。输入缺失/重复 ID/无效几何/CRS 或来源不一致时阻塞，不静默修复。
5. 阅读 notebook 实际代码，核实它是否包含影像搜索、SCL、缩放和 NDVI，写清它与独立入口的差异；确认后使用 `--notebook-reviewed` 记录已经完成的代码审阅。

```sh
PYTHONPATH=src src/satellite/.venv/bin/python -m satellite smoke --notebook-reviewed
```

输出路径：

| 文件 | 含义 |
| --- | --- |
| `data/processed/satellite/timeseries.csv` | 合同全部逐场景记录，包括有效比例低于 0.5 的记录 |
| `data/processed/satellite/features.csv` | 共同样本的一行特征；检索完全失败时不捏造一行 |
| `reports/b_satellite/run_report.json` | 执行状态、成功读取场景数、有效日数、最长缺口、阻塞项 |
| `reports/b_satellite/BLOCKERS.md` | 可直接转交团队的缺文件与处理错误说明 |
| `reports/b_satellite/catalog_probe.json` | 实际目录连通性检查，与场景查询严格区分 |
| `reports/b_satellite/scene_inventory.json.gz` | 真实 STAC 查询结果、窗口和 A 提供的几何 |
| `reports/b_satellite/scene_provenance.json` | 每个已处理产品的来源、URL、参数和像元计数 |
| `reports/b_satellite/ndvi_timeseries.png` | 仅真实有效日存在时输出；只画观测点，不插值、不连成假观测 |

`completed` 仅表示全部已检索场景读取成功且至少有一个有效日，不能代替 `quality_flag`，更不代表模型准确率。部分场景读取失败为 `partial`，退出码 2；不足一天或全云为 `blocked_no_valid_observations`。已有真实输出不会因前置文件暂缺被清空，消费者应先读本次 run_report 状态。

## 影像和质量规则

1. 只搜索 Earth Search 的 `sentinel-2-l2a`，空间 `intersects` 使用 A 的完整 Polygon/MultiPolygon；时间严格为 `[year-04-01, year-12-01)`，UTC。读取分页直到结束，防止静默截断。场景级云量不预筛，保留田块实际云情况。
2. 仅远程读取 B04、B08、SCL 的田块 COG 窗口，不下载整景或整州影像，不把原始影像提交 Git。B04 投影 10m 网格为参考，每个窗口最多 2,000,000 像元，超限明确阻塞。GDAL 内存缓存上限 64 MiB，最多 4 个窗口线程；持久缓存只存派生数字与公开来源，上限 256 MiB，不缓存原始影像。
3. 使用 STAC `raster:bands` 的 `scale` 与 `offset`：`reflectance = DN * scale + offset`。offset 省略时按 Raster Extension 的缺省 0；缺少 scale 则阻塞，不能凭日期或处理基线猜偏移，也不再额外减一次 0.1。保存 processing baseline 与 `earthsearch:boa_offset_applied` 供追溯。
4. 无数据值来自 STAC 或栅格元数据，先作为 nodata 掩膜，再进行缩放。B08 和 20m SCL 用最近邻映射到 B04 的 10m 中心网格；不对分类层做双线性插值。
5. 边缘只取中心落入田块的像元（`all_touched=False`），不使用按面积加权的部分像元；多边形孔洞排除。窗口即使跨出场景仍按完整田块网格计算分母，未覆盖部分保持 nodata，不能提高覆盖率。没有任何中心落入小田时明确阻塞，不人为增加像元。
6. 沿用官方 starter 的 SCL 白名单 **4（植被）、5（非植被/裸土）、6（水）、7（未分类）**。0/1 无效或饱和、2 暗区/地形影、3 云影、8/9 云、10 卷云、11 雪均排除。保留裸土以观察收割；7 的保留与原件一致，但未分类像元仍有污染风险，不能当作人工确认的晴空。
7. `valid_pixel_fraction` 分母是完整田块中所有参考 10m 中心像元数，包括云、影、nodata、未覆盖像元；分子是通过 SCL、两个反射率均有限、和大于 1e-12、NDVI 有限且在 [-1,1] 的像元数。超范围比值设为无效，不裁剪至端点。NDVI 是有效像元的中位数，全部无效时留空，绝不填 0。
8. 同日按有效比例降序选一个场景，比例平手按 scene_id 升序；原始所有场景留在时序表。选出的场景比例至少 0.5 且 NDVI 非空才进入特征。缺测不插值。

## 合同特征

- peak 为最大有效日 NDVI，平手最早；DOY 为年内日序。
- 相邻有效日下降为 `(previous-current)/days`，负值截 0；最大下降平手取较早的后一个日期（数值平手容差 1e-12）。无下降时 rate=0、drop_doy 留空；不到两个日则 rate 也空。
- late mean 为 `[09-01,12-01)` 的有效日均值，无有效日时留空。
- `max_gap_days` 是相邻有效日期及窗口两端之间的日期差：`start→first`、相邻有效日、`last→exclusive_end`。无有效日就是完整窗口 244 天，不从天数差再减一。
- 0 日 no_data；1 日 insufficient；至少 2 日但少于 6 日、或 gap>30 为 limited；其余 usable。missing_reason 单列晚季缺测、观测过少、长间隔和读取失败。

## 验证和下一阶段

单元检查覆盖同日去重、比例阈值、峰值/下降平手、窗口端点、无观测/单日、nodata/云的分母、20m→10m SCL 最近邻和实际缩放计算。栅格检查使用内存中的隔离合成 GeoTIFF，不是卫星结果。

真实共同样本已产出部分结果，完整窗口仍因网络而未验收。`batch` 按 A 标签清单执行，以成功真实 smoke 为门槛；目前 smoke 为 partial，完整批处理尚未执行。

```sh
PYTHONPATH=src python -m satellite batch --labels data/processed/core/labels.csv --dry-run
PYTHONPATH=src python -m satellite batch --labels data/processed/core/labels.csv --notebook-reviewed
```

`--limit N` 显式限制键数，报告区分选中范围与完整标签清单。网络恢复后重复 smoke 会复用 `.cache` 成功检查点并读取缺失场景。`--offline` 只使用已记录的 inventory 和检查点，核验几何、窗口、集合，不做网络请求；缺检查点场景明确阻塞，不能当作全云或零 NDVI。缓存不提交 Git，另一台机器需要重新读取影像。真实 A 分支输入命令见 reports/b_satellite/README.md。

`--reuse-inventory` 可在目录 API 临时不可用时复用已记录的真实检索清单；先验证 A 几何、窗口和集合完全一致，再在线读取缺失场景。当前全部 141 个缺失场景已逐项重试，其中 139 个 HTTP 503、2 个栅格格式识别失败。
