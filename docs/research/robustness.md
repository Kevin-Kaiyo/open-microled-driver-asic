# v0.4：实际输出路径的电气边界检阅

日期：2026-10-05。先读[总体架构](research-report.md)，再读[共同 PEX 的几何、器件和投影说明](joint-pex.md)。本页回答：把真实版图输出级接入单像素后，电流与最低灰阶是否仍成立，以及哪些供电和控制假设还不能用于下一阶段。

**结论：在预先声明的三个 MOS／电压／温度研究条件和静止邻居条件下，实际提取的信号路径通过既有工程门槛。实际 reference generator、真实上电保护、整个数字晶体管路径和完整 PDN 仍未闭环。下一步应优先实现 reference／关断／供电边界，再扩展阵列。**

## 1. 从架构到实际模拟边界

链路是 `RTL 逻辑事件 → 最末级 buf_2 输入 → 实际输出级与金属 → 六 MOS analog pixel → LED 电气负载`。本轮切口在末级 buffer 的输入 I；没有模拟上游 flip-flop 的 transistor 波形、C-Q delay、整个数字切换功耗或 reset 的 transistor-level 行为。输入是实际 RTL 的逻辑事件，施加1 ns全摆幅 ramp；上电探针将该事件乘以当时 logic rail 电压。这是刺激合同，不是 voltage-aware FF 或 POR 的实现。

本轮有一个改变研究前提的重要发现：v0.3连接了 standalone analog RC 的旧formal入口；共同 GDS 的数字 PWM 实际从 analog 金属右端进入。新版整体使用 **12 MOS（buffer6＋analog6）、45 signal R、77 aggregated C、34明确 neighbor ports**，替换旧 buffer／analog RC／digital SPEF／link 四部分。没有把新寄生叠加到旧寄生上。Pre/post差异包含入口与联合寄生表示的改变，不能全部归因于buffer junction。

实际PWM入口为 `[119.99,111.52] µm`，`PWM_DRIVE` 是实际 Z pin。Nominal输出到入口的等效金属R为17.394804 Ω，explicit C总和86.12439 fF；这些C不含MOS intrinsic／junction capacitance。Actual AD／AS／PD／PS由提取给出，并由锁定GF180模型计算junction行为。Nominal模型SHA为 `03813e63e64bf505570dbd1f81e6809366e6b4d31bbee129c28022956e1cc623`。

该模型仍是 **selected signal-path cutout**：source/body/PG电阻理想化，PG-only电容投影排除，包括19项固定PG模板校正负C；保留signal↔PG C。稳定固定rail下，这个投影适用于所选信号路径。上电或rail变化时，实际PG metal／well充电、内部PG压降与完整cell/chip能量不在模型内；本轮startup不能升级为完整真实12MOS cell／芯片PG功耗。具体保留、排除及几何来源见[提取合同](../../evidence/joint-pex/nominal/summary.json)与projection ledger。

34个neighbor有真实hierarchical身份，但多数是fillcap floating导体或FF内部节点。默认以理想源固定0 V，只是人工quiet-clamp条件；startup另做全部跟随logic rail的高电位bracket。两者都不证明真实floating或切换邻居的安全性；没有已识别的clock neighbor，因而没有宣称完成clock crosstalk。

## 2. 条件和门槛先声明

保持analog mirror20/4 µm、IREF100 µA、1 MHz clock、256 slots/frame。完整spec在[预声明文件](../specifications/electrical-v0.4.md)。三组研究条件如下，不称matched STA corners；原Liberty条件与这里的温度／供电并不相同。

| MOS条件 | 温度 | Vlogic | VLED | Main RC |
|---|---:|---:|---:|---|
| typical | 27 °C | 3.3 V | 5 V | nominal |
| ss | 85 °C | 2.97 V | 4.5 V | nominal |
| ff | 0 °C | 3.63 V | 5.5 V | nominal |

Pre/post使用同一RTL事件、LED、IREF和输入ramp。Warm-up两个frame，在514.5–1026.5 µs积分两个完整frame；测试duty0/1/64/255/256。工程guard：满开100 µA±5%；最低码相对 `Ifull×1/256` 的电荷面积±2%；off数值guard<1 nA；actual Liberty定义30→70% rise／70→30% fall≤3 ns；50% high/low pulse≥950 ns，两个frame必须各有对应脉冲，即共2 rise＋2 fall。

Post duty1另将maxstep10→1 ns，平均电流与charge相对改变量≤0.2%；两个frame平均电流差≤0.2%。仅均值绝对值<1 nA的near-zero案例用1 nA绝对数值容限，最低灰阶仍用严格相对门槛。记录节点端点状态，但两个frame平均一致本身不证明所有内部电荷已达到周期稳态。

合成LED先独立校准100 µA／27 °C到2.8 V，然后才耦合MOS。它仍是synthetic electrical/dynamic model。真实LED dataset只用于另列的static DC，不用于上电、温度或光学预测。

## 3. 实际电气结果

