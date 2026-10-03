# Open MicroLED Driver ASIC：单像素教学技术报告内容稿

状态日期：2026-10-03（Asia/Tokyo）。对象：了解基本电路、希望逐步学习 ASIC 数字与模拟设计的读者。顺序遵循 **整体架构 → 数字控制 → 模拟电路与选型 → 模型假设 → 复现与证据 → 单像素版图 → 4×4 先决条件**。共 28 页，每页只有一个主要教学目的；讲者备注与参数账本承担细节，页面正文保持可读。

当前电气性能数据包括两份独立证据：原 Phase 1 的 RTL + pre-layout model-subset simulation，以及锁定 full gf180mcuD 的 standalone analog cell 物理验证和配对 RC 回归。当前 cell 已有实际 MAG/GDS、Magic DRC=0、Netgen unique match、GDS roundtrip DRC/LVS通过、7/7 nets RC extraction。配对回归17条件×2variants=34，加仅RC variant的duty1/64两次50ns finer-step runs，共36 transient与3LED DC，19guards通过。完整数字physical integration、pads/ESD、foundry signoff、硅片与光学实测仍未完成。Post-layout只对同一full PDK的schematic/RC variants配对比较，不能将旧model-subset与full-PDK差异归因于layout寄生。

## 讲述与视觉原则

- 开场直接给总体框架，然后只放大当前的一条单像素路径。概念图采用独立绘制的方块与电路示意，不复制商业原图。
- 第一次出现术语先给中文含义，再给 English term；定义在公式之前。用一根蓝色路径跟踪控制，用一根青色路径跟踪电流。
- 每页 footer：阶段证据等级、关键条件、仓库 source link。近似推导写“用于解释”；仿真数字写“本模型、本条件”。
- 图与代码配合：先看示意，再展示约 3–8 行关键源码，最后指出完整源码位置。图不能代替连接表、参数或 netlist。
- Chinese body 优先 PingFang SC，English display 用 Tw Cen MT 或 Avenir Next；暖白背景、navy/teal，避免高密度表格。

## 第一部分：先看整体系统（01–04）

### 01｜整体架构：让一个数字设定变成 LED 电流

**教学目的：** 能说出整个项目的输入、处理环节和输出。

**页面正文：**

1. 用户设定：每帧点亮多久 `duty`，是否启用 `enable`。
2. 数字控制：时钟、计数与比较产生 PWM。
3. 模拟驱动：reference 与 MOS current sink 设置导通电流。
4. LED 负载：电流与器件 I–V 共同决定工作点。

**主图：** `设定数据 → PWM逻辑 → MOS开关/电流镜 → MicroLED电气模型 → 电流波形`。在图下加两条独立供电轨：`Vlogic 3.3 V`、`VLED 5 V`，以及 `外部 ideal IREF 100 µA`。把“真实 optical output”放在下一阶段待测边界。

**讲者备注：** 先把 ASIC 看成分工明确的系统。数字逻辑回答“什么时候开”，模拟驱动回答“开时流多少电流”，LED 的电气特性参与决定电压工作点。当前输出是仿真电流，不能直接标为实测亮度。Python 负责运行、桥接和检查；实际 PWM 来自 RTL，电流来自 MOS/LED 的 SPICE 求解。

