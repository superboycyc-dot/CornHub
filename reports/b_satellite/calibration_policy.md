# PC 原始 DN 的校准依据

本次44个田块年批处理使用同一提供方、同一产品集合和相同处理规则，不能将未校正的PB04+与早期数据直接拼接。

- ESA Sentinel-2 L2A质量报告明确说明，PB04开始引入BOA_ADD_OFFSET，并且所有光谱波段为-1000 DN；反射率为 `(DN + BOA_ADD_OFFSET) / QUANTIFICATION_VALUE`。[ESA产品说明](https://sentiwiki.copernicus.eu/web/s2-products)；[ESA L2A DQR](https://sentiwiki.copernicus.eu/__attachments/1692737/OMPC.CS.DQR.002.03-2026%20-%20i96r0%20-%20S2%20MSI%20L2A%20-%20Data%20Quality%20Report.pdf)。
- [Microsoft Planetary Computer官方讨论与数据集示例](https://github.com/microsoft/PlanetaryComputer/issues/134)确认PC原始COG未统一消除该偏移。读取API时使用unscale=false，避免隐含重复换算。
- 对每景实际 `s2:processing_baseline`：PB<04使用0 DN偏移，PB04–05.13使用-1000 DN，缺失或未知版本直接报错。不使用拍摄日期来猜测；旧年份也可能是PB04重处理产品。
- 先将DN转换为float64、掩膜原始0 nodata，再加偏移。B04和B08共同的量化除数10000在NDVI比值中抵消；不将DN称为物理反射率，不对负值做uint16减法或伪造零植被。
- 这是**官方规范和产品基线驱动**的校准，不是声称已读取每份无法访问的product-metadata.xml。前一版保守跳过的2021-11-19 PB04产品现在可按同一明确规范处理。

每景记录实际基线、applied_dn_offset、请求参数、网格、源URL和引用。测试覆盖PB02/03/04/05、未知版本拒绝和偏移后NDVI比值。
