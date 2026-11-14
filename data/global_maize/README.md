# 有青贮或籽粒用途标签的玉米田块
数据按田块与年份使用，区域间的 ID 仅在各自来源内有效。以下文件可直接下载。欧洲和加拿大的标签是申报用途，边界是年度农业田块。不同来源的测绘误差、实际收割日和最终用途尚未逐块实测核验。

|目录|覆盖和用法|
|---|---|
|eurocrops/parcels|2023 年比利时两区、保加利亚、捷克、德国勃兰登堡、丹麦、斯洛文尼亚和斯洛伐克。按区域与年份读取目录里的所有 GeoParquet 分片。保留所有源列和原始几何坐标，新增 harvest_label、source_region、source_year 与来源代码表名称。coverage.csv 列出各类数量。|
|quebec|加拿大魁北克 2025 年，保留原始属性与 NAD83 田界，限定单一申报作物且占地 100%。实际筛出 MGR 籽粒玉米 39,653 块。MAF 在代码字典中是饲用玉米，提取程序会标记 forage_unspecified，此次筛选未得到该类。|
|netherlands_2025|荷兰东南部 134 块，原始 GeoJSON 与 8 景 Sentinel-2 影像的 NDVI。用 field_id 连接 ndvi_all.csv 和边界。|
|us_barc|美国马里兰，2021–2023 年的 44 条带标签田块年度记录。按 field_id 关联几何；已有时序针对 barc_1 的 2021 年。|

JRC 目录覆盖 153 个地区年度文件。inventory.csv 给出版本化原始下载地址，codes_identified 表示该地区代码表存在此次核对过的标签，具体年份的出现情况以提取结果为准。原始代码依据地区匹配；通用玉米、混合穗轴料、能源玉米和只有“青饲”描述的类别需单独判定。此次移除了保加利亚 168 条和斯洛文尼亚 2 条空几何。奥地利、法国等其余地区及历史年份可使用同一份代码表和 fetch.py 重建。示例：安装 pyarrow 和 shapely 后，运行 python eurocrops/fetch.py at 2023。省略两个参数会逐一下载目录中全部已核对代码的地区年份，消耗较多网络和磁盘。魁北克 inventory.csv 列出 2003–2026 的各年官方 ZIP，以 extract.py 加 ZIP 路径筛选。仓库实物覆盖见上表。其他地区调查与待取得田界见 sources.md。

欧洲数据来自 European Commission Joint Research Centre, EuroCropsV2 gpqtv202，按 CC BY 4.0 再发布。修改为按原始作物代码筛选、几何质量筛选、标签翻译与分片压缩。原始许可见 eurocrops/COPYRIGHT.txt。 [JRC 数据目录](https://jeodpp.jrc.ec.europa.eu/ftp/public/JRC-OpenData/DRLL/EuroCropsV2/) · [作物代码映射](https://github.com/Martincccc/EuroCropsV2/blob/main/data/cropcodemapping/eurocrops.csv)

加拿大数据来源为 La Financière agricole du Québec，BDPPAD。此处发布单作物子集并转换为 GeoParquet。[来源及历年档案](https://www.fadq.qc.ca/documents/donnees/base-de-donnees-des-parcelles-et-productions-agricoles-declarees/) · [代码说明](https://www.fadq.qc.ca/fileadmin/geo4tb/BDPPAD/bdppad-v03-guide-utilisateur.pdf) · [许可](https://www.donneesquebec.ca/licence/)
