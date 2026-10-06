# 从 1 Pixel 开始的实验性研发方法验证路线

更新日期：2026-10-06。本项目用于**实验性研发方法验证与教学**，从独立假设出发，用可复现实验研究 MicroLED 器件电测与驱动共设计；每次规模扩展均由明确的实验问题决定。v0.4在既有registered PWM、W20/L4 analog layout、公开静态LED数据和共同GDS上，增加实际输出级junction／cell metal与联合signal PEX、五种RCstyle及有预设门槛的电气研究。带pads/ESD完整芯片、实际PG／substrate／邻居驱动网络、real reference、LED动态／温度、provider接受与silicon／optical仍属后续。

每一步先达到明确 exit criteria，再扩展规模；结果始终区分 simulation、layout/physical verification、foundry acceptance 和 silicon measurement。

起于旧 10/2 版本的 [独立审阅](review/README.md) 修复了 LVS 忽略 property errors 的判定漏洞，并明确不能只靠 nominal 或 fixed-corner pass 判断精度。后续按同一预设指标发现旧版最差条件 MC 有 4/256 超限，因此采用 20/4，并用真实新提取结果重新验证。

| 当前完成项 | 可检查的结果与入口 |
|---|---|
| 单像素 analog layout | W/L=20/4 µm；GDS cell 边界 95×37.66 µm，面积 3577.7 µm²，比旧版增加 41.26%；严格 DRC/LVS、GDS roundtrip 与 7/7 nets RC extraction 通过，见[版图说明](layout/README.md) |
| Accuracy / reference / mismatch | 预设 absolute-current ±5%、最低码电荷 ±2%；实际 RC 的 1080 点 PVT/reference 范围 99.28026–102.07565 µA，五组各 256 MC 样本无超限，三条件最低码最大误差 0.76830%，见[研究报告](research/reference-and-matching.md) |
| 真实 LED static 数据 | 可追溯 20 µm 方形黄色 InGaN 曲线与 model card；真实曲线/实际 RC 静态耦合完成，动态、测量温度和光学仍有缺口，见[实测数据说明](research/measured-led.md) |
| 数字 registered PWM | 输出改由 FF 驱动，保留 256-slot/frame 语义；synthesis 与 gate-level 回归完成，见[数字验证](digital/README.md) |
| 数字 macro 与独立检查 | PWM macro 物理实现及独立 KLayout rule-deck 检查已完成；具体工具、timing 条件、GDS/LEF 及 deck 覆盖见[物理实现](digital/physical.md) |
| 共同 macro top 与真实接口 | 实际 PWM / PG routing、共同 full-GDS extraction / transistor LVS / DRC、label-free connectivity 与负对照；54 transient输出级研究，见[集成](../evidence/integration/README.md)、[接口](research/interface.md) |
| v0.4联合signal PEX | 实际output12六MOS加像素六MOS，nominal45R／77C、34邻居端口；5种RCstyle；实际M3右端cut；PG-only理想化及原始projection ledger见[joint PEX](research/joint-pex.md) |
| v0.4主研究与失败边界 | 主37 transient／12 DC、146guards通过；总66 transient／28 DC另3calibration；startup、reference、control与实测LED headroom失败分开报告，见[电气研究](research/robustness.md) |
| 研究方法与教学资料 | [分层报告](research/research-report.md)、[bench计划](research/bench-validation-plan.md)、[实验方法与研究价值](research/technical-value-market.md)；独立实验问题、预算与证据边界 |

当前顺序：**单像素real reference／安全上电控制与PG／邻居网络 → 真实LED动态／温度／光学及bench数据 → 独立复现与实验问题复核 → 4×4共享reference／供电／通信实验 → 按测量需要评估MPW**。独立frame／mask场景可先在functional模型中研究，并将selected pixel接回既有单像素路径；该新模型尚未实现，也不替代物理阵列的进入条件。所有4×4面积、功耗、buffer和packet数字只是场景预算，未实现；MPW／封装尚无实际报价。有限MC和公开deck pass不等于制造yield或foundry acceptance。

## 1. 1-Pixel simulation baseline

范围：独立设计 PWM RTL、GF180MCU 6 V MOS current mirror / PWM switching cell、external ideal current reference、简化 MicroLED 电气模型，以及 event trace → PWL → ngspice 的单向联动。这条基础回归已完成并保留，用来理解各部分；后续更真实的条件在独立证据中验证。

Exit criteria：

- 从 locked dependencies 和校验过的公开模型出发，能用仓库命令复现；保存实际 tool versions、netlists、原始波形与 metrics。
- RTL 自检覆盖 duty endpoints、中间灰阶和 reset/enable 行为；实际 PWM event trace 驱动 SPICE，不使用另一个独立 PWM 波形替代 RTL。
- LED model 在指定 reference current / temperature 下通过独立校准；明确这是 synthetic electrical model。
- 能解释 LED current waveform、完整 frame 的平均电流与 duty 的关系；Vf sweep、headroom negative control 和 timestep refinement 有可检查结果。
- 文档明确该 baseline 的理想 reference/供电、尺寸、有限 output resistance、无 layout parasitics 和无光学模型等假设；新增 layout、实测 static 负载和 reference 实验独立标注，不能混写成同一个验证等级。

