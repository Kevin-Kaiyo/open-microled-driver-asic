# 单像素数字／模拟接口检验

日期：2026-10-04。对象是实际布线 PWM 的末级输出单元、模拟像素的实际 RC 提取视图，以及共同顶层新增的 PWM 金属连接。电路保持单像素、100 µA 理想 reference、1 MHz clock、256 slots。

## 1. 从逻辑值到晶体管输入

此前 STA 的 output load 72.91 fF 是配置预算；生成 SDC 将它表示为 0.0729 pF。它不是模拟像素端口的测量，也不能用 LEF 的 `ANTENNAGATEAREA=8 µm²` 换算。后者是三个受 PWM 控制器件的 gate 面积，用于 antenna 检查，单位不是电容。

实际 routed netlist 的最后一级是 `output12`，型号 `gf180mcu_fd_sc_mcu7t5v0__buf_2`，输入 `net12`、输出 `pwm`。它是两级非反相 buffer，实际公开 SPICE 有六个 MOS：输入级各一只 NMOS/PMOS，输出级各两只并联 NMOS/PMOS。NMOS 为 `nfet_05v0 W=.82 µm/L=.6 µm`，PMOS 为 `pfet_05v0 W=1.22 µm/L=.5 µm`。引脚顺序是 `I Z VDD VNW VPW VSS`，这里 `VNW=VDD`、`VPW=VSS`。型号中的 5 V 器件名称不自动证明 3.3 V 接口兼容；本次用完整锁定模型在实际研究电压下仿真。

链路为：RTL 的 PWM 事件 → 声明的末级 buffer 输入电压坡度 → 六 MOS buffer → 数字宏内部的 nominal 输出金属 RC → 新增跨宏连接 RC → 模拟宏的实际六 MOS RC → LED 电气负载。前级 flip-flop、时钟树与逻辑的晶体管延迟没有包含在这条 SPICE 链路中，不能与此前 SDF 的总路径延迟相加后称为完整芯片晶体管验证。

buffer 自身使用 upstream schematic SPICE；它未显式提供 `AD/AS/PD/PS`，未完成该标准单元的 junction／metal PEX。本次也没有修改寄生参数以迎合 Liberty。模拟像素则确实使用已通过 DRC/LVS 的实际 RC 提取视图。因此此处的高速边沿是已声明模型中的结果。

## 2. PWM 输入负载实际是多少

对模拟 RC 的外部 `pwm` 引脚施加电压并积分源电流，包含三个 gate、宏内互连电容以及其他节点响应产生的耦合电荷。`Ceq=Q/ΔV` 是电荷等效负载，不能当作与工作点无关的真实固定电容。

TT／27°C／3.3 V／5 V、合成 LED 条件下，0.25／1／10 ns 完整电压坡度得到：

| 完整输入坡度 | 上升 `Q/3.3 V` | 下降 `−Q/3.3 V` |
|---|---:|---:|
| 0.25 ns | 36.71527 fF | 36.66832 fF |
| 1 ns | 36.71530 fF | 36.66831 fF |
| 10 ns | 36.71526 fF | 36.66831 fF |

上升积分窗为 99–1000 ns，下降为 1099–1950 ns，明确记录有限积分窗与残余电流；同时保留较短窗作比较。下降扩窗的电荷改变量约 0.016%，不是省略的 DC leakage 修正。上升电荷约 121.16 fC。

另在 PWM DC bias=0／0.825／1.65／2.475／3.3 V 做 AC 分析，频率 0.1 MHz–1 GHz，按 `Cparallel=Im(Y)/(2πf)` 计算。结果 30.30–36.93 fF；中间逻辑电平会改变内部节点状态，AC admittance 也可能含有有源反馈，因此 AC 表不是 Liberty pin characterization，更不是所有状态的量产保证。

