# A：实际吸流辅助轨候选（原理级探针）

2026-10-25。本候选用于下一阶段公平 A/B 晶体管比较，**没有完成 A/B 比较、通信接收验收、PVT、布局或启动可靠性验证**。正常通信探针从已建立 OP 开始；自主启动诊断暴露了明显冲流与体结正偏，不能称启动通过。

## 接口与实现

源：[`route_a.spice`](../../analog/fair_driver_v1/route_a.spice)，SHA-256：
`02ba88d9b7654b68b11b4db15bd8bbf316271123c8d377944335602763657a53`。

```spice
.subckt fair_a D0 D1 OUT VIN VDD VREF VSS DISABLE params: RH=180k RL=88k
```

| 端口/参数 | 本探针条件 |
|---|---|
| VIN、VDD、VREF、VSS | 5 V、3.3 V、2.5 V、0 V；VIN 同时连接 LED anode，三路上游端口均计能 |
| D0 | 原 A 的 RIN8 → 两级 CMOS → 输出对；0 对应 I0，1 对应 I1 |
| D1、DISABLE | D1 未使用；DISABLE 仅保留接口，未实现保护或自主 POR，正常通信固定 0 |
| RH、RL | 分压下电阻，两个上电阻均 100 kΩ；只在 TT/27°C 校准一次，不允许 PVT 逐点调值 |
| 选定校准值 | **RH=177683.3997653013 Ω，RL=87444.56014738003 Ω**；实例化时显式传入，源中默认值保留最初候选 |

原 A 六只 06v0 MOS 的 W/L、D/G/S/B 连接及 PDK `ppolyf_u_1k_6p0` RIN 的 8 µm × 1 µm 几何均保留。每条辅助轨增加五 MOS PMOS 输入 OTA、二极管 PMOS + 1 MΩ 实际偏置、NMOS shunt，合计 **20 MOS + RIN**。差分对第一支输入轨电压，第二支输入分压基准；轨电压升高使 shunt gate 升高，增加真实吸流。

每轨由 VIN 经 100 kΩ feed 电阻供电，流入轨的 LED 电流最终由 NMOS 分流耗散。这里没有理想 VH/VL、理想内部偏置或能量回收源。两只 **10 nF 电容和 0.2 Ω ESR**、feed/分压/bias 电阻均明确作为片外理想 R/C 器件表示在子电路内，以保持封闭接口；未包含其容差、封装寄生或产品模型，不能计作片内版图。后续可分别增加现实器件参数。

所有 MOS 使用共同的原理级结几何估计 `AD=AS=W×0.44µm`、`PD=PS=2×(W+0.44µm)`，包括原核心。它们不是 GDS 测得结面积/周长，不能混称 actual layout PEX。

内部节点：`VH VL HSET LSET HPB LPB HTAIL LTAIL HN1 LN1 HG LG DI N1 CTRL`；`HC LC` 是 ESR 后的片外去耦节点。flat MOS 连接可直接从源逐只读取，便于共同 runner 保存全部器件端差。

## 已执行的有限探针

工具：ngspice；PDK 来自 `build/nrz-reference-v2/selected-final-r2/inputs/pdk`，已复制冻结在本探针 `inputs/`。LED 使用已公开静态 I–V 模型 `lin2026-yellow20-dc.spice`，另加假设 200 fF、1 Ω / 0.5 nH；没有增加测得光学或温度性能的声明。

原始输出目录：[build/fair-driver-v1-a-probe](../../build/fair-driver-v1-a-probe/)。每个 case 保留实际 core/deck/log、压缩原始波形、输入/源/runner SHA 和结果。初次校准的 14 个 DC 执行均成功；汇总写入遇到 NumPy bool 的 JSON 序列化错误，已修正脚本，并从原 `result.json` 重建校准表，未重跑或改动 DC 数值。旧 runner 保存为 `runner-initial.py`。