已补齐一条公开实测 LED I–V、20×20 µm² mesa 面积与 model card，并在[单像素 v0.2 指标](specifications/single-pixel-v0.2.md)中声明精度、短脉冲和研究 envelope。135 点实测 static 耦合矩阵在 MOS 27°C 等条件下给出 98.17501–100.98377 µA，另外保存 headroom 与功耗探针。仍需要 C–V/impedance 或 transient、I–V(T)、测量不确定度与光学数据；未知测量温度不能默认为 27°C。Synthetic 单点 DC 校准只确认模型按设定运行，不能替代这些物理资料。

当前阶段的证据由 README 链接的结果和运行 `summary.json` 给出；具体样本数、检查数和误差以对应运行记录为准。

## 2. 1-Pixel transistor layout、DRC/LVS/PEX

范围：先取得锁定版本的完整 `gf180mcuD` PDK 和 EDA 环境；把已仿真的 analog cell 做成真正 transistor-level layout，并把数字 PWM block harden 后作为可集成模块。

Exit criteria：

- 明确 full PDK variant、build hash、tool/deck version；schematic/source netlist 与此前 SPICE baseline 对齐。
- Analog layout 包含 device geometry、well/substrate ties、guard rings、contacts、routing 和可辨认 pins；布局采用可解释的 matching 方法。
- DRC 无未解释错误；LVS 必须同时确认 connectivity 与 deck 检查的参数，拒绝 property errors，保存完整报告与任何必要 waiver 的来源。当前 deck 的 W/L tolerance 为 1%，允许 D/S 交换，忽略 AD/AS/PD/PS 等属性；不得把通过扩大为全部几何/寄生属性一致。
- PEX 后重新仿真 PWM、current、headroom 和关键 corners；量化与 pre-layout 的差异。当前 schematic 与 extracted RC 同时存在 diffusion geometry 和 wiring RC 差异，必要时增加无 wiring RC 的几何抽取中间对照，避免把全部变化归因于连线。
- 明确非理想 reference 的 accuracy、drift、compliance、启动和 power sequencing；在已定义的误差/功耗/最短脉冲预算下做 mismatch 与交叉 PVT 验证。区分目标电流误差、版图前后变化和 timestep 收敛误差。
- 数字 PWM 的 synthesis / timing / placement / routing 有保存结果；模拟 macro 具有 GDS / LEF / SPICE 和明确接口假设。
- GDS 可打开、检查且具有一致 layer mapping。此结果标为通过所选 open decks 的 physical verification；只有实际 foundry/shuttle 接受后才声称满足其 signoff。

当前进度：实际 20/4 模拟 cell 完成 Magic DRC=0、Netgen 唯一匹配且无 property errors、GDS 回读、7/7 nets RC extraction 与 19 项配对/收敛 guards；并导出 GDS/LEF/SPICE。Reference 预算与 PDK 随机失配已独立复验，使用的是新结几何与新 RC，旧 10/2 失败及概念候选均保留。数字 registered-PWM macro 物理流程与独立 KLayout 检查也已完成，分别见[模拟版图](layout/README.md)、[reference/matching](research/reference-and-matching.md)、[数字物理实现](digital/physical.md)。

旧native KLayout启动问题保留为历史环境记录。v0.3按[集成退出条件](specifications/single-pixel-v0.3.md)完成共同top、full-GDS transistor LVS／DRC、独立geometry与真实错误检测；分块buf／analogRC／link电气结果冻结保留。v0.4按[joint目标](specifications/joint-pex-v0.4.md)取得真实末级junction与selected联合signal模型，从实际右侧接入，并用一份post模型替换旧分块路径；重现按语义而非记录排序字节检查。

v0.4 PG/body电阻和PG-only电容仍是ideal-rail投影，34邻居的quiet／live-high clamp不建立其真实floating／active状态。Startup能量没有完整PG、preceding FF/logic或真实reference，因此probe完成不等于系统启动资格。[电气研究](research/robustness.md)保留10kΩ假设LED供电下的current失败及enable提交延迟，下一步应按用户要求决定reference/compliance、POR/关断控制与测量条件，而不是先扩像素。实际PG／邻居网络、real LED dynamics、digital total power、pad/ESD及制造要求仍需闭环。

## 3. 4×4 array

范围：复制已验证 pixel cell，加入独立定义的最小 register / pixel-data / serial interface 和 array timing。先研究 replication、reference distribution、PWM timing 与 power routing。

