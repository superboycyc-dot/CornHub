# B 真实样本执行交付

负责人 B；账号 `aiaiai-ajlk`；分支 `work/b-satellite`；PR #5。

A 的 PR #6 / `work/a-data` 提交 `df7ce8c` 已交付。B 使用其固定提交的只读 worktree，未复制或改写 A 的文件。共同样本 **barc_1 / 2021，6.63739333 ha**，窗口 **[2021-04-01,2021-12-01)**。完整提交与输入 SHA256 见 `core_handoff.json`；官方 notebook 已实际审阅，见 `notebook_review.md`。

## 已取得真实结果：partial，不是完整成功

| 项目 | 实测结果 |
| --- | --- |
| STAC 场景条目 | 210，保留同日不同产品版本 |
| 成功读取的场景 | 69，不是 69 个独立日 |
| 已处理日期 | 30 |
| 合同日聚合后的有效日 | **14** |
| 最长无有效观测间隔 | **177 天**，含窗口边界 |
| quality_flag | **limited** |
| 未完成读取 | **141**；网络 HTTP 503，不等于全云 |
| 晚季均值 | **空值**；9–11 月未读取，不等于 0 |

时序与特征在 `data/processed/satellite/`；实际观测图 `ndvi_timeseries.png` 已核看，不插值、不补造点。低质量场景保留于原表，特征仅使用合同选择的有效日。详细覆盖见 `coverage_report.json`。

**当前峰值和下降率只描述已覆盖窗口，不能解释为完整季节玉米峰值或收获时点，也不能用于声称 S/G 分类成功。**

## 故障、来源和续跑

初始 GDAL CA 信任问题已修复，始终保留 HTTPS 验证。首景 2021-04-03 实测 667 个田块中心像元全部有效，NDVI 中位数约 0.465742。之后 S3、Earth Search、GitHub API 出现相同 HTTP 503 上游连接失败；独立请求和 Planetary Computer 查询也未恢复，详见 `network_diagnostics.json`。

先通过 offline resume 验证记录的几何/窗口/集合与 A 一致，重建真实读取的 69 个场景；随后使用 `--reuse-inventory` 在线逐项重试全部剩余场景，139 个返回 HTTP 503、2 个栅格格式识别失败，因此最终保持 partial。缺失 141 个场景明确记入报告，没有为它们生成 NDVI、零有效比例或假读取时间。`scene_provenance.json` 保留原始读取时间、产品、URL、缩放、网格和像元计数。

`.cache/` 被 Git 忽略，只保存小型派生数值检查点，原子写入，按几何、A 请求、产品元数据和算法参数哈希定位，容量上限 256 MiB。最多 4 个窗口线程；没有整景/整州下载或原始影像落盘。

## 实际命令

依赖见 `src/satellite/requirements.txt`。以下假设 A 的只读 worktree 为兄弟目录 CornHub-a-inputs；A 合入后可去掉输入参数。

```sh
PYTHONPATH=src python -m satellite smoke \
  --fields ../CornHub-a-inputs/data/processed/core/fields.geojson \
  --sample ../CornHub-a-inputs/data/processed/core/smoke_sample.json \
  --notebook-reviewed
```

网络恢复后重复该命令，会复用成功检查点并重试缺失场景。若目录 API 本身不可用，在相同命令后加 `--reuse-inventory`，复用经过几何/窗口验证的既有真实检索清单，仍在线读取缺失波段；不冒充一次新查询。当前机器可在相同命令后添加 `--offline` 重建本批真实结果，不做网络请求；实测退出码 **2 / partial**。缓存不提交 Git，另一台机器需要重新读取公开影像。

## 批处理和实际检查

A 的全部 **44 个真实标签键**已校验，见 `batch_plan.json`，其余田块年未执行影像读取。`batch` 支持标签清单、`--dry-run`、`--limit` 和续跑，但以完整成功的真实 smoke 为启动门槛；当前 smoke 为 partial，实际 batch 检查返回 blocked，未越过门槛。

**24 tests passed**，覆盖合同特征、SCL 重采样、缩放、nodata 分母、缓存复用/失效/损坏重算、离线缺缓存不得读取或造数、真实标签清单校验和批处理成功门槛。合成数据仅在隔离测试中，未发布为卫星结果。

仍只修改 B 的四个目录，原件、合同、队友实现不变。下一步是恢复网络并补齐 141 个场景，完成完整单田验收后再开启全标签批处理。
