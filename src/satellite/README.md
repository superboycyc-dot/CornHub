# B：44个田块年批处理

已完成A完整清单：**44个field_id+year，34块不同田，2021–2023年**。当前主交付为44行特征、4,524行逐场景时序；不是单田样例。读取/目录错误为0，所有44个田块年均有有效观测；26个usable、18个limited，未放宽合同规则。

## 运行

依赖：Python 3.11+，`pip install -r src/satellite/requirements.txt`。

```sh
PYTHONPATH=src python -m satellite.pc_batch --core data/processed/core
```

A未合并main时，本次实际使用 `--core ../CornHub-a-inputs/data/processed/core`，对应固定A提交df7ce8c的只读worktree，不改A的ID、边界、标签或划分。依赖和配置均在B目录，不改根配置。

## 输出

- data/processed/satellite/timeseries.csv：4,524条场景记录，保留低质量/缺NDVI场景。
- data/processed/satellite/features.csv：完整44个键的合同特征。
- reports/b_satellite/field_year_coverage.csv：逐田块年有效日、缺口和质量。
- reports/b_satellite/field_timeseries/：44张真实NDVI图。
- pc_batch_report.json及pc_batch_provenance.json.gz：执行状态、来源、时间、产品、基线、偏移、网格与像元计数。

## 处理规则

严格使用[04-01,12-01)窗口。PC公开L2A检索清单按年保存；只请求田块原生10m整像元矩形，响应CRS/transform/shape须匹配，再按A多边形中心像元掩膜。分母是完整田块中心像元，包括云、nodata和覆盖缺口；分子通过nodata、SCL及NDVI有效性要求。SCL最近邻，保留4/5/6/7（与官方starter一致，包含裸土）；不插值、不把nodata填0。

PC原始DN按实际产品基线校正：PB<04偏移0，PB04–05.13偏移-1000 DN，未知版本报错。先float64转换和nodata掩膜再减偏移，公共量化因子在NDVI中抵消；具体官方依据见reports/b_satellite/calibration_policy.md，不凭拍摄日期猜测。

同日选有效比例最大场景，平手按scene_id字序；低于0.5不进入特征。峰值、下降率、晚季均值、含窗口边界的max_gap_days及no_data/insufficient/limited/usable按合同计算。模型质量不等于卫星质量。

原始裁剪只在内存，检查点只保存被Git忽略的派生数字和来源，支持重跑；没有整景/整州下载。本次依用户要求跳过额外逐行/人工核对，仅确认执行完成和导出行数；此前单元测试日志保留，不当作本批新增核对。

`python -m satellite`和`python -m satellite.pc_fallback`保留单田入口供单独调试；会导出单样本，**不要把单田调试输出替代全量交付**。旧结果已归档到reports/b_satellite/single_field_prior及earthsearch_partial，当前全量以pc_batch_report和两张合同CSV为准。
