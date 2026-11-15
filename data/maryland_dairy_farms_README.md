# 马里兰州奶牛场位置与牛数

采集日期：2026-11-14。**这是公开来源整合清单，不是马里兰州全部在营奶牛场的完整普查。** 没有获得州卫生部门完整、逐场、区分牛/羊且含当前状态的奶源生产许可证登记册，因此不能计算全州覆盖率，也不能把历史候选记录视为当前奶牛场。

## 文件

| 文件 | 记录数 | 用途 |
| --- | ---: | --- |
| `maryland_dairy_farms.csv` | 67 | 有大概坐标的公开奶牛/乳牛场相关地点；27 条有公开牛数（其中 1 条为 2019 年历史值），7 条按面积粗估，33 条牛数及可用面积未查到 |
| `maryland_dairy_farms_unresolved.csv` | 1 | Mason Dixon Farms 有许可证申报牛数，但未确定马里兰州养殖地点坐标，经纬度留空 |
| `maryland_dairy_historical_candidates_2015.csv` | 93 | 2015 年 Dairy 图层的全部候选点，可能包含羊奶场、出售乳品的农场、已停业地点；不得当作当前奶牛场训练标签 |

主表和待定位表共 68 个公开地址/地点，不一定等于 68 家独立企业。同一农场的门店、加工地点和养殖地点可能不同。Long Delite Farm 与 Deliteful Dairy 为同一农场企业的不同公开地址，其牛数仅在 Deliteful Dairy 行填写。历史表与主表有交集，三个文件的记录数不能相加当作农场总数。按用户允许的大概位置，主表包含 2 个道路附近参考点、1 个同名乳品店的其他地址点，使用 `location_precision` 区分。

## 数据来源及收集范围

