# BARC 地块收割方式预测 · v3final

`v3final.csv` 每行对应一块 BARC 官方田地的一年。83 块官方地块使用同一套边界，从 2021 至 2025 年每年各 83 条，共 415 条。地块与年份共同构成唯一键。

| 列 | 含义 |
|---|---|
| field_id, year | 官方 OBJECTID 加 barc_ 前缀、观测年份 |
| harvest_type | v3 对玉米收割方式的预测。silage 为青贮，grain 为籽粒。无有效 NDVI 时留空 |
| probability | 预测类别的原始模型概率，范围 0–1 |
| p_silage, p_grain | 青贮和籽粒的原始模型概率。青贮概率达到 0.5 时判青贮 |
| official_label | 官方文件明确提供的年度收割方式，空白表示未提供 |
| maize_status | officially_labeled 表示有官方玉米标签。unconfirmed 表示该年是否种玉米尚未确认，其预测仅在种植玉米的前提下解释 |
| v3_training_overlap | 该地块年度是否出现在 v3 训练清单中 |
| ndvi_source, valid_ndvi_dates, quality_flag | NDVI 来源、有效日期数和已有质量标记，空白表示来源未提供 |
| ndvi_peak, peak_doy | 年度观测窗口内的 NDVI 峰值及其年内日序 |
| max_drop_per_day, drop_doy | 最大日均下降幅度及其年内日序 |
| ndvi_late_mean | 9 月至 11 月有效观测的平均 NDVI |
| nearest_dairy_distance_km | 地块内代表点至最近奶牛场的 WGS84 测地线距离，单位千米。各年使用相同的项目奶牛场名录 |

推理在 NVIDIA Brev 上运行，使用项目第三阶段保存的完整模型 global_full_model.joblib。以已有地块年度 NDVI 为先，缺失部分根据 4 月至 11 月的 Sentinel-2 地块像元补算。使用训练时保存的缺失特征处理和决策阈值。模型权重、CSV 的 SHA-256 和分类计数见 manifest.json。

官方 BARC_Corn.2021-2023.gpkg 只给出了 2021–2023 年部分地块的收割标签。表中的 probability 是模型分类概率，实际正确率需要另行验证，训练重叠行尤其不能用来评价泛化。
