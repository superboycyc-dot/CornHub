# 北美玉米收获报告与田块核查

## 美国马里兰州

USDA Beltsville Agricultural Research Center Gridded Yield Data Archive v1 的管理附件包含 49 份按农场与田号命名的 PDF。此处保存美国公共领域原始附件，校验 MD5 与 USDA 档案一致。另有 2014、2016–2021 年七个产量档案，地址及校验值见 usda_archive_files.csv。已检查 2014 包，含原始收割机点位、清理后点位、CSV、插值产量 GeoTIFF 和克里金误差；田块原始外边界需另行匹配。[USDA 原始档案](https://doi.org/10.15482/USDA.ADC/28950746) · [方法论文](https://doi.org/10.1002/agg2.20474)

harvest_operations.csv 收录能解析到日期、Whole Field、面积、作物及设备的收割行，覆盖 39 份 PDF、2015–2023 年。25 条有 CSIL 和 Chopper，60 条有 FLDCRN 和 Combine，后者按作物与机械组合判为 grain。PDF 中的播种汇总、分区作业、机械缺失和未能解析的记录均不在这些数字内。复核时按 CSV 的文件名和页码打开原报告。记录中的面积为英亩，计算 NDVI 时宜同时检查作业面积与边界面积。

matched_field_years.geojson 将 25 条作业记录按农场名及田号精确匹配到挑战数据 2021–2023 年的 23 个田块年度。包括 18 个与已有标签一致的田块年度、4 个原标签空白的田块年度，以及 1 个出现两类机械记录的田块年度。匹配使用了项目既有田界，未验证各收割年份边界位置误差。对冲突田块保留两条作业并将 evidence_label 留空。边界以外年份只保留记录和可匹配的田号。美国已有 NDVI 在相邻 us_barc/timeseries.csv 中。

## 美国其他研究

|地区与报告|现场证据|空间数据可用性|
|---|---|---|
|宾夕法尼亚，Chesapeake Bay 覆盖作物项目|2010 年沿路调查 28,400 英亩，区分前茬 corn silage 与 corn grain。遥感分析覆盖约 340,000 英亩；报告第 23/29 页列 Berks、Lancaster、Lebanon、York 四县。|PDF 有带 COS、COG 的田界图；公开下载的原始田块矢量和逐田调查表待核实。[项目报告](https://www.nfwf.org/sites/default/files/finalreports1/22988_Final_Report.pdf)|
|纽约，Cornell 农机产量研究|表 1.5 汇总四个农场 7–10 年记录，青贮组 245 块、籽粒组 253 块。表 1.2 列农场概况与设备，图 3.2 和 3.5 有试验条带和田内产量分布。|公开论文可核对方法和样本规模；精确经纬度边界与产量点文件仍待取得。[Cornell 论文](https://ecommons.cornell.edu/server/api/core/bitstreams/b1f49d72-64ce-4be7-bcc0-bbe8deb5ec85/content)|
|加州 Tulare County，UCCE 青贮试验|2006 年 6 月 2 日播种、9 月 18 日收割；2007 年 6 月 14 日播种、10 月 16–17 日收割。整小区收割、逐车取样测水分，报告有鲜重及水分调整后产量。|试验小区有行数、长度和收割窗口，公开田界坐标待核实。[2006](https://ucanr.edu/sites/default/files/2010-07/31360.pdf) · [2007](https://ucanr.edu/sites/default/files/2010-07/32384.pdf)|
|加州 Sacramento County，2024 Tyler Island|Delta 试验 4 月 26 日播种，10 月 14 日收割。11 个品种、三次重复，附产量、土壤、灌溉和施肥说明。|地点精度到岛与试验说明，不能直接生成小区多边形。[UCCE 报告](https://corn.ucdavis.edu/sites/g/files/dgvnsk14546/files/inline-files/2024%20FINAL%20UCCE%20field%20corn%20variety%20trial%20results_1.pdf)|
|全国，USDA ARMS 调查说明|调查员手册区分计划收籽粒与最后收作青贮或青割的情况，适合核对标签定义。|公开材料是调查规则；精确定位的受访田块数据仍待取得。[USDA 手册](https://ers.usda.gov/sites/default/files/_laserfiche/DataFiles/52816/W_2021_All_Phase2%20Interviewers%20Manual_M_COP_FOH.pdf)|

## 加拿大与墨西哥

加拿大 BC 省 Hullcar Valley 2022 年调查在收割后复查了 50 个与 2021 年相同的农业调查田块，涵盖多种作物。报告将青贮玉米单列，并提供分层土壤硝态氮。田块按一致的氮肥管理划分并控制在 25 公顷以下，和农户整块收割单元可能有差异。2016 年报告另列作物与采样区地图。原始可下载 GIS 边界尚待核实。[2022 调查](https://www2.gov.bc.ca/assets/gov/farming-natural-resources-and-industry/agriculture-and-seafood/agricultural-land-and-environment/soil-nutrients/nutrient-management/technical-reports/soil-nutrient-studies/2022_hullcar_final_report.pdf) · [2016 调查](https://www2.gov.bc.ca/assets/gov/farming-natural-resources-and-industry/agriculture-and-seafood/agricultural-land-and-environment/soil-nutrients/nutrient-management/technical-reports/soil-nutrient-studies/post-harvest_nitrate_study_-_final_report_-_sep_2017.pdf)

墨西哥 DGSIAP 公开 2003–2025 年农业生产结算档案，可按市镇、作物品种、生产季和灌溉方式查询。能用于区域基准，空间粒度到 municipio。此次未确认能把公开的逐地块边界与同年粮用或饲用收割记录直接连接的墨西哥档案。[DGSIAP 年度档案](https://nube.agricultura.gob.mx/datosAbiertos/Agricola.php)