**Source：** [设计系统图](../design.md#本阶段的系统)、[runner](../../scripts/run_phase1.py)。**条件：** 单像素；单向 digital→analog。

### 02｜现在与长期：先完成一个像素，再增加规模

**教学目的：** 分清当前交付范围与长期 ASIC 架构。

**页面正文：**

- 已跑通一个像素的 RTL → transistor → LED 电流路径。
- Standalone analog cell 已有 MAG/GDS、DRC/LVS 与 RC 回归。
- 下一步完成数字 physical integration、reference 与芯片接口。
- 4×4 的通信和像素存储仍按后续独立阶段展开。

**主图：** 路线阶梯；已完成的single-cell节点用实色，数字集成与4×4后续节点用轮廓。另画长期 `Host → Controller → Serial receiver → Register bank → PWM → Pixel array`；将 current reference 与诊断画作独立支路。

**讲者备注：** 当前已经推进到 standalone 六 MOS analog cell：Magic DRC=0、Netgen unique match、GDS roundtrip 复核通过，七个 nets 全部 RC extraction 后完成配对电气回归。这只支持该 analog cell 与所选公开 deck 的结果。数字 PWM 的 synthesis/physical integration、pads/ESD、foundry signoff、硅片及光学实测仍未完成。FPGA 是未来外部 controller 候选，当前 RTL 使用 Icarus 执行。4×4 的 receiver、register map 与 pixel memory 尚未实现，先学习并完成这一个像素的完整接口责任。

**Source：** [单像素物理与RC回归](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/layout/summary.json)、[roadmap](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/docs/roadmap.md)、[当前layout](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/layout/layout.png)。**条件：** standalone analog cell；open-deck与full-PDK配对结果，不是完整芯片signoff。

### 03｜四种量：数据、时间、电流与光

**教学目的：** 分清设定 code、PWM duty、导通电流与 optical brightness。

**页面正文：**

| 量 | 当前职责 | 当前例子 |
|---|---|---|
| `duty` code | 数字设定 | 64 |
| 高电平时间比例 D | PWM 时间控制 | 64/256 = 25% |
| 导通电流 | 模拟 amplitude | 约 101.3 µA |
| 平均 branch current | 电气 brightness proxy | 约 25.32 µA |

**主图：** 相同脉冲高度、不同宽度；与“不同脉冲高度”示意并排，说明 PWM dimming 与 current amplitude dimming。

**讲者备注：** 只改变 duty 时，理想情况下改变的是点亮时间，导通电流幅值由 reference/mirror 决定。平均电流近似等于时间比例乘导通电流，但真实边沿有电荷项。把电流转换为光还需要器件效率、温度、current density 和测量，这些尚未建模或测量。

**小练习：** 保持导通电流 100 µA，25% duty 的理想平均电流是多少？答案 25 µA；这只是预估，稍后用仿真积分核对。

**Source：** [brightness proxy](../design.md#branch-current-与-optical-brightness)、[metrics](../../evidence/phase1/metrics.csv)。**条件：** typical、27 °C、VLED=5 V、synthetic Vf=2.8 V。

### 04｜把信号路径与电流路径分开看

**教学目的：** 在同一图上找出控制信号和真实导通电流路径。

**页面正文：**

- 信号：`duty / enable / reset → PWM → gate selection`。
- Reference：`IREF → XREF → bias → XPASS → gate`。
- LED 电流：`VLED → VSENSE → LED → led_k → XOUT → GND`。
- 共地是当前 testbench 假设；两个电源均为 ideal source。

**主图：** 独立绘制简化 schematic；高亮 LED 电流路径；`bias`、`gate`、`led_k` 用与波形一致的 label。

**讲者备注：** Gate 控制与 drain/source 导电路径不是同一根线。`VSENSE` 为零伏电压源，用于读取 branch current，不在模型中额外产生压降。全开时还有 reference 支路电流，系统总耗电不能只用 LED current 表示。真实供电阻抗、pad、封装和互连都需要以后加入。

**Source：** [pixel_driver.spice](../../analog/driver/pixel_driver.spice)、[make_deck](../../scripts/run_phase1.py)、[独立电路图](../research/driver-evidence.md#1-第一版选择)。**条件：** ideal rails、ground、IREF；当前无走线 R/C。

## 第二部分：慢慢读懂 PWM 数字逻辑（05–10）

### 05｜先定义 clock、slot 和 frame

**教学目的：** 用时间轴读懂 PWM 的时间单位。

**页面正文：**

- Clock：每个 rising edge 推进一次状态；1 MHz → 1 µs。
- Slot：两个相邻 rising edge 之间的一段时间。
- Frame：256 个 slot，counter 覆盖 0…255。
- `Tframe=256 µs`，`fPWM=1 MHz/256=3906.25 Hz`。

**主图：** 先画 8-slot 教学缩略图，再标注“实际 256 slots”。高电平占其中 2 格，演示 25%。

**讲者备注：** 教学缩略图只用于手算，不是改变实际 RTL。PWM frequency 描述一帧重复的速率，clock frequency 描述数字计数的步速。1 MHz 与 256 是起始设计假设，不是由 MicroLED datasheet 推导出的最佳参数。最短非零脉冲为一 slot，也就是 1 µs。

**小练习：** clock 改为 2 MHz 且仍为 256 slots，frame 多长？128 µs；频率 7812.5 Hz。此练习不改源码、不声称已验证。

**Source：** [pwm.md](../pwm.md)、[RTL](../../rtl/pixel_pwm.v)、[testbench](../../sim/rtl/tb_pixel_pwm.v)。**条件：** baseline 1 MHz / 256 slots。

### 06｜counter 与 comparator 怎样生成 PWM

**教学目的：** 能按 slot 手算 PWM 输出，并对应到 RTL。

**页面正文：**

```verilog
counter <= counter + 8'd1;
assign pwm = active_enable &&
             ({1'b0, counter} < active_duty);
```

`duty=64`：counter=0…63 时高，64…255 时低。`active_duty` 是当前帧已提交的设定。

**主图：** counter ramp + threshold + PWM pulse，箭头标出 `<` 的判断。

**讲者备注：** 计数器寄存器保存“现在走到第几格”；组合比较器判断“是否还处于点亮范围”。零扩展 `{1'b0,counter}` 将 8-bit 计数值与 9-bit threshold 对齐。这里不用较复杂的通信知识也能读懂逻辑；后续接口只负责可靠地产生新的设定。

**小练习：** 用 8-slot 教学表、duty=3，写出输出：`11100000`。再回到真实 256-slot 代码。

**Source：** [pixel_pwm.v](../../rtl/pixel_pwm.v)。**条件：** enable=1，帧内 active_duty 固定。

### 07｜为什么 duty 有 9 bits，counter 只有 8 bits

**教学目的：** 理解 exact off / exact full-on 两个端点的编码。

**页面正文：**

| 设定 | 输出 |
|---|---|
| 0 | 全关 |
| 255 | 高 255 格、低 1 格 |
| 256 | 全开，无帧边界 low pulse |
| 257…511 | 饱和到 256 |

```verilog
bounded_duty = (duty > 9'd256) ? 9'd256 : duty;
```

**讲者备注：** 8 bits 能表示 0…255，不能表示 256。多一位用于全开端点，所以合法状态共 257 个；不能据此称为 512 级灰阶或 9-bit analog effective resolution。代码 clamp 的测试覆盖所有 255 个越界值。

**Source：** [RTL](../../rtl/pixel_pwm.v)、[rtl-selfcheck.log](../../evidence/phase1/rtl-selfcheck.log)。**条件：** counter=0…255；duty 为 9-bit unsigned。

### 08｜帧边界提交：让一次更新作用于完整一帧

**教学目的：** 区分 requested duty 与 active duty。

**页面正文：**

- 输入 `duty / enable` 可以在帧中变化。
- 只在 counter=255 后的新 frame boundary 锁存。
- 当前帧使用旧的 `active_duty / active_enable`。
- 下一帧采用边界前最后的输入值。

**主图：** 三条轨迹 `requested_duty 64→192`、`active_duty`、`PWM`；变化落在一帧中间，提交点标在下一 frame 开始。

**讲者备注：** 如果直接用帧中变化的 duty 作比较，当前脉冲可能被截短或重新打开。锁存把请求与正在执行的一帧分开。当前输入属于同一 clock domain，尚未实现异步通信的 CDC 或 handshake。多像素后会需要整帧 atomic commit，这是同一思想的扩展。

**小练习：** 在 counter=100 时把 duty 从 64 改为 192，当前帧会立刻变高吗？不会；下一 frame 才使用 192。

**Source：** [更新与 reset](../pwm.md#更新与-reset)、[RTL](../../rtl/pixel_pwm.v)。**条件：** 输入满足同域时序假设；未证明物理 setup/hold。

### 09｜reset 与 enable：两种不同的关断规则

**教学目的：** 预测 reset、disable 与恢复输出的时间。

**页面正文：**

- `rst=1`：高有效同步 reset，下一 rising edge 清除 active state。
- Reset 将 counter 置为 255，释放后下一 edge 从 slot 0 开始。
- `enable=0`：在下一 frame boundary 提交整帧 off。
- 输入同步/reset 行为已由 RTL testbench 检查。

**主图：** 同样在 frame 中间提出 disable / reset，显示两种生效时刻。

**讲者备注：** reset 可以中断当前 frame，enable 的正常更新则等到下一 frame。同步 reset 之前，RTL 寄存器没有已定义的初始化值。当前不是安全保护关断设计：没有过流 comparator，也没有异步 fault path。逻辑仿真通过不等于综合后组合 PWM comparator 无毛刺，后续数字物理验证需要单独进行。

**Source：** [RTL](../../rtl/pixel_pwm.v)、[pwm.md](../pwm.md)。**条件：** rising-edge synchronous reset；未实现 fault feedback。

### 10｜从执行后的 RTL 边沿到 SPICE 电压

**教学目的：** 理解 feed-forward 联动是怎样建立的。

**页面正文：**

1. Icarus 执行 RTL，导出 `time_ns,pwm`。
2. Bridge 保留 event timestamp，拒绝未知状态。
3. 0/1 转成 0/3.3 V，边沿从 timestamp 开始做 10 ns ramp。
4. ngspice 求解 MOS 与 LED 电流；模拟结果不反馈到 RTL。

**主图：** 一条 edge CSV 小表与对应 PWL ramp；显示 `t_edge` 到 `t_edge+10 ns`。

**讲者备注：** 逻辑 1 本身没有 3.3 V 的电气含义，bridge 显式加入这条假设。第一条已知 low 来自 500 ns reset，桥接把它向前延伸到 SPICE 0 ns，这是启动假设。10 ns 并非 standard-cell 测得的 slew，也不包含 pad、level shifter 或 drive strength。真正反馈联仿需要模拟检测改变 RTL 状态；当前只有单向 replay。

**Source：** [read_events / pwl_points](../../scripts/run_phase1.py)、[bridge tests](../../tests/test_bridge.py)。**条件：** 10 ns slew、3.3 V amplitude；首个 frame=2.5 µs。

## 第三部分：从模拟机制到器件选型（11–17）

### 11｜Current mirror：先用 reference 求出 bias，再复制电流

**教学目的：** 理解 diode-connected reference MOS 与 output MOS 的分工。

**页面正文：**

- `XREF` 的 drain 与 gate 相连，外部 IREF 决定 bias 电压。
- `XOUT` 使用相近的 gate-source bias，作为低侧 current sink。
- 相同 W/L，目标为 nominal 1:1 current ratio。
- 只有合适工作区与足够匹配时，才近似复制电流。

**主图：** 只保留 XREF/XOUT 两个 MOS 的教学示意，然后指出真实电路还有 gate selection。

**讲者备注：** Current mirror 复制的是 reference 定义的电流关系，不是无条件把任何 LED 电流锁死为 100 µA。XREF 把给定电流转换成所需 VGS。输出端 VDS 与参考端不同，PDK model 会包含由此产生的误差；当前未启用 mismatch。适合用这个最小电路学习 bias、工作区和非理想误差。

**Source：** [pixel_driver.spice](../../analog/driver/pixel_driver.spice)、[COCOA §5.3](https://bmurmann.github.io/COCOA/contents/partI/partI.5.html#current-mirrors)。**条件：** 1:1 W/L；external ideal IREF；无 cascode/feedback。

### 12｜Headroom：LED 占用电压后，MOS 还剩多少余量

**教学目的：** 用节点电压解释为什么降低供电会掉电流。

**页面正文：**

- `Vf`：LED 在实际电流下的正向压降。
- `VDS,out`：XOUT drain-source 之间的电压。
- 当前无线阻时：`VDS,out = VLED − Vf(ILED)`。
- 5 V case：actual Vf≈2.801 V，VDS≈2.199 V。

**主图：** 5 V 的电压预算柱，拆成 LED 压降与 MOS 电压。旁边加低供电示意。

**讲者备注：** MOS 维持近似恒流需要最低 compliance voltage，常称 headroom。长沟道近似可用 VDS ≥ VGS−VTH 来理解，但不能拿这个式子替代 BSIM 模型或可靠性检查。LED 的实际 Vf 会随电流改变，2.8 V 是 100 µA/27 °C 的锚定标签，不是固定电压源。

**小练习：** 暂按 Vf=2.8 V 手算：5 V→2.2 V 余量，2.9 V→0.1 V 余量。随后用 actual Vf 与电流核对，保留近似与仿真的差别。

**Source：** [headroom 推导](../research/driver-evidence.md#3-headroom-与-vf-sensitivity-的独立推导)、[summary](../../evidence/phase1/summary.json)。**条件：** typical、27 °C、full-on；公式用于解释。

### 13｜完整单像素电路：六个 MOS 各做一件事

**教学目的：** 能从器件表逐项核对完整 netlist。

**页面正文：**

| MOS | 功能 | 主要连接 |
|---|---|---|
| XREF | 生成 bias | D/G=bias，S/B=GND |
| XOUT | LED current sink | D=led_k，G=gate，S/B=GND |
| XPASS | 导通时传递 bias | D=bias，G=pwm，S=gate，B=GND |
| XCLAMP | 关断时拉低 gate | D=gate，G=pwm_b，S/B=GND |
| XINV_N | 反相器下拉 | D=pwm_b，G=pwm，S/B=GND |
| XINV_P | 反相器上拉 | D=pwm_b，G=pwm，S/B=vlogic |

**主图：** 与源码一一对应的原创六 MOS schematic；表可放备注中、正文用编号图避免拥挤。

**讲者备注：** 原始 PDK 以 `X` subcircuit 调用，端序为 D、G、S、B，B 是 bulk/body。NMOS bulk 接 ground、PMOS bulk 接 vlogic 是当前 schematic 连接；到 layout 要实现 well/substrate ties。讲完读者应可以逐行读源码，并指出每个 net 去向。

**Source：** [pixel_driver.spice](../../analog/driver/pixel_driver.spice)、[PDK lock](../../analog/models/pdk-lock.json)。**条件：** original nmos_6p0 / pmos_6p0；不是 full-PDK extracted netlist。

### 14｜On / Off 两个状态：为什么需要 gate clamp

**教学目的：** 预测 gate selection 的状态，并理解 off-state 放电。

**页面正文：**

| 状态 | XPASS | XCLAMP | gate |
|---|---|---|---|
| PWM high | 开 | 关 | 接近 bias，XOUT 导通 |
| PWM low | 关 | 开 | 被拉低，XOUT 关断 |

- Inverter 产生 `pwm_b`。
- Gate 有电容；只有断开 XPASS，可能留下残余电荷。
- 真实边沿需要检查 delay、overlap 与 bias droop。

**讲者备注：** Clamp 不是装饰，它主动移除 gate charge。开关放在 gate 控制支路，LED 导通路径只有一个 XOUT，保留 headroom。Inverter 有有限延迟，pass 与 clamp 可能短暂同时导通；这种现象要从 gate/bias/pwm_b 波形判断，不能凭平均值说边沿完美。NMOS pass 能否传递 bias 还受 threshold/body effect 影响。

**Source：** [gate selection 选择理由](../research/driver-evidence.md#2-为什么-pwm-放在-gate并明确夹到-ground)、[edge CSV](../../evidence/phase1/edge-duty064.csv)。**条件：** Vlogic=3.3 V、10 ns input slew。

### 15｜为什么第一版选 GF180MCU 6 V MOS

**教学目的：** 看懂工艺选择的需求与证据，而不是只记一个名称。

**页面正文：**

- 起始需求为 5 V LED supply、3.3 V control 与低侧 sink。
- GF180MCU 公开模型提供 3.3 V / 6 V MOS。
- Phase 1 原始 model subset 与完整 gf180mcuD 分别锁定。
- Layout 与 post-layout 对比使用同一 full PDK，避免混合版本。

**主图：** “需求 → 候选 → 当前选择 → 再评估触发条件”的四列卡片。

**讲者备注：** 第一版工艺选择来自教学路径的电压域与器件需求，不是只记一个工艺名称。Phase 1 使用原始 nmos_6p0/pmos_6p0 model subset；当前物理流程使用完整 gf180mcuD，build hash为54435919abffb937387ec956209f9cf5fd2dfbee。Post-layout 的 schematic与RC提取网表都在这个 full PDK 下配对运行，不能把旧model subset与新版RC数值之差全归因于寄生。6 V器件标签不代表任意电压组合可靠或已达到foundry signoff。真实LED、IO与MPW要求仍可能改变最终选择。

**Source：** [Phase1模型锁定](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/analog/models/pdk-lock.json)、[full PDK和tool pin](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/scripts/layout/bootstrap_macos.sh)、[物理回归模型边界](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/layout/summary.json)、[GF180 MOS device list](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_1_4_1.html)。**条件：** standalone analog cell；open-deck与full-PDK配对结果，不是完整芯片signoff。

### 16｜把尺寸、供电和版本全部写出来

**教学目的：** 能从参数表重建当前设计，不依赖口头说明。

**页面正文：**

| 实例 | W / L（µm） |
|---|---|
| XREF、XOUT | 10 / 2 |
| XPASS、XCLAMP、XINV_N | 2 / 1 |
| XINV_P | 4 / 1 |

`VLED=5 V`、`Vlogic=3.3 V`、`IREF=100 µA`，均为 testbench ideal sources。Model commit：`9f992d5a9186d1f7820c58f039c484ad35b2edea`。

**讲者备注：** 尺寸是 baseline 假设，尚未针对面积、速度、mismatch 或功耗优化。较长 L 常用于降低输出电压影响，也增加面积/电容；该趋势需以具体 sweep 量化。原始 model 用米表达 W/L，`10u` 是 10 µm，不能与某些 open_pdks wrapper 的 µm 单位约定混用。PMOS 4 µm 宽度是起始 sizing，不能直接称成最优或平衡 rise/fall。

**Source：** [driver netlist](../../analog/driver/pixel_driver.spice)、[pdk-lock.json](../../analog/models/pdk-lock.json)、[runner](../../scripts/run_phase1.py)。**条件：** original model units；ideal current reference 未实现片上电路。

### 17｜为什么先用 simple mirror，什么时候升级

**教学目的：** 将拓扑复杂度与具体问题对应起来。

**页面正文：**

| 方案 | 能解决什么 | 新代价 |
|---|---|---|
| 电阻限流 | 最容易手算 | Vf/电源变化会改变电流 |
| Simple mirror（当前） | reference→current、机制清楚 | 有输出电压依赖与 mismatch |
| Cascode | 增大 output resistance | 额外 headroom、bias、面积 |
| Current DAC/feedback | amplitude 设定或误差调节 | matching、glitch、稳定性、校准 |

**讲者备注：** 第一版选择 six-MOS baseline 是为了能按器件学习并推进 layout。升级要由问题触发：例如 pre/post-layout 显示电流偏差大、低 duty settling 不足或阵列 reference fanout 过重，再设计相应改进。当前模型的 Vf 三点电流变化不大，不等于已经解决真实像素一致性。

**Source：** [baseline 比较](../research/driver-evidence.md#1-第一版选择)、[COCOA §5.3](https://bmurmann.github.io/COCOA/contents/partI/partI.5.html#current-mirrors)。**条件：** 工程判断与教学趋势；非商业性能结论。

## 第四部分：LED 模型与可复现实验（18–21）

### 18｜Synthetic LED：公开假设比“像真的”更重要

**教学目的：** 认识模型包括什么、每个参数是什么。

**页面正文：**

| 参数 | 值 | 当前含义 |
|---|---|---|
| N、RS | 3、50 Ω | I–V 斜率假设、串联压降 |
| CJO、VJ、M | 2 pF、2.5 V、0.33 | junction-charge 参数 |
| TT | 1 ns | SPICE transit/storage 假设 |
| EG、TNOM | 2.6 eV、27 °C | 温度方程参数与 nominal temperature |
| IS | 按目标 Vf 计算 | 100 µA/27 °C 单点锚定 |

**讲者备注：** 这些参数由本项目独立设置，尚未拟合真实样品。CJO 不是所有偏压下固定 2 pF；TT 不是实测光学 rise time；EG 不能用于宣布材料颜色。当前无颜色、面积、current density、EQE、自热、aging 或封装参数。默认 Vf=2.8 V，变体 2.4/3.2 V 都是 synthetic load。

**Source：** [microled.spice](../../analog/models/microled.spice)、[ngspice 47 manual §7.2](https://ngspice.sourceforge.io/docs/ngspice-47-manual.pdf)。**条件：** 所有 LED 参数均 synthetic。

### 19｜独立 DC 校准：先确认负载，再连接 driver

**教学目的：** 理解参数计算不等于 simulator 实际执行正确。

**页面正文：**

1. 单独用 100 µA DC source 驱动 LED，不连接 mirror。
2. 27 °C 下读取 actual Vf，分别核对 2.4/2.8/3.2 V。
3. 数值校准容差 <0.1 mV；当前三点误差约 1 µV。
4. 接入 driver 后再次读取 actual Vf，而不是照抄 target label。

**备注公式：** 先定义 thermal voltage `VT=(k/q)T`；由 `Vf=N·VT·ln(I/IS+1)+I·RS` 得 `IS=I/expm1[(Vf_target−I·RS)/(N·VT)]`，I=100 µA、T=300.15 K、N=3、RS=50 Ω。

**讲者备注：** 曾出现 N=2.2 时计算的 IS 过小、simulator 下限处理使不同 target 变为相同曲线的问题。干净日志无法替代独立 operating-point 检查。最终 N=3 是为了当前教育性模型与数值范围一致，不是从真实器件提取出的 ideality factor。DC 校准只证明本模型在一个规定点执行正确。

**Source：** [led_calibration evidence](../../evidence/phase1/led-calibration.json)、[led_is / calibrate_led](../../scripts/run_phase1.py)、[已记录的故障](../verification.md#模型校准故障与修正)。**条件：** 27 °C / 100 µA；不证明全 I–V/温度范围。

### 20｜可以跟着做：四个入口与各自输出

**教学目的：** 读者能运行 baseline 并定位输出文件。

**页面正文：**

```sh
make setup
make test
make sim
make evidence
```

- setup：锁定 Python dependencies、下载并校验 MOS models。
- test：bridge unittest + RTL self-check。
- sim：实际 RTL→PWL→SPICE，生成 raw data 与 checks。
- evidence：全部检查通过后保存仓库中的 compact evidence。

**讲者备注：** 当前已验证 Mac arm64、Python 3.12.13、Icarus 13.0、ngspice 47。新机器应先按 environment.md 安装并记录实际版本；Homebrew formula 没有固定 native binary。`build/` 是可再生的完整本地输出，`evidence/` 是紧凑公开证据。只看到图不能验收，必须核对 exit status、summary checks 与原始数据。

**小练习：** 先跑 `make test`，在 RTL log 找到 518 frames 与 133159 checks；再跑 sim，找 `duty_064` 的 events.csv 与 testbench.spice。

**Source：** [Makefile](../../Makefile)、[environment](../environment.md)、[uv.lock](../../uv.lock)。**条件：** 工具已安装、首次 model acquisition 需网络。

### 21｜如何量电流：先定窗口，再按时间积分

**教学目的：** 能解释 average current 的分母和计算方式。

**页面正文：**

- 首帧：2.5 µs；预热 2 frames。
- 测量：514.5–1538.5 µs，4 个完整 frames，时长 1024 µs。
- `Iavg = ∫ Ibranch(t)dt / 1024 µs`。
- Adaptive solver sample 密度不同，不能直接平均样本。

**主图：** warmup 与 measurement window 时间带，叠加非均匀采样点；在窗口边界标插值。

**讲者备注：** Runner 插值到精确窗口边界后进行 trapezoidal integration，同时核对 RTL 报告的 frame/window，防止修改时钟后继续用旧时间窗。Plateau current 是排除每个 edge 后 100 ns 的 on-state 中位数；不能代替整帧面积。公开 uniform CSV 是 200 ns 插值 view，原始 adaptive waveform.dat 保存在可再生 build 中。

**Source：** [windowed / average](../../scripts/run_phase1.py)、[verification](../verification.md#测量定义与门限)、[waveform CSV](../../evidence/phase1/waveform-duty064.csv)。**条件：** 4 complete frames；max timestep=200 ns baseline。

## 第五部分：看结果，也看证据边界（22–25）

### 22｜Nominal 结果：PWM 改变时间，平均电流跟着变化

**教学目的：** 用 measured full-on result 核对 duty-current 关系。

**页面正文：**

| Duty code | 时间比例 | 平均 branch current（µA） |
|---|---:|---:|
| 0 | 0% | 0.00000361 |
| 1 | 1/256 | 0.39494 |
| 64 | 25% | 25.32414 |
| 128 | 50% | 50.64903 |
| 192 | 75% | 75.97392 |
| 255 | 255/256 | 100.90310 |
| 256 | 100% | 101.29959 |

**主图：** [duty-current.png](../../evidence/phase1/duty-current.png)，配 full-on 与 quarter-duty 波形。

**讲者备注：** 对照值是 D×measured full-on average，不是 D×ideal 100 µA。Simple mirror output 略高于 IREF，不能将 nominal linearity 当作绝对 current accuracy。门限为 max(0.01 µA, expected×3%)，属教育性 regression criterion。Off 约 3.61 pA 是模型输出，不能将之承诺为实物 leakage。

**小练习：** 计算 101.29959×0.25=25.32490 µA，与 measured 25.32414 µA 比较，差约 0.00076 µA。

**Source：** [summary](../../evidence/phase1/summary.json)、[metrics](../../evidence/phase1/metrics.csv)。**条件：** typical、27 °C、VLED=5 V、IREF=100 µA、synthetic Vf=2.8 V、4 frames。

### 23｜改变 Vf 与供电：必须保留掉电流的条件

**教学目的：** 通过 negative control 识别 headroom 限制。

**页面正文：**

| 条件（full-on） | 平均 current（µA） |
|---|---:|
| VLED=5 V，target Vf=2.4 V | 101.7901 |
| VLED=5 V，target Vf=2.8 V | 101.2996 |
| VLED=5 V，target Vf=3.2 V | 100.7338 |
| VLED=2.9 V，target Vf=2.8 V | 49.3874 |

**主图：** [vf-current.png](../../evidence/phase1/vf-current.png)，低供电 current/VDS 结果单列强调。

**讲者备注：** 5 V 三点 spread 约 1.04%，但它只说明当前模型与条件。2.9 V case actual Vf≈2.74273 V、VDS≈0.15727 V，电流约为 nominal 的 48.75%。回归要求低于 nominal 90%，目的是确认模型能暴露 compliance 不足。3.0/3.3 V 也保留在 metrics。FF/SS 与 0/85 °C 是 full-on pilot cases，未覆盖完整 PVT×duty×Vf 组合。

**Source：** [summary](../../evidence/phase1/summary.json)、[metrics](../../evidence/phase1/metrics.csv)。**条件：** typical、27 °C，除特别标记外；Vf label 由 100 µA DC 校准定义。

### 24｜放大 PWM 边沿：branch current 包括充放电

**教学目的：** 区分电气 transient、plateau 与 optical output。

**页面正文：**

- 同时看 `pwm / pwm_b / bias / gate / led_k / Ibranch`。
- duty=64：current peak≈103.63 µA，minimum≈−2.24 µA。
- Branch current 含 conduction 与 charge/displacement 成分。
- 当前平均电流是 electrical brightness proxy；光学量待测。

**主图：** [waveforms.png](../../evidence/phase1/waveforms.png) 加 edge CSV 的局部放大图；所有轴明确单位。

**讲者备注：** 短暂负电流或 overshoot 可以由电容充放电产生，不等于出现“负光”或更亮光峰。当前 runner 未单独提取 conduction current。Duty=1/64 用 200 ns 与 20 ns maximum timestep 比较，积分相对变化低于 0.5% 门限；不能把此结论扩大到所有 transient peak 的收敛或电压应力检查。

**小练习：** 先在图上识别 gate 被 clamp 拉低的时刻，再查看 bias 有没有短暂 droop，不用只盯 average current。

**Source：** [edge-duty064.csv](../../evidence/phase1/edge-duty064.csv)、[summary](../../evidence/phase1/summary.json)、[verification](../verification.md)。**条件：** typical、27 °C、5 V、duty=64；有限 10 ns control edge。

### 25｜读证据：每一个“通过”只属于它的层次

**教学目的：** 能用分母、条件与文件判断当前完成程度。

**页面正文：**

- Bridge：7 tests；RTL：518 frames / 133159 checks。
- Phase 1：19 coupled runs + 3 LED DC，19 analog assertions。
- Full PDK 配对回归：36 transient runs + 3 LED DC，19 guards。
- 每个通过只支持对应层次、模型、条件与检查范围。

**讲者备注：** 不要把不同证据层次合成一个通过数字。旧Phase1有19个coupled transistor runs，另有3个独立LED DC校准；新full-PDK回归为17条件×2variants=34，再加仅RC variant的duty1/64两次50ns finer-step runs，共36 transient与3 LED DC。19 guards包括17个配对电流差检查和2个RC积分收敛检查。Standalone cell另有DRC0、LVS unique match与GDS roundtrip复核。这些不建立full PVT、Monte Carlo、数字timing closure或foundry signoff；两个PDK版本分别锁定。

**Source：** [RTL selfcheck](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/phase1/rtl-selfcheck.log)、[Phase1 summary](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/phase1/summary.json)、[full-PDK paired summary](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/layout/summary.json)、[postlayout回归实现](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/scripts/layout/run_postlayout.py)。**条件：** standalone analog cell；open-deck与full-PDK配对结果，不是完整芯片signoff。

## 第六部分：先补同一个像素的物理实现（26–28）

### 26｜Layout flow：每一步回答不同的问题

**教学目的：** 知道 schematic、DRC、LVS、PEX 各自验证什么。

**页面正文：**

- 实际 MAG/GDS 已生成，six-MOS cell DRC=0、LVS 唯一匹配。
- GDS roundtrip 后再次得到 DRC=0 与 LVS 唯一匹配。
- Magic RC extraction 覆盖 7/7 nets，配对回归 19 guards 全部通过。
- 这些是 standalone cell 证据，完整芯片 signoff 仍待完成。

**主图：** `netlist → layout → DRC → LVS → RC extraction → post-layout SPICE`；六个cell阶段均标实际结果，另列数字physical integration与foundry signoff待完成。

**讲者备注：** 先定义每个检查回答的问题：DRC检查所选deck的几何规则，LVS核对器件、尺寸与连接，PEX提取寄生后才进行post-layout电气对照。当前Magic 8.3.684得到DRC=0，Netgen 1.5.324得到Circuits match uniquely；GDS重新导入后两项再次通过。Magic RC extraction覆盖7/7nets，产生六MOS、59个R与43个C；full-PDK配对回归36transient+3DC、19guards通过。公开deck结果不替代foundry signoff，数字PWM physical integration、pads/ESD与实测尚未完成。

**Source：** [physical checks与计数](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/layout/summary.json)、[Magic DRC日志](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/layout/magic-generate.log)、[Netgen LVS日志](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/layout/netgen-lvs.log)、[GDS roundtrip DRC](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/layout/magic-roundtrip.log)、[GDS roundtrip LVS](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/layout/netgen-roundtrip-lvs.log)、[Magic RC extraction](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/layout/magic-pex.log)。**条件：** standalone analog cell；open-deck与full-PDK配对结果，不是完整芯片signoff。

### 27｜一个像素的 layout：先理解连接与 matching

**教学目的：** 能指出当前六 MOS cell 物理实现需要关注的节点。

**页面正文：**

- 真实 layout 实现了六个 MOS 与七个电气 nets。
- 相同 full PDK 下，schematic full-on 为 101.29959 µA。
- 加入提取 RC 后为 101.23651 µA，变化 −0.06227%。
- Duty=64 的 RC 平均电流为 25.30824 µA。

**主图：** 使用真实 [layout.png](../../evidence/layout/layout.png)，配同一full PDK的schematic/RC current对照表；实际报告链接列于source。

**讲者备注：** 用真实layout图对照第13页连接表，追踪bias、gate、led_k、pwm_b与body供电连接。Schematic符号最终需要well/substrate ties、contacts和metal实现；截图不能替代LVS网表。Post-layout比较必须固定同一full PDK：typical、27°C、VLED5V、Vlogic3.3V、IREF100µA、synthetic Vf2.8V，测量四个完整frames。全开平均电流由101.29959µA变为101.23651µA（−0.06227%）；quarter-duty为25.30824µA。此结果解释这块cell的提取寄生影响，不保证像素mismatch、阵列IR drop或实测精度。

**读图练习：** 对照第 13 页连接表，追踪 bias、gate、led_k、pwm_b；用 LVS extracted netlist 核对，而不是只看截图。

**Source：** [真实layout图](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/layout/layout.png)、[Magic source](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/layout/pixel_driver_layout.mag)、[extracted RC netlist](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/layout/pixel_driver_rc.spice)、[full-PDK paired current](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/layout/summary.json)、[postlayout日志](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/evidence/layout/postlayout-regression.log)。**条件：** standalone analog cell；open-deck与full-PDK配对结果，不是完整芯片signoff。

### 28｜4×4 之前：把单像素规则变成阵列规则

**教学目的：** 理解增加 16 个像素会新增哪些系统责任。

**页面正文：**

- 数据：16 个独立设定；address、shadow/active storage、frame commit。
- 通信：独立定义最小 command/register 接口，再做协议与 CDC testbench。
- 模拟：shared reference fanout、simultaneous switching、current spread。
- 物理：clock、power/ground routing、IR drop、阵列 DRC/LVS/PEX。

**主图：** `controller → receiver → shadow pixel settings → frame commit → 16 active settings → 16 PWM/driver cells`；示意全开/棋盘格/单点 pattern。

**讲者备注：** 这是下一阶段概念，没有已实现 register map 或商业协议。若直接保存本项目 0…256 duty encoding，需要 16×9=144 bits，enable 可以另设；未来也可独立设计 8-bit brightness code 的映射，两者需明确。若 all-on electrical current 仅按 baseline 粗估，16×101.3 µA≈1.62 mA，只是 LED 支路预算，不含 reference/logic，更不构成阵列验证。先完成单像素物理退出条件，再定义可执行的 4×4 接口与预算。

**小练习：** 在 4×4 图上选 pixel (row=2,col=1)，列出一次更新需要的“地址、数据、提交时刻”，暂不指定通信位序。下一阶段再把它写成独立 protocol spec 与 testbench。

**Source：** [4×4 exit criteria](../roadmap.md#3-44-array)、[长期概念](../design.md#长期概念尚未实现)。**条件：** 全页为后续概念/预算；先单像素 layout，未实现 4×4。

## 讲者补充：完整假设与参数账本

这份账本可放入技术报告或 PPT notes，不要求全部塞在投影片正文。参数变化应更新源码、DC 校准、coupled regression 与证据，不能只改文案。

| 类别 | 当前设定 | Source / 条件 |
|---|---|---|
| Digital timing | 1 MHz clock；256 slots/frame；counter 8 bits；duty 9 bits，0…256 有效、257…511 饱和 | `rtl/pixel_pwm.v`、`sim/rtl/tb_pixel_pwm.v` |
| Input update | duty/enable 只在 frame boundary 提交；高有效同步 reset；同 clock domain | `rtl/pixel_pwm.v`；无 CDC/handshake |
| Control bridge | 0/3.3 V PWL，10 ns rise/fall；实际 RTL timestamp 为 ramp 起点 | `scripts/run_phase1.py::pwl_points` |
| Startup/window | first known low=500 ns，延伸至 SPICE 0 ns；首帧 2.5 µs；预热 2 frames；测量 4 frames，514.5–1538.5 µs；stop=1540.5 µs | testbench、runner；启动假设明示 |
| Nominal rails/current | VLED=5 V，Vlogic=3.3 V，IREF=100 µA，ground ideal；IREF 从 vlogic 到 bias | `make_deck`；无片上 reference、供电阻抗、pads/ESD |
| MOS types/units | 原始 `nmos_6p0/pmos_6p0`，X subcircuit，D/G/S/B；W/L 以米表示 `u=10^-6` | `pixel_driver.spice`、锁定原始 model |
| MOS dimensions | XREF/XOUT 10/2 µm；XPASS/XCLAMP/XINV_N 2/1 µm；XINV_P 4/1 µm | 当前起始尺寸，未优化 |
| Model version | Google GF primitive commit `9f992d5a9186d1f7820c58f039c484ad35b2edea`；design.ngspice、sm141064.ngspice、LICENSE 的 SHA256 | `analog/models/pdk-lock.json`；仅 model subset |
| Statistics/corner | sw_stat_global=0；sw_stat_mismatch=0；nominal typical | `make_deck`；没有统计变化或 yield 结论 |
| Synthetic LED | N=3；RS=50 Ω；CJO=2 pF；VJ=2.5 V；M=0.33；TT=1 ns；EG=2.6 eV；TNOM=27 °C | `microled.spice`；不是实测参数 |
| LED calibration | target Vf=2.4/2.8/3.2 V 在 100 µA/27 °C；IS 用 explicit exponential relation 计算 | `led_is`；IS≈3.938153e−18/2.272535e−20/1.311380e−22 A |
| Solver options | Coupled reltol=1e−5、abstol=1e−12 A、vntol=1e−7 V；DC calibration reltol=1e−7、abstol=1e−14 A | `make_deck`、`calibrate_led` |
| Transient | `tran 100n STOP 0 MAXSTEP`；MAXSTEP baseline=200 ns；duty 1/64 refined=20 ns | ngspice adaptive samples；100 ns output request 不是严格 uniform samples |
| Measurements | Branch current=i(VSENSE)；精确窗口边界插值+trapezoidal integral；plateau 排除每个 edge 后100 ns，on 条件 pwm>3 V | `run_case`；未分离 conduction current |
| Nominal cases | duty=0/1/64/128/192/255/256；disable(duty=128,enable=0) | `summary.json`，每 case 四帧 |
| Variation cases | Vf=2.4/3.2 V at 5 V；VLED=2.9/3.0/3.3 V at target Vf=2.8 V；FF/SS at 27 °C；0/85 °C at typical；全部 full-on | 少量 pilot cases，不是全组合 PVT |
| Linearity gate | error ≤ max(0.01 µA，measured expected×3%)，expected=D×measured full-on average | 教育性门限；不保证 IREF accuracy |
| Off/calibration gates | abs(Iavg)<1 nA；isolated DC abs(ΔVf)<0.1 mV；coupled full-on abs(ΔVf)<10 mV | `scripts/run_phase1.py`、summary checks |
| Headroom/convergence gates | VLED=2.9 V current < nominal×0.9；200→20 ns integral relative change <0.5% | 故意暴露失败余量；不保证 peak convergence |
| Public trace view | waveform-duty064.csv 为两 measured frames 的 200 ns uniform interpolation；edge-duty064.csv 为一个 turn-on 周围原始 adaptive samples | `evidence/phase1/`；完整 raw output 可在 build 重生 |
| Tool evidence | Darwin arm64；Python 3.12.13；Icarus 13.0；ngspice 47；Python dependencies uv.lock | `summary.json`；native binary 未由 Homebrew pin 固定 |
| Current limitations | 没有真实 LED fit、optical/thermal/aging、full PVT、mismatch、noise、electrical stress signoff、current reference circuit、physical digital glitches/timing、完整芯片/MPW 接受证据 | `docs/design.md`、`docs/verification.md`、`docs/roadmap.md` |

## 公开质量记录：source-hashes 只追踪可复现源码

本稿编写时发现原 source manifest 会纳入 macOS Finder 的 `.DS_Store`。主任务已修复为八项明确源码输入的 allowlist，排除本机 metadata，并增加 provenance 回归检查。Bridge tests 从六项增为七项；重新执行后其余 RTL、transistor 和 analog checks 保持通过，电气 metrics 与原 baseline 一致。

当前 `evidence/phase1/source-hashes.json` 已记录更新后的 runner SHA256。本稿的课程与结果仅引用可公开的源码和 `evidence/phase1` 文件，不引用本机 metadata 或未保存在仓库的局部图作为公开证据。这项改进服务于课程复现，课堂主线仍是数字控制与模拟电路。

## 读者课后检查表

完成 01–10 页后，应能手算 duty=64 的高电平 slots，并解释帧中更新、reset 与 enable 的时刻。完成 11–19 页后，应能从六 MOS netlist 追踪 bias/gate/led_k，解释 headroom，并指出哪些 LED 参数只是 synthetic assumptions。完成 20–25 页后，应能重跑 baseline、读取四帧积分结果，找出 negative control 与 timestep refinement。完成 26–28 页后，应能区分 DRC/LVS/PEX 的证据，并说明 4×4 接口、reference 与供电为什么需要新增验证。
