# 最小C：真实MOS Gray译码与三单元PAM4电流输出

2026-10-25。C已从概念图推进为可运行的**原理图级49 MOS电路**，完成四档DC及逐器件端压探测。它没有对应本轮GDS/PEX、PAM4眼图、动态转换或光学BER结果；本文件不为A/B/C排序。历史B的真实PEX资格不能转移到这个新网表。

## 1. 冻结接口与一次名义校准

正式源：[route_c.spice](../../analog/fair_driver_v1/route_c.spice)，不包含机器相关`.include`路径。

```spice
.subckt fair_c D0 D1 OUT VIN VDD VREF VSS DISABLE params: RSET=20k WUNIT=1.92u RINL=8u
```

调用方提供`common.spice`中的参考模块，接口必须为：

```spice
.subckt nrz_vi_reference VIN VSS VSET SENSE IOUT IPB IN2 ICTRL DISABLE KRET
```

探测直接包含现有[vi_reference_switched_keeper.spice](../../analog/nrz_reference_v2/vi_reference_switched_keeper.spice)，其中10 MOS为反馈参考，另2 MOS分别钳位BIAS及控制keeper返回。正式公共模块应保持同样电路与结几何。VREF是外部2.5 V电压基准边界，不能称为本电路已实现片内bandgap；VIN约5 V，VDD为独立逻辑电源。

源文件保留原始默认RSET=20 kΩ、WUNIT=1.92 µm；共同比较运行时使用**仅TT选定后冻结**的参数：

| 参数 | 最终传入值 | 说明 |
|---|---:|---|
| RSET | 20125.423810323304 Ω | 先以TT低档25 µA调节；连续名义阻值，不等于已选商业器件精度 |
| WUNIT | 2.02 µm | 再以TT高档100 µA调整，落在5 nm宽度网格 |
| RINL | 8 µm | 三单元均相同；A/B/C新原理级候选统一阻尼 |
| WREF / WBASE、L | 2 µm / 2 µm、1 µm | 固定，不另调中间电平 |

RSET与WUNIT是与A的两电压设定、B的RSET/WTAIL相等的两项名义自由度。只在TT/27°C、VDD3.3 V、VIN/VLED5 V、VREF2.5 V校准；SS/FF及中间电平没有重新拟合。调用示例：

```spice
XDRV D0 D1 OUT VIN VDD VREF VSS DISABLE fair_c RSET=20125.423810323304 WUNIT=2.02u RINL=8u
```

最终参数及来源锁定：[calibration-r2-esr.json](../../build/fair-driver-v1-c-probe/calibration-r2-esr.json)。此前无ESR的校准JSON保留为父记录，新增0.5 Ω补偿ESR后未再调参数。

## 2. 电路与计数

| 功能 | MOS数量 | 实现 |
|---|---:|---|
| 反馈参考＋DISABLE/keeper | 12 | 全部06v0；复制既有独立电气参考 |
| REF二极管＋基础电流BASE | 2 | nfet_03v3，W/L=2/1 µm |
| 共享`NB0=!D0` | 2 | 06v0 CMOS inverter |
| `T1=D1 OR D0` | 6 | NOR2＋inverter；串联PMOS各W7.86 µm |
| `T2=D1` | 0 | 实际同一net，不用理想受控电源造信号 |
| `T3=D1 AND NB0` | 6 | NAND2＋inverter；串联NMOS各W5 µm |
| 三个相同转向单元 | 21 | 每个1个03 tail＋2个06 steer＋两级共4个06 buffer |
| **合计** | **49** | **5个03v3 NMOS、24个06v0 NMOS、20个06v0 PMOS** |

所有普通buffer及steer保持N W/L=2.5/0.7 µm；buffer P W/L=3.93/0.55 µm。译码串联栈加宽是本候选固定设计选择，用来减小串联导通电阻，不根据电平/PVT调尺寸。每个单元在译码输出后有真实PDK高阻poly RIN（W=1 µm、L=RINL），随后两级buffer得到GB/GP，再驱动LED/dummy两只06v0 NMOS。RIN是PDK电阻，其他外部网络是明示名义R/C。

三个独立dummy各由VIN经150 kΩ供电；这是旧75 µA总dummy/50 kΩ按三个25 µA单元拆分的初始headroom选择。未导通dummy接近5 V，因此steer使用06v0；没有把全部MOS都视为6 V器件。三只tail共享BIAS、各WUNIT/L1 µm，不能把3个单位的瞬态/失配误差当作理想相加。

外部网络在本层次网表中计入端口电流，但**不代表片内布局**：VREF→200 kΩ/50 kΩ分压，RIBIAS100 kΩ，RSET，`IN2—0.5Ω—CC—150pF—VSS`，三路150 kΩ dummy，以及OUT→1.8 MΩ→KRET的受控keeper。共9个名义电阻、1个补偿电容，另有3个PDK RIN。外围电源有限源阻抗由root的共同harness加入，不能把本DC探测的理想VIN/VDD当成最终供电条件。

