# 单像素版图：从六个 MOS 到可检查的 GDS

更新日期：2026-10-04（Asia/Tokyo）。这一节对应教学项目的**同一个 1-Pixel analog cell**，当前 mirror 为 W/L=20/4 µm。模拟 cell 已有真实 layout、GDS/LEF、严格 DRC/LVS、RC 提取与电气复验；数字 registered-PWM macro 的 physical implementation 和独立 KLayout 检查也已完成，见[数字物理实现](../digital/physical.md)。两者仍按独立模块记录，不等于整个 mixed-signal 顶层 ASIC 已集成。

器件物理前提、数据计算与检查流程的历史检阅见 [审阅总览](../review/README.md)。其中发现的 LVS property 判定漏洞已修复。随后保留旧 10/2 失败对照，完成 20/4 实际版图及 [reference/matching 复验](../research/reference-and-matching.md)，并加入[公开实测 LED 的静态耦合](../research/measured-led.md)；各自的条件与证据不能互相替代。

![实际 GF180MCU GDS 几何与接线](../../evidence/layout/layout.png)

## 1. 先理解这张图

原理图回答“哪几个器件相连”；layout 则回答“这些器件的扩散区、gate、接触孔和金属实际放在哪里”。上图由本次生成的 GDS polygons 绘制，不是概念效果图。横纵坐标单位为 µm；GDS database unit 是 0.001 µm。当前几何 bounding box 为 **95.00 × 37.66 µm = 3577.7 µm²**，含 routing 和 ties；相比旧 10/2 版的 2532.7 µm² 增加 **41.26%**，见[前后 GDS 面积记录](../../evidence/characterization/actual-w20-l4-area.json)。这是单个模拟 cell 的几何范围，不是芯片面积，也不包含数字 macro 或 pad ring。

从左向右是 MREF、MOUT、MPASS、MCLAMP、MINV_N、MINV_P。长条的两个 mirror MOS 保持相同 **W/L=20/4 µm** 与方向，W/L 比值仍为 5。其余三个 NMOS 为 2/1 µm，inverter PMOS 为 4/1 µm。每个器件有独立 guard ring 与 well/substrate tie；NMOS bulk 接 VSS，PMOS bulk 接 vlogic。M1 用于局部 contacts/ties，M2 把各端子向下引出，M3 的七条总线对应 VSS、bias、gate、pwm、pwm_b、led_k、vlogic。

M2 与 M3 相交不自动导通；有 Via2 的位置才连接。MOS gate 的 poly 通过 contact→M1→Via1→M2 接入控制总线。版图保留较大间距，便于逐器件检查与教学阅读；不是最小面积方案。mirror 采用相邻、等尺寸、同方向放置。增大 W/L 已取得 PDK 随机失配改善的证据，但尚无 common-centroid、dummy devices 或系统性布局梯度验证；器件对称及有限 MC 样本都不能证明制造 yield。

## 2. 这次实际检查了什么

| 步骤 | 实际结果 | 对应证据 |
| --- | --- | --- |
| Magic geometry DRC | `drc(full)`，错误数 0 | [magic-generate.log](../../evidence/layout/magic-generate.log) |
| Netgen LVS | 6 MOS / 7 nets / 7 pins；唯一匹配且没有 property errors；连接与 deck 检查的 W/L 等属性通过 | [netgen-lvs.log](../../evidence/layout/netgen-lvs.log) |
| GDS 写出后回读 | 回读 GDS 重新 DRC，错误数 0；重新 LVS 唯一匹配 | [magic-roundtrip.log](../../evidence/layout/magic-roundtrip.log)、[roundtrip LVS](../../evidence/layout/netgen-roundtrip-lvs.log) |
| Magic RC extraction | 7/7 nets 完成；6 MOS、59 resistors、43 capacitors | [magic-pex.log](../../evidence/layout/magic-pex.log)、[RC SPICE](../../evidence/layout/pixel_driver_rc.spice) |
| Paired post-layout regression | 17 条件 × schematic/RC 两版本 + 2 次细步长检查；36 transient runs；另 3 次独立 LED DC calibration；19 guards 通过 | [summary.json](../../evidence/layout/summary.json)、[regression.log](../../evidence/layout/postlayout-regression.log) |
| Actual 20/4 reference / mismatch | 1080 点 PVT/reference；五组 MC 各 256；三条件 × 两步长最低码积分复验 | [actual summary](../../evidence/characterization/actual-w20-l4-summary.json) |
| 独立 KLayout / 数字 macro | 已完成独立 rule-deck 检查及 registered-PWM macro 物理流程；具体配置、覆盖与计数另列 | [数字与独立物理检查](../digital/physical.md) |
| 模拟 macro 接口 | 已导出 GDS / LEF / extracted SPICE；接口与抽象边界独立记录 | [LEF](../../evidence/layout/pixel_driver_layout.lef)、[GDS](../../evidence/layout/pixel_driver_layout.gds)、[RC SPICE](../../evidence/layout/pixel_driver_rc.spice) |

