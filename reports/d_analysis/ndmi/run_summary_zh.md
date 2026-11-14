# 实际运行结果：马里兰州玉米区域 NDMI

计算完成 1/60 月；待计算 59 月；有场景错误 0 月。

全部数值是有效像元月度拼接的空间统计，NDMI 无单位。computed 不代表覆盖率 100%。

| 年份 | CDL Corn 网格面积 ha | 12个月有效覆盖率范围 |
| --- | ---: | ---: |
| 2021 | 207096.30 | 9.12%–9.12% |

| 年月 | NDMI 均值 | 中位数 | p10 | p90 | 有效覆盖率 | 状态 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2021-01 | null | null | null | null | null | pending |
| 2021-02 | 0.08257 | 0.07762 | -0.02727 | 0.19418 | 9.12% | computed |
| 2021-03 | null | null | null | null | null | pending |
| 2021-04 | null | null | null | null | null | pending |
| 2021-05 | null | null | null | null | null | pending |
| 2021-06 | null | null | null | null | null | pending |
| 2021-07 | null | null | null | null | null | pending |
| 2021-08 | null | null | null | null | null | pending |
| 2021-09 | null | null | null | null | null | pending |
| 2021-10 | null | null | null | null | null | pending |
| 2021-11 | null | null | null | null | null | pending |
| 2021-12 | null | null | null | null | null | pending |
| 2022-01 | null | null | null | null | null | pending |
| 2022-02 | null | null | null | null | null | pending |
| 2022-03 | null | null | null | null | null | pending |
| 2022-04 | null | null | null | null | null | pending |
| 2022-05 | null | null | null | null | null | pending |
| 2022-06 | null | null | null | null | null | pending |
| 2022-07 | null | null | null | null | null | pending |
| 2022-08 | null | null | null | null | null | pending |
| 2022-09 | null | null | null | null | null | pending |
| 2022-10 | null | null | null | null | null | pending |
| 2022-11 | null | null | null | null | null | pending |
| 2022-12 | null | null | null | null | null | pending |
| 2023-01 | null | null | null | null | null | pending |
| 2023-02 | null | null | null | null | null | pending |
| 2023-03 | null | null | null | null | null | pending |
| 2023-04 | null | null | null | null | null | pending |
| 2023-05 | null | null | null | null | null | pending |
| 2023-06 | null | null | null | null | null | pending |
| 2023-07 | null | null | null | null | null | pending |
| 2023-08 | null | null | null | null | null | pending |
| 2023-09 | null | null | null | null | null | pending |
| 2023-10 | null | null | null | null | null | pending |
| 2023-11 | null | null | null | null | null | pending |
| 2023-12 | null | null | null | null | null | pending |
| 2024-01 | null | null | null | null | null | pending |
| 2024-02 | null | null | null | null | null | pending |
| 2024-03 | null | null | null | null | null | pending |
| 2024-04 | null | null | null | null | null | pending |
| 2024-05 | null | null | null | null | null | pending |
| 2024-06 | null | null | null | null | null | pending |
| 2024-07 | null | null | null | null | null | pending |
| 2024-08 | null | null | null | null | null | pending |
| 2024-09 | null | null | null | null | null | pending |
| 2024-10 | null | null | null | null | null | pending |
| 2024-11 | null | null | null | null | null | pending |
| 2024-12 | null | null | null | null | null | pending |
| 2025-01 | null | null | null | null | null | pending |
| 2025-02 | null | null | null | null | null | pending |
| 2025-03 | null | null | null | null | null | pending |
| 2025-04 | null | null | null | null | null | pending |
| 2025-05 | null | null | null | null | null | pending |
| 2025-06 | null | null | null | null | null | pending |
| 2025-07 | null | null | null | null | null | pending |
| 2025-08 | null | null | null | null | null | pending |
| 2025-09 | null | null | null | null | null | pending |
| 2025-10 | null | null | null | null | null | pending |
| 2025-11 | null | null | null | null | null | pending |
| 2025-12 | null | null | null | null | null | pending |

## 一个真实像元的计算过程

产品：`LC08_L2SP_017032_20210204_02_T1`；网格位置 row=1964、col=301。

```text
DN_B5=21175, DN_B6=11238
rho_B5=21175×0.0000275−0.2=0.38231250
rho_B6=11238×0.0000275−0.2=0.10904500
NDMI=(0.38231250−0.10904500)/(0.38231250+0.10904500)=0.55614799
QA_PIXEL=21824, QA_RADSAT=1
```

其余真实示例及来源坐标见 pixel_calculation_examples.csv。

## 检查与限制

5 项数值/QA 检查通过；导出程序核查唯一键、面积与覆盖率、场景贡献数、月份、指数范围及真实 DN 示例的公式。逐文件哈希和实际检查见 validation.json。

不能只凭曲线把变化归因于干旱或收获：年度玉米区域、源分辨率、月内观测日期、云雪缺测及物候都可能变化。冬季是年度玉米区域的地表状态，非冬季活玉米含水率。

本次没有补造 2024/2025 的 BARC 标签或预测，原有分类数据阻塞仍然独立存在。详细步骤、命令和来源见 README.md 及 sources.csv。
