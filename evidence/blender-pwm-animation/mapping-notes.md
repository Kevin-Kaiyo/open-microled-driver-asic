# 六MOS电路—r5真实版图映射核对

已逐项对照 contract、原理图网表、版图生成器和实际GDS；契约/网表/生成器hash匹配r5证据快照。24个器件引脚均验证 Via1 的 M1/M2 落点、Via2 的 M2/M3 落点、M2 中心线、M3 到真实端口连续性。选定的24个Contact与对应引脚位于同一M1连通多边形中。

像素六管为 XP_REF / XP_OUT / XP_PASS / XP_CLAMP / XP_INV_N / XP_INV_P。不能使用未出现的 M_SW1/M_SW2 名字替代。MREF=MOUT=20/4 µm，MPASS=MCLAMP=MINV_N=2/1 µm，MINV_P=4/1 µm。

正常条件 FAULT=0、PERMIT=1、参考稳定：PWM_DRIVE高时MPASS传递BIAS到GATE，MOUT导通，MINV_N拉低PWM_B从而关MCLAMP。PWM_DRIVE低时MPASS关断，MINV_P拉高PWM_B，MCLAMP把GATE拉低，MOUT关断；MREF仍维持参考电流。反相器及栅极路径只能在切换时画短暂充放电，稳定时应停止粒子；“导通”器件不等于始终有大电流。

mapping.paths 的坐标是未夸大的名义Z，渲染时再统一垂直夸张/层偏移。电流正方向为 LED_A→片外LED→LED_K→MOUT→VSS；其中片外LED与引线须清晰标注“片外示意”。paths.led_high 从真实 LED_K M3 端口开始。MOUT沟道线与选择单个接触孔是解释方向的简化，不能宣称为实际载流子轨迹或电流密度仿真。电子运动方向与常规电流相反，本动画只画常规电流。

需要特别区分接触孔 Contact（器件/Poly→M1）、Via1（M1↔M2）和Via2（M2↔M3）。只有投影交叉、没有via的M2/M3导线彼此不连接。层分离仅改变显示，原器件之间的电气拓扑不变。

最终外接补偿为30pF而非contract内历史3pF；放电电阻为10Mohm。动画像素特写无需将外接元件误画进芯片。
