# 数据、计算与数值求解独立检阅

检阅日期：2026-10-03。审核基线为 commit `e26e2f6c7dcb168d428d6b710fee59b180d202c3` 已发布的 Phase 1 与原始运行 `build/layout/pixel-ozx2_pwq`，对应输入哈希见 [numeric-summary.json](../../evidence/review/numeric-summary.json)。检阅期间主流程修复了独立发现的 LVS 属性验收问题并重新发布 physical evidence；本页的“24 项匹配”指审核起点，不能解读为修复后的文件仍应匹配旧哈希。原数值审计不会把正常修复判为篡改。本页审查计算与证据边界，器件模型物理适用性和版图规则另行审查。

**结论：已发布平均电流的算术、积分窗口、单位和 RTL duty 没有发现错误。关断电流的 pA 数字以及稳态波形上的小纹波，需要降级解释；它们明显受求解器设置影响。当前回归通过证明指定模型下的运行结果及版图前后的一致性，不能直接证明真实器件绝对精度。**

## 1. 独立方法与检阅分母

审计实现为 [numeric_audit.py](../../scripts/review/numeric_audit.py)，没有导入 `run_phase1` 或 `run_postlayout` 的计算函数。

| 对象 | 检阅数量 | 独立检查 |
|---|---:|---|
| Phase 1 transient | 19 | 17 个常规 case，加 2 个步长细化 case |
| 全 PDK schematic transient | 17 | 与 published summary 一一对应 |
| extracted RC transient | 19 | 17 个常规 case，加 2 个步长细化 case |
| 独立 LED DC 校准 | 6 | 两套流程各 3 个 Vf，读取实际 `calibration.dat` |
| 既有源文件哈希条目 | 24 | Phase 1 的 8 项，加 layout 的 16 项；有重复源文件 |
| 新增 solver probes | 12 | 8 次容差/方法比较，加 4 次 GMIN 扫描 |

55 份 transient 的采样值全部有限、时间严格递增、覆盖完整积分窗口；所有平均电流重算通过。最大差为 **1.4211×10⁻¹⁴ µA**，属于浮点求和差。6 份 DC 原始输出均与 public summary 相同，24 条已有源哈希均匹配检阅开始时文件。

独立积分对每个原始时间段做截断，再对线性段求解析积分，最后用 `math.fsum` 汇总：

```text
Iavg = Σ [(tb − ta) × (I(ta) + I(tb)) / 2] / (Tend − Tstart)
Tstart = 514.5 µs
Tend   = 1538.5 µs
窗口长度 = 1024 µs = 4 × 256 µs
```

这与原程序的时间加权梯形积分数学等价，但实现独立。不能对自适应采样直接做算术平均：例如 Phase 1 `duty_001` 的正确时间平均为 **0.394943145 µA**，原始采样点的简单平均却是 **4.901971763 µA**。原流程没有犯这个错误。

## 2. 数字时间、PWL 与单位

审计用整数 ns 计算每段 RTL 事件与测量窗口的重叠长度，独立确认全部 case 的占空比为 `min(duty, 256)/256`；disabled 为 0。1 MHz 时钟给出 1 µs slot、256 µs frame、3906.25 Hz PWM。测量开始前已有两个完整 warmup frame；逐帧平均也稳定，没有发现用启动过渡冒充稳态的情况。

PWL 的节点全部与实际导出的 RTL 事件一致。模拟电压的 10 ns ramp 从数字事件时刻开始，因此 50% 电压交越比事件晚 5 ns。这是已设定的外部驱动 slew，不是综合后标准单元延迟。每个完整周期的上升和下降 ramp 对理想电压积分相互抵消；真实电流的开关误差仍由晶体管求解决定。

`VSENSE vdd led_a 0` 的正电流方向由电源流向 LED，平均值乘 `1e6` 得到 µA。边沿允许短暂负电流，不能把它等同于负光功率。负值可含结电容和布线电容的充放电；数值峰值还需收敛验证。

Phase 1 原始文本以约 9 位有效数字导出，在 1 ms 附近的时间量化可达数 ps。对 10 ns ramp 重新插值会出现约 **1.65 mV** 的最大差异，来自导出精度；full-PDK 流程设定 `numdgt=15` 后相应差约 2.2×10⁻¹⁰ V。现有平均电流不因此失效，但后续边沿/延迟研究应统一采用高精度时间导出。

## 3. LED 校准公式与绝对电流

用 SI 精确定义的 Boltzmann 常数和元电荷独立计算：

```text
VT = kT/q，T = 300.15 K
Vf = N × VT × ln(1 + I/IS) + I × RS
N = 3，I = 100 µA，RS = 50 Ω
```

代回当前 `IS`，解析结果分别为 2.4、2.8、3.2 V。ngspice 与解析结果的差为约 −0.81、−0.95、−1.09 µV，远小于原校准门槛 0.1 mV。这证明参数到仿真器的映射正确；不能替代真实 LED 测量拟合。

| 指标 | Phase 1 | extracted RC |
|---|---:|---:|
| nominal 全开电流 | 101.299593699 µA | 101.236512039 µA |
| 相对理想 IREF=100 µA 的误差 | +1.29959% | +1.23651% |
| duty=1 的电流 | 0.394943145 µA | 0.394573258 µA |
| duty=1 相对“全开值/256”的误差 | −0.19166% | −0.22300% |
| duty=64 相对“全开值/4”的误差 | −0.003006% | −0.003495% |

“版图后相比同 PDK schematic 只变化 −0.0623%”与“相对 100 µA 的绝对误差 +1.2365%”是两件不同的事。不能用前者取代后者，更不能把仿真中的小差异当作 silicon 精度。

