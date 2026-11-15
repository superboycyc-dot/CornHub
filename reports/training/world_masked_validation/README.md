# 全范围遮罩验证：第一步、第二步及筛选模型

所有数据预测、过滤模型折验证和评分均在 NVIDIA Brev 上完成。预测时只传NDVI特征及有距离模型要求的距离特征；标签仅在所有预测概率生成后用于计分。第一步、第二步原模型及选定v2模型按原文件加载，没有重训。筛选模型只加载保存的折模型，测试折所在组没有用于训练。

## 遮罩

第一、二步训练涉及34块马里兰田、44个田块年度记录。测试集中已移除这些田块的全部年份记录，共移除58条；因此不把模型训练见过的田块拿来打分。剩余美国记录中有22条来自同一批5个农场，报告标记了这层农场相关性。

加拿大与荷兰的可用NDVI记录来自未参与第一、二步拟合的来源；全世界可用记录并不等于完整全球覆盖。大量没有NDVI的候选保留在来源清单中，不参与准确率。

## Overall结果

|模型|测试范围|样本|正确|准确率|多数类基线|宏F1|平衡准确率|青贮召回|
|---|---|---:|---:|---:|---:|---:|---:|---:|
|refit_drop_ge90pct_label_countries_ndvi|all_available_external_countries|39788|39205|98.53%|99.73%|0.5566|0.6787|37.04%|
|step2_ndvi_distance_44_frozen|all_available_external_countries|39788|38251|96.14%|99.73%|0.5166|0.6805|39.81%|
|step1_ndvi_44_frozen|all_available_external_countries|39788|38144|95.87%|99.73%|0.5148|0.6838|40.74%|
|step2_v2_selected_44_frozen|all_available_external_countries|39788|36671|92.17%|99.73%|0.4966|0.7160|50.93%|
|refit_drop_single_label_countries_ndvi|all_available_external_countries|39788|35749|89.85%|99.73%|0.4927|0.8291|75.93%|
|refit_drop_ge90pct_label_countries_ndvi|strict_unseen_farm_all_countries|39766|39188|98.55%|99.74%|0.5571|0.6858|38.46%|
|step2_ndvi_distance_44_frozen|strict_unseen_farm_all_countries|39766|38233|96.14%|99.74%|0.5167|0.6882|41.35%|
|step1_ndvi_44_frozen|strict_unseen_farm_all_countries|39766|38126|95.88%|99.74%|0.5149|0.6916|42.31%|
|step2_v2_selected_44_frozen|strict_unseen_farm_all_countries|39766|36656|92.18%|99.74%|0.4967|0.7258|52.88%|
|refit_drop_single_label_countries_ndvi|strict_unseen_farm_all_countries|39766|35734|89.86%|99.74%|0.4928|0.8437|78.85%|
|step1_ndvi_44_frozen|test_excluding_ge90pct_label_countries_CA_NL|22|18|81.82%|81.82%|0.4500|0.5000|0.00%|
|step2_ndvi_distance_44_frozen|test_excluding_ge90pct_label_countries_CA_NL|22|18|81.82%|81.82%|0.4500|0.5000|0.00%|
|refit_drop_ge90pct_label_countries_ndvi|test_excluding_ge90pct_label_countries_CA_NL|22|17|77.27%|81.82%|0.4359|0.4722|0.00%|
|refit_drop_single_label_countries_ndvi|strict_unseen_farm_excluding_Canada|113|87|76.99%|92.04%|0.5705|0.6720|78.85%|
|refit_drop_single_label_countries_ndvi|test_excluding_Canada|135|102|75.56%|80.00%|0.6902|0.7500|75.93%|
|step2_v2_selected_44_frozen|test_excluding_ge90pct_label_countries_CA_NL|22|15|68.18%|81.82%|0.4054|0.4167|0.00%|
|refit_drop_single_label_countries_ndvi|test_excluding_ge90pct_label_countries_CA_NL|22|15|68.18%|81.82%|0.4054|0.4167|0.00%|
|step2_v2_selected_44_frozen|test_excluding_Canada|135|78|57.78%|80.00%|0.5526|0.6806|50.93%|
|step2_v2_selected_44_frozen|strict_unseen_farm_excluding_Canada|113|63|55.75%|92.04%|0.4650|0.7089|52.88%|
|step1_ndvi_44_frozen|test_excluding_Canada|135|71|52.59%|80.00%|0.5183|0.7037|40.74%|
|step2_ndvi_distance_44_frozen|test_excluding_Canada|135|70|51.85%|80.00%|0.5117|0.6991|39.81%|
|refit_drop_ge90pct_label_countries_ndvi|test_excluding_Canada|135|65|48.15%|80.00%|0.4750|0.6481|37.04%|
|step1_ndvi_44_frozen|strict_unseen_farm_excluding_Canada|113|53|46.90%|92.04%|0.4127|0.7115|42.31%|
|step2_ndvi_distance_44_frozen|strict_unseen_farm_excluding_Canada|113|52|46.02%|92.04%|0.4064|0.7067|41.35%|
|refit_drop_ge90pct_label_countries_ndvi|strict_unseen_farm_excluding_Canada|113|48|42.48%|92.04%|0.3746|0.6368|38.46%|

“删加拿大”与“删≥90%单标签偏斜国家”两列是测试集筛选，只用于原封不动的第一、二步模型；新筛选模型另外采用所有可用国家的分组OOF测试。每个模型/测试范围的逐国细项见 `country_results.csv`。

## 解读限制

本次可评分国家只有加拿大、荷兰和美国，不能称为全世界准确率。加拿大全是籽粒，单看总准确率会被类别比例主导。美国剩余22条与训练农场相关，不能当作独立农场外测。筛选模型的全国家OOF分数与第一、二步冻结模型的全范围外部评分使用相同测试行，但模型训练数据和验证方式不同；报告指标用于比较当前可见样本上的准确率，不代表未来/全球部署性能。全球标签在前几次开发实验中已被检查，因此并非从未看过的盲测集。

完整总表、逐国表、逐条预测、模型校验清单和源哈希保存在 NVIDIA 本次运行目录。
