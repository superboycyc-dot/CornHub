# 交给 NVIDIA/Brev 管理员 AI 的执行提示词

请实际配置并启动 CornHub 的 NDMI 云端并行任务，完成验证后再汇报，不只提供教程。

项目仓库：https://github.com/superboycyc-dot/CornHub
工作分支：`work/d-analysis`
已知待核实目标：Brev 组织 `supchen-f3631d-lwff`、实例 `cornhub-model`。
目标：计算马里兰州 2021–2025 年、每年各月的年度 CDL Corn 区域 NDMI。允许使用现有实例上本任务获分配的全部 CPU/GPU 资源，优先实际吞吐速度；不自动购买新实例或扩容计费资源。

## 权限与目录

先读仓库规则与 `docs/team-contract.md`。只修改 `src/analysis`、`notebooks/d_analysis`、`data/processed/analysis`、`reports/d_analysis` 及其目录内依赖，走现有 PR #7，不推 main、不强推。NVIDIA 上使用独立 venv 和持久缓存，不改模型、前端或共享根配置，不覆盖现有 Ollama 服务和其他用户任务；资源冲突时由管理员协调本任务可用 GPU。

使用操作者本人的 Brev/GitHub 权限。需要登录时由本人完成，不读取、复制或发送别人的凭据，不把私钥、个人 token 或临时签名贴回聊天或写进 Git。给请求者授权 SSH 即可，不提供管理员私钥。

## 实际执行顺序

1. **连接现有实例。** 若已经在该 NVIDIA 终端，无需另装客户端。否则安装官方 Brev CLI，运行 `brev login`，检查本机 `brev org --help` 后选择上述组织，执行 `brev refresh`、`brev ls`，再 `brev exec cornhub-model "nvidia-smi"` 验证。组织/实例不存在时报告真实列表，不自行新建付费实例。
2. **检查硬件与存储。** 记录可见 GPU 型号/数量/空闲显存、驱动、CPU 配额、可用内存、磁盘空间。确认实际持久挂载点，优先提供至少 8 CPU、16 GiB RAM、20 GiB 空闲持久盘；不足时启动器会下调并发。不要仅凭 `nvidia-smi` 顶部 CUDA 字样认定已安装对应 Toolkit。
3. **同步代码。** 在干净隔离工作区获取 `work/d-analysis` 最新代码；如已有工作树包含其他人的修改，使用独立 worktree，不 reset/clean 覆盖修改。保留现有四个已核实完整月份；2021-06 的历史结果可能是带网络错误的 partial，不当作完成。
本地已有年度掩膜和无错误月份的检查点可复用。获得请求者 SSH 连接后，可用 rsync/scp 从 `/tmp/cornhub_md_ndmi/` 同步到远程持久 cache，排除 `ndmi_scene_*` 临时影像；先确认本地任务已停止并只复制完整检查点。缓存不是 Git 数据，不上传仓库；其中失败月份必须按 retry-incomplete 规则重算。

4. **确认网络。** 必须能 DNS/TLS 访问 `pdi.scinet.usda.gov`、`tigerweb.geo.census.gov`、`planetarycomputer.microsoft.com`，以及 STAC 实际返回的 Landsat Azure Blob 主机（已见 `landsateuwest.blob.core.windows.net`）；能读取 TIFF 的 HTTP Range。还需 Python 包下载及私有 GitHub 仓库读写权限。配置现有代理/出口后运行提供的真实网络探针，失败时先修网络，不启动 60 月批次反复空等。
5. **建立独立环境。** 选定持久路径 `NDMI_WORK_ROOT`，Python 3.12。按真实驱动/设备兼容性选 CUDA 12 或 13 的 CuPy 依赖。不要同时安装两种 CuPy 包，不替换系统 NVIDIA 驱动；默认 CPU 路径可独立工作。

```sh
# 从仓库根目录运行；路径必须替换为已确认的持久挂载目录。
export NDMI_WORK_ROOT="/已确认的持久目录/cornhub-ndmi-runtime"
export NDMI_PYTHON=python3.12
# 选 12 或 13；暂不装 GPU 时填 none。
export NDMI_CUDA_MAJOR=12
bash src/analysis/ndmi/remote/bootstrap.sh
```

bootstrap 执行真实源网络探针、独立 venv 安装、数值/资源/GPU 对照测试、明确标为合成输入的性能测试，并保存依赖版本。任一步失败先修复，不宣称配置成功。

6. **选择实际更快的后端。** 查看 `$NDMI_WORK_ROOT/backend_benchmark.json`。GPU 测试必须在每张可见 GPU 上通过，NDMI 误差 ≤1e-7、有效像元掩膜完全一致。性能比较包含 CPU↔GPU 传输、预热后重复计时，不以异步 kernel 发射耗时冒充完成时间。合成基准不是卫星结果；条件允许时用真实同网格 uint16 四波段窗口另存 NPZ，再运行：