进入条件：单像素在选定LED/model card、可实现reference及声明PVT/mismatch下达到accuracy、power和short-pulse预算，并完成相应matching／独立physical检查；明确至少一项需要多像素才能检验的实验假设及其通过／失败条件。当前尚未满足，继续单像素和[bench计划](research/bench-validation-plan.md)。优先研究共享reference能否降低持续bias功耗，先验证fanout、startup、失配与跨通道耦合；不把预算省电量称为已实现。

Exit criteria：

- 独立协议与 register map 有文档及可执行 testbench，覆盖全部 16 个 pixel 的寻址、更新、reset/enable 和 test patterns。
- 可生成并检查阵列 current / PWM patterns，解释同时点亮负载、数据更新和帧同步行为。
- 保存各 pixel 与全阵列的供电/current budget；评估 shared reference、IR drop、clock distribution、routing 和 matching。
- 面积从actual cell、shared logic/reference、routing和pads/ESD分别建账；305×180µm是共同macro跨度，不能乘16当作array die。数据更新频率、PWM frame与serial wire rate分开声明，prototype packet预算要通过实际testbench。
- 阵列级 DRC/LVS 和必要 PEX / post-layout 分析完成；结果允许定位到具体 pixel，不能仅证明单个 cell。
- 新接口与验证仍完全来自公开资料及本项目独立设计。

## 4. 8×8、16×16

范围：逐级扩展 memory、command handling、clock/power network 与 array integration；按证据引入可编程 current 或 calibration。

Exit criteria：

- 每一级均有可复现 functional、timing、physical 与 post-layout regression，保存面积、power/current、routing congestion 和 clock/IR-drop 条件。
- 对 simultaneous switching、reference loading、pixel current spread 与 shortest PWM pulse 的误差给出量化结果。
- 数据更新带宽、memory size、PWM resolution / frequency 与 frame timing 是有依据的预算，并在 testbench 验证。
- 先解决上一规模暴露的问题，再进入下一规模；precision DAC、gamma、diagnostics、ADC、temperature/aging compensation 按需求逐项加入。

## 5. MPW feasibility 与 tape-out review

范围：带着明确silicon measurement问题，在可检查的GDS和post-layout证据上评估实际shuttle、package、pads/ESD/IO、power与test strategy。公开route存在不代表当前可提交；GF180MCU与其他BCD、SKY130 analog模板/报价不能互换。[实验方法与研究价值](research/technical-value-market.md)说明进入实物研究前所需的证据与资源边界。

Exit criteria：

- 有实际候选 MPW provider 对工艺/variant、PDK/tool/deck 版本、analog voltage/current/pin limits 和提交格式的当前要求。
- 完成 pad ring、IO、ESD、seal ring、density/fill、antenna、可靠性相关规则及 package / bond-wire / board interface review。
- 用对方要求的验证工具和规则完成审核，保存接受证据；补齐 PVT / mismatch / extracted simulation 与可执行 bring-up plan。
- 明确费用、deadline、package、交付数量和测试责任；真正购买/提交前形成可审阅设计包。
- 投片与 silicon bring-up 分开报告；电气 measurements、真实 MicroLED drive 和 optical output 均有条件、原始数据及误差边界。

## 2026-10-06：独立控制与电气实验平台

本轮[研发方法验证报告](research/experimental-methods/report.md)与[平台计划](research/experimental-methods/platform-plan.md)围绕独立假设定义控制、芯片、电气与仿真层之间的实验关系。研究对象包括帧更新是否完整、故障是否被检测、量化如何影响单像素电荷，以及reference／供电／保护条件如何改变输出。工程基线仍为v0.4；新的场景模型、帧缓存和控制器联动路径尚未实现。

下一实施包先定义独立synthetic scene／mask → golden frame → 完整帧校验／双buffer atomic commit → selected pixel量化 → 既有RTL／PWL／冻结joint PEX的可复现路径。帧格式、时序、错误处理和通过／失败条件由本项目独立定义。全logical image仅在functional模型中存在；它不改变上面4×4 physical的进入条件。至少一个正常场景和一个错误更新对照须保留frame／source hashes、分段latency、量化误差和电荷积分，形成可检查的实验记录后才报告实现完成。

单像素reference／startup／保护blank、真实PG／邻居及同器件dynamic／optical bench继续是工程优先门槛。先明确可测负载、仪器、原始数据格式、温度和测量不确定度，再确定硬件平台与后续阵列；不默认拥有FPGA、camera或测量仪器。未来硬件的作用是检验已声明假设，并量化模型与测量之间的差异。

## 与独立 FPGA 项目的关系

ASIC 与 FPGA 保持独立 repositories。长期分工设想是 FPGA 负责 frame / mapping / scheduling / system control，ASIC 负责本地 data reception / pixel state / PWM / current drive。**双方接口当前尚未定义或联调验证**；需要后续共同固定 voltage、physical signals、clocking、protocol、reset/fault behavior 和 throughput budget。

本阶段不会用 FPGA 项目的既有验证结果替代 ASIC 验证，也不会用 ASIC synthetic LED simulation 宣称真实光链路或光输出已得到验证。
