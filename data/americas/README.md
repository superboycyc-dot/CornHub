# 美洲玉米田块、收割方式及卫星观测

主表 field_harvest.csv 与 Excel 是同一张表，每条记录对应一个国家、田块 ID 和作物年份。按 country、field_id、year 连接卫星明细。字段 longitude 和 latitude 是田内代表点；精确边界位于 boundary_file（相对于仓库 data/），可按 boundary_key 取回。在美国 GeoJSON 中连接 feature.id；在魁北克 GeoParquet 中连接 IDANPAR。加拿大主表 field_id 取 IDPAR。Excel 中年份、面积、坐标、观测次数和有效 NDVI 日期范围可排序。

|范围|田块年度|grain|silage|冲突|至少一个有效 NDVI 日期|
|---|---:|---:|---:|---:|---:|
|美国马里兰州|101|74|26|1|81|
|加拿大魁北克省|39,653|39,653|0|0|39,653|

总计 39,754 行。卫星明细实际取得 83,967 条田块与场景观测，按田块年度与有效日期去重后共 80,627 个田块观测日。20 个未匹配到可靠边界的美国作业田块年度保留原始证据。美国 81 个可定位田块年度中，48 个在项目田界年份范围内，33 个使用其他年份参考田界。

## 收割证据

美国采用仓库 04_Evaluation/BARC_Corn.2021-2023.gpkg 内的 OBJECTID、FARM 和 FIELD。通过农场名和同一田号对接 USDA 作业报告，按年份与 data/processed/barc_field_year_labels.csv 合并。保留全部 44 个项目标签和 85 条作业的年度并集。采收多日以竖线列出。challenge_only 表示只有项目标签，operations_only 表示只有作业记录，corroborated 表示二者一致。作业记录以 CSIL 加青贮机械确定 silage，以 FLDCRN 加联合收割机推断 grain。barc_248 在 2023 年有两种作业，主表保留 unresolved。带相似后缀的田号没有可靠的一一对应关系，保留作业和原始田号，位置留空。reference_other_year 表示田号精确匹配，但边界来自 2021–2023 项目，在其他年份的形状尚未核实。area_ha 表示所关联田界的面积，实际当次收割面积见作业明细的 acres。[USDA 管理档案](https://doi.org/10.15482/USDA.ADC/28950746)

魁北克采用 FADQ 2025 年整块单一作物面积占比 100% 的 MGR 籽粒玉米田，证据状态 declared。主表中的美国和加拿大记录保留各自证据类型。墨西哥以及中南美洲目前没有本仓库内同时具备田块身份和收割标签的已核验输入。[FADQ 档案](https://www.fadq.qc.ca/documents/donnees/base-de-donnees-des-parcelles-et-productions-agricoles-declarees/)

## 卫星数据

|文件与方法|内容及使用|
|---|---|
|satellite/us_existing_sentinel2.csv / S2_field|美国既有项目分支的田块统计。共 4,524 条田块与场景记录，包含日期、产品编号、田块 NDVI 和有效像元占比。主表统计 NDVI 非空且有效占比至少 0.5 的日期。原项目的特征、质量覆盖和逐景处理证据在同目录。原 CSV 缺少 country 列时取 US。|
|satellite/point_samples.csv.gz / S2_point|新取的 Sentinel-2 L2A 田内代表点 B04、B08 原始数值和 SCL 类别。B04、B08 为 10 米，SCL 为 20 米，各自读包含代表点的原生像元。魁北克取 2025 年 8 月、10 月，美国补取项目已有时序以外可定位田块对应年份的 8、9、10 月。首轮两期均无有效值的魁北克田块再尝试 9 月和 7 月。每月检索前 28 天，在检索窗口中优先选择整景云量低且覆盖点的产品。单点 NDVI 保留 SCL 4、5；排除无数据、负反射率和无效分母。反射率根据产品比例与偏移换算。原始逐景 STAC 元数据和波段下载地址保存在 sentinel2_items.json.gz。|
|satellite/us_2015_landsat8.csv / L8_point|2015 年美国缺少所查 S2 产品，补取 USGS Landsat 8 Collection 2 Level-2，30 米田内像元。保留 B4、B5、QA_PIXEL、QA_RADSAT，DN 乘 0.0000275 再减 0.2。排除填充、膨胀云、卷云、云、阴影、雪、水、相关波段饱和和地形遮挡。对应元数据保存在 landsat_items.json。|

田内单点的 valid_pixels 是 0 或 1。整田统计取田界范围内有效像元；两种支持范围分别标记，解释时应区分。卫星数据采用实测的遥感反射率，不能单独确定收割方式。没有可定位边界的记录保留在主表，其卫星观测次数为零。satellite_observations 只统计实际取得影像的田块场景，包含质量掩膜后无效的观测；valid_ndvi_dates 按有效日期去重。last_valid_ndvi 是最后一个有效日期的 NDVI，同日多景取中位数。下载内容为关联田块的卫星观测值、波段样本及来源；原产品全景在元数据的资产链接中。

[原仓库卫星分支版本](https://github.com/superboycyc-dot/CornHub/tree/05a81a7d1634c80d3c56b66cf9eb9acb9527fc9b) · [Copernicus Sentinel-2 产品说明](https://sentiwiki.copernicus.eu/web/s2-products) · [Earth Search 公开目录](https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a) · [USGS Landsat Collection 2 地表反射率](https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-reflectance)
