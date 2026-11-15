# 训练公式与符号

本页统一符号便于对照；数学等价改写不代表新增论文结论。所有公式都必须连同数据条件使用。

| 符号 | 含义 |
| --- | --- |
| x | 潜在干净信号/参考影像；现实中不一定可取得 |
| y | 带噪观测；随机加性噪声例子为 y=x+n |
| f_theta / R_theta | 参数为 theta 的重建网络/残差网络 |
| norm_F | 所有空间像元及波段元素的 Frobenius 范数 |
| mean | 对参与计算的空间、波段和批次元素取平均 |

## 1. DnCNN：残差监督

来源：Zhang et al.，IEEE TIP，2017，[作者预印本](https://arxiv.org/abs/1608.03981)，Eq. (1)。保留原文损失的 1/(2N) 归一化：

$$
\widehat{x}=y-R_\theta(y)
$$

$$
\mathcal L_{\mathrm{DnCNN}}(\theta)
=\frac{1}{2N}\sum_{i=1}^{N}
\left\|R_\theta(y_i)-(y_i-x_i)\right\|_F^2.
$$

N 是训练影像/patch 配对数。网络学习的是噪声残差。原文的重要应用包括高斯去噪；这不证明它能直接去除卫星厚云、条带或 SAR 乘性斑点。

## 2. Noise2Noise：带噪目标

来源：Lehtinen et al.，ICML，2018，[论文](https://proceedings.mlr.press/v80/lehtinen18a.html)，Eq. (6)。下面是该经验风险在平方误差下的期望形式，不是原文逐字记号：

$$
y_1=x+n_1,\qquad y_2=x+n_2,
$$

$$
\mathcal L_{\mathrm{N2N}}(\theta)
=\mathbb E\left[\|f_\theta(y_1)-y_2\|_2^2\right].
$$

在有限二阶矩、且满足例如 E[n2|x,y1]=0 的条件下，可展开为：

$$
\mathcal L_{\mathrm{N2N}}(\theta)
=\mathbb E\left[\|f_\theta(y_1)-x\|_2^2\right]
+\mathbb E\left[\|n_2\|_2^2\right].
$$

最后一项与参数无关，因此期望风险可以有相同最优解；不保证有限训练后逐像元恢复真值。两张图必须对应同一潜在地表状态。玉米田不同日期的收获、生长或灌溉变化不满足“同一个 x”，不能随便组成训练对。

## 3. Noise2Void：盲点/掩膜自监督

来源：Krull et al.，CVPR，2019，[论文](https://arxiv.org/abs/1811.10980)，Eq. (10)。把图像索引省略、取平方误差后，可写成：

$$
\mathcal L_{\mathrm{N2V}}(\theta)
=\frac{1}{|\Omega|}\sum_{i\in\Omega}
\left(f_\theta(\widetilde y)_i-y_i\right)^2.
$$

Omega 是被遮位置对应的标量像元/波段元素集合，单波段时即像元集合；输入中的这些值被替换，目标仍为原始带噪值。信号需能从上下文预测；噪声需满足给定信号下逐像元独立、适当零均值等假设。论文指出结构化噪声可能保留。不能把这一目标直接当作厚云重建目标。

## 4. DSen2-CR：Cloud-Adaptive Regularized Loss

来源：Meraner et al.，ISPRS JPRS，2020，[全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC7386944/)，Eq. (3)。下面以 mean 代替原文除以 N_tot 的 L1 范数，含义相同：

$$
\mathcal L_{\mathrm{CARL}}
=\operatorname{mean}\!\left|
M\odot(P-T)+(1-M)\odot(P-I)
\right|
+\lambda\operatorname{mean}|P-T|.
$$

- P：预测光学影像；T：无云参考；I：输入有云影像。
- M：云/云影为 1，晴空为 0，沿光学波段广播；odot 为逐元素乘法。
- 第一项对云区参照 T、晴空区参照 I；第二项是对参考的正则化。

两个 mean 都是在所有相应影像元素上计算，**不能擅自改为“云区平均＋晴空区平均”并说与原文完全等价**。论文实验选择 lambda=1；它不是 CornHub 已调优参数。原文输入为 Sentinel-2 L1C 和 Sentinel-1 SAR，不能不经适配套在 Landsat 地表反射率上。

## 5. SEN12MS-CR-TS：框架示意

来源：Ebel et al.，IEEE TGRS，2022，[论文 DOI](https://doi.org/10.1109/TGRS.2022.3146246)。论文提供多时相数据，并研究 3D CNN 及序列到序列方案。

$$
\widehat{x}_t
=f_\theta\!\left(\{y_\tau,s_\tau\}_{\tau\in\mathcal T}\right).
$$

这里 y 为光学输入、s 为 SAR、T 为可用日期集合。这只是本报告画出的通用输入/输出示意，**不是论文的编号公式，也不是完整网络结构或统一训练损失**。具体实现应按作者模型与代码分别核对。

## 6. CornHub 的评价定义（不是新增论文训练目标）

应在可比较、有效且空间配准的参考区域评价波段误差和指数误差。NDVI/NDMI 使用正确物理缩放后的反射率：

$$
\mathrm{NDVI}(z)=\frac{\rho_{\mathrm{NIR}}(z)-\rho_{\mathrm{Red}}(z)}{\rho_{\mathrm{NIR}}(z)+\rho_{\mathrm{Red}}(z)},
\qquad
\mathrm{NDMI}(z)=\frac{\rho_{\mathrm{NIR}}(z)-\rho_{\mathrm{SWIR1}}(z)}{\rho_{\mathrm{NIR}}(z)+\rho_{\mathrm{SWIR1}}(z)}.
$$

分母过小、nodata 或无效反射率排除，不默认为 0。波段对应关系、分辨率和缩放取自实际传感器/产品元数据。指数的 MAE 是有效比较区域中绝对差的平均；这不是田块分类准确率，也不是直接的含水率误差。负 NDMI 本身不能被认定为噪声。
