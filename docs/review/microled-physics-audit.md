# MicroLED 物理模型与研究前提独立检阅

检阅日期：2026-10-03。范围：`analog/models/microled.spice`、`scripts/run_phase1.py` 的 LED 参数计算、Phase 1 电流数据、现有设计与教学说明。另对原始 pre-layout 六 MOS cell 做 GMIN 对照；本篇不替代 full-PDK / RC / MOS 可靠性审查。

**判断：当前模型可以继续用于教学和驱动机制验证，但尚不能决定真实 MicroLED 的电流、供电、热设计、速度或光学性能。** 单点校准的计算正确；物理参数多数仍是有意设置的 synthetic 假设。下一步优先把一种有尺寸、材料、温度和测量出处的 LED 负载定义完整，再用它审查单像素边界。暂不以扩到 4×4 代替这一前提验证。

本次独立结果：[36 次成功 SPICE 实验与手算数据](../../evidence/review/led-independent-checks.json)、[复核脚本](../../scripts/review/led_audit.py)。原始 deck / log 在本地 `build/audit_led/`；未修改基线模型、RTL、PDK 或既有 PDF/PPT。

## 1. 检阅结论与优先级

| 优先级 | 发现 | 对研究方向的影响 |
|---|---|---|
| 必须先限定 | 没有颜色/材料、发光区几何、面积定义、目标 current density、真实 I–V / C–V / 光学数据 | `100 µA / 2.8 V / 2 pF` 只能是实验起点，不能称为真实像素选型完成 |
| 必须修正理解 | 原报告约 3.61 pA 的关断电流强烈依赖 GMIN | 不能用该数值推导实物 black level、contrast ratio 或 leakage 规格 |
| 必须先限定 | 当前温度模型在 100 µA 给出 **正** Vf 温度系数 | 温度 sweep 只说明 synthetic 参数如何被执行，未验证真实样品的温度规律 |
| 补齐参数表 | `FC=0.5`、`XTI=3`、`TLEV=0`、`TLEVC=0` 目前来自 simulator 默认值 | 动态电容与温度行为不只由已列出的显式参数决定；应记录默认参数和 ngspice 版本 |
| 计算通过 | 在 27 °C / 100 µA，2.4、2.8、3.2 V 三个目标均在约 1.1 µV 内复现 | 证明代数和模型执行在指定锚点一致；不证明模型拟合了真实 I–V |
| 解释需要具体化 | `CJO=2 pF` 时，100 µA 工作点的内部小信号结电容实际约 **4.828 pF** | 不能用恒定 2 pF 或 `TT=1 ns` 推算发光速度；需偏置相关的阻抗和光学响应 |

现有 `docs/design.md`、`docs/research/driver-evidence.md` 和教学 notes 已明确 synthetic、单点校准、非光学测量等边界，方向上没有冒充真实器件数据。本次新增的风险在于：即使标注 synthetic，读者仍可能把其数值当成后续硬件参数依据，因此需要在研究入口列出上述限制。

## 2. 参数逐项检查

| 参数 | 当前设置与计算含义 | 物理证据状态 |
|---|---|---|
| `N=3` | 有效 emission / ideality 系数；决定指数 I–V 的斜率 | 为教育模型及数值范围选定，未从实测拟合；不能据此认定具体复合机制 |
| `IS` | 从 27 °C / 100 µA / target Vf 反算 | 拟合一个数学锚点；不等于实物可测 reverse saturation/leakage |
| `RS=50 Ω` | 100 µA 时压降 5 mV；1 mA 时压降 50 mV | 未分离接触、半导体、电极、封装与连接线；不能据此定真实串联电阻 |
| `CJO=2 pF` | SPICE 零偏底部结电容参数 | 未绑定发光面积/周长/接触/封装；没有 C–V 或阻抗拟合 |
| `VJ=2.5 V, M=0.33` | depletion-charge 曲线参数 | 非发光阈值；不能把 `VJ` 当成 LED 固定 Vf |
| `FC=0.5`，默认 | 在内部结压 `FC×VJ=1.25 V` 后使用电容的延拓表达式 | 对当前约 2.795 V 的内部结压直接相关，原参数表应显式披露 |
| `TT=1 ns` | charge-storage / diffusion-capacitance 参数 | 非实测光学 rise/fall time，非单一可识别的 carrier lifetime |
| `EG=2.6 eV` | diode 温度方程的 activation-energy 参数 | 未拟合温度响应；不能用 `1240/EG` 宣布发光波长或材料 |
| `TNOM=27 °C` | 参数参考温度 | 与校准温度一致，单位与 Kelvin 换算正确 |
| `XTI=3, TLEV=0, TLEVC=0`，默认 | 饱和电流及电容的温度模型选择 | 没有真实样品支持；默认值不是材料表征结果 |
| 几何 / `AREA` | 没有器件几何；SPICE 默认缩放因子 1 | 因子 1 不代表 1 µm² 或 1 cm²；不能推出 current density |
| reverse / thermal / optical | 未显式拟合 breakdown、reverse leakage、自热、EQE、光谱、老化 | 当前仿真不能给这些属性作可靠性或性能保证 |