全部最终运行共66 transient、28 circuit DC，以及3次独立synthetic LED校准。短probe10 transient／12 DC；main37 transient／12 DC与146个预声明guard；boundary19 transient／4 DC。Boundary的“数值完成”不等于系统资格通过。

| 条件／nominal RC | Pre full-on µA | Post full-on µA | Post duty1 µA | Duty1面积误差 | Rise／fall ns |
|---|---:|---:|---:|---:|---:|
| typical／27 °C／3.3 V／5 V | 100.695401 | 100.752788 | 0.392575663 | −0.251524% | 0.271417／0.144443 |
| ss／85 °C／2.97 V／4.5 V | 100.068779 | 100.112984 | 0.388401993 | −0.681304% | 0.463540／0.237175 |
| ff／0 °C／3.63 V／5.5 V | 101.353805 | 101.423393 | 0.395437053 | −0.188819% | 0.185828／0.103581 |

Nominal post duty64为25.187206／25.025587／25.355098 µA；duty255为100.358226／99.719372／101.026445 µA。Off post为3.596–4.028 pA量级的模型数值，不能作为量产leakage规格。完整pre/post15对及原积分结果在[汇总](../../evidence/robustness/summary.json)和[main CSV](../../evidence/robustness/main-transients.csv)。

五种RC style先做短edge probe；额外完整最小交叉矩阵只做以下四例：

| MOS条件×RC style | Full-on µA | Duty1面积误差 | Rise／fall ns |
|---|---:|---:|---:|
| ss×HRHC | 100.113096 | −0.700133% | 0.524982／0.263842 |
| ff×LRLC | 101.422977 | −0.186243% | 0.175853／0.098809 |

因此已测试矩阵的最差最低码面积误差为0.700133%，最慢rise为0.524982 ns、fall0.263842 ns。最短post high/low pulse为999.898886 ns。五份提取存在不等于五RC×三MOS的完整电气矩阵通过。

三个nominal post最低码10→1 ns改变量最大约 `8.94×10⁻⁷%`，小于0.2%门槛。这是上述已保存波形积分的数值收敛，不是LED物理模型精度达到同样小的误差。所有case的maxstep、测量窗口和源hash在分批summary。

## 4. 边界探针发现了什么

### 理想IREF会掩盖上电问题

上电探针用100 ns全ramp，在1或8 µs启动rail，观察0–20 µs。Early idealIREF从0开始、100 ns升到100 µA；late在logic上电后0.2 µs启动。另一个compliant行为边界仅用 `head_min=1 V / Rout=10 MΩ / head_cal=1.9 V` 限制IREF；它不是reference generator。

LED-first、early idealIREF时，BIAS最高高出未建立的logic rail **1.372421 V**。行为电流源在部分时间主动输出 **1.093095 nJ**，最小吸收power为 **−137.242097 µW**。虽然20 µs净吸收仍为+1.206487 nJ，也不能据此把主动供能现象抹去。这说明理想源可维持现实reference未必能建立的bias。

晚启动理想源与compliant边界消除了明显主动供能，但并不完成真实startup验证。Compliant LED-first仍出现约16.46 mV的BIAS-over-live-rail瞬态、command-low区间LED branch峰约2.013 µA。Branch电流包含位移电流；command-low也包含命令变化后尚未传播完成的转换点。不能称其持续off leakage或光学flash。完整rail／bias／源能量在[boundary CSV](../../evidence/robustness/boundary-transients.csv)。

### Enable当前是帧更新，不是紧急关闭

真实RTL在20 µs输入enable=0，注册PWM到258.5 µs才变低：等待238.5 µs。在300 µs重新enable，514.5 µs恢复。Reset在20／30 µs切换，注册PWM在20.5／30.5 µs响应，即0.5 µs同步等待；另有约1 ns的本轮末级电气刺激＋输出传播。没有实现立即关断、power-good或POR。以后必须明确区分正常亮度帧更新与保护关断路径。

### 供电阻抗会先吃掉headroom

非理想探针的Rlogic0／10／100 Ω、RLED0／100／1000 Ω及两个1 nF外部去耦都是声明的假设，不是提取的真实PDN。TT synthetic LED、100 Ω／1000 Ω时full-on100.670995 µA，logic rail约3.290 V、LED anode4.899329 V；最低码0.392451431 µA，LED anode最低约4.936450 V。系列R损耗与假设去耦端点储能单独分账。这些结果只给已选signal model的边界敏感度，没有验证真实IR/EM或package/rail噪声。

真实作者static I–V的独立probe：typical27 °C MOS、3.3 V logic、5 V源、理想100 µA IREF；该LED原测量温度未知，表格未做温度缩放。实际结果：

| 外部RLED假设 | LED anode V | Current µA | 相对100 µA | ±5% target |
|---:|---:|---:|---:|---|
| 0 Ω | 5.000000 | 99.840287 | −0.159713% | 满足 |
| 1 kΩ | 4.900286 | 99.714227 | −0.285773% | 满足 |
| 5 kΩ | 4.505399 | 98.920293 | −1.079707% | 满足 |
| 10 kΩ | 4.117340 | 88.265992 | **−11.734008%** | **失败，保留** |

