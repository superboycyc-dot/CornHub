# CornHub 第二版：2018–2025 逐田逐年模型与 A/B/C 交接提示词

状态：实施方案与 AI 工作指令，尚未下载新版 CSB、提取新增时序或训练 v2。2026-11-14，由 C 成员提出。
本文件是 v2 的增量提案；现有 BARC 合同、v1 数据、5 个农场留出折及发布结果保持可复现。A 负责协调共享字段变更，B/C 在版本化目录实施，D/E 后续接入。

## 1. 第二版要回答什么

同一位置今年种玉米、明年换作大豆或休耕；即使连续种玉米，收获用途也可能逐年改变。因此分析单位是“来源版本内的田块＋年份”，不是永久给田块贴上青贮标签。

流程：2018–2025 作物历史 → 当年玉米候选 → 当年卫星观测 → 当年青贮/籽粒概率或无法判断 → 按年面积汇总。

两条工作线独立验收：
- 方法验证：BARC 2021–2023 的44条用途真值，复用既有农场留出5折。测试增强特征是否改善青贮识别。
- 地域扩展：CSB 2018–2025 候选与年度作物信息。无新增用途真值时仅作未验证迁移推断，不报告全国精度或可靠供给。

新增几百万候选不等于新增几百万监督标签；不保证数据更多就提高性能。补贴、作物类别、早收信号和 CropSight Confidence 均不能当作真实 S/G 标签。

## 2. 来源、版本与当前缺口

- USDA CSB 官方入口：https://www.nass.usda.gov/research-and-science/crop-sequence-boundaries
- 2018–2025 元数据：https://www.nass.usda.gov/research-and-science/crop-sequence-boundaries/metadata-crop-sequence-boundaries-2025
- 官方包：https://www.nass.usda.gov/sites/default/files/Research_and_Science/Crop-Sequence-Boundaries/datasets/NationalCSB_2018-2025_rev23.zip
- 元数据记载2026-03-27发布，图层 national1825，含 CSBID、CDL2018…CDL2025、面积与地区字段；下载后核对真实 schema，不根据文档猜字段大小写或类型。
- CSB 覆盖美国本土连续48州，是多年 CDL 推导的统一分析多边形与年度多数作物类别；不是每年实测田界、产权界或种植者申报。不能完整追踪真实田块拆分/合并。
- PR #10：https://github.com/superboycyc-dot/CornHub/pull/10 。已提供旧版2016–2023来源的2021–2023玉米候选、CropSight及政策研究；不要将旧候选数量复制为新版计数。
- CSBID含起止年份，不跨版本直接连接。BARC与CSB用有审计的空间对应表，禁止按最近邻强认同一田。
- 原始全国包、解压及影像会占空间：先检查共享10 GB限制，分批处理与缓存预算；原包不加入Git，处理分片登记manifest与哈希。不要再向Git历史无预算地提交全国大包。

## 3. A → B/C 的 v2 数据合同提案

以下为待实现交接格式，不表示文件已存在。A 可与 B/C 协调后调整，但必须统一版本及说明。
目录：data/processed/v2/core/；报告：reports/a_data/v2/。

|产物|字段与要求|
|---|---|
|fields 分片 GeoParquet|candidate_id, source_field_id, source_dataset_id, source_version, geometry, geometry_valid, area_ha, state_fips, county_fips；几何EPSG:4326，全国面积EPSG:5070|
|crop_history 分片 Parquet|candidate_id, year, crop_code, crop_name, corn_status, crop_source_dataset_id, source_available_at；唯一键candidate_id+year；corn_status仅corn/non_corn/unknown|
|barc_candidate_crosswalk.csv|field_id, candidate_id, source_version, match_method, intersection_area_ha, barc_overlap_fraction, candidate_overlap_fraction, match_status；保留一对多/无匹配，不把标签扩散到全部重叠对象|
|pilot_field_years.csv|entity_id, entity_kind, year, geometry_ref, selection_reason；分别列BARC验证和外部候选试点，锁定数据版本与范围|
|manifest.json、sources.csv、acceptance.json|原件链接、版本、获取时间、许可、SHA、分片行数、年度类别数、未知数、无效几何数、面积口径、来源可用日期与实际验收|

必须先保存完整农业候选库或可复取的完整源manifest；模型使用的玉米子集按八年任一年为玉米筛选，同时保留这批多边形全部八年的历史，不能只留下种玉米年份。无记录/无效类别保持unknown，不能默认为非玉米。Corn代码1与甜玉米、爆米花、复种代码分开定义；明确当前分析口径及不覆盖项。

BARC原边界和原标签是验证主键；CSB不替换BARC田界。轮作特征若映射歧义，设缺失并解释。BARC标注玉米但CDL判为非玉米时保留冲突标记，不能通过筛除难例改善指标。

## 4. B → C 的卫星合同提案

