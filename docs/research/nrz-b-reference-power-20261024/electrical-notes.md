# B 路真实参考与供电：电气工作记录

当前候选是 **10 MOS V-to-I servo + 1 MOS 外部 DISABLE 钳位 + 1 MOS 条件泄放开关**，dummy 支路直接使用实际 5 V RAW 输入和 50 kΩ，取消曾尝试的 3.3 V LDO。0.5 Gb/s 数据通路、旧 B 的 9 MOS/RIN、MicroLED 静态模型与 200 fF、冻结 RX/PRBS 均保持。12 MOS 候选已完成 pre-layout 启动验证；真实联通 21 MOS + RIN 的 GDS/fullRC 与全部 10 条 0.5 Gb/s 回归已完成，均在冻结 RX 下观察到 0/511 错误；最终原始数据身份与覆盖审计已完成。不能把先前 pre-layout 数字替代最终版图结果。

主要边界必须并列披露：正常上电和稳态条件通过相应项目门槛；错误提前释放 DISABLE 的负控出现约 4.862 V 的 03v3 端差；保留 LED/基准的 RAW 重启虽满足原功能和六对绝对端压门槛，却观察到约 0.747 V 的 PMOS 扩散区对 nwell 正向偏置，注入电流与锁存/可靠性尚未闭合。因此不能把整组启动测试概括成“任意顺序安全”或“重启完整通过”。

## 偏置来源与保留边界

旧 B 的 RREF 实际从理想 VDUMMY = 3.3 V 接到 BIAS，阻值 88.3861064910889 kΩ，RDUMMY = 28 kΩ 也由 VDUMMY 驱动。它并非从逻辑 VDD 供电。旧 TT 的 BIAS = 1.11327 V，参考支路 = 24.7399 µA；SS/FF 的参考 MOS VGS 改变会使电流变化。因此本轮把电压基准、V-to-I 反馈、镜像及输出 compliance、dummy 供电分开验证。

外部 generic 2.5 V precision anchor 经 200 kΩ/50 kΩ 分压产生 0.5 V，真实 06v0 反馈网络令 RSET = 20 kΩ 上电流接近 25 µA，另一只同尺寸 PMOS 将电流送至旧 B 的 BIAS diode。RBIAS = 100 kΩ。外部 RAW = 5 V 经 0.25 Ω/0.5 nH 到 VIN，并有 100 nF/0.2 Ω ESR 去耦；RDUMMY = 50 kΩ 从 VIN 接 DUMMY。逻辑 VDD 仍为 TT 3.3 V、SS 2.95 V、FF 3.65 V，未声称由 2.95 V 无 dropout 产生 3.3 V。

电压基准仍是外部输入边界。本轮对它声明有限输出阻抗、确定性初始误差与 signed linear TC；这不是某厂商产品的准确宏模型，也不是 box-method TC 保证。基准输出端能量计入总能耗；真实外部参考的内部 Iq 和上游转换损失另列预算。未完成片内 bandgap。上述 R/C、GPIO 输出阻抗和封装假设属于板级边界，不纳入片内 GDS 面积或 PEX。

## 为什么取消 LDO

首版实际实现了 19 MOS：10 MOS VI 和 9 MOS OTA/PMOS LDO。真实模块 GDS、两套 DRC、LVS/PEX 已完成，模块 fullRC 为 `build/reference-v2-layout/nrz-r1/N/full-rc/nrz_bias_power_rc.spice`；它与旧 B RC 的阶段性组合使用显式理想块间线，并非最终集成版图。

6 个 pre-layout DC 点的 ISET 为 25.022–25.027 µA，VREG 为 3.2946–3.3011 V。但 DC 正常不代表动态稳定：20 µs 启动时 SS/TT/FF 的 VREG 仅为 1.2655/1.8449/2.6034 V。延长到 100 µs 的实际 RC 启动中，TT/FF 的导电 LED 峰值为 163.052/180.905 µA，末 10 µs 的 VREG 波动约 50.7/50.4 mV。20 µs 负载保持阶跃也未满足 ±2% 调节目标。

