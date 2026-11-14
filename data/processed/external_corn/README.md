# 全国玉米候选田库：CSB 与 CropSight-US，2021–2023

这是外部扩展数据，不替换主办方 BARC core，不包含真实 silage/grain 用途标签。两种来源不可直接合并为同一地块：可能空间重叠、边界不同或同一块田有多个观察对象。

## 文件和字段

数据以 GeoParquet/ZSTD 分片保存，单片目标 <50 MB。可由支持 GeoParquet 的 GIS 或 pyarrow 读取。几何为 EPSG:4326 的 WKB，经度在前；area_ha 在美国本土等积投影 EPSG:5070 计算。invalid geometry 保留 geometry_valid=false，不静默修复；该标记需要下游考虑。面积不是官方地籍面积。

共同字段：candidate_id、source_field_id、source_dataset_id、area_ha、geometry_valid、geometry、harvest_type（全部空）。candidate_id 使用独立 csb_/cropsight_命名空间，不能冒充 barc_ID；不是模型输入或真实答案。

- csb/：同一多边形只存一次；保留 cdl2021/cdl2022/cdl2023。只要三年任一年代码为1就纳入。**使用某年样本时还要筛对应 cdlYYYY=1**，不能把全表当三年均为玉米。本次代码1筛选针对Corn类别，未把甜玉米、爆米花或含玉米的复种独立代码混入；它是明确定义的候选集合，不能宣称涵盖所有玉米用途/种植制度。范围为美国本土连续48州产品，边界由2016–2023多年CDL推导，不是实测田界；对历史实时回测需考虑使用未来年度信息的风险。
- cropsight/：仅 source Year=2021/2022/2023 且 Label=corn（大小写规范化）对象，保留原 crop_label_raw、year、month 和提供的不确定性字段。作者模型预测的玉米类别不是 S/G 地面真值；源 FID 仅标识此版本内对象，不能据此推断跨年的同一农场/田块，也不能把重复观察对象当独立地面样本。

逐片路径、行数、SHA-256、筛选后年度数量、源 CRS 和质量计数在 reports/a_data/external_corn/*_processing.json。分片几何未简化；原始包及源schema/版本与哈希另见来源报告。

## 获取、存放与复现

两份官方数据包已下载并处理；raw 大包保存在本地 data/raw/external_corn/（忽略目录），GitHub 同步处理后分片、来源、manifest和脚本，原件通过官方链接复取。全国CSB ZIP约3.51GB、解压约5.58GB，不纳入Git历史。不要将解压大包或环境加入Git。

```sh
python3 -m venv /tmp/cornhub-external-venv
/tmp/cornhub-external-venv/bin/python -m pip install -r src/data/external_corn/requirements.txt
# 原始URL/大小/校验见 sources_manifest.json；解压后将实际向量文件路径传入
/tmp/cornhub-external-venv/bin/python src/data/external_corn/process.py csb data/raw/external_corn/NationalCSB_2016-2023_rev23/CSB1623.gdb
# CropSight 输入路径以源压缩包清单和处理报告为准
/tmp/cornhub-external-venv/bin/python src/data/external_corn/process.py cropsight <vector-path>
```

处理器拒绝覆盖已有 parquet；重建请指向干净副本或先将旧结果安全移出。通过 where 过滤并分批读取，不需一次把全国数据加载进内存。生成后验证器独立回读所有分片、校验hash/唯一键/CRS/筛选条件与记录数。

## 来源和署名

- USDA NASS [CSB](https://www.nass.usda.gov/research-and-science/crop-sequence-boundaries)，2016–2023 rev23；官方元数据 public domain。
- Zhou, Liu & Diao，[CropSight-US v1.0.1](https://zenodo.org/records/19501943)，CC-BY-4.0；论文 https://doi.org/10.5194/essd-18-3069-2026 。派生数据进行了年份/玉米类别筛选、重投影、字段规范化和格式转换。保留该署名和版本。

本库只提供候选范围与作物线索，不宣称全国田界完整精确、不宣称全国分类效果，也不能用政策补助记录推导单田收获用途。2022–2025政府支持研究另见 reports/a_data/policy_2022_2025/README.md。

## 本次实际产物与质量

|来源|原始包|解压|筛选对象|处理后大小|分片|
|---|---:|---:|---:|---:|---:|
|CSB|3,505,346,935 bytes|5,584,214,724 bytes|6,112,209|2,092,859,083 bytes|1,223|
|CropSight-US|297,267,115 bytes|468,825,921 bytes|15,939|52,853,611 bytes|9|

CSB年度玉米数：2021=3,184,035、2022=2,993,250、2023=3,262,384。同一多边形可能多年度种玉米，三年数量之和不等于独立多边形数。CropSight年度对象数：2021=6,676、2022=5,126、2023=4,137。

**CSB有209,931个导出几何无效，保留flag，不静默删除或修复。其余5,902,278个几何通过有效性检查。** 具体示例包括Ring Self-intersection，见invalid_geometry_examples.json；未判定是源边界本身还是变换精度等因素造成。空间裁剪/影像掩膜前建议明确筛 geometry_valid=true，或另建有修复方法与误差记录的版本。有效几何也不意味着地面边界精确或真实收获用途已知。CropSight此次筛选对象无无效几何。

全部1232个分片已回读：SHA、行数、ID唯一性、筛选条件、空收获用途、GeoParquet CRS、面积正值、几何标记一致性通过。每片抽1个对象的几何重投影面积对照通过，容差0.001ha（这不是对全部对象做独立面积重算）。CSB数量另与原始GDB不读几何的独立属性扫描对照一致。两包ZIP CRC通过，CropSight另与作者MD5完全一致。

示例：只读取加州2022年且几何有效的前500条，避免将全国数据一次放进内存：

```python
import pyarrow.dataset as ds
import shapely
candidate = ds.dataset('data/processed/external_corn/csb', format='parquet')
selected = candidate.head(500, filter=(ds.field('cdl2022') == 1)
                          & (ds.field('statefips') == '06')
                          & ds.field('geometry_valid'))
polygons = shapely.from_wkb(selected['geometry'].to_pylist())
```

分片按batch子目录组织，每目录不超过100片；完整Parquet数据约2.15GB，Git历史会增加相应体量。它们属于本轮独立扩展；队友如只接BARC，不需改变原接口。