10 kΩ是刻意的headroom探针，不是推荐PDN阻抗。失败不能隐藏在main passes内。这里得到的是该dataset静态工作点的供电敏感度，不能推出动态响应、光功率或其他LED器件的结果。

## 5. 功耗应按端口和来源分账

平均branch current是电气亮度proxy。5 V×I是LED外部branch rail预算，包含LED device与低侧sink；不能直接称LED自身power。类似地，共享joint VDD pin的draw不含从BIAS注入的reference能量，不能用它表示12MOS总耗能。

TT nominal、稳定两个frame的分账如下，单位µW。Main仍使用理想100 µA IREF，reference rail始终耗330 µW：

| 端口／来源 | Off duty0 | 最低码 duty1 | Full duty256 |
|---|---:|---:|---:|
| LED branch外部rail load | 0.0000180 | 1.962878 | 503.763938 |
| LED device terminal load | 0.00000515 | 1.094236 | 282.170133 |
| 进入joint的LED_K terminal | 0.0000129 | 0.868642 | 221.593804 |
| Reference rail load | 330.000000 | 330.000000 | 330.000000 |
| 其中behavioral source吸收 | 192.765019 | 192.765343 | 192.765020 |
| 其中BIAS注入joint | 137.234981 | 137.234657 | 137.234980 |
| Joint VDD terminal input | 0.0000451 | 0.003937 | 0.0000458 |
| Joint全部端口net input | 137.235039 | 138.107247 | 358.828831 |
| 声明的全部外部源net supply | 330.000063 | 331.966826 | 833.763983 |

表中reference rail与其两项内部拆分不能重复相加。Joint全部端口net input包括VDD、BIAS、LED_K及输入／neighbor刺激源，允许内部储能变化，因此不能无条件称纯热耗散。Startup另保留源端／负载端、series-R损耗与假设去耦端点能量；没有包括被投影排除的实际PG charging。

这解释了下一步方向：最低灰阶LED branch仅约1.96 µW时，持续理想reference rail仍是330 µW；简单扩大阵列会暴露reference组织与关断策略的问题。是否共享reference、如何enable、启动如何保证、误差预算如何分配，应先设计和验证，不能从本轮理想源结果推断实际芯片功耗。

## 6. 复现、独立审查和教学波形

代码、参数与端口合同保存在[scripts/robustness](../../scripts/robustness/)和[stage contract](../../evidence/robustness/stage-contract.json)。每批将源文件复制到唯一raw目录，记录PDK／model／input／deck／waveform SHA。Current用saved piecewise-linear I的trapezoid；power用分别插值V与I后的二次乘积精确积分。它们不能恢复未保存的连续信号。15位小数序列化导致control终点差1–2 ULP的开发期后处理失败已保留在failure record；只放宽8 ULP的表示容差，实际模型和所有工程门槛未变。

```sh
build/layout/venv/bin/python scripts/robustness/run.py --contract evidence/robustness/stage-contract.json --group probe
build/layout/venv/bin/python scripts/robustness/run.py --contract evidence/robustness/stage-contract.json --group main
build/layout/venv/bin/python scripts/robustness/run.py --contract evidence/robustness/stage-contract.json --group boundary
build/layout/venv/bin/python scripts/robustness/publish.py
```

本机raw目录为 `build/robustness/probe-8p0a15d1`、`main-mx5nfi8b`、`boundary-zkivszoz`；失败及此前批次保留在build。公开主结果与[manifest](../../evidence/robustness/manifest.json)是紧凑摘要，raw长波形不进入仓库。独立review不导入runner的积分函数，复算current／charge／power／edge／分母、source/load/R/declared-C守恒及实际负对照；其状态以[独立review evidence](../../evidence/research/v04-review.json)为准。

教学CSV包括[TT最低码完整edge](../../evidence/robustness/nominal-lowest-pulse.csv)、[LED-first理想参考](../../evidence/robustness/startup-ideal-LED-first.csv)、[compliant边界](../../evidence/robustness/startup-compliant-LED-first.csv)、[registered enable](../../evidence/robustness/registered-enable.csv)。除了最低码edge保留窗口内全部点，其余分别每5／20点取教学样本；不是积分输入。每条教学切片在summary记录原raw SHA、窗口与stride。

公共primary sources沿用锁定的[GF180 buf_2标准单元源码](https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_sc_mcu7t5v0)、[GF180器件说明](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_1_4_1.html)与[ngspice v47 manual](https://ngspice.sourceforge.io/docs/ngspice-47-manual.pdf)。作者LED数值来源与许可见[measured LED说明](measured-led.md)，完整工具／模型版本见[PDK lock](../../layout/pdk-lock.json)。网页描述不能替代本轮actual locked file身份。