单变量 LDO Miller C 从 3 pF 改到 30 pF 后，TT VREG 峰值增至 4.1114 V，未修复。输出 ESR 从 0.2 Ω 改到 100 Ω 的候选仍有约 49.8 mV 晚期波动。去除模块 RC、使用真实几何 MOS 的控制仍出现类似振铃，说明问题不能只归咎于供电走线压降。首版单电压注入得到异常相位与高频再穿越，已标为无效稳定裕量诊断；没有用其异常 357° 数字支持设计。

19 MOS 还增加了明显静态代价：VIN 电流约 0.30–0.47 mA。LDO 控制支路二极管 PMOS 与 pass 管同 W/L，会复制接近负载的电流。名义实际 RC 的全 rails + DATA 能量约 5.49 pJ/bit。由于 dummy 只需合适 compliance，3.3 V 是旧供电假设而非 RX 合同，改为 RAW/50 kΩ 是架构简化，而非宣称失败 LDO 已稳定。

## VI 环路与启动修复

直接 RAW 的 10 MOS VI 首次用 15 pF IN2 对地补偿，FF 长时启动持续振荡。原 3 pF IN2–ICTRL Miller 在 TT 较好，但 FF 也未稳定。局部双注入估计在同一 FF、DATA = 1 工作点得到：

| 外部补偿 | 单次向下 0 dB 穿越 | 相位裕量估计 |
|---|---:|---:|
| 原 3 pF Miller | 4.616 MHz | −0.226° |
| 15 pF IN2 对地 | 3.387 MHz | −3.089° |
| 150 pF IN2 对地 | 676.8 kHz | 66.31° |

闭环与两个注入电路的 DC 工作点最大差约 1.3×10⁻¹¹。该结果与长时域 FF 振荡一致，支持将补偿改为 150 pF 对地；它仍是 local two-injection return-ratio estimate，不能称为严格多环路 Tian 签核。高速 DATA 通路不要求慢参考环跟随每个 2 ns UI。实际集成 PEX 将再检查三 PVT、低/高负载与补偿脚 R/L。

仅改善环路仍不够。参考建立前，旧 03v3 BASE 关断会使 OUT 升高。新增真实 06v0 NMOS XDIS（W/L = 10/0.7 µm）把 BIAS 钳至 VSS，受外部 DISABLE 经 100 Ω 控制。该信号默认 3.3 V asserted，等待 anchor 建立后释放，**不是自主 POR**。恒定 OUT 泄放 10 MΩ 虽降低 DC OUT，仍在 1 µs VLED 上升期间产生约 3.79 V 瞬态端差；CLED×R 约 2 µs，位移充电不能用 DC 值代替。

将 OUT 泄放改为 1.8 MΩ，保留原 1 µs 冷启动坡度、LED 模型与 RX。pre-layout 11 MOS + 旧 B fullRC 的 TT/SS/FF 启动导电峰值为 101.229/98.252/104.232 µA，末值为 101.082/98.144/104.049 µA，晚 10 µs 纹波小于 2×10⁻¹⁴ A，最小型号端压余量约 0.999 V。先仅换 150 pF、保留 10 MΩ 的单因素控制仍端压失败，保留为独立负证据。

DISABLE 钳住输出偏置并接通保护泄放，但不关掉 VI 放大器；它不是参考电路的 power gating，不能把保持态称为低静态功耗关机。

1.8 MΩ 带来真实非零保持电流：TT/SS/FF 的保持峰值约 1.278/1.278/1.291 µA，时间平均约 1.214 µA。正常 DC 的低电流为 25.973–26.168 µA，高电流为 98.144–104.049 µA；TT 为 26.061/101.082 µA。RSET 仍固定 20 kΩ，没有逐角校准。报告必须把相对 25/100 µA 的电流误差与 device screen 分开，不能因为端压通过就宣称电流精度通过。

