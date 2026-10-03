# 1-Pixel Driver：公开证据、方案选择与验证边界

调研日期：2026-10-03（Asia/Tokyo）。本页记录公开来源与本项目独立设计判断；不包含商业产品的协议、register map、内部 schematic 或 layout。公开产品和论文用于识别问题，不作为可直接复用的电路 IP。第一阶段执行结果以仓库生成的波形、日志和结果文件为准，本页不是仿真通过证明。

## 1. 第一版选择

选择 **1:1 simple NMOS current mirror sink + MOS gate selection + off-state gate clamp**。它同时展示 reference current、MOS 饱和区、LED headroom、PWM 动态和电流积分，而且可以逐个器件进行后续 layout。第一版只做 1 pixel；不加入 cascode、current DAC、温度补偿或商业协议。

当前独立电路在 [`analog/driver/pixel_driver.spice`](../../analog/driver/pixel_driver.spice)：

```text
                           VLED
                             |
                       synthetic LED
                             |
                           led_k
                             |
                    MOUT current sink
                             |
                            GND

external IREF -> diode-connected MREF -> bias
                                         |
                                   MPASS (PWM)
                                         |
                                     MOUT gate
                                         |
                                MCLAMP (PWMbar)
                                         |
                                        GND

PWM -> transistor-level CMOS inverter -> PWMbar
```

图为本项目独立概念示意，不是任何来源的原图。MREF、MOUT、MPASS、MCLAMP 和 inverter 的两个 MOS 共 **6 个 MOS**。`IREF`、电源、RTL 到电压的转换由 testbench 提供，尚未实现片上 reference generator、level shifter、pad 或 ESD。当前 netlist 使用 GF180MCU 原始 ngspice 模型中的 `nmos_6p0` / `pmos_6p0`；模型版本和文件校验值另见 [`pdk-lock.json`](../../analog/models/pdk-lock.json)。这项选择不等同于整芯片选型或 sign-off。

| 方案 | Vf 改变时的机制 | Headroom / 代价 | 第一阶段判断 |
|---|---|---|---|
| Resistor limiting | 电流由电源、LED I-V 和电阻共同决定 | 电阻压降与功耗；片上绝对阻值有工艺偏差 | 可作为敏感度对照，不能承担稳定电流主方案 |
| Simple current mirror | 饱和区内用相同 VGS 复制 reference current | 一个输出 MOS 的 saturation margin；有 channel-length modulation、mismatch | **Baseline**；复杂度足够低，误差原因可解释 |
| Cascode mirror | 增大输出电阻、减少输出电压变化对 mirror 的影响 | 堆叠器件和 bias；损失 compliance margin | 等 baseline 的 DC sweep 显示改进需要后再做 |
| Programmable current sink | 开关 reference、设置 bias 或 feedback 调节电流 | reference、控制电路、settling 和校准 | 先把外部 IREF 参数化，再实现片上可编程结构 |
| Current DAC | 多个 unit current cell 按 code 汇总 | 面积、matching、DNL/INL、code-change glitch、reference fanout | 是后续 amplitude dimming 扩展，不是第一版必要条件 |

