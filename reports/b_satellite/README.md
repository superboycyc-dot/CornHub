# B 全量批次交付：44个田块年 / 34块真实田

已使用A固定交付df7ce8c的完整labels.csv批量运行，不是仅导出共同样本。

- 状态：**completed**；44个田块年、34个不同field_id，年份2021/2022/2023。
- 特征表：**44行**；逐场景时序：**4524行**。
- 场景任务：4524；成功：4524；目录错误：0；场景错误：0。
- 有有效观测的田块年：44；质量分布：{'no_data': 0, 'insufficient': 0, 'limited': 18, 'usable': 26}。质量规则未放宽，缺测不插值。

## 数据位置

- data/processed/satellite/features.csv：全部44个field_id+year特征。
- data/processed/satellite/timeseries.csv：全部逐场景观测，包括低有效比例场景。
- reports/b_satellite/field_year_coverage.csv：逐田块年数量、缺口和质量。
- reports/b_satellite/field_timeseries/：逐田块年真实NDVI图。
- pc_batch_report.json：执行汇总和错误；pc_batch_provenance.json.gz：每场景原始来源、日期、基线、DN偏移、像元计数与请求参数。
- pc_batch_inventory_2021/2022/2023.json.gz及对应search.json：完整公开检索清单与查询收据。

统一使用PC官方服务端小窗口裁剪。按每个产品原生10m网格对齐矩形，SCL最近邻，然后按A真实多边形中心像元掩膜；nodata不当作零植被。PB04+按ESA与微软已公开确认的-1000DN规范校正，依据产品元数据基线，不按拍摄日期猜测。详见calibration_policy.md。

```sh
PYTHONPATH=src python -m satellite.pc_batch --core data/processed/core
```

本次实际输入来自A只读worktree的同名core目录。无整景或整州下载，原始小裁剪仅在内存；检查点是被Git忽略的小型派生JSON。按用户要求，本批结束后只做导出行数与执行汇总的完成确认，**未再做逐行或额外人工核对**。此前单元测试结果保留，但不冒充本批新增验证。

历史单田/失败路径结果保留于single_field_prior/和earthsearch_partial/。它们不代表当前全量交付。B未修改A、C、D、E的目录，也未直接推main。