## 恒定 keeper 的实际 PEX 精度失败与第二次修改

真实联通 20 MOS + RIN（`nrz-joint-r1c`）已完成 DRC/LVS/fullRC，但基准 DC 与电流精度不是同一件事：FF 组合条件下，I0 = 26.62118 µA（+6.485%）、I1 = 105.91882 µA（+5.919%），端压筛查仍通过。恒定 1.8 MΩ keeper 已消耗主要低电流误差预算。

因此新增第二只控制 MOS：XKEEP 为 06v0 W/L = 1/0.7 µm，连接 KRET–VSS，gate 同为 DISABLE；外部 1.8 MΩ 改接 OUT–KRET。保持期间它提供相同保护，正常通信时断开电阻。12 MOS pre-layout + 旧 B fullRC 的 TT/SS/FF I0 改善到 25.16110/25.07220/25.26864 µA，I1 为 100.40210/97.45931/103.37418 µA；RSET 仍固定 20 kΩ，未逐 PVT 调整。三角点启动、迟到 anchor、残余电源重启均通过原峰值/保持/ready/端压合同。

宽容差 RSET ±1%/±100 ppm 的 FF 组合仍得到 I1 = 105.24999 µA（+5.250%），这项失败保留。最终另列可实施的选型等级：RSET ±0.1%/±25 ppm，RDUMMY 仍 ±1%/±100 ppm，anchor 与分压器边界不变；通过实际 PEX 测试决定该等级是否足够。不会把窄容差结果覆盖到宽容差，也没有通过修改 RX 或每角校准掩盖精度问题。原 20 MOS 实版图和失败 DC 保留为控制，最终计划升级为真实联通 21 MOS + RIN。

## 外部时序合同与负控制

最终验证前预声明的新合同为：冷启动电源及 anchor 在 1 µs 上升；DISABLE 先 asserted，从 anchor 开始上升计 20 µs 后释放；保持导电 LED ≤2 µA，释放后 2 µs 内进入 100 µA±5% 并持续；完整峰值 ≤125 µA，同时满足型号端压筛查。这里约 20 µs 的使能延迟是明确系统代价，不等于旧 LDO 的 20 µs 失败变成成功，也不等于完全关断。

旧恒定 keeper 的 11 MOS pre-layout 控制中，迟到 anchor 30 µs、50 µs 释放通过；错误地在 20 µs 释放、anchor 30 µs 才到达时没有峰流或端压失败，但到 33.486 µs 才进入目标带，违反释放后 2 µs ready 合同。该无端压失败结论只属于旧恒定 keeper。

最终条件 keeper 的真实联通 21 MOS PEX 中，同一错误顺序会把 OUT 泄放同时关掉，最坏 03v3 端差上升至约 4.86194 V，超出 3.63 V 项目筛查 1.23194 V；释放到进入目标带延迟 13.5297 µs。正确的 30 µs anchor/50 µs release 控制通过。条件 keeper 降低通信时的偏置误差，同时更依赖已声明的外部时序；不能声称任意顺序安全、自主 POR 或物理击穿已被模拟证明。

旧 11 MOS pre-layout + 旧 B fullRC 的恒定 keeper 阶段，保留 VLED 与 anchor、RAW 在 20–24 µs 掉电重启的 FF 控制中，DISABLE 提前 asserted 并在 44 µs 释放；导电峰值 104.355 µA，保持峰值 1.269 µA，释放后约 85.54 ns 进入目标带，最小端压余量 0.9977 V。这仍是指定边界内的模拟，不是任意电源故障覆盖。

## 正式矩阵与证据限制

`evidence/nrz-reference-v2/final-scope-amendment.json` 及 `final-scope-amendment-conditional-keeper.json` 在对应最终 PEX 执行前冻结：最初 92 DC、10 NRZ、11 启动/重启、5 慢时标与 7 AC 点；条件 keeper 与精密 RSET 选型的第二次预声明增加为 112 DC，其余数量不变。独立扫描 RSET/RDUMMY 的 ±1% 初始误差、±100 ppm/°C 线性温漂，保留 ±5% 负控制；扫描 anchor 误差/TC/输出阻抗、分压器误差、RAW ±5%、组合条件。旧 RREF/RDUMMY 独立误差控制已经保留。不是统计良率或完整 PVT 笛卡尔积。