DRC 是“几何是否符合当前 deck 的规则”，LVS 是“抽取出的器件与连线是否等于指定 schematic”，PEX 是“把实际连线的 parasitic R/C 加回仿真”。三项各解决一个不同问题。GDS 回读检查用于发现写出/导入后改变连接或几何的情况；不能把这些检查合称为 foundry signoff。

LVS runner 现在要求唯一的成功 final result，并拒绝 property errors。**在旧 10/2 版审阅时**，真实负对照仅把比较用 schematic 的 MOUT W 从 10 µm 改为 20 µm，Netgen 仍返回 exit 0，并在“连接唯一匹配”之后报告 property errors；仅检查退出码或匹配句会误判。原始版图尺寸与连接正确，修复后的检查已正确拒绝该负对照。当前 20/4 是 schematic 与 layout 同步修改并重验后的版本，不是该故意失配的负对照。锁定 Netgen deck 对 W/L 采用 1% tolerance，允许对称 MOS 的 D/S 交换，并忽略 AD/AS/PD/PS、SA/SB/SD 等属性；因此 LVS 成功不证明 junction geometry、局部版图环境或寄生参数相同。见 [真实对照](../../evidence/review/mos-lvs-controls.json) 和 [修复后检查](../../evidence/review/lvs-guard-checks.json)。

Magic `drc(full)` 是锁定公开 PDK 所提供的 Magic 规则集合；这里的 `full` 是该工具的 style 名称，不表示所有 foundry signoff 规则覆盖。新增的独立 KLayout 检查有自己的 deck、选项与完成范围，见[物理实现说明](../digital/physical.md)。项目尚未取得 foundry acceptance；芯片级 density/fill、antenna、ESD、IO/pads、IR-drop、电迁移、封装与顶层集成不能由一个 standalone cell 的结果推出。RC 是 Magic 当前名义 `ngspice()` extraction style 的结果，没有建立 RC corner qualification 或与 silicon 测量的校准。

## 3. 加入实际 RC 后有什么变化

为避免混用模型，本次比较的两侧都采用同一个锁定完整 `gf180mcuD` PDK。左侧是相同 W/L 的 schematic，右侧是其实际 layout 的 extracted RC。第一阶段较早的 model subset 被保留；没有把它替换后继续当作原来的证据。

两侧同时存在 diffusion geometry 和 wiring RC 的差异：schematic 的 AD/AS/PD/PS 默认 0，抽取网表包含真实 diffusion 面积与周长。因此配对 transient 的差值不能全部归因于连线 RC。历史 10/2 审阅曾补做“真实 diffusion geometry、但无 wiring RC”的中间 DC 对照，得到 101.299594 µA；它仅解释当时的 DC 差异，不能直接替代新尺寸或瞬态边沿的归因。下表使用当前 **20/4 两版本 transient 的完整窗口平均电流**。

| 条件 | 同一完整 PDK 的 schematic | 实际 layout RC | 变化 |
| --- | ---: | ---: | ---: |
| 5 V / 27 °C / IREF=100 µA / full-on | 100.752515 µA | 100.695401 µA | −0.05669% |
| 同上 / duty=64/256（25%） | 25.186904 µA | 25.172612 µA | −0.05674% |

完整列表在 `summary.json`。17 个条件包括 duty=0、1、64、128、192、255、256，disabled，synthetic Vf=2.4/3.2 V，supply=2.9/3.0/3.3 V，FF/SS，0/85 °C。每次先运行真实 RTL trace，重放 10 ns 电压 edges，再积分 **514.5–1538.5 µs 的 4 个 PWM frames**。正常最大时间步为 200 ns，duty=1 与 64 另用 50 ns 复核。