每只MOS的结几何统一为`AD=AS=W×0.44µm`、`PD=PS=2×(W+0.44µm)`。tail使用参数表达式，WUNIT改变时几何同步改变；该假设不是新提取结果。正式网表没有行为译码、理想电流源或温度计码PWL；只有D0/D1外部数据、PDK MOS、R/C及明确参考层次。探测中的MicroLED仍为既有冻结静态I–V行为模型，它属于外部负载，不是隐藏输出驱动。

## 3. Gray真值与DC结果

| level | D1D0 | T1 T2 T3 | 目标电流 µA |
|---:|---|---|---:|
| 0 | 00 | 000 | 25 |
| 1 | 01 | 100 | 50 |
| 2 | 11 | 110 | 75 |
| 3 | 10 | 111 | 100 |

探测使用相同冻结MicroLED静态模型、CLED200 fF、LED串联1 Ω/0.5 nH；DC中这些储能元件不提供带宽证据。数字高电平随VDD，DISABLE=0，外部VREF源阻抗0.2 Ω、GPIO100 Ω；VIN/VDD为直接DC源。RIN PDK角与对应MOS角配对。没有统计失配、外部R容差/温漂、噪声或光学模型变化。

最终实际源含0.5 Ω ESR，未逐角重调：

| 条件 | L0 µA | L1 µA | L2 µA | L3 µA | 最大绝对目标相对误差 |
|---|---:|---:|---:|---:|---:|
| TT / 27°C / VDD3.3 V | 25.002035 | 50.063372 | 75.054740 | 99.998475 | 0.126745% |
| SS / 125°C / VDD2.95 V | 24.914783 | 49.822621 | 74.685499 | 99.503619 | 0.496381% |
| FF / −40°C / VDD3.65 V | 25.107960 | 50.288019 | 75.386982 | 100.434835 | 0.576038% |

12个操作点均单调、DC译码真值正确、四电平电流在±1%目标内；49只MOS均通过按型号的六对端压项目筛查：03v3 3.63 V、06v0 6.0 V。**电流误差和端压是两个不同判据**。这些静态结果不覆盖上电、DISABLE释放、动态过冲、体结注入、SOA或foundry可靠性。

定义端点LSB为`(I3−I0)/3`；`DNL[k]=(I[k+1]−I[k])/LSB−1`；`INL[k]=(I[k]−I0−k×LSB)/LSB`。端点方法去除了增益/偏移，因此同时保留上表绝对电平误差，不能用小INL/DNL掩盖整体幅度不准。

| 条件 | DNL[0→1,1→2,2→3] / LSB | INL[0,1,2,3] / LSB |
|---|---|---|
| TT | +0.00250108, −0.00029783, −0.00220325 | 0, +0.00250108, +0.00220325, 0 |
| SS | +0.00180563, −0.00000274, −0.00180289 | 0, +0.00180563, +0.00180289, 0 |
| FF | +0.00283170, −0.00039809, −0.00243361 | 0, +0.00283170, +0.00243361, 0 |

初始20 kΩ/1.92 µm下TT为25.156780/49.020889/72.819645/96.573697 µA，最高档低3.4263%；这组未校准结果与SS/FF结果均保留。校准步骤为先RSET20.125424 kΩ，再WUNIT2.03 µm试点，最后WUNIT2.02 µm。中间档没有独立参数。原始RIN58 µm探测`dc-r1`同样保留，仅为历史单因素记录，不作为当前速度限制或PEX依据。

## 4. 必须覆盖的12种有向转换：计划，尚未运行

| 起始level / D1D0 | 目标level / D1D0 | 改变输入bit数 |
|---|---|---:|
| 0 / 00 | 1 / 01 | 1 |
| 0 / 00 | 2 / 11 | 2 |
| 0 / 00 | 3 / 10 | 1 |
| 1 / 01 | 0 / 00 | 1 |
| 1 / 01 | 2 / 11 | 1 |
| 1 / 01 | 3 / 10 | 2 |
| 2 / 11 | 0 / 00 | 2 |
| 2 / 11 | 1 / 01 | 1 |
| 2 / 11 | 3 / 10 | 1 |
| 3 / 10 | 0 / 00 | 1 |
| 3 / 10 | 1 / 01 | 2 |
| 3 / 10 | 2 / 11 | 1 |

完整最小覆盖序列可为`0,1,0,2,0,3,1,2,1,3,2,3,0`，恰好包含全部12条有向边。必须向真实D0/D1施加Gray输入，不得直接驱动T1/T2/T3绕过14 MOS译码。相邻电平Gray码只改变1 bit，但任意符号跳变仍可能改变2 bit，不能只测相邻电平而宣称无毛刺。