该比较是本项目工程判断；基本 mirror 和 cascode 机制可追溯至 [COCOA 第 5 章，§5.3](https://bmurmann.github.io/COCOA/contents/partI/partI.5.html#current-mirrors)。不能把“current mirror”写成无条件恒流：它只在相应 operating region 和误差预算内近似成立。

## 2. 为什么 PWM 放在 gate，并明确夹到 ground

本项目采用 **bias / ground 二选一的 gate 控制**：PWM 高时 MPASS 把 MOUT gate 接到 mirror bias；PWM 低时 MCLAMP 放掉 gate charge。它避免在 LED 大电流通路中再串一个 switch，因此保留输出 headroom，也避免故意让 MOUT gate 在整个 off interval 浮空。

仅在 bias 到 gate 之间放一个 series MOS 不足以可靠关断：关掉 switch 后，gate 电容可能保留原来的 VGS，LED 继续导通；`.ic`、数值泄漏或人为大电阻可能掩盖这个问题。若在 MOUT source 下串 PWM switch，则 source 电位、body effect、mirror VGS 和内部浮动节点都会变化；若在 drain 上串 switch，还要预算其压降并检查内部节点 charge。不是不能用这些拓扑，而是第一版 gate-select 更容易逐项解释。

**Gate clamp 不保证边沿没有异常。** 当前 CMOS inverter 有有限延迟；MPASS 和 MCLAMP 可能短暂同时导通，使 reference bias 被拉低，再恢复。MOS 的 Cgd/Cgs、charge injection、Miller coupling 和 LED junction charge 还会改变电流边沿。必须同时看 `bias`、`gate`、`pwm_b`、`led_k`、LED current；仅看平均电流不能发现这些现象。

MPASS 为 NMOS pass device，必须检查实际 `Vlogic - Vbias` 是否足够越过它在当前 source/body 电位下的 threshold；数字高电平不能凭空保证完整传递 bias。当前 3.3 V 控制电压是模拟 testbench 设定，不代表 1.8 V standard-cell 输出已能直接控制所有模拟器件。未来标准单元集成要明确 rail、level shifting 和器件端电压。

先做 nominal 边沿，再覆盖：

- reset、disable、0% duty、100% duty，确认 gate 的 off-state；
- 最小非零 PWM code，确认脉冲仍有有效 conduction charge；
- rise/fall time 和 inverter propagation 的变化；
- LED `Vf`、电源和模型 capacitance 的变化；
- 仿真最大 timestep 减半，确认电流积分和峰值不是采样假象。

若 reference droop 或 turn-off tail 妨碍低灰阶，再比较 non-overlap 控制、buffered bias 或不同 switch topology；不要用强理想电压源钳住 gate 后宣称 transistor switch 的动态已验证。

## 3. Headroom 与 Vf sensitivity 的独立推导

以下是用于解释仿真的低阶关系，不替代 PDK BSIM 模型。

对 simple mirror，在长沟道、饱和区、匹配器件近似下：

```text
Iout / Iref ≈ (W/L)out / (W/L)ref
              × (1 + λ VDS,out) / (1 + λ VDS,ref)
```

MREF 为 diode-connected，`VDS,ref = VGS,ref`；LED `Vf` 改变 `VDS,out`，因此即使两器件的 W/L 相同，也不是严格 1:1。较长 L 可改善 output resistance，但增加 gate capacitance、面积和 settling 时间；结果要在模型 sweep 中验证。

```text
VDS,out ≈ VLED - Vf(ILED) - ILED × Rwire
margin ≈ VDS,out - VDS,sat
```

当 `Vf` 增大或 `VLED` 降低，MOUT 会失去 saturation margin，电流明显下降。低阶 MOS 用 `VDS,sat ≈ VGS - VTH`；实际 PDK 的 region 和可接受 regulation error 要从仿真得到。Cascode 可改善输出电阻，但多一个饱和器件与 bias 的要求，不能只根据“精度更好”决定采用。

对 resistor baseline，忽略 switch resistance，局部小信号近似为：

```text
ΔI ≈ (ΔVLED - ΔVf_offset) / (Rlimit + rd,LED)
```

独立示例：若暂按固定 Vf 处理，电源 3.3 V、目标 100 µA、Vf=2.7 V，需要 `Rlimit=6 kΩ`；Vf 增大 0.2 V 后电流约为 66.7 µA。这只是理想化对照计算，不是 MicroLED 实测数据。

Driver 敏感度应报告 sweep 条件和 `Isteady`、`VDS,out`、参考电流、相对 nominal 的变化；把失去 compliance 的点保留在结果中。不能删去高 Vf 失败点后再概括“对 Vf 稳定”。

## 4. Synthetic MicroLED 模型与 brightness proxy

当前 [`microled.spice`](../../analog/models/microled.spice) 是 **未拟合实际样品的电气负载**：diode exponential I-V、series resistance、junction capacitance 与 transit-time 项。它用于验证驱动机制，没有代表特定品牌、颜色、尺寸、current density 或像素几何。

| 参数 | 当前假设 | 物理/验证边界 |
|---|---|---|
| `N` | 3 | synthetic effective emission coefficient，不是论文提取值；在 2.4–3.2 V sweep 范围保持 IS 高于 solver 的下限 |
| `RS` | 50 Ω | 用于电气串联压降；不含 bond / package / array 的独立走线模型 |
| `CJO` | 2 pF | 零偏置 capacitance 参数；forward-bias 下不是恒定 2 pF |
| `VJ`, `M` | 2.5 V，0.33 | diode junction-capacitance 模型假设 |
| `TT` | 1 ns | SPICE charge-storage/transit-time 假设，不能等同 LED 光学 rise time |
| `EG` | 2.6 eV | diode 温度方程参数假设；未校准颜色或温度系数 |
| `IS` | 由 runner 为目标 Vf 计算 | 在 27 °C、100 µA 的 reference point 上锚定；不是物理提取出的 saturation current |

锚定关系为 `Vf(I)=N·VT·ln(I/IS+1)+I·RS`；因此修改 IS 的 Vf sweep 是一组 synthetic load variants。它没有验证实际器件跨温度、全 current range 或 reverse-bias 的 I-V。不得把默认 silicon diode 参数套用后的高温输出当成 GaN/AlGaInP 的可靠温度预测。[ngspice manual v47 §7.2](https://ngspice.sourceforge.io/docs/ngspice-47-manual.pdf) 给出了 diode 参数和 charge 模型定义。

本次运行发现 ngspice 会把极小 `IS` 静默钳到 `epsmin`；[官方 diode setup 源码](https://sourceforge.net/p/ngspice/ngspice/ci/master/tree/src/spicelib/devices/dio/diosetup.c?format=raw) 可核对该机制。因此每次仿真先用独立 100 μA / 27 °C OP 验证 2.4、2.8、3.2 V 三个 target，容差 0.1 mV，不能只看 netlist 参数与干净 log。失去 headroom 的 negative control 用降低 LED supply 来构造，避免超出合成模型的校准范围。

报告应区分：

- **Total branch current**：端口电流可含 junction/displacement current，可能有短负脉冲或 overshoot；用于观察电气应力与瞬态。
- **Conduction current / charge**：用于 electrical brightness proxy；如果暂未单独提取，就把 total-current average 明确标成该负载的电气代理，避免把边沿峰值解释成发光峰值。
- **Average current**：对完整稳定 PWM frame 积分，`Iavg=(1/T)∫I(t)dt`，不能对 adaptive timestep 样本简单取算术平均。
- **Optical brightness**：第一阶段没有 optical power、EQE、wavelength、热效应、droop、aging 或 photometric measurement，不能报告 cd/m²、真实 gamma 或效率。

在固定 pulse amplitude、每个 on interval 均充分 settle、off leakage 很小、光电转换效率近似不变时，才有 `Iavg≈D·Ion` 和相对亮度随 duty 近似线性。低 code 或高速 PWM 时，rise/fall area 与 capacitance 的占比增加；应使用积分检查这一近似在哪些条件下失效。

## 5. RTL / SPICE integration 的现实路径

| 路径 | 什么真正联动 | 证明能力 | 第一阶段定位 |
|---|---|---|---|
| RTL run → transition/VCD → finite-edge PWL → ngspice | 同一 RTL 产生的 PWM edge 驱动 transistor gate，ngspice 解出 LED current | 完整 **feed-forward coupled simulation**；可验证 duty 到电流，模拟不能改变已生成的 RTL 状态 | 先跑通的默认方案 |
| Yosys → XSPICE digital code-model netlist | synthesized digital primitive 与 analog solver 的事件联动 | 可加 analog→digital bridge；不等于真实 standard-cell transistor timing | 可研究的中间方案 |
| ngspice XSPICE `d_cosim` + Verilator / Icarus | HDL block 在 ngspice 调度下收发 event-node，analog bridges 把电压和事件相连 | 可实现双向反馈；需实际编译 libraries、验证阈值/延迟/port order | 下一次 integration 升级 |
| Python + shared libngspice + digital simulator | 显式同步、callback 与步进 | 灵活，但 time synchronization、rollback/不可逆事件、阈值跨越需要工程实现 | 不必为 1 pixel 先自建联仿引擎 |
| Verilog-A / OpenVAF / OSDI | analog behavioral/device model 被 SPICE 解算 | 适合 compact/behavioral analog 模型；仅编译 Verilog-A 不等于运行数字 RTL | 模型升级用 |

官方 [ngspice extras](https://ngspice.sourceforge.io/extras.html) 明确 Verilator `d_cosim` 从 v42 起提供、GHDL 从 v44 起提供；[release manual v47 §10.3](https://ngspice.sourceforge.io/docs/ngspice-47-manual.pdf) 还记载 Icarus/VVP 的集成。不要沿用“ngspice 只能做 analog、不能接 RTL”的过时说法。安装版本号也不能证明二进制已经启用 XSPICE 和相关 runtime。

PWL 必须来自执行后的 RTL event trace，而不是 Python 重新计算一个理想 PWM 后分别画两个仿真。转换要保留 time unit、reset/disable、edge count 和最后保持状态，拒绝未知的 X/Z，并记录 finite rise/fall assumption；PWL voltage 是数字输出 buffer 的抽象，不包含 I/O drive strength 或 level shifter 动态。

**本阶段是一条完整驱动链，但不是控制闭环。** 真正反馈联仿的最小可验例子应是：`transistor current → sense/comparator → adc_bridge → RTL fault/enable → PWM off`，在模拟故障后 RTL 改变状态，并由同一个联仿 run 使后续电流关断。给结果增加 Python 检查或把 current 波形画在 PWM 旁边，都没有建立这个反馈。

`d_cosim` 升级还要核对 timescale precision、output delay、event thresholds、analog hysteresis、端口位序和 simulator library。Icarus 路线需要启用 `--enable-libvvp` 的 runtime（manual 建议 v13+）；默认安装 `iverilog` 不保证包含它。v47 manual §10.3 说明其 HDL 状态甚至可能不能通过 `remcirc` 清除；参数扫描宜每个 run 启动新 process。该路线在此页仅为 source-backed recommendation，未宣称本项目已经跑过。

## 6. 公开来源与证据账本

以下条目保留 title、组织/作者、可核实的日期/版本、source locator、证据类型和适用范围。网页核查日期为 2026-10-03；未核实年份不作推断。所有第三方电路图默认仅 link/cite；本项目不在 public repo 重贴许可未确认的商业图表。

### LED / MicroLED 设计证据

| ID | 原始来源与身份 | 已核查证据与 locator | 支持的判断 / 不支持的外推 |
|---|---|---|---|
| LED-01 | [TLC5955 datasheet](https://www.ti.com/lit/ds/symlink/tlc5955.pdf)，Texas Instruments，SBVS237，March 2014，datasheet | p.1 features、§8 功能、§9 typical application；**supplier specifications / application circuit** | 恒流输出、PWM、amplitude correction 可以作为不同功能理解；不支持内部 transistor topology、MicroLED matching 或复用其 serial format |
| LED-02 | [TrainLED2 — RGB-LED Driver for TinyTapeout3p5](https://github.com/cpldcpu/tt03p5-TrainLED2)，cpldcpu，Apache-2.0，version/year 未核实；open RTL project | README 明确 fully digital；3×8-bit RGB PWM；`src` 有 RTL 与 testbench；**published design + author simulation** | 可研究小型 LED/PWM ASIC 组织；没有 analog current sink、MicroLED electrical model 或本项目所需的完整 mixed-signal chain。协议另行独立定义 |
| LED-03 | [CMOS Backplane Pixel Circuit With Leakage and Voltage Drop Compensation for an Micro-LED Display Achieving 5000 PPI or Higher](https://ieeexplore.ieee.org/document/9031408/)，Jewoo Seong、Jinwoong Jang、Jaehoon Lee、Myunghee Lee；UNIST / Sapien Semiconductors；IEEE Access 8，2020-03-10，DOI 10.1109/ACCESS.2020.2979883 | publisher abstract，pp.49467–49476；**author-reported simulation + 180 nm test-chip measurements** | leakage / IR drop 会成为小像素阵列问题；摘要的 95% 改善是 simulation、whole-display IPIXEL error <2.5% 是作者 test result。未提取全文测试分母、Vf、bias、温度和图轴，不能当作本项目指标或全条件保证 |
| LED-04 | [A 1280 × 720 Micro-LED Display Driver with 10-Bit Current-Mode Pulse Width Modulation](https://ieeexplore.ieee.org/document/9634720)，IEEE A-SSCC，2021，DOI 10.1109/A-SSCC53895.2021.9634720；[NTHU institution record](https://scholars.nthu.edu.tw/esploro/outputs/conferenceProceeding/A-1280-x-720-Micro-LED-Display/9957818087806774) | title、conference / DOI metadata；**publication locator only**；机构全文页面本次 fetch 超时 | 指向 current-mode PWM 研究；未读取完整结果，不引用其功耗、像素面积、工艺或测量精度，不将它当成开源实现 |
| LED-05 | [US20200135092A1 — Methods and apparatus for in-pixel driving of micro-LEDs](https://patents.google.com/patent/US20200135092A1/en)，inventor Khaled Ahmed、original assignee Intel；publication 2020-04-30；B2 版本 US11676529B2，2023-06-13 | description / figures / claims；**patent disclosure，非性能验证** | 公开 in-pixel PWM、stored image signal、current paths 的研究方向；不能据 patent disclosure 声称实测性能、可自由商业实施或某一电路最优。本项目不按其具体结构克隆 |
| LED-06 | [TIDA-01183 — Precision PWM Dimming LED Driver Reference Design for Automotive Lighting](https://www.ti.com/tool/TIDA-01183)，TI；[design guide](https://www.ti.com/lit/pdf/TIDUC97)，TIDUC97A，Oct 2016 / revised Jan 2017 | guide §5、p.16；**supplier board test**：固定 duty、oscilloscope 记录；batch / −40…110 °C 条件；后两项 std. dev. <0.5%，样本数未给出 | 示范把 PWM accuracy 和实验条件一起报告；是 switching power / automotive board，不是 MicroLED pixel、open ASIC 或本项目 car-grade evidence |
| LED-07 | [Dimming in Switched-mode LED Drivers](https://www.ti.com/document-viewer/lit/html/SSZT647/GUID-B42F4989-AA4F-43DC-8333-DA8D9D9EAB78)，TI、Issac Hsu；SSZT647，Aug 2018，technical article | enabling on/off 与 shunt-FET 两种 PWM，output capacitance 注意项；**supplier engineering explanation** | settling time、stored charge 限制 PWM minimum pulse；其 inductor / power-driver 数值不搬到本项目 µA 级线性 sink |

**可直接核对的事实摘录**（独立重排的数值表，不重贴商业原图；locator LED-01 p.1）：

| Datasheet 字段 | 原值 | 条件 / 适用范围 |
|---|---|---|
| Constant-current output channels | 48 | TLC5955 产品功能 |
| PWM grayscale resolution | 16 bits，65,536 steps | 产品数字 PWM；不是 analog effective resolution |
| Logic supply `VCC` | 3.0–5.5 V | 与其 LED supply 分开 |
| 最大 sink current 的两项 feature 值 | 23.9 mA；31.9 mA | 分别 `VCC≤3.6 V, MC=5`；`VCC>3.6 V, MC=7`；DC、BC 为最大 data |

该表说明 rail、reference/current setting 和 PWM 必须分开记条件，不给本项目设定 mA 级电流或商业精度目标。

### Open mixed-signal / simulation 证据

| ID | 原始来源与身份 | 已核查证据与 locator | 对本项目的作用 / 边界 |
|---|---|---|---|
| AMS-01 | [Caravel Harness](https://github.com/efabless/caravel)，Efabless；[Caravel analog user project template](https://github.com/efabless/caravel_user_project_analog)，Apache-2.0；版本年份未核实 | harness README 的 analog wrapper 要求；template 有 `gds`, `mag`, `netgen`, `xschem`, `verilog`；**public integration template** | 说明 custom analog macro 与 digital harness 的文件和 interface 边界；不是 analog 自动生成工具，不证明本项目 LVS/DRC，也不证明当前 MPW schedule 或供货条件 |
| AMS-02 | [10 bit SAR-ADC + Analog Circuits / sky130_cw_ip](https://github.com/efabless/sky130_cw_ip)，Christoph Weiser / Efabless，源自 mpw7 project；version/year 未核实 | README “Included”、“Logic”、“Simulation”、“Top-Level Simulation”；schematic、GDS、Verilog SAR、corner setup；**author-reported design + PVT/PEX simulation** | Magic/ KLayout custom layout + OpenLane logic + Yosys/XSPICE 是具体集成案例；top-level PEX 用 modified PDK / Xyce；README 留有未来 silicon characterization，因此本次不宣称测量已验证 |
| AMS-03 | [WoWA，Tiny Tapeout 06 project 265](https://www.tinytapeout.com/chips/tt06/tt_um_psychogenic_wowa)，Pat Deegan / psychogenic；version/year 未核实 | analog ADC/DAC/comparator、数字 control，TODO / test instructions；**author design status report** | 明确 analog + digital LVS-clean 与 full simulation 失败可以同时成立；提醒 wrapper/LVS 通过不等于行为验证。网页没提供可核实的完整 silicon results，本次不提升证据等级 |
| SIM-01 | [Ngspice User’s Manual v47](https://ngspice.sourceforge.io/docs/ngspice-47-manual.pdf)，Holger Vogt、Giles Atkinson、Dietmar Warning、Paolo Nenzi；2026-08-11 | §7.2 diode，§8.4.25 `d_cosim`，§10.3 HDL paths，§15 shared-library interface；**official implementation documentation** | 支持真实事件联动与 diode model 定义；不证明当前机器的二进制具备全部 features，也不证明此仓库 d_cosim 已运行 |
| SIM-02 | [ngspice XSPICE](https://ngspice.sourceforge.io/xspice.html) / [extras](https://ngspice.sourceforge.io/extras.html)，ngspice maintainers；网页 version/year 未核实 | event / analog coordinated algorithms；d_cosim release thresholds；**official implementation overview** | 开源 mixed-signal 路线存在；仍需 pin / version / runtime / smoke test |
| CIR-01 | [COCOA — Biasing Circuits](https://bmurmann.github.io/COCOA/contents/partI/partI.5.html)，Boris Murmann / contributors；日期版本未核实 | §5.3、figs.5.3 / 5.13 / 5.20：basic / cascode / high-swing mirror；**educational circuit derivation** | 可核查 mirror 与 compliance 的低阶关系；教学 model 不等于 GF180/SKY130 device parameters 或本项目的 Monte Carlo evidence |

AMS-02 / AMS-03 的价值是留下可检查的文件和失败边界，而不是以 README 中的词语代替独立重跑。本轮没有找到并重跑一个可直接承担本项目 1-pixel transistor-level MicroLED current/PWM 全链路的开源 ASIC；这仅描述本次检索范围，不声称这样的项目不存在。

## 7. 下一轮能够改变选择的证据

1. 用当前 MOS model 做 DC headroom / Vf sweep，并把 gate steering overlap 对 reference 的扰动画出来，决定 simple mirror 是否已足够。
2. 用真实 MicroLED 样品或公开可复用测量数据拟合 I-V、capacitance、temperature；在此以前保留 synthetic label。
3. 取得 analog transistor layout、DRC/LVS、PEX 后对照 pre-layout pulse area、off leakage 和 settling；数字 RTL-to-GDS 不替代这一步。
4. 跑最小 `d_cosim` feedback fault demo，记录工具 build、bridges 和真实 feedback 状态变化，再把阶段名称升级为双向 mixed-signal co-simulation。
5. 扩展 4×4 前验证 reference fanout、power/ground IR drop、supply step 和 simultaneous switching；不能把单像素平均电流简单乘 16 当作阵列验证。