Paired current guard 是 `max(|I_schematic|×1%, 1 nA)`；细步长 guard 是 `max(|I_RC|×0.2%, 1 nA)`。这些是当前教学回归的工程 guard，不是工艺、LED 产品或精度保证。上表这条 regression 仍使用 synthetic diode/R/C/TT、外部 ideal IREF、理想供电与 testbench 的 PWM 电压波形。独立实测 LED static model 已加入另一套实验，不能据此把本表改称真实 LED 动态验证；平均 branch current 仍只是 electrical brightness proxy。

尤其要区分“版图前后变化小于 1%”和“相对于 100 µA 目标的误差”：当前 nominal extracted RC 约 100.69540 µA，即 +0.6954%，而旧 10/2 约为 +1.24%。新增 [reference/matching 实验](../research/reference-and-matching.md)按预设 ±5% absolute-current 与 ±2% lowest-code charge 验收：实际 20/4 的 1080 点范围为 99.28026–102.07565 µA，五组各 256 个 MC 样本无超限，三条件最低码误差最大 0.76830%。这些是有限且条件明确的模型结果，不是制造 yield。

[真实 LED static 耦合](../research/measured-led.md)使用 20 µm 方形黄色 InGaN 的公开 I–V 曲线，同一个实际 RC 在 MOS 27°C、理想 IREF 容差等声明条件下的 135 点电流为 98.17501–100.98377 µA。该曲线的测量温度未知，没有 C–V / I–V(T)；假设电容 transient 仅是 sensitivity probe，真实动态、温漂和 optical output 仍待数据。

## 4. 模型名与单位怎样衔接

- 第一阶段 original model subset：`nmos_6p0` / `pmos_6p0`，commit 在 `analog/models/pdk-lock.json`。
- 本次完整 PDK 的 Magic/LVS/ngspice 名：`nfet_06v0` / `pfet_06v0`。完整 PDK build 与 primitive revision 在 [layout/pdk-lock.json](../../layout/pdk-lock.json)，二者不能当作同一份文件。
- 当前 schematic 与 extracted SPICE 使用 SI 尺寸：`w=20u l=4u` 表示 20 µm / 4 µm。Magic PCell 输入 `w 20 l 4` 使用 µm。不要把其他包装器的“无后缀数字代表 µm”假设加到这套网表。
- RC SPICE 的 `R` 数字单位为 Ω；`f` 后缀的 `C` 数字为 fF，MOS `ad/as` 为 m²，`pd/ps` 为 m。GDS 坐标由 database unit 换算成 µm。
- 从原来 global ground `0` 到 cell 显式 pin `VSS` 是接口整理，testbench 仍把 VSS 接 `0`，器件连线不变。对称 MOS 的 D/S 可在 LVS 中合法交换。
- RC summary 的 `on_cathode_to_global_ground_v` 是外部 `led_k` pin 对全局 ground 的电压，含 wiring drop；不能把它叫作内部 MOS VDS。当前 RC 输出 MOS 的内部两个端点是 `led_k.t0` / `VSS.t6`，配对 transient 没有记录其实际 VDS。**历史 10/2 审阅**的 nominal DC 内部 VDS=2.195460 V、VGS=1.382167 V，见 [MOS 审阅](../review/mos-pdk-audit.md)；这两个旧值不是当前 20/4 的工作点。`gate_v` 仍对应外部 monitor pin，内部 RC gate 是另一节点。

## 5. 工具、PDK 与复现

模拟 cell 流程在 **macOS / arm64** 实际执行。Magic 8.3.684、Netgen 1.5.324 从官方 source commits 构建到 `build/layout/tools/install`；Tcl/Tk 8.6.18；ngspice 47。Ciel 3.0.0 获取的完整 GF180MCU build 为 **`54435919abffb937387ec956209f9cf5fd2dfbee`**，选择依据是当时读取的 LibreLane 官方 `pdk_hashes.yaml`。模拟生成器本身不调用 LibreLane；数字 synthesis、physical implementation 及独立 KLayout 使用各自记录的环境和版本，见[数字验证](../digital/README.md)及[物理实现](../digital/physical.md)。

首次安装（已完成第一阶段的 Icarus/ngspice 环境，已有 Homebrew、uv、Xcode/可用 SDK）：