NRZ 始终使用原 0.5 Gb/s、20 ps DATA、200 fF、optical tau 200 ps、1 GHz RX、62.5 µA 阈值与原训练/验证数据。统计是有限码长零错误观察，不升级为 BER 保证。能量逐源积分实际 v(t)×i(t)，含 RAW、VREF、DISABLE、VLED、VDD 与 DATA；外部源内部 Iq 另列。供电与回地封装 R/L、LED R/L 和补偿引脚寄生分别声明。

03v3 六对端压 3.63 V、06v0 六对端压 6.0 V 是保守项目筛查，另存 gate-specific 最大值；它不是 foundry SOA/可靠性签核。没有温度相关 LED 实测拟合、真实光学测量、Monte Carlo/局部失配、完整片外噪声模型、独立三维衬底场验证或完整自基准。公开来源由 `evidence/reference-v2-research/sources.json` 记录。所有历史失败、分析包装错误与无效 AC 诊断保留，不改上一轮数据。

## 最终实际 PEX 已确认的静态、慢响应与功耗

真实联通 21 MOS + RIN（fullRC SHA `925b0e98ede116b7d3dc0c0f326aa1704fd08b84dd8cabe39cf03ae4ac4f3d6a`）的 112 DC 点全部完成求解与型号端压筛查。名义 TT/SS/FF 的 I0 为 25.15410/25.06540/25.26136 µA，I1 为 100.39516/97.44752/103.37196 µA。宽容差与负控制留下 4 个 ±5% 电流目标失败，不能算作精度通过：FF RSET−1%/+100 ppm 的 I1 +5.0747%；FF 宽组合 I1 +5.2465%；TT RSET−5% 的两态分别 +5.8408%/+5.5942%。选定精密 RSET 的组合 SS 为 24.90003/96.80444 µA、FF 为 25.36997/103.81115 µA，均通过 ±5% 目标。

11 个启动/重启条件中，10 个正确时序及其声明容差通过，故意提前释放的负控制失败。5 个慢响应条件通过；FF RAW 从 5 V 降到 4.75 V 后恢复、10 ns 边沿的 100 µs 测试中，导电 LED 最小/最大为 98.0105/108.8127 µA，排除每个已声明阶跃后 2 µs 的建立区间后，目标误差不超过 3.413%。这些长波形补足了约 1.6 µs NRZ 帧无法判断慢环稳定性的限制。

最终实际 PEX 的局部双注入估计：TT 450.4 kHz/72.956°，SS 283.5 kHz/78.335°，FF 668.7 kHz/66.250°；DATA=0/1 的差异很小。补偿脚额外 1 Ω/5 nH、ESR 0.5 Ω 的 FF 对照为 668.7 kHz/66.305°，同条件启动亦通过。这是指定 lumped 模型内的敏感性，不代替任意封装或 PCB 的验证。

额外同 6 个名义 DC 工作点的模型电流观测没有改变电路，LED 电流与原 DC 相差 0 A。TT 的 RAW 源供能分解为 OTA 控制支路约 451.26 µW、sense 参考支路 124.97 µW、输出参考支路 124.53 µW；VI 总静态代价约 700.88 µW。Dummy 在 DATA=0 约 377.10 µW、DATA=1 近零。模型 `m0[id]` 通道观测不能精确替代所有源/体/漏电端口电流，残余 0.089–0.171 µW 单列；真实完整能量仍以外部源实际 v×i 为准。首次把通道和完整源电流要求在 10 nA 内闭合的诊断断言失败已保留，属于测量假设修正，未放宽电路性能条件。