动态计划先使参考稳定并满足外部DISABLE合同，再覆盖全部边；在共同符号率/20 ps边沿下分别检查零偏斜和两个数据bit的±20 ps、±100 ps偏斜。偏斜数值是预声明工程负控，不是实测数字接口规格。T2路径没有NOR/NAND译码延迟，T1/T3有额外门延迟；预期可能出现温度计码瞬态不一致，需测而非假定被Gray消除。正式比较若PAM4承载与NRZ同gross吞吐，应使用一半符号率、三个阈值及同一通道/RX传递函数；不能沿用单个62.5 µA二值判决器后声称PAM4接收通过。

逐转换记录：实际源/目标电流、有效相邻LSB，导电LED峰值/谷值、相对源目标包络的超调，转换电荷，建立到目标±5%有效LSB的时间，T1/T2/T3及GB/GP的交叠/空挡，所有端口正向/返回/净能量。验收数值应在共同harness中冻结，不能事后放宽；本文件仅给覆盖与观测方案。

## 5. 节点与能量边界

- 外部端口：D0、D1、OUT、VIN、VDD、VREF、VSS、DISABLE。电源必须包括LED供电、VIN、VDD、VREF，以及两路数据和DISABLE源的端口功率；译码所有门均直接接VDD/VSS，不能遗漏其动态功耗。
- 参考/保护：BIAS、VSET、SENSE、IPB、IN2、ICTRL、CC、KRET；参考内部`XREFMOD.IN1/ITAIL`。重点观察参考环启动、补偿节点保持/掉电及钳位释放。
- 译码：NB0、N_OR、P_OR、T1、N_AND、N_STACK、T3；T2就是D1的net别名。全部MOS的D/G/S/B已列入DC探测的`plan.json`。
- 每单元j=1..3：DIj、GBj、GPj、VXj、DUMMYj，共15个节点；分别观察tail/steer电流与tail compliance。必要器件电流向量应由正式harness加入，当前probe保存端口电流、全部MOS端电压和导电LED电流，没有把未保存的瞬态支路电流当已验证。
- 外部负载：LED_A、LED_K、导电LED电流与串联支路电流。导电电流不包含CLED位移电流，也不等同光功率；本次没有光学消光比或BER数据。

上游电压源本身仍是明确边界；外部基准内部Iq、转换效率、数字serializer/clock、真实光学RX未在此DC模型实现。probe的DC总功率是该工作点所有端口功率，不是动态pJ/bit，也不能用固定速率直接相除代替含译码转换的瞬态能量积分。DISABLE采用已有受控钳位和keeper接口，**未验证C的启动保护，且不是自主POR/ready**。

## 6. 复现、来源与保存

运行入口：[c_probe.py](../../scripts/fair_driver_v1/c_probe.py)。每次必须用全新`--work`，已有run不可覆盖；使用NRZ专用锁，每次只运行一个ngspice。初始两轮、TT中间校准和最终DC都在[探测目录](../../build/fair-driver-v1-c-probe/)保留。各run在执行前保存plan/source快照；每个波形即时无损gzip、解压SHA复核后，仅移除本run新生成的未压缩副本。

```bash
build/layout/venv/bin/python scripts/fair_driver_v1/c_probe.py \
  --work build/fair-driver-v1-c-probe/reproduce-selected-new \
  --rset 20125.423810323304 --wunit 2.02e-6
```

此命令重做12个DC操作点，不运行动态PAM4或EDA。最终结果：[selected-esr-r7/summary.json](../../build/fair-driver-v1-c-probe/selected-esr-r7/summary.json)；完整四电平码表、INL/DNL、全部器件端压、日志、退出码和源哈希在对应子目录。当前保留数据约11.23 MB，低于200 MiB约束。

| 冻结对象 | SHA-256 |
|---|---|
| `analog/fair_driver_v1/route_c.spice` | `096ecd179eadf8193896b6c1177d845c666bbe93903ccf5a99020593c6da8b1d` |
| 复用参考源码 | `280abc05195bc5ddc665379023999b55f4ec4a29d007eabd87c2f5ed9cc03fc8` |
| `calibration-r2-esr.json` | `23e002d395f787ac8d07618c1663094723f0a4c10744680ee737ac0bd8765dfd` |
| 冻结LED静态模型 | `51dabe11ee4a3fbbb7bf387e422eaa4faa0203d149a3c5701ab1dfaeba9734cc` |

root的共同harness将加入一致的有限电源/封装边界及能量记账，再比较A/B/C。当前DC结果只证明这个具体原理级候选可以产生单调且接近目标的四档电流；不得据此宣布C优于A/B、实现低BER或达到任何PAM4速率。
