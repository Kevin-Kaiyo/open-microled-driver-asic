# Open MicroLED Driver ASIC

单像素研究报告 v0.2 · 2026-10-04 · 开源教学项目

## 01 从整体框架开始

当前目标是把**一个像素**的数字控制、晶体管驱动和物理实现逐项做实，再决定阵列怎么扩展。峰值电流目标 100 µA；LED 电源 5 V；数字及模拟控制电源 3.3 V；1 MHz clock 产生 256-slot PWM。

系统路径是：**duty / enable → registered PWM → gate-pass / clamp → NMOS current mirror → LED electrical load**。外部 IREF 决定导通电流，PWM 决定导通时间。两者一起决定每帧的平均电流。

这轮检阅后的实质改进有三项：引入有出处的真实 LED 静态曲线；依据同种子统计结果，把镜像管从 10/2 改为 20/4 µm 并重做实际版图；把 PWM 输出注册，并推进标准单元物理流程。

| 证据层级 | 当前成果与边界 |
| --- | --- |
| LED 数据 | 一条公开数值 I-V 曲线；温度、动态、光学模型仍未知 |
| Digital logic | Registered PWM；exhaustive RTL 与 mapped gate simulation |
| Analog physical | 真实六 MOS layout、严格 LVS、DRC、GDS 与 7/7-net RC extraction |
| 电路研究 | 真实静态负载耦合；reference 误差预算；固定 corners 与有限 MC 分开验证 |
| Digital physical | CTS、routing、STA、GDS/LEF；第 07 页列出最终实际结果 |
| 芯片与实物 | 数字与模拟尚未合成一个通过全芯片检查的 top；无 pad/ESD、silicon 或 optical measurement |

**判断：继续单像素。** 目前可以教清楚一条实际 ASIC 研究流程，但不能把模型通过称为真实 LED 动态或 tape-out readiness。4×4 的通信、寄存器和供电分配在单像素接口与预算稳定后定义。

<!-- page -->

## 02 六个 MOS 各自做什么

LED 阳极接 5 V；阴极接 `led_k`。输出 NMOS 把电流拉向 VSS，因此这是 **current sink**。外部参考电流从 3.3 V 注入 `bias`，二极管连接的参考管将 IREF 转成 VGS；输出管复制这个偏置。

| 器件 | v0.2 W/L | 作用 |
| --- | --- | --- |
| MREF | 20/4 µm | drain 与 gate 接 bias；把 IREF 转成偏置 |
| MOUT | 20/4 µm | drain 接 LED 阴极；gate 接可开关的 gate 节点 |
| MPASS | 2/1 µm | PWM 高时把 bias 传给输出 gate |
| MCLAMP | 2/1 µm | PWM 低时把输出 gate 放电到 VSS |
| MINV_N | 2/1 µm | 与 PMOS 组成 CMOS inverter |
| MINV_P | 4/1 µm | 产生互补控制 pwm_b；bulk 接 vlogic |

PWM 高：pass 开、clamp 关、输出管导通。PWM 低：pass 关、clamp 开、输出 gate 放电。clamp 是必要的，因为仅断开 pass 会留下带电的浮动 gate。

选择 simple mirror 是为了让偏置、有限输出电阻、headroom 和失配都容易解释。它没有 cascode、误差放大器或校准反馈；相同 W/L 只给出 nominal 1:1 比例，**IREF=100 µA 不保证 IOUT 恰好 100 µA**。

本项目选用公开 GF180MCU 6 V MOS，参考 [官方器件说明](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_1_4_1.html)；实际模型版本和文件 hash 由仓库 lock 固定。数字采用同工艺标准单元的 3.3 V Liberty 条件，不能把名字中的 5V0 当作当前供电设定。

详细连接、单位和原理见 [design](../design.md)。`w=20u l=4u` 是 SI 网表中的 20/4 µm；Magic PCell 输入 `w 20 l 4` 使用 µm，二者不能混用。

<!-- page -->

## 03 真实 LED 数据改变了什么

