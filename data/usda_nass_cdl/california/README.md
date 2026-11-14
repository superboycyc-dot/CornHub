# USDA NASS CDL：加利福尼亚州，2022–2025

## 数据名称与来源

数据名称：**USDA National Agricultural Statistics Service Cropland Data Layer (CDL), California**。州 FIPS：`06`。发布机构：美国农业部国家农业统计局（USDA NASS）。

- 用户指定的来源：[USDA CDL 公告页](https://www.nass.usda.gov/research-and-science/cropland/sars1a)
- 官方产品与发布信息：[National Download](https://www.nass.usda.gov/research-and-science/cropland/release)
- 实际下载：USDA NASS CropScape 的 George Mason University 数据缓存；各年原始 URL 见 `manifest.json`。
- 获取日期：2026-11-14。原始 ZIP 字节保持不变，未裁剪、重分类或修改。

| 年份 | 原始数据包 | 压缩大小（十进制） | 实测像元大小 |
| --- | --- | --- | --- |
| 2022 | [CDL_2022_06.zip](CDL_2022_06.zip) | 76.02 MB | 30 米 |
| 2023 | [CDL_2023_06.zip](CDL_2023_06.zip) | 76.92 MB | 30 米 |
| 2024 | [CDL_2024_06.zip](CDL_2024_06.zip) | 67.68 MB | 30 米 |
| 2025 | [CDL_2025_06.zip](CDL_2025_06.zip) | 70.16 MB | 30 米 |

**2026 年：本次未找到已发布数据。** 官方全国发布页最新为 2025 年，州缓存对应 2026 年文件返回 404，因此没有补造文件或用其他年份替代。

## 分辨率与内容

四份 ZIP 的 GeoTIFF 均已核实为 **30 × 30 米**、23648 × 40345 像元。官方全国 CDL 从 2024 年起提供 10 米版本；本目录保存的是州缓存提供的 30 米版本，2024–2025 年文件不能当作原生 10 米数据使用。

每包包含 `CDL_<年份>_06.tif`、对应的 `.tif.vat.dbf` 作物类别属性表，以及服务附带的 ArcGIS 颜色表属性文件和说明文档。逐项文件名与解压大小见 `manifest.json`；解压后单年 GeoTIFF 约 954 MB，故在 Git 中保留原始压缩包。

## 校验与读取

下载后已逐包通过 ZIP CRC 检查，并记录每个 ZIP 的 SHA-256：

```sh
cd data/usda_nass_cdl/california
sha256sum -c SHA256SUMS
python -m zipfile -e CDL_2022_06.zip /tmp/cdl_ca_2022
```

可用 GDAL、QGIS 或 Rasterio 读取解压后的 GeoTIFF。类别值的解释使用随包属性表。

## 使用范围与许可

CDL 是年度作物类型分类栅格，可用于玉米候选区域筛选；它不提供青贮/籽粒收获用途标签，也不是官方田块边界，不能直接作为 CornHub 的 S/G 训练真值。

USDA NASS 元数据说明 CDL 属于 public domain，可免费再分发；数据按原样提供，USDA NASS 不担保用户据此作出的结论。已保存 [2022 年元数据](metadata/USDA_NASS_metadata_ca22.html) 和 [2023 年元数据](metadata/USDA_NASS_metadata_ca23.html)。原始在线元数据入口：

- https://www.nass.usda.gov/research-and-science/cropland/metadata/metadata-ca22
- https://www.nass.usda.gov/research-and-science/cropland/metadata/metadata-ca23
- https://www.nass.usda.gov/research-and-science/cropland/metadata/meta

建议引用：USDA National Agricultural Statistics Service. Cropland Data Layer, California, [数据年份], 30 m state download. Retrieved 2026-11-14.
