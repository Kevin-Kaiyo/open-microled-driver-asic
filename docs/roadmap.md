# 从 1 Pixel 到可评估 MPW 的路线

本项目建立一个长期的 open mixed-signal ASIC 学习与研究平台。当前交付范围是 **1-Pixel RTL PWM → transistor driver → synthetic MicroLED electrical model 的可复现仿真路径**。完成这个里程碑不等于用户完整愿景、完整 ASIC design flow 或全平台已经完成。

每一步先达到明确 exit criteria，再扩展规模；结果始终区分 simulation、layout/physical verification、foundry acceptance 和 silicon measurement。

## 1. 1-Pixel simulation baseline

范围：独立设计 PWM RTL、GF180MCU 6 V MOS current mirror / PWM switching cell、external ideal current reference、简化 MicroLED 电气模型，以及 event trace → PWL → ngspice 的单向联动。

Exit criteria：

- 从 locked dependencies 和校验过的公开模型出发，能用仓库命令复现；保存实际 tool versions、netlists、原始波形与 metrics。
- RTL 自检覆盖 duty endpoints、中间灰阶和 reset/enable 行为；实际 PWM event trace 驱动 SPICE，不使用另一个独立 PWM 波形替代 RTL。
- LED model 在指定 reference current / temperature 下通过独立校准；明确这是 synthetic electrical model。
- 能解释 LED current waveform、完整 frame 的平均电流与 duty 的关系；Vf sweep、headroom negative control 和 timestep refinement 有可检查结果。
- 文档列出理想 reference、供电、尺寸、有限 output resistance、没有 layout parasitics/光学模型/真实 LED measurement 等限制。

当前阶段的证据由 README 链接的结果和运行 `summary.json` 给出；具体样本数、检查数和误差以对应运行记录为准。

## 2. 1-Pixel transistor layout、DRC/LVS/PEX

范围：先取得锁定版本的完整 `gf180mcuD` PDK 和 EDA 环境；把已仿真的 analog cell 做成真正 transistor-level layout，并把数字 PWM block harden 后作为可集成模块。

Exit criteria：

- 明确 full PDK variant、build hash、tool/deck version；Xschem schematic netlist 与此前 SPICE baseline 对齐。
- Analog layout 包含 device geometry、well/substrate ties、guard rings、contacts、routing 和可辨认 pins；布局采用可解释的 matching 方法。
- DRC 无未解释错误；LVS 确认器件、参数和 connectivity 一致；保存完整报告与任何必要 waiver 的来源。
- PEX 后重新仿真 PWM、current、headroom 和关键 corners；量化与 pre-layout 的差异。
- 数字 PWM 的 synthesis / timing / placement / routing 有保存结果；模拟 macro 具有 GDS / LEF / SPICE 和明确接口假设。
- GDS 可打开、检查且具有一致 layer mapping。此结果标为通过所选 open decks 的 physical verification；只有实际 foundry/shuttle 接受后才声称满足其 signoff。

## 3. 4×4 array

范围：复制已验证 pixel cell，加入独立定义的最小 register / pixel-data / serial interface 和 array timing。先研究 replication、reference distribution、PWM timing 与 power routing。

Exit criteria：

- 独立协议与 register map 有文档及可执行 testbench，覆盖全部 16 个 pixel 的寻址、更新、reset/enable 和 test patterns。
- 可生成并检查阵列 current / PWM patterns，解释同时点亮负载、数据更新和帧同步行为。
- 保存各 pixel 与全阵列的供电/current budget；评估 shared reference、IR drop、clock distribution、routing 和 matching。
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

范围：在可检查的 GDS 和 post-layout 证据上评估真实 shuttle、package、pads、ESD、IO、power 和 test strategy。公开路线存在不代表本项目当前可提交。

Exit criteria：

- 有实际候选 MPW provider 对工艺/variant、PDK/tool/deck 版本、analog voltage/current/pin limits 和提交格式的当前要求。
- 完成 pad ring、IO、ESD、seal ring、density/fill、antenna、可靠性相关规则及 package / bond-wire / board interface review。
- 用对方要求的验证工具和规则完成审核，保存接受证据；补齐 PVT / mismatch / extracted simulation 与可执行 bring-up plan。
- 明确费用、deadline、package、交付数量和测试责任；真正购买/提交前形成可审阅设计包。
- 投片与 silicon bring-up 分开报告；电气 measurements、真实 MicroLED drive 和 optical output 均有条件、原始数据及误差边界。

## 与独立 FPGA 项目的关系

ASIC 与 FPGA 保持独立 repositories。长期分工设想是 FPGA 负责 frame / mapping / scheduling / system control，ASIC 负责本地 data reception / pixel state / PWM / current drive。**双方接口当前尚未定义或联调验证**；需要后续共同固定 voltage、physical signals、clocking、protocol、reset/fault behavior 和 throughput budget。

本阶段不会用 FPGA 项目的既有验证结果替代 ASIC 验证，也不会用 ASIC synthetic LED simulation 宣称真实光链路或光输出已得到验证。