SPICE 参数定义采用 [ngspice 47 手册 §7.2](https://ngspice.sourceforge.io/docs/ngspice-47-manual.pdf)。默认参数和 `IS` 下限可在 [ngspice-47 `diosetup.c`](https://github.com/imr/ngspice/blob/ngspice-47/src/spicelib/devices/dio/diosetup.c) 的 `DIOsetup()` 核对。这里是对已运行模型的解释，不是实物器件参数表。

## 3. 独立计算：锚点正确，但不是唯一物理模型

从基本常数重新计算，`VT=(k/q)T=25.864925786 mV`，其中 `T=300.15 K`。使用

`IS = I0 / expm1[(Vf0 − I0·RS)/(N·VT)]`

得到如下结果。独立 deck 不调用 runner 的 `led_is()`，采用 ngspice 47、27 °C、100 µA。

| target Vf | 独立 IS / A | 独立 SPICE Vf / V | 偏差 / µV |
|---|---:|---:|---:|
| 2.4 V | 3.9381533843e−18 | 2.399999185 | −0.815 |
| 2.8 V | 2.2725351142e−20 | 2.799999049 | −0.951 |
| 3.2 V | 1.3113800660e−22 | 3.199998913 | −1.087 |

原 0.1 mV 校准容差下三项通过。约 µV 量级的差异不影响此结论。

**一个点无法确定斜率。** 固定 `RS=50 Ω`，让 `N=2.2 / 3 / 4` 各自重新求 IS，三者都精确经过 100 µA / 2.8 V，却有如下不同 I–V。下表是独立公式计算，完整 SPICE 对照见 JSON；这些 N 仅用于数学可识别性对照，不是实际样品范围。

| 电流 | N=2.2 / V | N=3 / V | N=4 / V |
|---|---:|---:|---:|
| 1 µA | 2.53300 | 2.43771 | 2.31860 |
| 10 µA | 2.66448 | 2.61683 | 2.55728 |
| 100 µA | 2.80000 | 2.80000 | 2.80000 |
| 1 mA | 2.97602 | 3.02367 | 3.08322 |

因此，保持锚点正确仍可能使低电流 Vf、开关充放电轨迹和低供电 headroom 改变。`N=3, RS=50 Ω` 在锚点的小信号差分电阻为 `N·VT/I+RS≈825.95 Ω`，不能把 50 Ω 当成该工作点的总动态电阻。

已独立复现旧数值问题：`N=2.2, target Vf=3.2 V` 需要 `IS≈4.1218e−29 A`。默认 EPSMIN 下实际得到 3.149566 V；仅在隔离的对照中设 `epsmin=1e−50`，则恢复到 3.199999 V。**这说明数值下限要单独验证；不能为了收敛而把真实拟合的 N 改成 3。** 当前合成模型可保留 N=3，未来拟合实测时必须重新审查 simulator 表达范围和收敛。此对照不等于建议全局降低 EPSMIN。

## 4. 关断电流：GMIN 影响是实测外推的阻断项

原 pre-layout 六 MOS cell，typical / 27 °C / VLED=5 V / Vlogic=3.3 V / IREF=100 µA / duty=0，做独立 OP。

| GMIN / S | LED branch current | LED cathode / V |
|---|---:|---:|
| 1e−9 | 3.086057 nA | 3.086023 |
| 1e−12 | 3.609294 pA | 3.573769 |
| 1e−15 | 40.0603 fA | 3.886211 |
| 1e−18 | 36.1879 fA | 3.891910 |

使用原容差及更紧的 `reltol=1e−7, abstol=1e−16 A, vntol=1e−9 V` 分别复核，表中结果一致。GMIN 改变后，原本“3.61 pA”变了约两个数量级；这已足以排除将其当作稳定的真实漏电规格。最低值也只属于本 PDK 模型/solver，不能升级成 36 fA 实物预测。

GMIN 是计算辅助导通。ngspice [diode 加载源码 `dioload.c`](https://github.com/imr/ngspice/blob/ngspice-47/src/spicelib/devices/dio/dioload.c) 中可直接核对其进入电流和电导的方式。整个 driver 的变化还涉及 MOS 结模型，不能把全部差异归到 LED 单一元件。

审查过程中，过严的 `reltol=1e−10, abstol=1e−20 A, vntol=1e−12 V` 在 GMIN=1e−9 下使 OP 失败并输出 NaN；ngspice 仍返回 exit 0。复现失败日志保留于 `build/audit_led/gmin_strict_failure/ngspice.log`。成功结果来自上面的可收敛容差，复核程序还检查输出存在和有限值；没有把干净退出码当成成功证据。

## 5. 电容和温度：当前模型实际做了什么

在孤立 LED 上注入 100 µA DC 与 1 A AC 的小信号测试源，于 1 kHz 读取复阻抗。AC 1 A 是线性化求解的归一化系数，不是施加了 1 A 的物理电流摆幅。去掉模型已知的 50 Ω 后，`C = Im[1/(Z−RS)]/(2πf)` 给出：

| 只修改的合成参数 | 内部结电容 / pF |
|---|---:|
| CJO=2 pF，TT=0 | 3.539447 |
| CJO=0，TT=1 ns | 1.288747 |
| CJO=2 pF，TT=1 ns（baseline） | 4.828194 |
| CJO=2 pF，TT=10 ns | 16.426917 |
| CJO=20 pF，TT=1 ns | 36.683220 |

在该偏压下，depletion 部分采用 FC 后的延拓公式；diffusion 部分近似 `TT×gd`。结果与 ngspice charge 模型一致。这是数学模型的小信号验证，不能用来推断 LED 真实 capacitance、带宽或 package parasitics。

同样保持 100 µA，独立温度点得到：0 °C → 2.789114 V，27 °C → 2.799999 V，85 °C → 2.821322 V。模型在 27 °C 附近的解析斜率约 `+0.3912 mV/°C`，并未被测量验证。`EG=2.6` 加上默认 XTI 会产生这个结果；不能只因温度 sweep 顺利结束，就把其方向当成真实 MicroLED 的温度规律。温度实现可查 [ngspice-47 `diotemp.c`](https://github.com/imr/ngspice/blob/ngspice-47/src/spicelib/devices/dio/diotemp.c)。

## 6. branch current、光学输出和低 duty

LED 端口电流包含 conduction 与 charge-storage 的时间变化项。PWM 边沿出现短时负 branch current，可以来自电荷回流；不能翻译为“负亮度”。同样，正尖峰不代表等比例瞬时光功率。应记录 LED 电压、内部电荷或电容电流、source current 的符号约定，并在最短脉冲下验证 settle。

在严格周期稳态、整周期积分且结电荷首尾相同时，电容项的净积分会抵消；但有限启动窗口、长时间常数和不完整周期会破坏这个前提。原 runner 的整帧积分是必要措施，还需要逐帧稳定性和 CJO/TT/输入 slew 敏感度。

即使平均 conduction current 已知，光功率还依赖 EQE、光谱、温度和非辐射通路。公开测量论文对这个区分很明确：Wolter 等在蓝光 InGaN/GaN 0.65–20 µm 器件上同时测 I–V 与 EL，且其部分 EQE 曲线只有相对单位。该研究的尺寸、工艺和出光收集条件不能被省略后移植为本项目绝对亮度指标。[原论文，§2、§3 与 Figure 5](https://pmc.ncbi.nlm.nih.gov/articles/PMC8064358/)

## 7. 为什么必须先定义面积与使用场景

仅用 `J=I/A` 做独立换算：同样 100 µA，若发光区是以下正方形，会对应完全不同的 on-state current density。这些尺寸只是单位敏感性示例，没有选定实际器件。

| 正方形边长 | 5 µm | 10 µm | 20 µm | 50 µm | 100 µm |
|---|---:|---:|---:|---:|---:|
| J / A·cm⁻² | 400 | 100 | 25 | 4 | 1 |

“100 µA 很小”不是器件工作点判断。发光面积、mesa 面积、接触面积与 pitch 必须分别记录；有电流拥挤时，几何平均 J 也不等于局部峰值。先定义目标用途为 PWM 调光教学还是高速光通信；当前 1 MHz 计数时钟、256 slots、最短 1 µs 脉冲，并不是从真实 LED 带宽要求推导出的最优值。

## 8. 下一阶段可执行的准入条件

1. **建立一张真实负载 model card。** 选定一种颜色/材料、明确发光区面积与几何、样品/来源 ID、封装/连接方式、温度范围、允许峰值/平均电流和目标用途。公开数据可以先承担电学拟合，但必须保留 source license、器件编号、测量条件与误差。暂不把某商业器件悄悄定为默认。
2. **先拟合 I–V，再确认 headroom。** 数据要覆盖目标峰值电流附近以及最短脉冲会经过的低电流区域；同时记录温度。用部分数据拟合 `N/IS/RS`，留出电流点或温度做独立验证，报告残差与不确定度。若单二极管形式不能同时解释低电流和高电流，应改变模型形式或缩小适用范围，不以修改 N 掩盖数值问题。
3. **补动态与关断证据。** 在多个 DC bias 下测/取得复阻抗或 C–V；把接线与 pad 的寄生和结电容区分开。以脉冲电流及光学响应分辨电气 RC 和复合过程。漏电测试需给出仪器底噪、偏压、温度、dark 条件；仿真补 GMIN/容差/启动/周期性检验。
4. **先写验收标准，再选升级电路。** 规定允许的电流误差、供电范围、低灰阶误差、稳态/settling、功耗和目标样品条件；按预算分配 reference、mirror、headroom、寄生和负载误差。依据失败原因决定是否需要 reference generator、cascode、feedback、calibration 等，不能仅因结构更复杂就升级。
5. **在真实负载边界上关闭单像素问题后再扩阵列。** 4×4 才引入共享 bias、mismatch、IR drop、互扰、数据接口、时序与热问题。若只有公开 I–V 而没有 C–V/光学资料，可以推进电气静态研究，但动态和光学结论继续保留未验证标签。

可立即尝试的数据入口：Stefan Wolter 等，*Size-Dependent Electroluminescence and Current-Voltage Measurements of Blue InGaN/GaN µLEDs down to the Submicron Scale*，Nanomaterials 11(4):836，2021，DOI [10.3390/nano11040836](https://doi.org/10.3390/nano11040836)。论文 Data Availability 指向 [TU Braunschweig dataset DOI 10.24355/dbbs.084-202103240746-0](https://doi.org/10.24355/dbbs.084-202103240746-0)。本次核实论文声明和方法；数据站点返回 Security Check，尚未取得或拟合原始数据，dataset 自身授权与可用列仍待核实。

## 9. 证据目录与复现边界

| ID | 来源 / 定位 | 类型与条件 | 支持 / 不支持 |
|---|---|---|---|
| LED-AUDIT-01 | `led-independent-checks.json`，calibration / same_anchor_iv / epsmin | 独立手算与 ngspice 47 DC，合成参数 | 支持代数、数值边界及非唯一性；不支持真实 I–V |
| LED-AUDIT-02 | 同文件 gmin_off | 原模型 subset / six-MOS / OP / typical / 27 °C / 5 V | 支持 solver 对 off 的影响；不支持硅片漏电 |
| LED-AUDIT-03 | 同文件 capacitance / temperature | 单 LED、100 µA；AC 1 kHz 或 0/27/85 °C | 支持当前模型执行；不支持真实速度/温漂 |
| LED-SRC-01 | ngspice 47 手册 §7.2；tag `ngspice-47` 的 `diosetup.c`、`dioload.c`、`diotemp.c` | 官方 simulator 实现/文档 | 支持模型定义；不是 LED 测量 |
| LED-SRC-02 | Wolter 等 2021，§2–3、Figure 5、Data Availability | 蓝光 InGaN/GaN 原始实验论文；文章 CC BY 4.0 | 支持几何、EL/IV 和相对/绝对单位必须记录；没有给本项目的参数赋值 |

`scripts/review/led_audit.py` 可从任意目录运行，依赖已安装 ngspice 47 和已下载 Phase 1 PDK subset。程序自动创建独立 run 目录，在运行前核对 PDK 文件 hashes，并复制冻结 LED、driver、PDK、脚本与 lock 输入；本次也从 `/tmp` 完整重跑验证了工作目录独立性。36 个成功实验：3 calibration + 15 N/I 对照 + 3 temperature + 2 EPSMIN 对照 + 4 GMIN driver OP + 9 AC。原始数据未当成实测数据；公开报告只复述必要结论，未复制论文整图或表格。