来源为 Lin 等人 2026 年的 **20 µm 方形 yellow InGaN MicroLED，transfer-printed 到 diamond**。作者 [Zenodo dataset](https://doi.org/10.5281/zenodo.20034288) 的 `I-V.xlsx / Sheet1 / A3:B102` 提供 100 点数值，覆盖 0.1 µA-32 mA、2.41622-6.40451 V。数值 dataset 为 CC BY 4.0；本图由这些数值独立绘制。

![作者数值数据独立重绘](figures/measured-iv.png)

100 µA 夹在 88.55 µA / 3.73408 V 与 100.65 µA / 3.76983 V 之间。线性插值：

`Vf = 3.73408 + (100−88.55)/(100.65−88.55) × (3.76983−3.73408) = 3.767909545 V`。

面积 `(20 µm)² = 4×10⁻⁶ cm²`，因此 `J = 100 µA / area = 25 A/cm²`。这只是 mesa 平均电流密度，未测局部电流分布。

模型最终采用单调 PWL 静态重放。75 点训练、25 点留出时最大电压插值误差 2.953 mV；101 次独立 OP 确认表示方式。全范围简化 diode/log/R 经验式留出最大误差 221.369 mV，故未采用。

温度、扫描时序、重复次数和测量不确定度未报告。**插值误差不等于测量误差**，一条曲线也不等于器件间分布。出处、许可、失败拟合和模型卡完整保存在 [measured LED 研究](measured-led.md)。

<!-- page -->

## 04 用电流误差检查电压余量

100 µA 时真实曲线 Vf≈3.768 V，5 V 电源只留下约 **1.232 V** 给驱动串联路径；旧合成 Vf=2.8 V 留下 2.2 V。不能沿用旧电压余量直接推断新负载可用。

实际 20/4 RC 网表与真实静态 I-V 耦合，共 148 DC：135 点网格，以及 13 点 typical 供电扫描。网格为 5 MOS corners × 3 logic rails × 3 LED rails × 3 IREF，MOS 温度固定 27 °C，LED 曲线温度仍未知。

![真实静态负载下的供电余量](figures/headroom.png)

| 工况 | 实际电流 |
| --- | ---: |
| 网格 VLED=4.5/5/5.5 V，Vlogic=2.97/3.3/3.63 V，IREF=99.5/100/100.5 µA | 98.175-100.984 µA，135/135 在 ±5% 内 |
| Typical，5 V / 3.3 V，IREF=100 µA | 99.788467 µA；相对目标 −0.211533% |
| Typical，VLED=4.2 V | 93.464616 µA，超出目标 |
| Typical，VLED=4.3 V | 97.006693 µA，达到目标 |

±5% 下的 typical 静态边界被扫描夹在 **4.2-4.3 V**，不能把 4.3 V 当作所有温度或批次的最低规格。全部 148 DC 电流在实测正向数据域内。结果与条件见 [耦合证据](../../evidence/characterization/measured-load-summary.json)。

<!-- page -->

## 05 镜像管尺寸为什么改为 20/4

预先设定 full-on absolute current 为 **100 µA±5%**。原 10/2 µm 在最差固定 corner/reference 条件叠加 local mismatch 后，有 **4/256** 个样本超过 105 µA。增加面积前先保留了失败结果，再用相同种子比较尺寸。

W 与 L 都加倍，W/L 仍为 5，镜像管 gate 面积变为 4 倍。较大面积降低模型中的随机失配，较长 L 改善有限输出电阻；代价是面积和充放电负担。最终结果来自重新生成、检查和提取的**真实新几何**，不是只改旧网表上的尺寸。

![同种子条件失配比较](figures/matching.png)

| 最差条件，256 个模型样本 | 旧 10/2 RC | 实际 20/4 RC |
| --- | ---: | ---: |
| 电流 sample σ | 0.90409 µA | 0.43287 µA |
| 最大观察电流 | 105.40741 µA | 103.21357 µA |
| 超出 ±5% | 4/256 | 0/256 |
| 模拟 cell bbox 面积 | 2532.7 µm² | 3577.7 µm²，增加 41.26% |

新尺寸五组 MC 各 256，共 1280 个 OP；每组均未观察到超限。此处采用 **synthetic LED 温度模型**；最差条件为 FF / 0 °C / Vlogic=3.63 V / VLED=5.5 V，reference 校准 +0.5%、TC=−25 ppm/°C、line=+3000 ppm/V。它们是模型的有限条件样本，不是实测 LED 的失配或 manufacturing yield。详细开关与复算见 [reference / matching 报告](reference-and-matching.md)。

<!-- page -->

## 06 Reference、误差和功耗怎样分账

当前仍采用外部 reference；没有片上 reference generator。行为模型是用于分配误差的工程假设：100 µA@27 °C、校准误差 ±0.5%、TC ±25 ppm/°C、line ±3000 ppm/V、输出电阻 10 MΩ、compliance ≥1 V。它不是已选定器件的 datasheet 保证。

1080 点 deterministic 检查为 5 fixed corners × 3 MOS temperatures（0/27/85 °C）× 3 logic rails × 3 LED rails × 8 reference 边界组合。LED 使用合成温度模型；与第04页真实静态负载的固定温度网格分开计数。

| 指标 | 实际 20/4 RC 结果 |
| --- | --- |
| Reference / fixed-corner 网格 | 99.280257-102.075649 µA，1080/1080 在 ±5% 内 |
| 最低码 1/256 | nominal / low / high 各 50 ns 与 10 ns；6 次 transient |
| 最低码最大面积误差 | 0.768297%，在预设 ±2% 内；只属于当前模型条件 |
| 理想 IREF、合成 LED、nominal full-on | 100.695401 µA；对 100 µA 误差 +0.695401% |
| 同条件 schematic → actual RC | 100.752515 → 100.695401 µA，变化 −0.056688% |

三种误差分别回答不同问题：**absolute error** 对 100 µA 目标；**PWM area error** 对同条件 full-on×导通时间；**pre/post delta** 对同尺寸 schematic。任何一项小都不能代替其他两项。

真实静态负载 nominal 下，LED rail 功耗 **498.942337 µW**，analog-control/reference rail **330.000012 µW**，合计 **828.942349 µW**。这是两个理想电源送入模拟 testbench 的功率，不含数字逻辑、实际 reference generator、封装和外部供电损失。PWM 关闭时 reference 仍约消耗 330 µW；低 off current 不等于低 standby power。

尚未覆盖 reference noise、startup、power sequencing、系统性布局梯度和独立 RC corners。预算、公开 PDK 公式、每组分母和冻结输入见 [实际 RC summary](../../evidence/characterization/actual-w20-l4-summary.json)。

<!-- page -->

## 07 从 PWM RTL 到标准单元物理实现

输入为 9-bit duty、enable、reset、clock；duty=0 持续低、256 持续高，257-511 saturate 为 256。输入只在帧边界锁存。1 MHz clock 的 slot 为 1 µs，每帧 256 µs，PWM 为 3906.25 Hz。

旧输出直接取 counter/comparator 组合结果，物理路径差异可能产生短暂毛刺。现在使用 **output FF**：普通 slot 注册 next-counter 比较结果，帧边界注册新 duty 的 slot 0。保持原有帧时序，不增加一个 slot 延迟。

| 验证 | 已完成结果 |
| --- | --- |
| RTL exhaustive | 518 frames / 133159 checks / 543 个已知 PWM events |
| Functional mapped gate simulation | 相同 exhaustive 检查通过；10 个 trace 与 RTL 完全相同 |
| Native Yosys synthesis | 95 standard cells，19 个 FF；Liberty cell area 2434.4768 µm² |
| 输出结构 | pwm 唯一直接 driver 为 FF.Q |
| 1 ns timing template | 仅 simulator 模板探针；不代表 PVT 或布线延迟 |

本轮实际完成 LibreLane 3.0.14 的76步flow：placement、CTS、routing、SPEF/SDF、GDS/LEF；九个corner组合的setup、hold、max slew、capacitance和fanout违规均为0。最差setup margin 793.656477 ns，hold margin 0.436677 ns。保持3 ns transition约束，通过buffer sizing修正原来的slow-corner slew超限。

STA 使用72.91 fF output load、0.15 ns clock transition、200 ns IO delays与0.25 ns uncertainty；这些是工程约束，不是实测analog输入电容。实际数字Magic DRC、route DRC、LVS以及独立KLayout结果见[physical证据](../../evidence/physical/summary.json)。

九份实际SDF各跑518 frames/133159 checks；关键clock/FF/output路径延迟与CSV边沿独立核对。TT rise/fall delay为2.644/2.360 ns。TT SDF→actual analog RC另跑5组duty配对、共10 transient+3 calibration；最低码相对理想RTL的平均电流变化为−0.00011170 µA。

SDF回放仍有24个XOR/XNOR ModPath未匹配、19项TIMINGCHECK不支持；关键输出路径已单独验证，setup/hold结论来自STA。模拟端仍是理想0/3.3 V、10 ns slew回放；未模拟真实输出级。条件与范围见[数字物理报告](../digital/physical.md)。

该数字 macro 和模拟 macro 分别生成；尚未以一个共同 routed top 做全芯片 LVS、供电和模拟接口验证。这里没有 SPI、通信协议或像素 memory；这些属于后续阵列阶段。

<!-- page -->

## 08 模拟 layout、规则与交付视图

新尺寸保留相邻、同方向的镜像管；独立 guard rings、bulk ties、contacts 和 M1/M2/M3 接线。器件增大后 bulk via landing 首次出现 4 个 M1 spacing 违规，调整 landing 位置后重新运行完整检查；原失败日志保留在 build 中。

![实际 20/4 µm GDS 几何](../../evidence/layout/layout.png)

实际 GDS bbox 为 **95×37.66 µm**，面积 3577.7 µm²。横向从左到右为 MREF、MOUT、MPASS、MCLAMP、MINV_N、MINV_P；下方七条 M3 总线对应公开的 macro 接口。图直接来自 GDS polygons，坐标为 µm。

版图保留宽松间距用于教学。相邻同尺寸同方向不等于 common-centroid 或已验证的系统梯度抵消。模型 MC 检查随机器件参数，不能自动反映布局梯度、机械应力或制造后的像素一致性。

<!-- page -->

## 09 检查范围与可集成接口

| 检查或输出 | 实际结果 |
| --- | --- |
| Magic DRC / GDS 回读 DRC | 两者均 0；采用 drc(full) |
| Netgen LVS / 回读 LVS | 唯一匹配，无 property errors；6 MOS / 7 nets |
| RC extraction | 7/7 nets；6 MOS、59 R、43 C |
| 版图前后电气回归 | 36 transient + 3 LED calibration；19 guards 通过 |
| 独立 KLayout | Linux 中运行锁定 GF180 variant D deck，0 违规；范围以报告为准 |
| Macro views | GDS / editable MAG / LVS SPICE / RC SPICE / 实际导出 LEF |

LEF 由同一个 layout 导出，尺寸与实际 GDS bbox 对齐，七个接口的 direction/use 明确；内部接线作为 routing obstructions。已由锁定 OpenROAD/OpenDB 实际读入，尺寸、ORIGIN、七个 M3 ports 与228个 OBS 检查通过，见[consumer 验证](../../evidence/physical/macro-read.json)。

| Macro 接口 | 含义与使用条件 |
| --- | --- |
| VSS / vlogic | Ground / 3.3 V analog-control rail，需定义 top 供电 |
| pwm | Registered digital control input，尚需验证最终 top 的负载与边沿 |
| bias | 外部 reference current 注入点，需满足 compliance |
| led_k | 外部 LED cathode；LED 阳极电源不在这个 cell 内 |
| gate / pwm_b | 模拟 gate 与反相 PWM monitor；当前作为公开教学端口 |

独立 KLayout 的 FEOL、BEOL、connectivity 和 off-grid 检查默认启用；density 与 antenna 未在该单独模拟运行中启用。不要把此处 0 DRC 写成所有规则零错误。新数字 macro 的检查范围另见数字 physical 报告。

严格 LVS 同时检查连接和 deck 保留的 W/L；deck 的 1% tolerance、D/S 交换和忽略 AD/AS/PD/PS 等限制仍保留。DRC 通过也不能代替 density、antenna、foundry/shuttle acceptance 或完整芯片检查。详细范围与证据见 [layout 报告](../layout/README.md)。

<!-- page -->

## 10 最低灰阶：数值稳定与物理准确分开

真实 I-V 模型没有已测电容，也没有 0.1 µA 以下的测量。为观察敏感性，外加 **0.2/2/20 pF 假设电容**，各跑 duty=1/64/256；20 pF 最低码再用 2 ns 细步长，共 10 次 transient。每次积分预热后四帧。

| 最低码 duty=1/256 | 面积误差 | 域外导电电荷比例 |
| --- | ---: | ---: |
| 0.2 pF 假设 | −0.345617% | 0.563943% |
| 2 pF 假设 | −0.227048% | 4.904857% |
| 20 pF 假设 | +0.135576% | 18.4548% |
| 20 pF / 2 ns fine | +0.135532% | 18.4532% |

所有探针面积误差在 ±2% 内；20 pF 细化的平均电流变化仅约 **0.0000433%**。这支持所设模型的数值积分，但不能证明实物有相同动态表现。

20 pF 最低码约 **90.651% 时间、18.45% 有符号静态导电电荷**落在未测低电流延拓区。0.2 pF 波形甚至短暂出现约 −9.77 mV LED 电压，而 reverse behavior 没有数据。域外比例的分母是 `∫I_static(VLED)dt`，不是 rail displacement current，也不是 `∫|I|dt`。

本轮沿保存的 V(t) 插入全部 PWL knot crossing 后分区积分，另外报告逐帧均值、同相节点、端点电容电荷和重建残差；未设隐藏的 periodicity “通过”阈值。证据明确 **dynamic_qualification=false**。

下一项有价值的数据是同结构器件的低电流/reverse I-V、C-V 或 impedance、pulse response、I-V(T) 和 L-I/EQE。取得前保留 synthetic baseline 与静态数据模型两条路径，不把 average current 写成真实 optical brightness。

<!-- page -->

## 11 复现、阅读与下一阶段

先按 [environment](../environment.md) / [layout 安装](../layout/README.md)取得锁定依赖和完整 PDK。命令必须实际成功后才更新公开 evidence：

```sh
make test
make evidence
build/layout/venv/bin/python scripts/layout/run_layout.py --publish-evidence
build/layout/venv/bin/python scripts/layout/export_macro.py
.venv/bin/python scripts/led/fit_lin2026.py
.venv/bin/python scripts/led/probe_boundaries.py
build/layout/venv/bin/python scripts/characterization/run_actual_mirror.py
build/layout/venv/bin/python scripts/characterization/measured_load.py
build/layout/venv/bin/python scripts/digital/run.py --publish-evidence
```

数字 physical 与独立 DRC 使用锁定 LibreLane container；完整安装、调用和检查范围见 [physical 流程](../digital/physical.md)。全 PDK、VM、raw waveforms 和失败日志留在 `build/`；仓库只保留可核查的小型证据与 source hashes。[输入映射](../../evidence/research/README.md)保存实际旧 TB 快照，22 次新旧 RTL 执行确认10组默认trace相同；旧run hash保留原样，可选实时日志变化单独记录。

### 下一阶段按证据推进

1. 把数字与模拟 macro 接成同一 routed top，核对接口电平/负载、供电和完整 LVS；把已完成的TT SDF回放延伸为实际输出级、模拟负载与跨条件验证。
2. 取得真实 LED 动态、温度和光学数据；确认最短有效 pulse 与亮度指标。
3. 选择可实现的 reference source，验证 noise、compliance、startup、sequencing 和总功耗；若需要低 standby，重新评估偏置关断与启动成本。
4. 单像素预算和接口稳定后，再定义 4×4 独立协议、register map、frame buffer、共享 reference 和供电分配。

MPW 是后续可行性工作：pads/ESD、package、density/fill、antenna、provider 接受规则及测试责任均需实际资料和检查。当前成果没有升级为可投片芯片。

[当前资料入口](README.md) · [旧教学 PPT](../teaching/open-microled-single-pixel-teaching-v2.pptx) · [2026-10-03 检阅快照](../review/README.md) · [完整 roadmap](../roadmap.md)。旧报告和 manifest 保留当时的设计与输入；当前 20/4、registered PWM 和新测量模型以本报告及新 evidence 为准。
