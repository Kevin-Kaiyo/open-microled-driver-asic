# 单像素共同顶层的独立集成审查

2026-10-04（Asia/Tokyo）。审查基线为已发布的 v0.2 analog 与 digital macro；本轮新增范围在 [v0.3 specification](../specifications/single-pixel-v0.3.md) 中预先确定。本文件独立检查接口及验收范围；新增 top 的结果须以其实际 GDS、抽取网表与运行日志补充，不能由两个 macro 的旧通过结果推出。

## 1. 架构与电压域

共同顶层的工作路径是 `clk / rst / enable / duty → registered PWM → 真实末级输出单元 → 跨宏金属连线 → 六 MOS analog driver → 外部 LED cathode`。LED anode 接外部 nominal 5 V；reference current 从外部注入 bias。数字 VDD 与模拟 vlogic 均为 nominal 3.3 V，VSS 共地。此阶段不在 top 内制造 reference generator、LED、pad ring、ESD 或 package。

标准单元名称含 `5v0`，但该库公开提供 nominal 3.3 V 的 TT / SS / FF characterization；本项目实际 config 选择 3.3 / 3.0 / 3.6 V Liberty，不能使用默认 5 V view 后仍称 3.3 V timing。[官方 MCU7 PVT corners](https://gf180mcu-pdk.readthedocs.io/en/latest/digital/standard_cells/gf180mcu_fd_sc_mcu7t5v0/spec/corners.html)与[本项目物理 config](../../layout/digital/config.json)分别记录原始规格与本次选择。

模拟选用 `nfet_06v0 / pfet_06v0`，是为了处理 LED 支路的电压余量及本电路的偏置条件。器件名中的 6 V 不等于任意 rail、任意上电顺序都得到可靠性保证。应记录实际内部 VGS / VGD / VGB / VDS、过冲、body diode 电流和持续时间，而非只记录外部 led_k 对全局地的电压。公开规则把 supply、电极间电压、HCI 和 oxide constraints 分开，并强调多电源条件；当前联合仿真只是选定条件下的电路证据。[GF180MCU operating conditions](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html)。

## 2. 实际端口合同

模拟 golden schematic 与 extracted SPICE 的顺序为 `VSS bias gate pwm pwm_b led_k vlogic`，共有 7 pins。原 `analog/driver/pixel_driver.spice` 的早期教学 subckt 使用全局 node 0，不能直接替代共同顶层的显式 VSS 合同。[显式 VSS schematic](../../layout/pixel_driver_schematic.spice)、[actual extracted analog](../../evidence/layout/pixel_driver_layout.spice)、[analog LEF](../../evidence/layout/pixel_driver_layout.lef)。

| 原 macro port | 顶层对应 | 应验证的含义 |
| --- | --- | --- |
| digital VDD / analog vlogic | VDD | nominal 3.3 V；实际金属连通，不能只依 net 名 |
| digital VSS / analog VSS | VSS | 共同 reference ground 与 bulk return |
| digital pwm / analog pwm | 内部 pwm_int | 唯一输出驱动；连接两块实际几何端口 |
| digital clk / rst / enable | 同名外部输入 | 外部信号仍能定位到正确 macro pins |
| digital duty[0]…duty[8] | 9 个独立 scalar endpoints | 位序及拼写保持；SPICE pin order 不直接照抄 Verilog header |
| analog bias | 外部 bias | 100 µA reference-current injection；不是 voltage source pin |
| analog led_k | 外部 led_k | 外部 LED cathode；VLED 阳极电源不进入 digital VDD |
| analog gate / pwm_b | 外部 monitor ports | 保留教学检查接口；未包含 pad / probe / package 实际负载 |

数字 LEF 共 15 pins：VDD/VSS、clk/rst/enable/pwm、9 duty bits。模拟的 7 个 instance pins 都应保留。若 PWM 只作内部连接，共同 top 最低为 18 个外部 pins；若另加 `pwm_monitor`，则为 19 个，需明确命名与负载。保留 monitor ports 不意味着它们可无限加载：gate 的 probe capacitance 会改变最低码波形，应继续与外部实际接口预算分开。

独立初审对 final PNL 的全部 887 instances / 34 leaf types 逐 pin 扫描：657 个实例有 VNW/VPW，全部 VNW→VDD、VPW→VSS；VDD/VSS 映射无错误。另有 156 filltie、74 endcap。此检查证明文件中的 tie mapping，并不单独证明版图几何接触连续、IR drop 或 latch-up immunity。数据来自 [final powered netlist](../../evidence/physical/digital/pnl/pixel_pwm.pnl.v)，SHA-256 `924c0d8c9c17d03042c3e05fdae64c4c4563a1148e07af83c7195e43095804bd`。

## 3. LEF origin 与真实 GDS 坐标

两份实际 GDS 都使用 0.001 µm database unit。数字 GDS top `pixel_pwm` bbox 为 `(0, 0)…(180, 180)` µm，含 34 leaf cells，共 35 cells；模拟 GDS top `pixel_driver_layout` 为单一 flat cell，bbox 为 `(0, −0.3)…(95, 37.36)` µm。模拟 LEF 的 SIZE 是 95 × 37.66 µm，ORIGIN 是 `(0, 0.3)`，不是 `(0, 0)`。[macro views](../../evidence/layout/macro-views.json)、[真实 OpenDB consumer 检查](../../evidence/physical/macro-read.json)。

因此 R0 放置若要求模拟实际 bbox 左下角为 `(a, b)`，GDS instance translation 应为 `(a, b + 0.3)`。此公式来自实际 GDS bbox；其他方向应对完整 bbox / port polygons 做变换，再比较实际落点。最低检查应包括 GDS hierarchy transform、端口 rectangles、真实抽取 labels 与对应网表，而非仅比较 width/height。负坐标 port rectangle 在 origin-adjusted bbox 内是当前 LEF 的合法数据，不能擅自 clamp 到 0 后仍声称同一接口。

模拟信号和 PG ports 位于 Metal3；数字信号 ports 在 Metal3，VDD/VSS 暴露 Metal4 / Metal5 rectangles。因此实际 PG connection 需要对应 Metal/Via stack；M3 与 M4 或 M5 的平面投影相交不构成导通。所有 routing 应以真实 pin geometries 和锁定 PDK 的 via/enclosure/spacing 规则为准。宏间开路未必违反 DRC；其检测由 connectivity / extraction / LVS 完成。

## 4. LVS 究竟比较什么

模拟 cell 已验证到六个 MOS 的连接、model class 与 W/L。锁定 deck 允许 MOS D/S permutation，并对 W/L 使用 1% tolerance；AD/AS/PD/PS 等已被删除的比较属性不能因 LVS 通过而认为匹配。[模拟 LVS scope](../layout/README.md)。

v0.2 数字 standalone extraction 产生的是各 standard cell 的 `abstract view` 空 subckt。旧数字 LVS 报告中出现 `Cell … disconnected node`，对应这些空 leaf pins；最终仍有 15 pins、122 merged devices / 131 nets 的唯一匹配。它检验 standard-cell 类型及其布线，没有重新验证每个数字单元内部 MOS。[历史数字 LVS report](../../evidence/physical/digital/lvs.rpt)。

v0.3 的稳定 r3 改为从共同 GDS 进行 full hierarchical extraction，并将数字内部 MOS 与实际 canonical standard-cell transistor SPICE 比较，已超过上述最低层次范围。独立读取 actual SPICE 与 Netgen JSON，确认 30 个保留的 digital leaf classes 内部均有 5 V MOS，analog cell 是 6 个 6 V MOS；33 个层次化电路比较均无 badnets / badelements / property errors。数字宏提取后有 506 个 retained instances；按各类内部 MOS 数量与实例数独立加权为 5638 MOS calls，其中 decap 为 4404，另有 analog 6 MOS。这是 parallel combining 前的层次网表计数，不能把 top 的两个 macro instances 当成两个晶体管。r3 与初次 r1 的完整提取 SPICE 逐 byte 相同，hash 为 `fd9aad23c41f4b6b25c8b376467e81f14e7b1f504f752171f4d758345b23b56c`。最终 source 与公开日志见[集成索引](../../evidence/integration/summary.json)、[full extracted SPICE](../../evidence/integration/pixel_integrated.spice)、[full Netgen report](../../evidence/integration/netgen-lvs.log)。

日志中的 `nfet_05v0 / pfet_05v0 / nfet_06v0 / pfet_06v0` 四端 primitive placeholders 作为 MOS model classes 使用，不等于把整个数字 standard cell 隐去。独立真实负对照仅把 golden `buf_2` 的输入 NMOS W 从 0.82 µm 改到 1.64 µm：Netgen exit 0、final 仍写 unique match，但产生 property errors，严格 guard 拒绝；只把 golden `output12` 的 VNW 从 VDD 改接 VSS，则 pin matching 失败。这证明该方式实际比较了数字内部器件 W 与 active body mapping。结论仍限于锁定 deck 比较的 MOS topology / W/L / body terminals，不涵盖被忽略的 filltie/endcap/fill_*、删除的 diffusion geometry properties、器件模型准确性或可靠性。完整小日志见 [baseline](../../evidence/research/integration-review/baseline.log)、[width mutation](../../evidence/research/integration-review/buf2-width.log)、[body mutation](../../evidence/research/integration-review/body-tie.log)。

公开 pinned Netgen setup 忽略 digital endcap、fill_*、filltie，并允许 fillcap 等 parallel merging；这意味着这些 cell 的 presence / count / body-tie routing 不能只依最终 match sentence 判断。[Pinned GF180 Netgen setup](https://github.com/fossi-foundation/open-pdks/blob/54435919abffb937387ec956209f9cf5fd2dfbee/gf180mcu/netgen/gf180mcu_setup.tcl)。因此新增 PG/tie 检查要逐实例保留 VNW / VPW 映射和真实 top 电源连续性，不能把 library abstractions 全部替换成一个不透明 digital macro 后仍称验证了全部内部 PG。

比较时须保存独立 golden top 与 actual extracted top；禁止两边都从同一 extraction 自动生成，或仅依据 label 名补上缺失连接。要求唯一 final result、没有 connectivity / property errors，且 top pin set、位序、外部 PG、两个 macro instances 和跨宏 PWM correspondence 都能审查。抽取网表中没有 global 0 代替遗漏的 VSS。若 digital leaf 保持 abstraction，其 source identity 与上一级原验证结果均应锁定。

## 5. 本轮最低验收证据

| Gate | 成功所需的最小证据 | 不由该项推出的结论 |
| --- | --- | --- |
| A：接口与输入身份 | 两份冻结 GDS/LEF/netlist 的 hashes、预设端口表、hierarchy transforms、实际尺寸 / pin locations；inputs 在运行前固定 | 合并后电气连通 |
| B：共同几何 | 共同 top GDS 实际读回，两个真实 macro 保留；所有新 Metal/Via 及 top labels 可定位；Magic DRC 与独立 KLayout deck 实际跑在此 GDS，errors=0，记录模式与 excluded rules | 芯片 density、antenna、pads/ESD、foundry signoff |
| C：共同电气连通 | 独立 golden vs actual top extraction 的严格 LVS；PG/VNW/VPW/body mapping 审查；单一 PWM driver；无 supply short / signal alias；正确 baseline 与预设负对照均留日志。数字内部 MOS 的额外检查按上述实际新增范围记录 | 被 deck 忽略的 cells / properties、IR drop / EM / substrate-noise qualification |
| D：新增 routing R/C | 来自 actual routing geometry / extraction 的各连线端点、R/C 数值与单位、net coverage、PDK/tool/extraction style、原始网表；清楚区分 standalone 内部 RC 与跨宏新增 RC | 多角落 joint PEX signoff、与 silicon 校准的 parasitics |
| E：输出级闭环 | actual implemented 末级 cell 的 canonical transistor SPICE + analog actual RC；real output / ideal-source 配对；off/duty1/mid/full、三声明条件、fine-step 检查、冻结积分窗口；报告边沿 / 端电压 / 电流 / Q1 | 整条数字逻辑 transistor transient、真实 LED 动态 / 光输出 |
| F：准确性与方向 | full-on 100 µA±5%，`Q1/(Ifull×1 µs)−1` ±2%；以实际 Liberty 阈值核对 3 ns slew；未通过结果保留，physical 与 electrical 条件对应 | 有限 MC 样本对应制造 yield、全部温压范围通过 |

跨宏 R/C 若仅采用线长、宽度和表中 sheet resistance / capacitance 估算，应称 geometry estimate，而非 actual PEX。若抽取仅覆盖 top routing，也应称 top-route extraction，而非全部数字 / 模拟内部 joint PEX。耦合仿真应避免把数字 SPEF、末级 cell 本身 SPICE、模拟 RC 和新连线 R/C 的同一寄生重复加入。初步功耗应分别给 digital supply、analog / reference、LED rail，与缺失的 reference generator、pads / board 损耗分开。

## 6. 负对照必须能拒绝什么

在保持 golden top、端点 labels 与原两个 macro 不变的情况下，独立复制布局并做以下错误注入；错误不得进入 baseline：

1. 实际删除跨宏 PWM 中央金属段。提取 / connectivity / LVS 应拒绝 open；仅把原理图 net 名改错不证明物理断线检测有效。
2. 实际桥接 VDD 与 VSS，或遗漏 analog vlogic 的接入。应由声明的供电连通 / LVS 检查拒绝；电源 global-name 合并不能掩盖物理断开。
3. 在 comparator input 中将 analog MOUT W 改成明显不同的值。应拒绝 property mismatch；Netgen exit 0 或 match sentence 不足以构成 pass。
4. 对 LEF/GDS 的 origin / bbox 或源 hashes 做错误输入。边界与 provenance guard 应拒绝，不能更新 expected hash 以消除失败。

LVS 若按 global / 重复 labels 把几何分离的区域按名合并，必须真实记录该局限，并增加 Metal/Via 连通图、可审查 extraction node 连续性或其他能够拒绝第 1 / 2 项的方法。没有规则违反的 open 不要求 DRC 报错。成功 baseline、同一错误被拒绝的方法、错误输出与失败日志应一一对应。

## 7. 新证据的复核状态

初审已完成 v0.2 输入端口、GDS 几何、PNL body-tie mapping 和实际 LVS abstraction scope 的核对。随后对稳定 r3 candidate 完成独立复核：两份原 macro 共 36 cells 的 direct shapes 和 instance hierarchy 保持相同；共同 top 有 37 cells、两个 macro instances、19 个外部 pins，实际 bbox 为 305 × 180 µm，即 54900 µm²。除了 LVS，还建立不依赖 net labels 的 M3/M4/M5 + Via3/Via4 几何连通图，包含 168 个导体区域，确认 PWM、VDD、VSS 分别跨宏连续，三者互不短接。实际 Magic `drc(full)` 为 0，独立 KLayout XML items 为 0。21 个独立检查与三个实际 Netgen comparison cases 均通过预定判断，见[公开独立检查索引](../../evidence/research/integration-review.json)。

复现本独立审查需要既有完成的 raw r3 run、locked PDK、项目 Lima VM 与 KLayout Python；运行 `build/layout/venv/bin/python scripts/research/review_integration.py --run build/integration/r3`。脚本不修改 baseline / PDK，mutation 副本与原始日志保留在新 `build/integration-review/review-*` 目录，公开日志去除了本机绝对路径。运行过程不重跑电路仿真。

独立器件尺寸 / body-tie 负对照已通过拒绝测试。最终实际 PWM 删段及 PG bridge controls 也已公开：保持 golden / endpoint labels 不变，在 top M3 实际删除 x=130…132 µm；另外在共同 VDD/VSS 间建立真实金属 / Via4 桥。两者 Magic DRC 均为 0，仍分别由真实 extraction / Netgen 与不依赖 labels 的金属连通检查拒绝，符合本文件事先说明的 electrical-open / short scope。[PWM open 证据](../../evidence/integration/negative-controls/pwm-open/control.json)、[PG short 证据](../../evidence/integration/negative-controls/pg-short/control.json)。

新增 routing extraction 仅覆盖两个 macro 边缘间 30 µm、宽 0.56 µm 的 PWM M3 span，R=4.81871 Ω，涉及信号的 capacitance 总和为 2.34604 fF。helper 本身没有 substrate contacts；原始 `pw` substrate node 被映射到实际 full-top 已连到 VSS 的 pwell / VPW boundary。原始和 normalized 网表均保留，并有 full `.ext` 的 merge-chain 证据。此处理不是新增一个测得的 substrate impedance，也不代表全部 joint PEX；PG rails 在后续 probe 中仍为理想边界。[RC 方法与原始数据](../../evidence/integration/link-rc.json)、[substrate correspondence](../../evidence/integration/substrate-proof.json)。

最终 54 组主瞬态与 6 组慢输入 stress 未重跑模拟而进行了独立原始数据复算，同时核对 12 个 DC points、5 bias / 25 AC table points、三组完整切换电荷的长短窗 / energy、公开 CSV 与 summary。所有 3014 个数值、身份与表一致性 assertions 通过；这是审阅 assertions 的计数，不是 3014 个独立工程工况。电流复算最大差为 1.42×10⁻¹⁴ µA，边沿和 pulse-width 重算一致，说明公开计算与波形数据一致，并非模型或真实器件的不确定度如此小。[独立电气复算](../../evidence/research/interface-review.json)、[可复现脚本](../../scripts/research/review_interface.py)。

as-run link hash `b43d95d8…` 与 current `f56728da…` 保持分别记录；独立 exact signature 比较四个 formal ports 的顺序及 R/C 类型、端点、Decimal 数值和重数，只忽略实例名与行序。改 R、删 C、重复 C、改端点、改类型、交换 port order 的六种独立负对照均被拒绝，因此没有将旧 source hash 重写成 current。

电气方法的单位和解释成立：`Cparallel=Im(Y)/(2πf)` 是 bias / frequency 条件下整个模拟输入端口的 small-signal response；signed `Q/3.3V` 是完整切换及 settling 的电荷等效负载，均不是独立且恒定的器件 C。实际 slew 采用 locked Liberty 的 rise 30–70% / fall 70–30%，pulse width 用 50% crossings。buffer 输入 full ramp 1 ns，以及另测 full ramp 7.5 ns（对应 input 30–70%=3 ns），均是声明的末级输入 stimulus；ideal replay 的 10 ns ramp 位于模拟输入。两侧电流差不能全部归因于 output resistance；preceding FF / CQ / logic transistor waveform、末级 cell 自身 PEX、非理想 PG 与真实 LED 动态仍未建立。[完整接口条件与结果](interface.md)。