1. [Maryland Department of the Environment AFO Public Search Tool](https://mdedataviewer.mde.state.md.us/Public/Land/CAFO/Public%20Search%20Tool)：Animal Type = Dairy Cattle，Permit Status = All，遍历全部两页，取得 19 条许可证记录；同一 AI 23565 的两条记录合并，保留较新的 2026-CDC-2506 记录及旧许可备注，共 18 个地点。Active/Pending 是许可证记录状态，不是实时产奶状态。
2. [Maryland's Best / MDH 直销牛奶农场名单](https://marylandsbest.maryland.gov/enjoy-maryland-milk/)：提取表中全部 13 条记录。该表只列面向消费者销售的农场，不覆盖全部奶源供应场。
3. [Washington County 政府农业目录](https://www.washco-md.net/business-development/agriculture/)：提取 Dairy 小节全部 36 条。类别说明支持其乳牛场身份，但没有逐一实地核实物种或经营状态。
4. [Maryland's Best Ice Cream Trail](https://marylandsbest.maryland.gov/ice-cream-trail/)：仅补充 Happy Cow / Grand View Acres、Keyes、Rocky Point、Chesapeake Bay 四个奶牛场相关地点；未将整张冰淇淋商店名单当作奶牛场。
5. [2015 Dairy Farms GIS Web Map](https://www.arcgis.com/home/item.html?id=094daac9f5d942399611c7251c13f0d7)：取 AG_MD_Farm_Dairy_2015_CLF 图层全部 93 条，未纳入同一 Web Map 的乳品加工厂图层。其[图层说明](https://www.arcgis.com/home/item.html?id=1cb5e616f51a45dca2f47b5eb14bc2ad)明确指出包含羊奶场且不完全覆盖所有农场。[Johns Hopkins CLF 项目](https://clf.jhsph.edu/projects/maryland-food-system-mapping-resource)已在 2023 年退役；[归档 DOI](https://doi.org/10.7281/T1/QUDBC6)。引用：Johns Hopkins Center for a Livable Future, 2023, Data associated with: The Maryland Food System Map, Johns Hopkins Research Data Repository, V1。归档标注 CC BY-NC 4.0，使用历史候选表应保留出处并遵守来源条款。

## 经纬度

- 坐标系：WGS84 / EPSG:4326，十进制度，北纬为正、西经为负。`latitude` 是纬度，`longitude` 是经度。
- 主表 59 条采用 [U.S. Census Geocoder](https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html) 的 Public_AR_Current 地址范围匹配。**这是沿街道地址范围插值得到的位置，不是牛舍、地块中心或测量级 GPS 点。** 保留 `coordinate_matched_address` 以便核对。
- South Mountain 的 1 条坐标采用 [Frederick County 官方 Farms GIS](https://fcgis.frederickcountymd.gov/server_pub/rest/services/Basemap/PointsOfInterest/MapServer/7) 的同地址发布点。
- 4 条采用 OpenStreetMap 中能匹配门牌号与 Maryland 的地址/建筑点；另外 2 条使用同县同名道路参考点，Keyes 使用另一公开地址的同名 creamery 点。后 3 条可能距离养殖地点数公里，不能当作地块定位。每行给出具体 OSM 对象链接。© [OpenStreetMap contributors](https://www.openstreetmap.org/copyright)，数据按 ODbL 提供；这些点同样未经实地测量。
- 历史候选表使用原始属性 X_Coord/Y_Coord，将 EPSG:3857 转换为 EPSG:4326，未重新地理编码。七位小数仅是存储精度，不表示厘米级实际精度。
- 只接受对应县的道路级参考结果；不同县的同名道路匹配已拒绝。同名商店地址与农场不一致时，标注为低精度关联地点。Mason Dixon 的养殖点仍未确定，保留待定位。

## 奶牛数量字段

| 字段 | 含义 |
| --- | --- |
| `cow_count` | 来源所报告的牛数；必须结合下述定义、年份和状态使用 |
| `cow_count_definition` | 数量口径：如产奶牛、乳牛群，或 MDE 申报的 Dairy Cattle 动物数量 |
| `cow_count_qualifier` | approximately 表示约数，reported_integer 表示来源报告整数，均不代表实地点数 |
| `cow_count_as_of` | 来源明确给出的时间；空白表示原文没有给出统计时间，不能以采集日代替 |
| `cow_count_status` | 来源与状态；not_publicly_found 表示尚未找到公开数量，不表示零头 |
| `cow_count_source_url` | 数量的直接来源 |
| `milking_cow_count` | 只有来源明确指正在挤奶/产奶的牛时填写；历史值仍须结合 cow_count_as_of 使用 |
| `dairy_cattle_count` | MDE 许可证/申请中 Primary Animal Type = Dairy Cattle 的 Number of Animals 原值；不保证只含泌乳成年母牛 |

主表 27 条有公开数量，7 条按用户要求由有来源的面积粗估，33 条数量和可用面积仍未知；待定位表还有 1 条许可证数量。未用全州平均数、奶产量、牛舍容量或评鉴样本数替代缺失牛数。2015 历史候选表未逐场确认牛种，未对其强行估算牛数。

## 面积估算方法

优先使用公开报告牛数；仅当牛数未知且找到农场面积时填写面积估算。`cow_count_status = estimated_from_area_very_low_confidence` 明确区分估算值。`cow_count` 是便于使用的数字列，**必须同时保留 `cow_count_status`，不可将整列视为实测数量**。`estimated_cow_count` 和 `estimated_cow_count_low/high` 单独保存估算及场景范围，`milking_cow_count` 不填面积估算。

- 面积列：`farm_area_acres`、`farm_area_hectares`、`farm_area_scope`、`farm_area_as_of`、`farm_area_source_url`。总经营面积可能含作物、林地、租地及多块地，不等于牧草面积。
- [Penn State Extension 的奶牛经营经验规则](https://extension.psu.edu/dairy-sense-keeping-the-dairy-right-sized)为每头成年牛约需 1.5–2.0 英亩饲料土地，并计入后备牛的配套用地。这是饲料/土地支持能力规则，**不是根据土地反推出实际存栏的定律**。
- 中间场景：`总面积 × 60% ÷ 1.75`，四舍五入到 10 头。
- 低/高场景：`总面积 × 30% ÷ 2.0` 与 `总面积 × 80% ÷ 1.5`，同样取整到 10 头。
- 30%/60%/80% 是分析者为未知可用饲料面积设置的假设，不是逐场测量或来源事实。区间只是敏感性场景，不是统计置信区间。饲料外购、外租地、闲置地和混合经营均可导致实际数量远离该区间。
- 经营面积来自 [MASCD 的 Land Managed 表](https://mascd.net/fscap-certified-farms/)、农场/政府介绍等逐行链接。Roth Meadowbrook 仅有 2008 年 121.4 英亩保育地役权地块记录，估算尤其不确定，不能视为整个农场当前经营面积。Broom's Bloom 的 240 英亩涵盖合并经营的三块地产。
- 例：Prigel 409 英亩得到约 140 头的土地支持能力代理值，低/高场景 60–220；此数字是模型粗估，未声称当前实际有 140 头奶牛。

面积也未知的农场继续留空，不给每个农场捏造一块统一面积。Long Delite 同一企业的另一地址不重复分配牛数。

数量补充取自每行链接的农场官网、州政府资料、农户介绍或行业组织资料。例如 Deliteful 约 60 头产奶牛、Moo Cow 约 80 头产奶牛、Rocky Point 175 头产奶牛。Shenandoah 的 115 头为明确的 **2019-11-16 历史值**，不是当前值。

## 已知冲突和使用限制

- Clear Spring：MDH/MDA 牛奶表给出 14312 St Paul Rd，县目录给出 14322 St Paul Rd；主表保留前者及其地址匹配点，并标注冲突。官网 About 页称约 30 头，2026-02 招聘文件称约 35 头，数量保留有日期的 35 头。
- Broom's Bloom：MDH/MDA 牛奶表给出 1616 S Fountain Green Rd，农场官网和 Ice Cream Trail 给出 1700 S Fountain Green Rd；主表坐标遵循 MDH/MDA 表中的地址，可能对应企业关联场址而非门店/牛舍。
- South Mountain：MDE 单一许可地点为 580 头；官网介绍整个 3300 英亩经营体有超过 1600 头乳牛。两个口径并不一致，未用企业总数替代此地址的许可数量。
- 网站常未标统计日期，牛数可能改变；许可证数量也可能来自申请资料，不是实时实存数量。数据不能直接用于按点位推算当前全州牛只总量。
- 目前覆盖 11 个县，明显遗漏一些县及研究型牧场。取得完整登记册后还需要按实际养殖地址定位、剔除停业与非牛奶生产者、逐场确认牛数。
- 对卫星识别任务，应另行核实牛舍和牧场边界；街道地址点及加工/零售关联地点不能直接视作地块真值。

## 检查

CSV 使用 UTF-8、标准引号转义和英文列名。检查了列数一致、主表经纬度无缺失、经纬度未颠倒、处于马里兰州大致外包范围、同一 AI 去重及原始来源追踪。外包范围检查不等于逐点州界/地块边界核实。未知值保留空白，未写成 0。