数字宏原有 PWM 输出 SPEF 的 series R 为 12.375 Ω：driver 端 grounded C=0.315849 fF，端口端 grounded C=0.315849 fF，并有 0.503421 fF 对邻近输入的耦合。这里将该邻居视为静止电压，合为端口端 0.819270 fF；没有模拟相邻逻辑的真实活动。

新增跨宏 M3 连接长 30 µm、宽 0.56 µm，实际提取 R=4.81871 Ω，与 PWM 连接的总 C=2.34604 fF。VDD 耦合保留四端网络，供电／substrate boundary 使用理想 Vlogic／VSS；没有模拟 substrate impedance 或完整供电网瞬态。约 36.7+1.14+2.35≈40.2 fF 只能作当前电荷预算对照，不能用不同节点的电容简单相加替代实际波形验证。现有 72.9 fF STA load 暂保留为保守预算，需完整 joint PEX 与一致的 PVT／输入波形后才能关闭接口 timing signoff。

## 3. 预设门槛与实际耦合回归

门槛沿用 v0.2：满开 100 µA±5%；最低码电荷面积误差≤±2%；off 数值 guard <1 nA。脉冲检查沿用 routed SDF 回放的 950 ns 最短 high／low guard。实际 TT 3.3 V Liberty 定义 slew 为 30–70% rise 与 70–30% fall，delay threshold 为 50%；输出 transition 与原 3 ns 约束比较。

| 包络 | MOS T | Vlogic | VLED | joint 满开 | joint duty=1 均值 | 最低码面积误差 |
|---|---:|---:|---:|---:|---:|---:|
| TT | 27°C | 3.3 V | 5 V | 100.69540 µA | 0.39235537 µA | −0.25068% |
| SS | 85°C | 2.97 V | 4.5 V | 100.06878 µA | 0.38821894 µA | −0.68426% |
| FF | 0°C | 3.63 V | 5.5 V | 101.35380 µA | 0.39516859 µA | −0.18810% |

这三个条件与模拟研究 envelope 一致，与已有 Liberty 的 TT25°C／3.3 V、SS125°C／3.0 V、FF−40°C／3.6 V 并不完全相同，不称为 matched STA corners。

理想源采用此前 10 ns 完整坡度，buffer input 采用明确声明的 1 ns 完整坡度。两个刺激位于不同节点，配对电流差不能全部归因于 buffer 或金属 R。每种驱动路径检查 duty=0／1／64／255／256，先两种驱动、后真实跨宏 RC，保留所有结果。主批次共 54 transient、12 个 DC driver／level 检查、5 个 AC bias 检查、3 个端口电荷 probe 和独立 synthetic LED DC calibration。

在 1 ns buffer input 完整坡度下，joint path 三包络中的最大输出 rise 为约 0.43991 ns、fall 约 0.21804 ns；最短 high／low 仍超过 999.89 ns。off 均值约 0.0036–0.0041 nA，仅是所用模型的数值结果。TT 最低码由 maxstep=10 ns 细化至 1 ns，面积／均值变化远小于 0.2% refinement guard。

再单独将 buffer input 的完整坡度增至 7.5 ns，即实际 30–70% input slew=3 ns，测试三包络的 duty1／255，共 6 个 stress transient。最大输出 rise=0.45495 ns、fall=0.25899 ns；最低码最大绝对面积误差=0.59075%；最短 low=998.79862 ns，全部通过原门槛。这是声明的最慢输入刺激，不是已恢复的 preceding flip-flop transistor waveform。

端口发生少量高于 Vlogic／低于 VSS 的 feedthrough。joint SS 例中最低约 −28.22 mV，最高约 Vlogic+35.64 mV；需要结合未来标准单元 PEX、真实 PG 与 pad／ESD 验证，不能当作实物电压的精确预测。

TT joint duty1 的末级 buffer 平均供电功耗约 0.002358 µW；此平均包含该末级的动态／静态模型电流，未含整个 digital clock／logic，也未含真实 reference generator。LED rail、analog logic/reference rail 和 buffer rail 分开报告，避免把这一数字当系统功耗。