目录：data/processed/v2/satellite/；报告：reports/b_satellite/v2/。
- timeseries：entity_id, year, date, sensor, scene_id, ndvi, ndmi, valid_pixel_fraction, source_dataset_id；唯一键entity_id+year+date+sensor+scene_id。
- features：entity_id, year，保留v1七项特征及质量字段；新增峰值后下降、持续低绿度、收割前后NDMI变化等列必须在README给出公式、时间窗口、单位、最少观测数和缺测规则。
- 保留v1 NDVI基线；v2增量NDMI=(B08-B11)/(B08+B11)，正确处理B11 20m与B08 10m网格、SCL和反射率缩放，记录连续波段及分类掩膜各自重采样规则。其他指数/雷达属可选，不阻塞主线。
- 延续04-01至12-01默认窗口、同日选景与质量规则；改变窗口必须版本化并做覆盖比较。固定时间窗与数据截止日，禁止按真值选择收割日期。
- 先覆盖44个BARC标签田块年，再选明确地区的至多100个外部玉米田块年试点。先报告检索覆盖、存储和计算预算，不启动全国全量影像。
- 非玉米年度不产生S/G概率；作物未知、卫星不足、来源冲突分开标记。统计全部候选、有效覆盖和排除原因。

## 5. C 的建模、时间口径与验收

目录：src/model/ 下独立v2入口或兼容扩展，notebooks/c_model/v2/、data/processed/v2/model/、reports/c_model/v2/。
现有pipeline对barc_及2021–2023有校验；不得直接删除校验让外部候选伪装为BARC。新增显式schema/适配器，区分标签验证与外部推断。

模型比较：
1. 冻结v1输入、代码SHA、现有5个farm-held-out折，复跑基线。
2. v2a：相同田块/相同折，增加B的新卫星特征，简单规则与小型RF对照。
3. v2b：在可匹配且有历史覆盖时加入轮作特征，例如前一年作物、此前可用年份玉米频率、连续种玉米年数；缺失历史不可编码为非玉米。
4. 在共同可评估子集报告配对比较，同时报告全44行的覆盖与排除；不得靠丢弃难样本宣称提升。

时间模式必须分开：
- retrospective：可使用目标年完整季节观测与事后发布的年度作物图，用于回顾分析。2018–2025 CSB含未来年份构界信息，所有历史结果明确为事后统一边界分析。
- as_of：若实现收割前/当季预测，只用截止日前已发布数据及卫星观测；逐条检查source_available_at，晚发布的目标年CDL及事后CSB不作实时可用证据。不能用8年玉米总次数、未来作物或未来卫星预测早年用途。
- BARC标签只覆盖2021–2023；2018起点缺少更早历史，按缺失处理。无跨年真值则不得声称验证了2018–2025用途变化。

验证使用既有按农场留出5折，所有预处理、填补、特征筛选、阈值选择在训练折内部；校准和调参只在可行的训练内分组拆分进行，样本不足保留未校准。相同田/同农场及重叠候选不得跨训练测试泄漏。若增加按年留出作为辅助实验，检查同田跨年与空间依赖并单列局限。

指标：混淆矩阵、两类precision/recall/F1、macro F1、Brier、每折及每年类别数、覆盖率、误差案例；青贮仅12条，不承诺指标提升。优先检查v1漏判青贮案例，不能据留出答案手工调阈值。
预测字段至少：entity_id, year, p_silage, predicted_label, prediction_role, fold_id, model_version, temporal_mode, as_of_date, data_quality, geographic_validation_status, missing_reason。
p_silage解释为“当年为玉米条件下”的用途概率；未校准需标注。OOF与全量inference分开；non_corn/unknown/insufficient保持概率null，另设状态，不能填0或0.5。概率加权面积仅限当年实际有预测覆盖，未验证全国迁移不发布全国真值面积。

交付 model_card.md、feature_dictionary.csv、input_manifest.json、merge_audit.json、metrics.json、v1_v2_comparison.csv、oof_predictions.csv、inference_predictions.csv、exclusions.csv、可复现命令与环境。指标未算为null；记录主模型是否采用增强特征及证据。政策不进入用途标签、补助资格判定或默认经济收入。

## 6. 可直接复制给 A 的 AI

```text
我是CornHub成员A。请读适用AGENTS.md、最新docs/team-contract.md及notebooks/c_model/v2/模型方案与ABC提示词.md。落实本文件第2–3节的2018–2025逐田逐年数据交接。先检查现有工作、PR #10及上游SHA，独立work/a-csb1825-v2分支，保留旧交付，不覆盖队友、不直接推main、不强推。

核实下载NationalCSB_2018-2025_rev23官方原件、实际schema、许可、CRS及校验。先查共享空间与下载预算，流式处理；原包及解压不进Git。保留完整来源manifest；构建八年至少一年种玉米的候选子集并保留全部8年作物历史，未知不能算未种。记录Corn代码口径、每年数量、几何有效性和面积口径；无效几何不静默修复。不要沿用旧版611万计数。

按第3节在data/processed/v2/core交fields分片、crop_history、BARC空间对应表、pilot清单与来源验收。CSB跨版本ID不能直接复用；BARC与CSB映射保留重叠比例及一对多/冲突，不能转移用途真值到全国候选。先交44个BARC验证田块年的历史映射，再选至多100个明确地区外部玉米田块年，与B/C锁定ID和版本。2026发布的事后边界及作物图注明可用时间；历史回顾与实时预测分开。

协调共享schema，报告实际下载/检查、数据路径与行数、来源SHA、B/C可用样本、未解决项。完成可执行部分并发PR，不只写计划；无法取得数据则交真实阻塞和可复现获取方法，不生成假数据。
```