三角点名义 0.5 Gb/s 均观察到 0/511 错误；TT/SS/FF 正向供能为 2.68827/2.51936/2.91744 pJ/bit，旧理想参考方案同条件为 1.27909/1.11079/1.51601 pJ/bit。新电路提高偏置稳定性，但有真实静态功耗代价。RAW 电源脉冲会反复充放电 100 nF 输入去耦，其正向/返还/净能量应作为扰动响应独立呈现，不能把该能量当常态每比特能耗，也不能默认免费回收返还能量。

跨目录入口 `scripts/nrz_reference_v2/reproduce.py --smoke-dc` 已在新空目录只复制 frozen inputs/stimulus、加载原执行 runner 后复现 TT 高态，电流差 0 A。它不复制旧波形，不重跑 EDA 或完整矩阵。保存预算因实际全 RC 波形大于预估获批由 2 GiB 改为 3.5 GiB，free floor 仍为 5 GiB；已完成源与案例未改，纯等待中的批处理管理中止单独归档，不算求解失败。

最终真实 21 MOS 的残余电源重启记录另外显示：虽然通过导电峰值、ready 与绝对六对端压项目筛查，VI 输入 PMOS x7（XR_IPD2）的 source-to-body 正向电压达到 0.746649 V，x9/x10 约 0.702 V。与 RAW 下落时 IN2 补偿/内部节点储能向较低 VIN 井端放电的机制一致，但未独立重算完整结电流或进行 latch-up/SOA 资格验证。因此该重启只能称为已声明功能与绝对端压条件通过，不能称为没有 body-junction injection 风险或可靠性闭合。未更改原筛查阈值，也未把该观察隐藏在“startup_passed”布尔值后面。

重启事件的原始波形定位：x7 / XR_IPD2 的提取 SPICE S = `IN2.t1`，对应原版图 D（DRC/LVS 物理映射已记录 D/S 互换），B = `VIN.t6`。在 21.173660 µs，扩散区为 0.749006 V、nwell 为 0.002357 V；RAW 源已为 0 V，VIN 端口为 2.30057 mV，而外部基准 2.5 V、DISABLE 3.3 V 仍保持。线性插值的正向差 >0 持续 2.290224 µs，>0.6 V 持续 2.036545 µs，>0.7 V 持续 1.400134 µs。这里的分级阈值只用于描述波形，不是新增 foundry 接受标准。精确来源、时间区间与 19–25 µs 实际采样 CSV 见 `evidence/nrz-reference-v2/restart-body-review.json` 和 `final-tables/restart-body-event.csv`。下一步应优先研究内部补偿节点复位、掉电隔离及真实 ready 控制；本轮未临时修改冻结的 21 MOS 设计。

## 收尾状态

正式 138 个案例全部有结果和对应分析（112 DC、10 NRZ、11 启动、5 慢响应），无计划缺项、无未计划项、无求解或分析失败；7 个 AC 条件单列。10 条 NRZ 均满足冻结接收器与型号端压项目门槛，不能推广为无限码长 BER。失败计数保持区分：4 个宽容差/负控制 DC 电流精度失败；1 个提前释放的 startup 合同失败同时也是 1 个端压筛查失败；1 次没有 ngspice 子进程的资源管理中止被单独归档并完成原案例。残余电源重启的正向体结观察是另一个未闭合资格边界，不能因原 `startup_passed` 为 true 而消除。

全压缩文件 SHA 和解压后原始字节 SHA 已逐一复核。最终表格与同条件旧/新对照在 `evidence/nrz-reference-v2/final-tables/`，正式汇总为 `selected-final-r2-summary-verified.json`，收尾索引为 `closeout-index.json`。较紧的 FF trap/80 steps/2e-6 数值控制同样完成，不需要省略或放宽 RX。保留数据实测 3.59785 GiB：末条已声明紧数值点在 3.5 GiB 的开跑门槛内启动，压缩后使最终保存量多约 100 MiB；完整证据未删除，实际量与 gate 语义见 `storage-closeout.json`。本轮 NRZ 仿真已停止，不再扩矩阵。