## 4. 需要修正的解释

### N1：3.6 pA 关断值受 GMIN 主导，不能当作物理 leakage 指标

原流程 `abstol=1e-12 A`，且使用默认 GMIN。审计对同一 RC 网表、27°C、duty=0，采用 Gear2、`reltol=1e-7`、`abstol=1e-16 A`、`vntol=1e-9 V`，仅改变 GMIN：

| GMIN (S) | 平均 branch current (pA) |
|---:|---:|
| 1×10⁻¹⁰ | 324.604525 |
| 1×10⁻¹² | 3.599458 |
| 1×10⁻¹⁴ | 0.064693 |
| 1×10⁻¹⁶ | 0.026689 |

这说明现有 **3.6 pA** 主要受数值电导设置影响。低 GMIN 的 0.026689 pA 同样不能升级为真实 leakage；模型仍缺乏相应物理验证。当前可保留的结论是“在指定模型与求解设置下，关断平均 branch current 小于 1 nA”。GMIN 的定义及默认值见 [ngspice DC solution options](https://nmg.gitlab.io/ngspice-manual/analysesandoutputcontrol_batchmode/simulatorvariables__options/dcsolutionoptions.html)。数据见 [GMIN probes](../../evidence/review/numeric-gmin-probes.json)。

### N2：平均电流收敛，不等于纹波、峰值和延迟已收敛

nominal RC 全开 case 在测量窗内没有 PWM 转换，但原始默认 trapezoidal 波形仍有 **0.0866476 µA** 峰峰变化。改用更紧容差和 20 ns 最大步长，trapezoidal 的变化降为 **0.000322438 µA**；Gear2 同时收紧容差后接近机器数值噪声。三者平均值仍为约 **101.236512 µA**，最大平均值差不足 **0.08 pA**。

这是小幅纹波受数值积分方法影响的直接证据，不能把原始 peak/min 用来建立物理稳态纹波指标。ngspice 官方手册说明默认积分方法是 trapezoidal，并专门讨论 trap ringing 与数值阻尼；改变方法也可能抑制真实振荡，因此不能单凭 Gear 波形平滑就宣称稳定。[Transient analysis options](https://nmg.gitlab.io/ngspice-manual/analysesandoutputcontrol_batchmode/simulatorvariables__options/transientanalysisoptions.html)

8 次新增容差/方法 probe 覆盖 duty=0、1、64、256。相对原 RC 平均值，非零 case 的最大相对变化为 **6.67×10⁻⁶（0.000667%）**，发生在 duty=1。该结果增强当前平均电流结论；尚未完成 edge peak、rise/fall time、settling time 和 bandwidth 的专门收敛判据。

### N3：回归门槛有明确盲区，不能替代设计规格

原 Phase 1 线性度用“本次 full-on 值×duty”作为基准，最低码误差门槛为 `max(0.01 µA, 3%)`；这验证比例关系，未直接约束 100 µA 的绝对误差。postlayout 用 `max(1%×pre, 1 nA)` 约束版图前后差异；两套模型若共同偏离目标仍可通过。现有 corner 和温度 case 主要记录全开电流，未覆盖 FF/SS 与供电、温度、Vf、duty 的组合，也未开启 mismatch。

因此建议下一阶段先明确并分别验证：absolute current error、PWM linearity、off-current bound、compliance/headroom、settling 与输入 slew 范围。阈值应作为研究目标公开，不能从“测试已经通过”倒推出来。现有 100 µA nominal 结果即使非常接近目标，也不能凭此承诺全 PVT 或阵列一致性。

## 5. 测试与溯源边界

既有 RTL testbench 的 518 个 `check_frame` / 133159 次 slot 或 value 检查，确实覆盖全部 257 个合法 duty 与 255 个 clamp 输入，以及帧边界更新、enable 和同步 reset。它没有证明时钟域跨越、输入亚稳态、门级 glitch、STA 或驱动能力；PWL source 也没有输出阻抗和负载反馈。

原 runner 在执行前删除旧 `waveform.dat`，并检查输出存在、形状、有限值和严格时间顺序，避免 ngspice 某些错误返回 0 时复用旧波形。这些措施有效。`build/phase1/vf_4.8` 是旧探索残留目录，未被本次 published summary 或 metrics 引用；本审计按 summary 的 case 清单读取，未把该旧目录当作当前证据。后续应保持 manifest 驱动读取，或者为每次 Phase 1 建立唯一运行目录。

当前 `on_plateau_current_uA` 是排除数字边沿后 100 ns 的样本中位数，属于描述性统计，既非独立 DC 解，也非证明 settle 完成；对极短脉冲或下一阶段更大的寄生负载应重新定义。

## 6. 重现与后续入口

```sh
.venv/bin/python scripts/review/numeric_audit.py --solver-probes
```

此命令读取已有 Phase 1 和最新 public layout summary 指向的 raw run，独立重算，再执行 12 次敏感性仿真；输出审计 JSON 到 `evidence/review/`，原始新增输出留在 `build/audit_numeric/`，不改写原 Phase 1/layout evidence。若要重算本页旧基线，增加 `--layout-summary build/layout/pixel-ozx2_pwq/summary.json`；这时新修复源文件与旧 manifest 的差异是预期结果，数值计算会单独报告。

本检阅支持继续单像素研究：先完善器件/LED 的适用条件及绝对规格，把数值误差和模型不确定性分别写清；阵列扩展应等待这些条件建立。这里已确认的是计算正确性和有限的数值稳定性，真实器件适用性仍需独立证据。
