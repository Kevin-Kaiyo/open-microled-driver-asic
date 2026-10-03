# PDK 与开源工具链选择

查阅日期：2026-10-03（Asia/Tokyo）。本文只使用公开、可追溯的主来源。厂商规格、软件支持声明与本项目验证结果分开记录；下面的选择是项目工程判断，不是 foundry 认证。

2026-10-04 实施更新：完整 `gf180mcuD` 已用于20/4单像素模拟cell与标准单元PWM macro；实际数字flow选用 **LibreLane 3.0.14 pinned arm64 container + 项目独立Lima Linux VM**。既有Docker Desktop VM遇到storage attachment故障，没有reset用户磁盘；native Nix未安装。当前实际工具、成功检查、历史失败与复现见[digital physical](../digital/physical.md)；本页后续Nix/Docker比较保留为初始选型调研，不能当作已经安装和执行的路径。

## 1. 结论与适用范围

**Phase 1 选择 GF180MCU 的公开 6 V MOS models，先完成 1-Pixel 电路和 RTL PWM 的联动仿真。进入版图时，获取锁定版本的完整 `gf180mcuD` PDK；数字实现优先采用 LibreLane，模拟 cell 使用 Xschem / ngspice + Magic / Netgen / KLayout。**

选择 GF180MCU 的原因是本项目第一条路径需要 5 V LED supply、3.3 V control、低速 PWM 与低侧 current sink。公开 GF180MCU 有明确的 3.3 V 和 6 V NMOS / PMOS 模型，电压分域较容易解释。SKY130 也有适用的高压 MOS，因此并未排除；若以后 shuttle、IO 或电流精度要求改变，应重新评估，而不是把第一次模型选择当成最终投片工艺。[GF180 device list](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_1_4_1.html)、[SKY130 device details](https://skywater-pdk.readthedocs.io/en/main/rules/device-details.html#v-10-5v-nmos-fet)

本项目第一阶段下载的是 **SPICE model 子集，不是完整 PDK**。它不包含本项目所需的全部 technology files、PCell、DRC/LVS deck、LEF、Liberty 或 pad library。模型仿真通过只证明给定电路和条件下的模拟结果；不证明本项目已有 layout、DRC、LVS、PEX、GDS、silicon 或 tape-out readiness。

## 2. SKY130 与 GF180MCU 比较

下面是根据源文档整理的比较，器件标称电压、SPICE 有效区间、可靠性限制和 shuttle 可用选项需要分别检查。

| 决策因素 | SKY130 | GF180MCU | 对本项目的意义 |
|---|---|---|---|
| 基础工艺与 MOS | 130 nm；1.8 V NMOS / PMOS，包括部分低/高 Vt；另有 5 V / 10.5 V、native 与其他高压器件 | 180 nm MCU；3.3 V、6 V NMOS / PMOS、6 V native；文档另外列出 5 V 和 10 V LDMOS 类别 | 两者都能研究 LED current sink；不能把 core MOS 直接接到 LED 高压节点 |
| 5 V LED supply | `sky130_fd_pr__nfet_g5v0d10v5` 等高压器件可作为候选，需要处理 core/control 的电压差异 | `nmos_6p0` / `pmos_6p0` 适合本阶段候选电压域 | GF180 让第一版控制和驱动电压域较直观；这是工程判断 |
| 模拟元件 | 电阻、MIM / VPP capacitor、diode、BJT 等公开选项 | 电阻、MIM / MOSCAP、diode、BJT 等公开模型；有 corner 与部分统计模型 | 足够学习 mirror、cascode、reference 与 Current DAC；可用选项必须以实际锁定文件为准 |
| 开源工具兼容 | Open PDKs、Ciel 与 LibreLane 支持；`sky130A` 的 timing extraction 校准较好 | 相同工具栈支持；LibreLane 当前推荐 `gf180mcuD` | 使用打包后的完整 PDK，避免自行拼接不同版本 |
| Metal variant | `sky130A`：5 metal + local interconnect；`sky130B` 有 ReRAM 相关 BEOL 差异 | `gf180mcuD`：5 metal，较厚 top metal；历史 A/B/C 与 D 不可混用 | Phase 1 无 BEOL 验证；进入 layout 时显式固定 variant |
| 文档与社区路径 | 有完整器件规则与丰富公开 flow；可检查 Tiny Tapeout / ChipFoundry 的相应模板 | 有 MCU electrical / model / physical rules；可检查 wafer.space / Tiny Tapeout 的相应模板 | 模板存在说明有集成路线，不等于当前接受本设计 |
| 开放状态与 signoff | 公开文档仍标为 experimental preview / alpha，非 production PDK 保证 | 公开 README 同样保留 experimental preview / alpha 声明 | 学习/test chip 与 foundry production qualification 是不同证据层级 |

主来源：[SKY130 rules](https://skywater-pdk.readthedocs.io/en/main/rules.html)、[GF180 electrical specifications](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/spice_specs.html)、[GF180 device list](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_1_4_1.html)、[LibreLane PDKs](https://librelane.readthedocs.io/en/stable/usage/about_pdks.html)、[SKY130 current status](https://skywater-pdk.readthedocs.io/en/main/#current-status-experimental-preview)、[GF180 current status](https://github.com/fossi-foundation/gf180mcu-pdk#current-status----experimental-preview)。

### 电压与精度的关键证据

以下是源规格的少量事实提取，不是本项目实测结果：

| Evidence ID | 原始来源定位 | 类型与条件 | 源值 | 支持的窄结论 / 边界 |
|---|---|---|---|---|
| PDK-E01 | [GF180 6 V electrical specs](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_2.html)，VT0 行 | 厂商规格；NMOS W/L = 10 / 0.7 μm | min / typ / max = 0.61 / 0.73 / 0.85 V | 3.3 V gate drive 作为导通候选有合理依据；该阈值不能直接代入 W/L = 10 / 2 μm 的精密 current 计算 |
| PDK-E02 | 同表，Idsat 行 | 厂商规格；NMOS W/L = 10 / 0.7 μm，VDS = VGS = 6 V | typ = 570 μA/μm | 数据对应特定尺寸与偏置；不是本项目 100 μA mirror 的 current guarantee |
| PDK-E03 | [SKY130 g5v0d10v5 model information](https://skywater-pdk.readthedocs.io/en/main/rules/device-details.html#v-10-5v-nmos-fet) | 模型有效范围；NMOS | VDS 0…11 V；VGS 0…5.5 V；VBS 0…−5.5 V | SKY130 高压 MOS 是可行备选；模型范围不是允许任意端子组合或可靠性 signoff |
| PDK-E04 | [GF180 model device list](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_1_4_1.html) | 模型支持声明；3.3 / 6 V 常规 MOS | BSIM4、scalable、corner、global/local statistics | 后续可做 PVT / mismatch；本阶段 nominal 不代表已完成这些分析 |

上述提取只供复核规格与决策，保留原页链接和尺寸/偏置条件；公开复用以事实摘要和引用为主。特别注意：电流控制的瓶颈通常是 **compliance/headroom、输出电阻、reference 误差和 mismatch**，不是单靠“6 V 器件”标签就能解决。

## 3. Phase 1 模型获取与锁定

源库：[GlobalFoundries 180 nm MCU primitive libraries](https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_pr)。该 Google 仓库当前为 archive，页面标注 2026-04-18 归档。选择它作为固定历史 baseline，便于第一阶段明确复现；并不宣称它是当前最新维护版本。当前另有 [FOSSi primitive library](https://github.com/fossi-foundation/globalfoundries-pdk-libs-gf180mcu_fd_pr)，后续完整 PDK 应与工具链一起升级、锁定和重新验证。

本阶段锁定 commit：

```text
9f992d5a9186d1f7820c58f039c484ad35b2edea
```

公开 API 核实该 commit 的 committer date 为 `2023-05-31T05:49:36Z`；这是版本日期，不是本文查阅日期。[Commit](https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_pr/commit/9f992d5a9186d1f7820c58f039c484ad35b2edea)

最少获取三个文件，保留源文件、license 和 SHA256 校验：

| 文件 | 用途 | SHA256 |
|---|---|---|
| [design.ngspice](https://raw.githubusercontent.com/google/globalfoundries-pdk-libs-gf180mcu_fd_pr/9f992d5a9186d1f7820c58f039c484ad35b2edea/models/ngspice/design.ngspice) | 全局 switches / 参数 | `8d9721a5bf8f079d3fddbd03339af9a0c84d4feb06db8e06465fbd02c7500508` |
| [sm141064.ngspice](https://raw.githubusercontent.com/google/globalfoundries-pdk-libs-gf180mcu_fd_pr/9f992d5a9186d1f7820c58f039c484ad35b2edea/models/ngspice/sm141064.ngspice) | 3.3 / 6 V MOS 和关联模型，文内 Revision 9 | `73fc67d38747d95ce03f3c2ba5f0a25c98f56a293363a9df4c971a3a28a3dcda` |
| [LICENSE](https://raw.githubusercontent.com/google/globalfoundries-pdk-libs-gf180mcu_fd_pr/9f992d5a9186d1f7820c58f039c484ad35b2edea/LICENSE) | Apache-2.0 source terms | `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |

SHA256 是本次直接对下载源字节计算的值。文件中的版权头保留。库内 `.lib` 采用相对路径自引用；当前 runner 在各 case 中建立模型的 relative symlink 并以 case folder 为工作目录。需要从其他目录执行一次复现检查，避免依赖开发者当前目录。

原始模型的名称与 Open PDKs 处理后的名称不同：

| 本阶段原始模型调用 | PDK 文档 / 打包工具中可能看到的对应名称 | 实例类型 |
|---|---|---|
| `nmos_6p0` | `nfet_06v0`、`gf180mcu_fd_pr__nfet_06v0` | 原始模型为 `X` subcircuit，端子 `d g s b` |
| `pmos_6p0` | `pfet_06v0`、`gf180mcu_fd_pr__pfet_06v0` | 原始模型为 `X` subcircuit，端子 `d g s b` |

名称转换必须由实际选定 PDK files 确认；不要仅根据名字替换。原始模型 W/L 参数以米表示，例如 `w=10u l=2u`。Nominal 运行在 include 后显式设 `sw_stat_global=0`、`sw_stat_mismatch=0`，再加载 `typical` corner；后续 statistical study 应开启对应开关、固定随机种子并记录样本数。[原始 model source](https://raw.githubusercontent.com/google/globalfoundries-pdk-libs-gf180mcu_fd_pr/9f992d5a9186d1f7820c58f039c484ad35b2edea/models/ngspice/sm141064.ngspice)、[原始 global switches](https://raw.githubusercontent.com/google/globalfoundries-pdk-libs-gf180mcu_fd_pr/9f992d5a9186d1f7820c58f039c484ad35b2edea/models/ngspice/design.ngspice)

本项目选用的起始实验参数属于 **设计假设**：LED supply 5 V、control 3.3 V、external ideal IREF 100 μA、mirror W/L = 10 / 2 μm、6 V MOS pass/clamp 和 CMOS inverter；RTL clock 1 MHz，256-cycle PWM，即 3.90625 kHz。理想 reference 不是已经设计完成的 on-chip reference。需要用 SPICE 确认导通区、headroom、边沿误差和各端子实际电压，不能根据器件名预先宣布电路通过。

## 4. 工具角色与 flow 比较

| 工具 / flow | 本项目角色 | 能做什么与关键限制 |
|---|---|---|
| Icarus Verilog / Verilator | RTL PWM 与 testbench | 数字波形和逻辑验证；其逻辑 `1` 不自动具有 3.3 V electrical 意义 |
| ngspice | Transistor-level DC / transient | 真实公开 PDK compact model 仿真；仍不是 silicon 测量。当前官方 macOS 下载说明指向 Homebrew |
| Xschem | 模拟 schematic source | 生成 SPICE netlist、层次化画图；本身不是 analog solver。原生 GUI 依赖 X11 / Tcl-Tk |
| Magic + Netgen | 模拟 layout / DRC / extraction / LVS | 手工 transistor cell、抽取 netlist、对比 schematic；需要与 variant 匹配的 tech files / setup |
| KLayout | GDS 查看、编辑、规则复核 | 适合可视检查和独立 DRC；工具支持不等于某一 deck 已覆盖 foundry signoff 全规则 |
| Yosys + OpenROAD | 数字 synthesis / physical implementation | 标准单元映射、floorplan、placement、CTS、routing、timing 等；不会自动把任意模拟镜像电路变成可投片 layout |
| LibreLane | 推荐的数字 flow orchestration | 当前有文档、可复现环境与 Classic / Chip flows；整合多工具，PDK 版本应跟随锁定 flow 而不是单独追新 |
| OpenLane 1 / OpenLane 2 | 既有设计与模板兼容研究 | 老项目可能要求其版本；新仓库优先 LibreLane，避免同时维护几套相似 flow |
| OpenROAD-flow-scripts（ORFS） | 可选数字 flow | 原生 RTL→GDS 流程，支持 SKY130 / GF180；若以后专门研究 placement/routing 算法再加入，第一版不重复搭建 |

来源：[ngspice downloads](https://ngspice.sourceforge.io/download.html)、[Xschem](https://xschem.sourceforge.io/stefan/index.html)、[Magic maintained source](https://github.com/RTimothyEdwards/magic)、[KLayout](https://www.klayout.de/)、[OpenROAD](https://github.com/The-OpenROAD-Project/OpenROAD)、[LibreLane](https://librelane.readthedocs.io/en/stable/)、[migration guide](https://librelane.readthedocs.io/en/stable/getting_started/migrants/)、[OpenLane 2](https://openlane2.readthedocs.io/en/stable/)。

第一阶段采用 **RTL event trace → 有限上升/下降时间的 PWL voltage → SPICE transistor cell → LED current**。这是可审计的单向 mixed-signal 联动：PWM 的时序由实际 RTL 执行生成，MOS 和 LED 由 SPICE 求解。它不含 analog-to-RTL feedback，也不含完整标准单元输出级、level shifter、封装和板级寄生。后续闭环诊断、ADC 或比较器需要交互 co-simulation，不能继续用单向回放替代。

## 5. Mac mini / arm64 开发环境

分阶段安装，先让最小实验可运行：

1. **Phase 1：macOS 原生 batch flow。** Icarus、ngspice、Python plotting/orchestration；显式记录操作系统、CPU architecture、可执行文件版本、Python dependencies 和 model hashes。无需先安装 GUI 或整套 physical flow。ngspice 官方页面当前建议 macOS 使用 Homebrew executable。[ngspice downloads](https://ngspice.sourceforge.io/download.html)
2. **模拟 layout：推荐锁定 IIC-OSIC-TOOLS 的 arm64 container。** JKU 的集合基于 Ubuntu 24.04 LTS，公开声明原生支持 amd64 / arm64，含模拟和数字工具；GUI 可用 VNC/noVNC。锁定 release/image digest 和其中 PDK version；不要把 `latest` 作为复现约束。此路径的优势是 Xschem/Magic 等 Linux GUI 和 PDK 集中配置；代价是下载、磁盘与 macOS Linux VM 资源。[IIC-OSIC-TOOLS](https://github.com/iic-jku/IIC-OSIC-TOOLS)
3. **数字 physical flow：优先 LibreLane native Nix。** 当前官方支持 macOS 15+，推荐 Apple M1+ 与 16 GiB RAM；原生 Apple Silicon 避免 Linux VM 层。Docker 是有官方文档的备选路径，当前文档要求至少 16 GiB。安装后分别保存 smoke-test log 和项目首次 hardening log；smoke test 成功只证明工具安装，不证明本设计完成。[Nix on macOS](https://librelane.readthedocs.io/en/stable/installation/nix_installation/installation_macos.html)、[Docker on macOS](https://librelane.readthedocs.io/en/stable/installation/docker_installation/installation_macos.html)
4. **KLayout 可使用原生 Mac viewer。** 官方下载页有 arm64 package，但每个包有对应 macOS/Qt/Python 依赖组合；按本机版本选择并确认脚本与 PCell 能运行，不能仅看应用可启动。[KLayout downloads](https://www.klayout.de/build.html)

完整 PDK 使用 [Ciel](https://github.com/fossi-foundation/ciel)（原 Volare）预构建包，避免第一步在 Mac 手动编译 Open PDKs。Ciel 用 Open PDKs commit hash 标识 SKY130/GF180 builds，`PDK_ROOT` 中保存版本；LibreLane 会选择其测试过的默认版本。进入版图阶段先固定 LibreLane revision / lockfile，再固定对应 `gf180mcuD` build hash，与设计一起记录。原始模型子集的 pin 不能代替完整 PDK pin。[Open PDKs](https://github.com/fossi-foundation/open-pdks)、[LibreLane PDK handling](https://librelane.readthedocs.io/en/stable/usage/about_pdks.html)

## 6. 进入 layout / GDS 的最短后续路径

1. 同一版本完整 GF180MCU PDK 上建立 Xschem schematic；核对原始 models 与 PDK netlist 名称/units；重跑 Phase 1 波形。
2. Magic 或 KLayout PCell 生成/手工布置 1-Pixel analog cell，包含 well/substrate ties、guard ring、实际尺寸和 pin labels。
3. 保存 deck/tool/PDK 版本和完整报告，完成 DRC、LVS；抽取 RC 后做 post-layout SPICE，重新评估 current、Vf sensitivity 与 PWM 最短脉冲。
4. 用 LibreLane 对数字 PWM block harden；模拟 cell 导出 GDS / LEF / SPICE、适当的 timing/power/interface views，再作为 macro 集成；明确供电域和时序假设。[LibreLane macro integration](https://librelane.readthedocs.io/en/stable/usage/using_macros.html)
5. 最后才选择实际 shuttle 的 pad ring、IO、ESD、seal ring、density/fill、antenna 与提交规则；对模拟节点、LED 外接路径、reference 和 packaging 做接口复核。

这条路线解决的关键约束是“模拟 cell 必须具有可验证的 transistor layout，再和数字 cell 集成”。数字 RTL→GDS 工具不会替项目完成这一步。

## 7. MPW 的现实边界

公开来源可以确认存在对应服务/模板路线：GF180MCU 的 wafer.space，SKY130 的 ChipFoundry，以及 Tiny Tapeout 的相关工艺项目。这份文档 **不宣称某个 shuttle 当前仍有空位、接受本设计或可按固定价格成交**；实际提交时需要重新核实 deadline、package、pin/supply limits、full PDK version 和验证要求。[LibreLane provider/template list](https://librelane.readthedocs.io/en/stable/getting_started/index.html)、[wafer.space](https://wafer.space/)、[ChipFoundry](https://chipfoundry.io/)、[Tiny Tapeout](https://tinytapeout.com/)

尤其要注意 Tiny Tapeout SKY analog 公共规格列出的 digital supply 为 1.8 V、optional analog supply 为 3.3 V。它不是本项目 5 V LED supply 的直接接口承诺；外部 LED 与 analog pin 的电压、电流、开关路径和保护必须单独检查，不能直接把本次 5 V testbench 包进去。[Tiny Tapeout analog specs](https://tinytapeout.com/specs/analog/#power-pins)

Tape-out readiness 需要候选 shuttle 对指定 tool/deck/PDK/output 的接受证据，同时补齐 pads、ESD、power integrity、post-layout/PVT、封装与测试。公开 PDK 的历史 commercial process、开源 flow 的历史 tapeout 数量、本项目 nominal SPICE 成功，三者都不能替代这一证据。

## 8. 少数最有价值的未决问题

- 真实 MicroLED 的 Vf / I-V / capacitance 与目标 current 是什么？这些值会改变 headroom、供电和器件选择。
- 100 μA ideal reference 能否换成可 layout 的 external resistor/reference 或 on-chip circuit，并维持合理面积与误差？
- 3.3 V control 使用哪一个最终 digital standard-cell library / IO library？在选定库的 Liberty 条件之外运行不能据此报告 timing closure。
- `gf180mcuD` 当前完整模型、PCell、DRC/LVS/PEX 配置与本项目原始模型子集之间有哪些转换？应以第一块 layout 和 post-layout 回归得到证据。
- 候选 MPW 能否接受 5 V LED 外接驱动、所需 analog pins 与 reference 接口？确认这一点后再固定 pad ring 与最终工艺。

研究成熟度：**公开规格/工具文档已核查；工艺选择为当前阶段工程判断；本文不包含项目物理验证或 foundry 接受证明。**