```sh
"$NDMI_WORK_ROOT/venv/bin/python" src/analysis/ndmi/remote/benchmark.py \
  --input-npz /真实窗口/raw_tile.npz \
  --output "$NDMI_WORK_ROOT/real_tile_benchmark.json"
```

NPZ 键为 `nir08,swir16,qa_pixel,qa_radsat`。GPU 显著更快且一致时选 `gpu`；否则选 CPU 并发，报告原因，不为了占满显卡而降低吞吐。选择 GPU 时不屏蔽本任务获分配的可用卡，启动器按可见 GPU 数分配进程，默认最多两进程/卡，并受主机内存、磁盘和 CPU 配额约束。小于 GPU 数量的待运行月数无法同时利用全部卡，单月验收时无需伪造 GPU 利用率。

7. **先验收一个真实月份。** 优先 2021 年 6 月，在独立输出目录实跑，记录墙钟耗时、状态、覆盖率、候选/贡献/异常场景数和真实像元示例。不要复用完整月份 JSON 冒充新计算。下面以 CPU 为例；通过 GPU 基准后可将 backend 换成 gpu。

```sh
"$NDMI_WORK_ROOT/venv/bin/python" -u src/analysis/ndmi/remote/launch.py \
  --cache "$NDMI_WORK_ROOT/cache" --backend cpu --workers auto \
  --year 2021 --month 6 \
  --output data/processed/analysis/ndmi/remote_smoke/months \
  --report reports/d_analysis/ndmi/remote/smoke
```

8. **后台运行全期。** 单月网络与真实输出通过后，在远程 `tmux` 会话内执行下列命令并 detach，或使用等效的远程持久作业管理器。不要让任务依赖本地 ChatGPT/SSH 会话存活。无需对外开放新端口。

```sh
"$NDMI_WORK_ROOT/venv/bin/python" -u src/analysis/ndmi/remote/launch.py \
  --cache "$NDMI_WORK_ROOT/cache" --backend cpu --workers auto \
  --report reports/d_analysis/ndmi/remote/batch
```

GPU 基准通过且实际更快则换成 `--backend gpu`。完整年份范围默认 2021–2025，每月一个任务；不同月不混合。失败月份自动归档旧 partial 并从头重算，正常中断的无错误检查点可续算。月份连续 3 个场景错误会提前停止该月并明确标记 partial；整批不应靠无限重试刷请求。遵循服务 Retry-After，不靠增加 GPU/并发冲击限流。

9. **检查和交付。** 监控日志及真实硬件使用情况；根据吞吐、429、内存及磁盘调整 workers，不假定越多越快。只有完整无错误的 60 月结果才运行严格导出；部分完成必须显式使用 allow-incomplete，保留 pending/partial：

```sh
"$NDMI_WORK_ROOT/venv/bin/python" src/analysis/ndmi/export_results.py --cache "$NDMI_WORK_ROOT/cache"
# 未完整时使用：
# "$NDMI_WORK_ROOT/venv/bin/python" src/analysis/ndmi/export_results.py --cache "$NDMI_WORK_ROOT/cache" --allow-incomplete
```

将结果 CSV、月份 JSON、计算过程、来源和检查证据提交到原分支/PR。原始影像、venv、缓存、私钥和签名不进 Git。上传前检查机器专属路径和凭据；不要用修改 BARC 模型/前端来掩盖缺数据。

## 必须回报给请求者的内容

- 实际组织/实例名称，以及请求者账号已获 SSH 权限的确认。
- CPU/RAM/磁盘和 GPU/驱动清单；本任务可用的 GPU 数及显存情况。
- 实际持久缓存目录、代码路径、分支和 commit；不要回传密码/私钥/token。
- `network_probe.json` 四项结果，尤其 Azure TIFF Range 是否成功。
- CPU/GPU 数值对照、含传输的耗时、选择的 backend/workers；未测试项明确标注。
- 远程 tmux 会话名或作业 ID、日志路径、恢复/查看命令。
- 首个真实月份的实际墙钟时间、NDMI、覆盖率及读取错误数；全期已完成/partial/pending 数。
- 结果文件与 PR 链接；未打通时提供明确阻塞，不能只说“CUDA 已装好”。

## 官方参考

- Brev 安装/本人登录：https://docs.nvidia.com/brev/latest/cli/getting-started
- Brev exec/SSH/tmux：https://docs.nvidia.com/brev/latest/cli/connectivity
- CuPy CUDA 12/13 安装：https://docs.cupy.dev/en/stable/install.html
- CuPy 同步计时、预热及性能注意事项：https://docs.cupy.dev/en/stable/user_guide/performance.html
