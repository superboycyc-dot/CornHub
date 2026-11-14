# B 第一阶段执行交付

负责人：B；GitHub：`aiaiai-ajlk`；分支：`work/b-satellite`。

已读取 root README、官方协作与提交说明，以及 main `51d5989` 的 `docs/team-contract.md`。本阶段以合同的 BARC 2021–2023 为准，未改写共同约定或队友目录。先前加州天气数据整理仍保留在独立工作目录，不包含在 B 的 PR 中。

## 已运行

```sh
PYTHONPATH=src python -m pytest src/satellite/tests -q
PYTHONPATH=src python -m satellite preflight
PYTHONPATH=src python -m satellite smoke
```

- 隔离单元与栅格计算检查：**19 passed**，原始输出 `test_results.txt`。
- preflight 和 smoke：**退出码 2，blocked，符合当前缺输入的预期**；详细结果 `run_report.json`。
- 公共 Sentinel-2 L2A 集合元数据：实际检查可访问，见 `catalog_probe.json`；没有进行未经 A 授权样本的田块查询。
- 官方 notebook 已进入 main，已逐 cell 阅读和清点；审阅记录见 `notebook_review.md`。JupyterLab 登录不再阻塞 notebook 获取。

## 尚未计算

真实田块/年尚未取得，因此真实样本有效观测日数、缺口和特征为 **未计算**；不是 0，也不是模型指标。两个交接 CSV 仅有合同表头，没有自造 field_id 或标签；没有时序图，没有将单元测试栅格发布为实际卫星数据。

已实现并在内存栅格上测试的逻辑包括 20m SCL 最近邻对齐 10m、nodata 掩膜、产品元数据缩放、田块中心像元分母、NDVI 中位数与质量比例。**远程真实 COG 读取流程尚未做端到端验证**，必须补齐样本后实际运行，不能把单元测试通过当作真实卫星成功。

## 精确阻塞与交接

1. 官方 notebook 已在 `03_Geospatial_References/sentinel-2_starter_notebook.ipynb`，无需重新下载；B 已阅读并适配其工作流。
2. A 交付 `data/processed/core/fields.geojson` 和 `data/processed/core/smoke_sample.json`。原始 GeoPackage、标签和共同样本选择由 A 负责，B 不另造边界或 ID。
3. A 交接到位后 B 运行 smoke，提交真实 timeseries、features、图及每场景处理来源，再汇报有效日数和缺测。
4. 真实样本验收后才扩展完整标签批处理、缓存和续跑；本轮未声称具备这些已验证能力。

参数、分母、边缘规则、质量公式与依赖见 `src/satellite/README.md`。仅请求少量 COG 波段窗口，无原始大影像落盘或提交 Git，避免占用团队 10 GB 容量。