```bash
bash scripts/layout/bootstrap_macos.sh
```

脚本编译 pinned Magic/Netgen，安装锁定 Python dependencies，再下载完整 PDK。PDK 占用约 3.8 GiB；实际安装日志保存在 `build/layout/logs/`。本机默认 CommandLineTools 的 macOS 27 SDK 曾导致 linker 无法识别 `arm64e.x1`（configure exit 77）；已用 Xcode 的 **MacOSX26.5.sdk** 成功构建。脚本默认通过 `xcodebuild` 选 SDK，可用 `LAYOUT_SDKROOT` 显式指定。这只修正该次构建的 SDK 路径，不改变系统默认工具设置。

从 fresh run directory 生成、检查、抽取、重跑电气回归并保存成功 evidence：

```bash
build/layout/venv/bin/python scripts/layout/run_layout.py --publish-evidence
```

每次 raw outputs 保存到新的 `build/layout/pixel-*` 目录，避免复用旧 netlist 或 waveform 掩盖失败。成功 compact evidence 更新到 `evidence/layout/`。GDS 内含生成时间，重跑后的 binary SHA 可能不同；检查结果、器件连接、尺寸与版图几何才是复现比较的主要对象。本次输出 SHA、source SHA 和 raw run locator 均在 `summary.json`。

## 6. KLayout 的历史阻塞与当前进度

Python KLayout 0.30.12 已实际读取 GDS、核对 bounding box 与 layer list，并生成上图。**2026-10-03 的本机 native 启动失败属于历史记录**：Homebrew 安装的 `/Applications/KLayout` CLI 停在 `_dyld_start`，最终终止 exit 143；macOS `spctl` assessment 为 `rejected`，包有 quarantine 与 ad-hoc signature。诊断仍保存在 `build/layout/logs/klayout-startup-sample.txt`、`klayout-spctl.log` 和 `klayout-install.log`，当时没有移除 OS 安全属性。后续已完成独立 KLayout rule-deck 检查，实际可执行环境、版本与结果见[物理实现说明](../digital/physical.md)；不再将这次旧主机失败写成项目当前未做独立 DRC。

当前已补齐公开实测 static I–V/model card、单像素研究指标、reference 行为预算、固定种子 mismatch/PVT、20/4 实际提取复验、registered-PWM macro 与独立物理检查。下一步仍保持单像素：取得真实 LED 动态与温度数据；把 external-reference 预算落实为可测器件/电路；检验 startup/power sequencing、真实数字输出级与模拟 gate 负载，并完成两个 macro 的顶层供电/连接与相应验证。Common-centroid 等布局手段应针对剩余的系统性匹配问题选择。4×4 的通信、register map、像素缓冲及扫描方案尚未实现，应在单像素接口和误差预算明确后逐步展开。

## 7. 公开来源与实现范围

本项目 layout/generator 为独立实现，使用公开 GF180MCU Magic PCell 与匹配 deck，不复制商业设计。完整 PDK 的第三方 notices 留在下载目录，仓库只保存锁定 metadata、独立源文件与本项目成功 evidence。

- [Ciel 官方安装与 PDK version 管理](https://github.com/fossi-foundation/ciel)
- [LibreLane 官方 PDK hashes](https://github.com/librelane/librelane/blob/main/librelane/pdk_hashes.yaml)
- [Magic 官方 macOS 构建说明](https://github.com/RTimothyEdwards/magic/blob/4f53bb3091d1e4a9b2009a58f157a8a4331d4c84/INSTALL_MacOS.md)
- [Magic 官方 extraction / extresist 说明与 source](https://github.com/RTimothyEdwards/magic/tree/4f53bb3091d1e4a9b2009a58f157a8a4331d4c84/doc/html)
- [Netgen 官方 source / LVS](https://github.com/RTimothyEdwards/netgen/tree/3cb047bd6b55ae09c8eefeb479b4fe746cfdb948)
- [Open PDKs pinned source](https://github.com/fossi-foundation/open-pdks/tree/54435919abffb937387ec956209f9cf5fd2dfbee)
- [GF180MCU primitive pinned source](https://github.com/fossi-foundation/globalfoundries-pdk-libs-gf180mcu_fd_pr/tree/41918f5a2356b9fb49a897ecc4fb4716b0ab1041)
- [KLayout 官方 macOS 包](https://www.klayout.de/build.html)