## 7. 可直接复制给 B 的 AI

```text
我是CornHub成员B。读适用AGENTS.md、最新docs/team-contract.md及notebooks/c_model/v2/模型方案与ABC提示词.md，落实第4节。沿用现有真实卫星代码，独立work/b-satellite-v2分支，只改B目录及B的v2产物，不覆盖v1、不直接推main。

先冻结v1代码与数据SHA，对现有44个BARC标签田块年提取NDVI基线与增量NDMI/收割后特征。与C确认公式和字段。处理SCL、反射率缩放、B08/B11网格与重采样、有效像元、观测空档；无数据保持缺失，不插造曲线，不按真值确定窗口。保持04-01至12-01默认窗口，改动需版本化。交timeseries/features及质量、覆盖、来源报告到data/processed/v2/satellite和reports/b_satellite/v2。

A交付前可完成BARC增强及独立v2读取接口；外部候选必须用A锁定的ID/边界/年度，先至多100个玉米田块年，报告预算后分批，不跑全国。非玉米/未知/低覆盖分开处理。不要用CSB替换BARC原边界；与C约定entity_id、年份、schema和数据截止日。NDMI缺失不阻塞NDVI对照。

提交实际可运行命令、输入输出SHA、每田每年观测数、缺测/冲突、单田证据图与PR。更多特征不等于效果提升，交给C用固定留出折评估。
```

## 8. 可直接复制给 C 的 AI（本成员）

```text
我是CornHub成员C，负责实施第二版模型。仓库https://github.com/superboycyc-dot/CornHub。先读适用AGENTS.md、最新docs/team-contract.md、notebooks/c_model/v2/模型方案与ABC提示词.md及当前模型报告，落实第5节。使用独立work/c-model-v2分支，保留v1输入、5农场留出折及结果，不覆盖A/B/D/E、不直接推main、不强推。

目标是“田块＋年份”的两阶段流程：A提供年度玉米/非玉米/未知及历史，B提供当年卫星特征；只对当年玉米且观测足够的记录做S/G条件概率。2018–2025 CSB和CropSight没有青贮/籽粒真值，不能当新增监督标签；补贴/早收信号/作者Confidence也不能当答案。

立即可做：审查现有pipeline的barc_和2021–2023限定，做显式v2适配与schema，保留v1校验；冻结并复跑v1；建立带来源、时间截止、覆盖/缺测、输入键和模型版本的v2接口、比较器和真实pending输出。缺A/B输入时继续完成这些独立工作，报告缺项，不能造预测或性能。

A/B到齐后，按固定5农场留出折比较v1、v2a卫星增强、v2b仅用此前历史的轮作增强。A的空间映射有歧义则缺失，BARC/CDL冲突不得静默删样本。全部44行覆盖报告与共同子集配对比较同时输出。填补、阈值选择、校准只在训练折内；样本不足不校准、不大调参。报告两类指标、Brier、每年每折计数及漏判案例，不承诺提升；若v2不优保留v1为主模型。

严格区分retrospective和as_of。2018–2025统一CSB利用未来年份构界，历史实验标为事后回顾；收割前预测需另有当时可用边界/作物信息及source_available_at，禁止目标年未发布CDL、未来卫星或八年总轮作频次泄漏。OOF/inference分离，non_corn/unknown/insufficient概率null。外部试点只标记未验证迁移推断，不能宣称全国精度。

按第5节交模型卡、特征字典、输入manifest、合并审计、OOF/推断、排除表、v1/v2比较及可复现命令；用有意义的schema/合并/泄漏/缺测/回归检查验证。通过PR交付，汇报实际完成、指标与限制、需要A/B什么、给D/E的兼容方式。不要仅写方案。
```

## 9. 协作顺序与完成定义

1. C先完成v2接口、v1冻结及比较流程；B可同步完成BARC增强；A同步处理新版来源和历史映射。
2. A先交共享ID/版本/试点 → B按清单交真实时序 → C完成受控对照及外部推断。
3. C交付后D做逐年覆盖与面积汇总；E增加版本/年份选择、非玉米/未知/缺测及迁移未验证状态。D/E接入另走PR，不要求A/B/C代改。
4. v2完成需有可复现输入、真实特征、固定折比较、时间泄漏说明、可追溯外部试点；有文档或候选库不代表模型训练完成。
