# 真实晶体管 reference：先证明能工作，再看精度来自哪里

日期：2026-10-13。这里是两个独立的 **pre-layout reference 候选**，均不修改原来的 100 µA ideal IREF 基线。外部 supply/PWM/测量夹具可以是理想电压源，但候选内部没有理想运放、受控补偿电流源或强制启动脉冲。最终数值以 [候选索引](../../evidence/reference/summary.json) 及各自 summary 为准。

## 1. 接口与范围

像素的 diode-connected MREF 需要一股从 Vlogic **流入 bias** 的电流，所以两个候选都使用 PMOS sourcing output。不能直接拿一个 NMOS sinking current reference 替换原 IREF。

| 候选 | 接口 | 参考精度来自哪里 | 当前适用结论 |
|---|---|---|---|
| [beta multiplier](beta_multiplier.spice) | `XREF vdd 0 bias beta_reference RL=13.5u` | MOS β、器件比例和 PDK poly 电阻 | 能自行启动；绝对 PVT 精度明显失败 |
| [VSET servo](vset_servo.spice) | `XREF vdd 0 vset sense bias vset_reference`；外接 `VSET vset 0 .5`、`RSET sense 0 5k` | 明确的外部 VSET/RSET 边界，真实 MOS amplifier 负责跟随 | 精度和动态结果需分别读 servo summary；不是片上 bandgap |

两个接口均**没有 enable、POR 或电源监测**。PWM off 后 reference 仍工作。独立 fault gate 的作用是阻止 LED 输出，不会自动消除 reference 功耗。这里接入的是现有六 MOS analog PEX，直接把 actual RTL replay 施加到 PWM pin；没有把这个结果写成完整 joint buffer／digital／PG 仿真。

本轮以 100 µA reference 为研究对象。0.1–7 mA 的 output bank 尺寸、pass-device 驱动、headroom、热量和短脉冲能量由另一组实验检验，不能从这里外推。

## 2. Beta multiplier：为什么不等于精密电流源

核心 NMOS 为 N1=20/4 µm、N2=80/4 µm，W/L 比为 1:4；PMOS 镜像三支各 40/4 µm。N1 drain/gate 为 nb；N2 drain 为 pg，source 经 XRSET 接 ground。所有 NMOS bulk 接 ground，N2 的 body effect 保留在模型里；PMOS bulk 接 VDD。

强反型平方律、两支电流相等、忽略 body effect／channel-length modulation 时：

`I ≈ 2/(β1·R²) · (1−1/√K)²`，其中 `K=4`，`β1=µn·Cox·W1/L1`。

这个式子解释了供电依赖为何较小，也直接说明 **R 和 mobility 变化会改变绝对电流**。它只是手算方向，不代替 BSIM。实际只在 TT／27°C／3.3 V／output clamp 1.4 V 校准一次；15 次二分后按 10 nm 网格选择 poly 长度 13.5 µm、宽度 2 µm。实际使用 `ppolyf_u`（body/end resistance、TC 和 substrate capacitance），不是人为固定的 2.5 kΩ 理想电阻。PDK 的 resistor corners 必须与 MOS corners **分别加载**。

启动三管：弱 PUP 先把 su 拉高，NKICK 把 pg 拉低、开启 PMOS；nb 上升后 NSENSE 把 su 拉低，NKICK 退出。PUP/NSENSE 静态支路仍耗约 4.37 µA。典型输出 100.0516 µA，但 VDD 总电流约 304.587 µA（含输出和两支核心），约 1.005 mW。

135 点 MOS5 corners × resistor3 corners × T(0/27/85°C) × VDD(2.97/3.3/3.63 V) 得到 **53.67–234.00 µA，126/135 点不满足 ±5%**。只看 TT／典型电阻，温度 0→85°C 也从 85.69 变成 134.03 µA。换 MOS 的 W/L 不会自动消除这类 reference 误差。

9 个 cold ramps（100 ns／10 µs／1 ms，各3 envelope）及3个硬零态恢复完成；关闭 NKICK 的3个负对照停在 pA 级。这证明 `.op` 给出非零电流不足以验证启动。耦合 PWM 的最低码电荷误差相对同条件 Ifull：TT −0.250%、SS/85°C −1.611%、FF/0°C −0.218%，均在 ±2% 内；**相对 PWM 电荷通过不抵消绝对电流失败**。

