# B：替代数据路径执行结果

A 的固定交付 df7ce8c：barc_1 / 2021，6.63739333 ha，窗口 [2021-04-01,2021-12-01)。B 未修改 A 的边界、ID 或标签。

## 当前交付

| 项目 | 原 Earth Search 路径 | 当前 Planetary Computer 路径 |
| --- | ---: | ---: |
| 成功场景/检索产品 | 69/210（含重复版本） | 86/87 |
| 有效观测日 | 14 | **47** |
| 最长有效观测间隔 | 177 天 | **33 天** |
| 晚季 NDVI 均值 | 空 | **0.4383674** |
| 合同质量标记 | limited | **limited**，没有放宽阈值 |

当前 `data/processed/satellite/timeseries.csv`、`features.csv` 和 `ndvi_timeseries.png` 来自同一套 PC 数据，不混合两家产品版本。旧结果和来源保留在 `earthsearch_partial/`。

采用 PC 官方服务端 `item/feature.tif` 裁剪接口，每景约十几 KB，不下载整景，无需浏览器登录或保存 SAS 链接。先按产品 B04 原生 10m 网格构造整像元矩形，响应必须与目标 CRS、transform、形状完全一致，再在本地对 A 真实田块执行中心像元掩膜。所有86景分母都是667像元，SCL最近邻、白名单[4,5,6,7]、有效比例至少0.5和特征定义不变。

PB02.12/03.00 的原始DN没有加性BOA偏移，公共乘法量化因子在NDVI比值中抵消；未将DN称为物理反射率。[ESA产品依据](https://sentiwiki.copernicus.eu/web/s2-products)。只按产品元数据判断基线，不凭影像日期猜测。

## 剩余标记

唯一未处理产品：`S2B_MSIL2A_20211119T160549_R097_T18SUJ_20230130T063849`，基线04.00，需要明确BOA加性偏移；当前可访问元数据中没有取得，所以不猜测零偏移。两条公开metadata镜像查询均404。产品保留在完整检索清单和issues中，没有静默丢弃。

33天间隔属于观测/质量筛选缺口，不通过插值制造观测；quality_flag仍为limited。当前状态partial，可交付真实时序和接口，不声称全部产品处理成功或模型分类正确。依用户指令，剩余项仅标记，不阻塞本次PR交付。

## 命令与验证

```sh
PYTHONPATH=src python -m satellite.pc_fallback \
  --fields ../CornHub-a-inputs/data/processed/core/fields.geojson \
  --sample ../CornHub-a-inputs/data/processed/core/smoke_sample.json \
  --refresh-inventory
```

A 合并后用本仓库 data/processed/core 的两份输入路径即可。首次需公共网络，后续复用派生数值检查点；原始裁剪影像仅在内存中。遇不支持的校准基线明确报错，命令当前退出码2，符合partial。

**28项测试通过**。真实结果另行核查了唯一键、NDVI/比例范围、原生网格、667像元分母、每景来源和无SAS token，见validation_report.json。PC全窗检索清单、查询收据、来源和每景参数均已保存；旧S3阻塞记录仍保留。完整44标签年的批处理未执行。