| 条件 | 实际结果 | 解释边界 |
|---|---|---|
| 初始 180k/88k，TT DC | I0=24.439255 µA；I1=98.839895 µA | 接近但未校准 |
| 一次 TT 校准后 DC | I0=25.0000061 µA；I1=99.9999976 µA | 后续角落共同固定 RH/RL |
| 校准后两态轨电压 | VH=1.600007 / 1.599787 V；VL=1.166447 / 1.167113 V | 包含原输出对压降，不能直接照搬旧理想轨值 |
| 全上游端口 DC 功耗 | bit0=0.6197569 mW；bit1=0.9947345 mW | VIN/VDD/VREF + DATA 端口净取能；未包含外部电源内部静态/转换损耗 |
| 200 ns 交替 NRZ，0.5 Gb/s，100 ps 边沿 | VH 0.731 mVpp，VL 1.396 mVpp；导电峰 113.022 µA；后半窗端口均功耗 1.160530 mW | 单个周期图样；不是随机码、接收器或 BER 验收 |
| 50 µs 固定电平切换，10 µs 升/约30 µs 降 | VH 1.172 mVpp，VL 4.130 mVpp；最终回到 25.000006 µA | 有限波形未见持续振荡，不等于 AC/PVT 稳定性证明 |

快波形若直接用未经传播延迟对齐的 DATA 中心采样，后半窗得到 I0≈40.865–40.873 µA、I1≈87.665–87.819 µA。这反映原核心与负载的传播/充电效应，必须交给同一接收条件与时序规则评估，不能用 DC 25/100 µA 代替动态电平，更不能据此宣布通信通过或失败。

当前脚本只给出**完整 TX 外部端口能耗范围**。后续公平报告可另报原驱动核心的 cut-boundary 能耗，但须在相同实际轨波形上积分，并与含参考/轨发生器的总端口范围分开；不能给 A 免费理想轨、同时让 B 承担参考成本。以上均不是含 RX/时钟/FEC/外部稳压器内部损耗的完整链路能耗。

## 启动诊断：失败与限制必须保留

VIN（同时为 LED anode）、VDD、VREF 共同从 0 在 1 µs 内升至标称值；固定 bit1 的 DATA 同步升至 VDD，固定 bit0 为 0。仿真至 1 ms，最大时间步 1 µs，记录自适应输出中的采样峰值；没有证明连续时间峰值或任意电源顺序的覆盖。

| 固定数据 | LED 导电采样峰 | 电源全幅后最后一次在目标 ±5% 之外 | XPOUT 最大 D-to-body 正偏 |
|---|---:|---:|---:|
| bit0，目标25 µA | **449.586 µA** | **117.0003 µs** | **0.823005 V** |
| bit1，目标100 µA | **1319.283 µA** | **41.2689 µs** | **0.791945 V** |

两例在 1 ms 终点均回到目标区间，但大幅冲流及 PMOS 输出漏结正偏意味着启动/可靠性仍未闭合。最大绝对 MOS 端差约 5.00022 V，并不能覆盖或消除体结注入风险。正常 OP 快波形的 XPOUT 最大 D-to-body 正偏约 0.15111 V；这也是采样诊断，不是工艺可靠性签核。

完整诊断数值存于 `selected-r1-diagnostic.json`；失败波形 `tt-start-b0-r1/waveform.dat.gz`、`tt-start-b1-r1/waveform.dat.gz` 保留。下一步若要闭合启动，应先制定安全电源/输出隔离与轨预充合同，再设计实际保护；本候选没有借 DISABLE 名称假装已经实现。

## 复现与交接

所有命令在工程根执行，case 名称必须使用新名称，脚本拒绝覆盖旧目录。200 MiB 探针目录预算与至少 5 GiB 可用空间门槛启用，使用共同 NRZ ngspice 锁；当前探针约 10.5 MB，没有新布局。

```sh
build/layout/venv/bin/python scripts/fair_driver_v1/a_support_probe.py calibrate --name repro-tt
build/layout/venv/bin/python scripts/fair_driver_v1/a_support_probe.py fast --name repro-fast --rh 177683.3997653013 --rl 87444.56014738003
build/layout/venv/bin/python scripts/fair_driver_v1/a_support_probe.py step --name repro-step --rh 177683.3997653013 --rl 87444.56014738003
build/layout/venv/bin/python scripts/fair_driver_v1/a_support_probe.py startup --name repro-start-b0 --bit 0 --rh 177683.3997653013 --rl 87444.56014738003
build/layout/venv/bin/python scripts/fair_driver_v1/a_support_probe.py startup --name repro-start-b1 --bit 1 --rh 177683.3997653013 --rl 87444.56014738003
```

本次交付可用于下一阶段共同 runner 的 **A 候选**。只有配对后才能判断在共同净吞吐、I0/I1、TT 单次校准、相同 LED/光路及两种功耗范围下的取舍；不预先排名，不把这次局部探针提升为公平比较已经完成。