## 3. VSET servo：用反馈管理电流，公开外部条件

目标 `ISET=VSET/RSET=0.5 V/5 kΩ=100 µA`。P-channel differential pair 比较 VSET 与 VSENSE；NMOS mirror load 输出 n2；NMOS common-source 第二级反相后驱动 ctrl。VSET 大于 VSENSE 时，n2 上升、ctrl 降低、PMOS REG 向 RSET 供更多电流，构成负反馈。相同 W/L 的 PMOS OUT 把该电流复制到像素 bias。

实际10 MOS 端口与尺寸逐行保留在 netlist。PMOS input pair、REG／OUT 为 100/10 µm；NMOS input load 为 50/10 µm。最终第二级 NMOS 为20/1 µm、diode PMOS load为100/10 µm，Miller CCOMP=3 pF。diode PMOS 加 RBIAS=100 kΩ 产生真实 tail bias。RBIAS 和 CCOMP 是显式 schematic passive 元件，尚无物理实现／TC／寄生；不能称已经完成单片版图。电路图中要保留它们，不能隐藏为理想 bias current。

外部 VSET ±0.1%、RSET ±0.1% 是**跨声明温度／供电范围的临时总误差边界**，没有选定或测量真实元件。若只保证室温初始精度，这个预算就不成立。最坏一阶误差约 ±0.2%，然后再叠加 amplifier tracking error、PMOS mirror output-resistance error、mismatch 与动态误差。

典型输出约99.25 µA，VSENSE约0.499328 V：VSENSE 跟随误差和 OUT/REG 镜像误差需要分开。180 点固定角／温度／供电和两项外部边界的四个符号组合为 **98.9420–99.5196 µA，0/180超±5%**。接入像素后18个DC检查通过；nominal LED电流99.9673 µA，包络及外部误差组合98.8833–101.0029 µA。三包络最低码电荷误差为−0.2529%／−0.6548%／−0.1966%，10→2 ns步长变化最大约0.00000345%。这只是这些模型条件下的可行性，不是制造良率；没有本轮 local mismatch／噪声／PSRR／AC loop-gain 与 phase-margin 结论。

第一个弱第二级原型（N10/4、PLOAD2/10）发生持续振荡，不能用正确 `.op` 宣称成功。原始失败保留在 `build/reference/servo-dynamic-probe-34nwnm7z`，其 `candidate-failed.spice` 固定原尺寸。加强实际第二级 gm 后才执行最终矩阵；并未用理想 amplifier 或电流补偿掩盖失败。最终电路的 hard capacitor initial states 也可能出现负电压或电流尖峰；稳定恢复不代表初态过程已满足安全限制。

9个cold ramps、6个hard initial states及3个VSET step均恢复，最长建立约0.783 µs，但100 ns冷启动的FF参考电流峰值约294.8 µA。这里的负载是diode-connected MREF，**没有连接LED**，不能把这个数称为LED发光尖峰。

逐管端压和迟到的VSET见 [servo-boundaries.json](../../evidence/reference/servo-boundaries.json)。正常cold ramp中最大外部端压差约3.286 V。Hard low初态的VSENSE最低−0.703 V是servo电阻／PREG drain节点；它使PREG drain-body反偏，PD2则在gate看到此电压，不能据此直接推出LED反向或某只MOS体结正向。实际逐端检查另外发现ctrl超过VDD，PLOAD drain-body forward polarity可达+0.483 V；最大PREG |VGD|约4.789 V。没有真实layout junction面积／well阻抗，这些数值不构成SOA通过。

VSET=0也**不是关断控制**：VDD已经开启时，参考电流仍约0.255 µA；VDD先起而VSET迟20 µs的测试中，VSET未建立前参考电流峰值约148 µA。VSET到达后约0.323 µs恢复至99.274 µA。系统应使用独立fault路径，而不能把外部参考电压为0当成失效安全。

## 4. 重现与证据边界