## 4. 实测静态 LED 只支持哪个结论

另做 TT 条件下实测静态 I–V+**假设的 2 pF** 负载对照，duty1／64／256 以及最低码细化。真实 buffer 端 duty1 均值 0.38916139 µA，最低码面积误差 −0.16350%。但约 98.713% 时间处于原始静态电压域之外，约 4.902% signed conduction charge 依赖未测量的低电流／reverse 扩展；虽然电荷多数在数据域内，也不能把未知 C／温度／反偏行为视为已经验证。`dynamic_LED_qualification=false` 保持。

## 5. 证据身份与独立复算

仿真前冻结模型、RTL、模拟 RC、数字 netlist／SPEF 与跨宏 link。raw deck／日志／波形留在 `build/interface/`，公开 summary 记录输入和 raw SHA-256，CSV 保留所有主要数值，公开 `nominal-pulse.csv` 是实际 joint duty1 波形的短窗切片。

最后一次金属 extractor 因 Magic 的元件枚举顺序重新生成，把 `C0/C1/C2` 名称和行序重排；R/C 端点、数值、重复元件与 subckt 端口完全相同。仿真实际使用的 `b43d95d8…` 与最终 `f56728da…` 两个字节哈希都保留：[输入映射](../../evidence/interface/input-mapping.json) 对 exact R/C graph 做等价检验，并用修改 R／删除 C 的负对照证明会拒绝电气变化；旧 as-run hash 没有被改写。metadata 补充了实际 substrate binding 的追溯证据，没有升级仿真范围。

`validate.py` 不调用仿真 runner 的积分／边沿函数，用独立 cumulative linear-panel primitive 重算所有 current／power／charge、30–70% 边沿和脉宽，再核查 CSV 单位、PDK 与原始波形哈希。研究门槛通过与数据身份／计算核验分别报告。

## 6. 重现与下一步

```sh
build/layout/venv/bin/python scripts/interface/run.py --joint-link evidence/integration/pwm_link_rc.spice
build/layout/venv/bin/python scripts/interface/stress.py
build/layout/venv/bin/python scripts/interface/map_inputs.py
build/layout/venv/bin/python scripts/interface/validate.py
build/layout/venv/bin/python scripts/interface/validate_stress.py
```

每次运行生成新的 raw 目录；当前 as-run snapshot 保留历史输入。当使用当前 link 新跑时，映射会退化为字节一致，而不会强制修改网表来复现旧枚举名。进行新仿真前保持足够磁盘空间，整个 PDK 留在本地，并使用既有 lock 核对实际依赖。

下一步应做完整标准单元／顶层互连的 joint RC、统一真实输入波形及 PVT 预算、PG 与启动／掉电域检查，再做 pad／ESD 与系统电源边界。真实 LED 的 charge／temperature 与光学测量仍是独立任务；仍先完善单像素再扩 4×4。

主要证据：[summary](../../evidence/interface/summary.json)、[全部 transient CSV](../../evidence/interface/transients.csv)、[输入电荷](../../evidence/interface/input-charge.csv)、[AC Y](../../evidence/interface/ac.csv)、[最慢输入刺激](../../evidence/interface/slew-budget-summary.json)、[独立复算](../../evidence/interface/validation.json)、[跨宏提取](../../evidence/integration/link-rc.json)。

公共 primary source：[GF180 buf_2 function／schematic／layout](https://gf180mcu-pdk.readthedocs.io/en/latest/digital/standard_cells/gf180mcu_fd_sc_mcu7t5v0/cells/buf/gf180mcu_fd_sc_mcu7t5v0__buf_2.html)。本次没有把该网页缺少完整条件的 delay 表当作 3.3 V 实测数据；实际 cell／SPICE／Liberty 的身份以锁定文件 SHA-256 为准。[标准单元源及许可](https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_sc_mcu7t5v0)／[本项目 notice](../../evidence/interface/NOTICE.md)。
