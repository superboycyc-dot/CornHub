# A 全国候选库扩展交付

本轮用户要求：核对团队进度；下载处理CSB/CropSight-US并同步GitHub；检索2022–2025美国玉米饲料相关政府支持。基线main=2f28056，独立分支work/a-external-corn；不改B/C/D/E实现、已有BARC core或模型预测。

## 已完成

- 官方CSB 2016–2023 rev23、CropSight-US v1.0.1完整原件已下载到本地data/raw/external_corn，并解压。原件/解压均忽略，不放入Git历史。GitHub同步**全量筛选后的候选分片**，不是仅样本、链接或空接口。
- CSB筛出三年至少一年Corn代码1的6,112,209多边形；CropSight筛出2021–2023的15,939玉米对象。GeoParquet分片保留来源ID、WGS84几何、等积ha、年度作物属性及可用的置信字段；收获用途全部未知。
- 全部分片回读验收通过：验证详见validation.json；原始来源、大小、SHA、CRC和作者MD5见sources_manifest.json，源元数据随报告保存。
- 团队进度与来源SHA在team_snapshot.json、team_status_zh.md；它们是检视远端交付的快照，未重新运行队友程序。
- 政策说明和CSV索引在../policy_2022_2025。只使用可核验的官方资料作背景，区分时间、受益人、直接/间接支持、补助/贷款；不改D经济参数。

## 重要限制

CSB导出有209,931个无效几何，按geometry_valid=false保留并提供样例；不是全量可直接作空间分析的清洁真值。使用时显式排除或审计修复。CropSight无无效几何，但其作物类别仍为作者模型预测。两个来源均无silage/grain用途答案，因此本轮**没有把44条BARC真值扩成611万条训练真值**，不以新候选数宣称模型提升。

全国数据只覆盖各自产品所定义的CONUS范围；CropSight是抽样对象，不是全国完整田块清单。不同来源/年度边界不能按近邻就宣称为同一实际田。CSB多年边界含较晚年度信息，不可直接支持早年实时能力的主张。

## 实际执行经过

1. fetch团队远端并读取角色报告/PR和C的真实metrics；工作区最初干净。新分支从最新main建立，保留首轮A分支。
2. CSB整包HTTP请求500，改为32MiB分段、4并发下载，完成3,505,346,935 bytes；整ZIP CRC通过后解压。
3. CropSight单连接速度降低；并发请求也出现超时。停止本任务重复连接，保留已完成块与部分字节续传，最终MD5=8df463cd8d09210354a6e31f8cdcada7，与作者一致；CRC通过。
4. 临时venv安装pyogrio/pyarrow等，具体锁定版本见src/data/external_corn/requirements.txt。CSB读OpenFileGDB、CropSight读Shapefile；先核对实际schema再处理。
5. 流式5000行批读取，只筛选规定年/代码；先生成flat分片，随后按每100片归入batch目录并更新manifest；交付脚本已直接产生相同batch目录结构。CSB几何不做自动修复，保留质量标记。CropSight源ID来自Shapefile FID，仅此版本对象身份。
6. 验证器实际回读所有1232个分片。CSB另从原GDB只读三年属性独立扫描16,194,800个记录，结果与筛选数量完全一致（csb_source_counts.json）。未做地面核验、卫星批量提取、模型训练或队友结果覆盖。
7. 因处理后数据约2.15GB，按两批Git提交/推送控制单次pack体积；PR交付，不直接推main。原包可按来源manifest复取，现成处理后分片可直接下载读取。

## 实际命令

仓库根目录，环境Python3.13。下载使用download_csb.py及断点续传脚本的同等临时版本；脚本已随src/data/external_corn保存，首次下载需保证原件路径不与已有完整包冲突。

```sh
/tmp/cornhub-a-data-venv/bin/python src/data/external_corn/register_sources.py
/tmp/cornhub-a-data-venv/bin/python src/data/external_corn/process.py csb data/raw/external_corn/NationalCSB_2016-2023_rev23/CSB1623.gdb
/tmp/cornhub-a-data-venv/bin/python src/data/external_corn/process.py cropsight data/raw/external_corn/cropsight/cropsight-us_app_dat_v1.0.1.shp
/tmp/cornhub-a-data-venv/bin/python src/data/external_corn/validate.py
```

源码流式处理的实际stdout在csb_run.log/cropsight_run.log；原件校验在source_verification.log；验收stdout在validation_run.log。独立source count由一次inline pyogrio.open_arrow(read_geometry=False, columns=[CDL2021,CDL2022,CDL2023])扫描记录：每列等于1的数量及三列OR总数。它未依赖Parquet处理结果。

## 给团队的交接

B：新增candidate_id命名空间和WGS84候选边界；先选明确范围并筛geometry_valid，不立即对全国611万对象提取卫星。C：没有新用途标签，不能直接加进S/G监督训练或将CropSight的Confidence作为我们的模型准确率。D：政策资料是背景，ECAP历史基础费率不能直接乘模型预测面积作应得补助。E：处理后文件不是BARC合同替代，不自动作为全国精度/供给展示。组长：主线范围仍以最新BARC合同为准，全国库是本轮显式授权的扩展。