```sh
.venv/bin/python scripts/reference/reproduce.py
```

需要既有 locked full GF180MCU D PDK、ngspice47、Icarus和 NumPy 环境。每次运行创建独立 `build/reference/` 目录，冻结源、RTL、LED、analog PEX 和两个 PDK 文件。紧凑的成功／失败数值和 hashes 保存在 `evidence/reference/`；不丢弃未满足预算的点。

- `beta-summary.json`／`servo-summary.json`：条件、门槛、实测模拟结果、源hash和限制。
- `beta-validation.json`／`servo-validation.json`：独立分段积分复算、PVT极值与失败计数、启动终态／ripple、reference外部端压极值。端压记录不是foundry可靠性签核。
- `servo-boundaries.json`：正常supply ramps、刻意的hard initial states与VSET建立顺序分别记录逐管signed VGS/VGD/VDS/VGB/VSB/VDB，不把体结方向、电压幅度和junction电流混为同一事实。
- `servo-coupled-conditions.json`：从18份实际DC testbench重新读取VSET、RSET、rail、corner及温度，保留各点testbench/data hash，补齐误差符号映射。
- DC 保持 reltol=1e−7、abstol=1 fA、vntol=1 nV。Servo＋PEX 在第一个 1 ns PWM edge 遇到极严容差的 timestep-too-small，Trap/Gear 原始失败均保留。其 transient 使用 reltol=1e−6、abstol=1 pA、vntol=0.1 µV，并继续执行10→2 ns maxstep 收敛检查；没有改变电路或 ±5%／±2%门槛。
- 新 reference 没有 layout/DRC/LVS/PEX；新 MOS diffusion area/perimeter 为默认0，intrinsic BSIM charge仍在。因此这里的建立时间与 overshoot 是 schematic 模型结果，不能升级为 physical bandwidth 或 silicon startup。
- Synthetic LED 的电流和电荷不是测量光功率。既有像素通过版图验证，也不会把新增 reference 的证据自动升级。

主源与版本定位见 [sources.json](sources.json)。其中 GF180 的公开 poly sheet resistance 使用5 µm宽／100 µA表征条件；本候选的2 µm宽使用实际模型 width/end correction。PRES.1最小宽0.8 µm、PRES.8最大1 mA/µm仅用于参数合理性初查，不能代替 reference 的完整物理检查。

## 5. 有限 junction geometry 敏感性对照

[vset_servo_with_junctions.spice](vset_servo_with_junctions.spice) 是单独的假设候选：每只新 reference MOS 的每侧 diffusion length 取0.44 µm，`AD=AS=W×0.44 µm`、`PD=PS=2×(W+0.44 µm)`。没有改变W/L、VSET、RSET、RBIAS或CCOMP，也没有替换已冻结的主参考源。它不能称为提取的面积／周长，不能升级为 physical PEX。

NominalDC仍约99.2518 µA。TT/FF 100 ns cold ramp的参考输出峰值从155.565/294.784变成160.304/302.139 µA；硬初态恢复仍小于0.707 µs。三包络最低码电荷误差最大约−0.65757%，A/B average current变化最大约0.00372%，10→2 ns复验一致。

对所有10只MOS保存并检查ngspice `@m.xref.xNAME.m0[ibd]`／`[ibs]`。TT hard-low的PLOAD drain junction正向模型电流峰值由默认零面积的0.4828 pA（对应gmin×V）增加为3.432 nA，forward-polarity voltage由+0.4828降至+0.4757 V；FF对应约0.1135 nA。实际端压、模型junction电流及substrate注入／latch-up风险是不同证据：此处只得到前两项的有限假设模型结果，不能以nA数值推出已满足注入或SOA要求。

结果见 `junction-sensitivity.json`／`junction-zero-controls.json`；独立复算见 `sensitivity-validation.json`，包括6条duty1积分、10管junction-current extrema、3个VSET顺序的平均电流。Standalone startup 的MREF负载保持原先默认结面积，以隔离reference几何变化；耦合PWM使用既有真实analog PEX junction geometry。后续必须以实际reference layout重提取，并考虑well/substrate阻抗、guard ring、package及真实外部元件。
