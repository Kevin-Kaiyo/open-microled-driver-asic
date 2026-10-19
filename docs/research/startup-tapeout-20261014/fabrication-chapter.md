# 从单像素电路到可测量的 ASIC：设计、版图与流片教学章节

更新：2026-10-14（Asia/Tokyo）。定位：公开的实验性研发方法验证与教学。本章说明制造路线及交付条件；新增参考、隔离和保护电路的启动仿真结果由同目录主报告提供。

**当前最合适的第一颗芯片，是采用硅 CMOS 工艺、驱动一只外置 LED 的单像素实验 ASIC。** 先让参考电流、PWM、独立关断、上电过程和测试接口在一个小系统中闭合。LED 可以在 PCB 上单独连接；把 MicroLED 阵列键合到 CMOS 背板是另一个需要 LED 制造、互连和封装协同的项目阶段。

目前已有旧版单像素 analog macro、PWM digital macro 和共同 top 的 GDS、指定规则下的 DRC/LVS 及部分寄生验证。**新增参考源、隔离、保护及 LED 钳位尚无对应新版完整版图；现有共同 GDS 不能代表这次电路已经物理实现。** 当前没有 pad ring、完整 ESD/POR、封装、投片接收或硅片测量证据。

## 1. 先认识三种图：电路图、版图、工艺截面

电路图回答“哪些端子相连，为什么这样连接”；版图回答“这些晶体管、接触孔和导线在芯片上具体放在哪里”；工艺截面回答“厂商怎样在硅片上把这些几何变成器件和互连”。它们相关，却不能互相替代。

| 图或文件 | 本项目中的例子 | 制造意义 |
| --- | --- | --- |
| Schematic / SPICE | 参考源、镜像管、PWM 开关、独立 fault、LED 钳位 | 定义连接、器件型号与 W/L；还不能直接制造 |
| RTL / gate netlist | PWM 计数器、fault inhibit、恢复条件 | 数字功能经综合映射到工艺标准单元 |
| Layout / GDSII | 实际器件和 Metal/Via 多边形，包含层号 | 几何交付载体；应配合层映射、工艺选项和检查报告 |
| Process stack | 硅、阱、扩散、多晶硅、介质、金属、钝化 | 厂商已有并控制的制造流程，设计者在 PDK 允许范围内选用 |

可以把全流程理解为：**规格 → 电路/RTL → 仿真 → 版图 → 提取寄生再仿真 → 制造检查及设计签核 → GDS 交付 → 掩模/晶圆加工 → 测试/切割/封装 → 回片验证。** 中间每一步都需要能追溯到同一个设计版本。

## 2. 材料：驱动器的 MOS 和发光的 LED 是两件器件

当前平台使用 GF180MCU：180 nm、bulk silicon CMOS、公开模型覆盖 3.3 V 与 6 V MOS families。**驱动器晶体管的半导体主体是硅；无需因为负载是 MicroLED 就把 MOS 改成 GaN。** 6 V MOS 是所选器件家族名称，不是说芯片每个节点可以任意加 6 V，也不是额定电流或寿命保证。官方公开 PDK 的过程与成熟商业工艺有关，但其 README 仍将公开发行内容标为 experimental/alpha，并限制其生产用途表述。[GF180MCU 官方仓库与状态说明](https://github.com/google/gf180mcu-pdk#current-status--experimental-preview)

MicroLED 的发光有源材料来自所选 LED 工艺。可见光 GaN 系列通常采用 InGaN/GaN 等 III–V 半导体结构；这与 ASIC 的硅 MOS 不是同一层工艺。本项目已使用的公开静态样本，是作者的 20 µm yellow InGaN MicroLED 数据；它不代表我们已能制造该 LED。材料、尺寸和工作电流还需具体器件测量约束。[原始 LED 数据集](https://doi.org/10.5281/zenodo.20034288)

| 部分 | 当前选择/边界 | 下一步要确定 |
| --- | --- | --- |
| ASIC 有源器件 | GF180MCU 硅 CMOS；模拟侧使用 6 V MOS，逻辑 nominal 3.3 V | 交付通道认可的器件/库、全端子电压及温度范围 |
| ASIC 电阻、电容 | 工艺允许的 poly resistor、MIM/MOS capacitor；当前部分 R/C 仍为理想网表元件 | 实际 PCell、容差、温度系数、匹配、面积、PEX |
| LED | 外置；动态负载仍有 synthetic 参数 | 同一实物的 I–V、C–V、瞬态、温度、光输出与可靠电流 |
| ASIC 与 LED 连接 | 第一阶段用封装引脚、PCB/短引线 | 封装寄生、回流路径、LED 端 ESD、供电余量 |
| 紧密阵列集成 | 尚未实施 | 键合/凸点、对准、互连良率、热设计和共同测试 |

硅晶圆、栅介质、金属互连等材料由工艺供应商的固定流程定义；我们不能像选择 PCB 铜厚那样随意改动。公开材料名称不足以重建完整制造配方，本项目也不需要自行开发外延、离子注入或晶圆生产线。

## 3. “多少层”应明确为多少金属互连层

**当前锁定 variant 为 `gf180mcuD`，实际选择是 `5LM_1TM_11K`：Metal1～Metal5 共五层互连金属，Metal5 是顶层金属。** Via1～Via4 连接相邻金属层；一层 poly 不是第六层金属。阱、active、implant、contact、介质、钝化、标记层仍各有规则。“五层金属”不能写成“芯片只有五层工艺”或“五张掩模”。

下表是锁定 open_pdks 构建文件中 A/B/C/D 的配置事实，并非本项目已经获得四种制造报价。不同栈的版图、顶层规则、LEF 和提取规则必须对应，不能仅改目录名后复用 GDS。[锁定 open_pdks Makefile](https://github.com/fossi-foundation/open-pdks/blob/54435919abffb937387ec956209f9cf5fd2dfbee/gf180mcu/Makefile.in)

| open_pdks variant | 构建的金属栈标签 | 金属层数 | 工程解释 |
| --- | --- | ---: | --- |
| A | 3LM_1TM_30K | 3 | 顶层厚金属选项不同；本项目未使用 |
| B | 4LM_1TM_11K | 4 | 比 D 少一个布线层；本项目未使用 |
| C | 5LM_1TM_9K | 5 | 顶层金属选项与 D 不同；本项目未使用 |
| **D** | **5LM_1TM_11K** | **5** | **当前锁定并实际用于旧版物理实现** |

GF 官方设计手册也列出多个 1P3M、1P4M、1P5M、1P6M 与顶金属/MIM 组合；该菜单不能直接推定每个公开 variant、每次 MPW 都接受全部组合。正式项目应锁定一个被接收的工艺选项。[GF DRM 2.0，2.8～2.10](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_02.html)

### 顶层厚度为什么出现三个数

这里保留来源差异，防止把一个标签当作物理测量：

| 数据身份 | 读取值 | 可以怎样使用 |
| --- | ---: | --- |
| 栈名称 `11K` / 11 kÅ 的单位换算 | 1.1 µm | 描述选项名称；不能单独当提取/EM 模型 |
| 本地锁定 nominal technology LEF，`Metal5 THICKNESS` | 1.19 µm | 证明数字工具读到的文件配置；该文件头明确提示其寄生信息不准确 |
| 官方 interconnect **电容仿真**导体表，TM(11KA) typical | 1.25 µm | 此来源的仿真表参数；不是本项目硅片厚度测量 |

本地 LEF 还给 Metal1～Metal4 的厚度为 0.54 µm；官方电容仿真表给相应 typical 为 0.55 µm。**它们的定义、版本和用途不同。PEX 要使用与工艺选项及规则版本对应的专用提取资料；电迁移要使用电流规则。** 不能为求“统一数字”任意选取一个值。[GF interconnect 表 2.1](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/layout/inter_specs/inter_specs_2_1.html)

本地事实入口：[物理 PDK 锁](../../../layout/pdk-lock.json)；对应 LEF 路径、行号和 SHA-256 见 [来源记录](fabrication-sources.json)。官方 1P5M/11KA/MIM-B 截面文字把 MIM 放在 M4 与顶金属 M5 之间；MIM 是电容结构，不会把五层布线金属变成六层。[官方截面章节 3.43](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/layout/inter_specs/inter_specs_3_43.html)

## 4. 开发平台：我们现有工具能做到什么

第一阶段适合维持公开、版本固定的开发链。数字物理实现已在 Linux/Nix 工具环境中运行；macOS 负责电路仿真、脚本、文档和部分版图操作。**需要用证据中的实际工具版本重现结果，不能以新安装的版本覆盖旧运行身份。**

| 工作 | 当前工具和真实证据 | 下一步输出 |
| --- | --- | --- |
| 电路与晶体管仿真 | ngspice 47、公开 GF180 模型、SPICE 网表、Python 复算 | DC、PVT、启动/掉电/故障、环路和寄生回归 |
| 数字时序与功能 | Icarus Verilog 13.0、RTL testbench | 正常/边界/失钟/异步 fault；数字存储的可实现电路 |
| 数字综合 | Yosys 0.62；映射到所选 standard-cell library | gate netlist、cell area、约束与等价/功能验证 |
| 数字布局布线/STA | LibreLane 3.0.14、OpenROAD commit dcf36133；已有旧 PWM routed macro | 新含安全逻辑的 placement、CTS、routing、STA/SDF |
| 模拟布局/提取 | Magic；旧 analog flow 用 8.3.684，Linux 联合 flow 用 8.3.623 | 新 reference/isolation/fault/clamp 的实际器件、井体和互连 |
| 几何复核 | KLayout；Linux DRC 0.30.7，macOS Python 0.30.12 | 所选完整 deck、density/antenna 模式及独立检查报告 |
| 连接一致性 | Netgen；旧 analog 1.5.324，Linux 联合 1.5.316 | 新 top 全连接和器件参数 LVS |
| 证据与数据 | Python、CSV、日志、版本锁和 SHA-256 | 同版电路、版图、提取、仿真和签核记录 |

上述为本仓库运行身份，详细来源见 [模拟物理锁](../../../layout/pdk-lock.json)、[数字/Linux 工具记录](../../../evidence/physical/tool-versions.json)和 [Phase 1 仿真记录](../../../evidence/phase1/summary.json)。图形化电路输入可后续加入 Xschem；它不是当前已有仿真结果的生成前提。

供应商可能要求另一套受支持的 EDA/PDK、签核 rule deck 或版本；此时需要在该接受流程中重跑。开源工具产生 GDS 与正式制造接受，是两个独立检查点。`analog/models/pdk-lock.json` 的模型子集尤其不能替代完整物理 PDK。

## 5. 怎样把当前架构落实为新版版图

建议分成四个可分别提取和验证的 hard macro：①参考电流源；②偏置隔离/传送；③单像素镜像和 PWM 开关；④独立 fault gate 与 LED 钳位。数字 PWM 和 fault 存储经标准单元流程实现。hard macro 的意思是内部器件、连接、尺寸已经固定，顶层用其 LEF/GDS/CDL 等视图进行放置和连接；不能只留下一个没有内部验证的矩形。

| 模块 | 布局重点 | 布局之后怎样验证 |
| --- | --- | --- |
| 参考源的 differential pair / mirror | 相同器件方向与环境、接触和井体条件；参考/复制支路对称；电阻和补偿电容落成允许 PCell | 匹配模型/Monte Carlo 范围，DC/PVT，启动、稳定性和失调；实际 R/C 改变后的回归 |
| MREF / MOUT 镜像 | 单元化、合适的对称/交错布局、边缘 dummy，检查 VDS 差异与热梯度 | 各支路电流、compliance；提取栅/源/漏/井寄生；随机失配不能由 TT/SS/FF 代替 |
| 偏置传送、隔离开关 | 避免长而弱的高阻偏置线，明确开关体端、关断泄漏、充放电路径 | 启动隔离、电荷注入、关断、PWM 最小脉冲；布局增加的结电容和耦合 |
| fault gate / LED clamp | 电源域清晰，fault 线路与实际存储/输入路径落实；LED 阳极参考的 clamp 井体归属明确 | 全端子电压、体二极管、失钟/掉电、反灌、电荷路径和最大瞬态电流 |
| Digital PWM / safety storage | 完整时序约束、reset 与异步 set/recovery 的边界、真实 buffer | STA、门级/SDF、异步恢复/释放与 analog 负载联动 |

官方模拟布局指南要求精密匹配元件周围避免无关导线穿越，并使用相应器件匹配规则。匹配布局应针对所选工艺失配模型设计，不能把 common-centroid 当作自动精度保证。[GF DRM 5.4](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_05_4.html)

### 电源与隔离要先设计，再画线

当前逻辑 nominal 3.3 V，LED 阳极 nominal 5 V；参考电路也是声明的控制电源域。LED clamp 可能接近 LED 端电源，必须逐管检查 G–S、G–D、G–B、D–S 与结偏置，以及**任一电源先上/先掉、输入先到、brownout**时的状态。6 V 型号不能免除这些检查；数字库名 `5v0` 也不等于本项目数字供电为 5 V。

电源规划应区分安静参考回路和大电流输出回路，再明确它们的共同参考与连接点。阱、substrate tie、guard ring、必要的 deep-nwell 选项、去耦和布局距离用于管理体电位及噪声耦合；**画出 guard ring 不等于通过 latch-up，也不会自动消除共享衬底噪声。** 应按规则检查 tap/井/guard-ring，再做供电与衬底边界分析，最终由硅测量和适用可靠性试验确认。GF 的可靠性章节分别讨论 HCI、栅氧、EM、latch-up 和 ESD，不能合成一句“6 V 器件安全”。[GF 可靠性及工作条件](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html)

现有 PWM M3 与供电 M4/M5 的连接是旧单像素 top 的具体实现；它不是新版最终层分配方案。新版要根据电流、IR drop、耦合、buffer 负载和 routing 可行性重新定线宽与 via 阵列。

## 6. 面积：从一个 MOS 的 W×L 到真正的 die

**`W×L` 是 MOS 栅极沟道的几何尺度，既不是整个 MOS 占地，也不是 die 面积。** 接触、扩散、阱、tap、guard ring、器件间距、dummy、供电和信号导线都要占空间。五层金属叠在同一平面上，不能把平面面积除以五。

### 三个来自实际 GDS 的面积

| 当前已有对象 | 可复算尺寸 | 面积 | 证明范围 |
| --- | ---: | ---: | --- |
| 旧 analog cell bounding box | 95 × 37.66 µm | **3577.7 µm² = 0.0035777 mm²** | 已画 analog macro；不含新 reference/protection/pads |
| 旧 PWM standalone macro bbox | 180 × 180 µm | **32400 µm² = 0.0324 mm²** | 数字宏预留 footprint；不是全部标准单元净面积 |
| 旧联合 top occupied span | 305 × 180 µm | **54900 µm² = 0.0549 mm²** | 两旧宏放置与互连的跨度；不是可投片 die |

原始数据：[analog bbox](../../../evidence/characterization/actual-w20-l4-area.json)、[PWM GDS 检查](../../../evidence/physical/digital/gds-inspection.json)、[共同 top](../../../evidence/integration/summary.json)。`1 mm² = 10⁶ µm²`。旧两宏 footprint 相加为 35977.7 µm²，联合跨度更大是因为放置间距和顶层连线；不能把两者混称“晶体管净面积”。

**新增参考、隔离、fault gate、clamp、真实电阻/补偿电容尚无新版 layout，因此目前不能给新版 die 的可信面积。** 正确做法是完成这些宏，读取各宏 bbox，再用一个符合 pad/封装/供电规则的 top floorplan 计算。

### 补偿电容也可能占很大面积

现有servo候选使用理想`CCOMP=3 pF`，后续若选择被制造流程接受的MIM PCell，可先用`Aplate ≈ C / Cdensity`估算平行板主面积。官方电容规格给1.0、1.5和2.0 fF/µm²等选项，并说明同一流程不能随意混用不同类型。**具体D variant与制造服务接受哪种电容，仍需确认。** 以1.0或1.5 fF/µm²作教学候选，3 pF对应约3000或2000 µm²；若做成正方形，其边长约54.77或44.72 µm。这些只是电容主面积，不含edge capacitance、contact、routing、spacing和guard/keepout，也不是已经完成的版图。

它说明：增加3 pF补偿，即使只增加一个“C”元件，也可能带来与旧analog macro同数量级的几何面积。不能通过ΣW×L遗漏这些被动器件。真正面积和稳定性应以实际PCell及提取参数回归。[GF MIM电容电气规格6.2](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_6_4.html)

### 可复算的早期估算方法

数字标准单元净面积先计算 `Acell = Σ(Ntype × Atype)`；若 placement utilization 为 U，则早期数字可放置面积约 `Adigital ≈ Acell/U`。这里的 U 不包含模拟禁布区；宏、clock/power、routing 拥塞和形状会增加实际需求。因此 `Acore ≈ Adigital + ΣAmacro + Akeepout + Arouting reserve` 只能作为 floorplan 起点，实际 bbox 才是几何结果。

完整 die 可用两组约束取较大者：

- 功能空间：`Wdie ≥ Wcore + 2 × Bring`，`Hdie ≥ Hcore + 2 × Bring`。Bring 代表每侧 pad/ESD、seal ring 与 required keepout 的规划宽度；并不是一个通用常数。
- 引脚空间：每边 `Wpad-needed ≥ (Nside−1) × Ppad + Wpad + 2 × Ccorner`。Ppad 为 pad pitch、Wpad 为 pad 宽、Ccorner 为角落余量，均必须来自所选库/封装规则。
- 最终 `Adie = Wdie × Hdie`；还要满足 MPW slot 的固定形状/尺寸。划片道是否计入购买面积，要按制造服务定义。

教学算例：假设某自定义库 pitch=100 µm、pad宽=80 µm，一边放6个pad、每端预留100 µm，则该边至少 `(6−1)×100+80+2×100=780 µm`。**这些尺寸只是演示算术，不是 GF180 pad 规则、封装规则或本项目选型。** 原始电路核心很小，仍可能被 pad/ESD 和封装引脚决定总面积。

公开服务模板给出一个四分之一 slot 的示例：die 1.94×2.53 mm，default pad ring 内 core 约1.05×1.65 mm。按长宽直接计算分别为4.9082 mm²和1.7325 mm²；网页的4.90、1.73是显示近似值。这说明 slot、core 和旧0.0549 mm² macro span 是三种不同面积。该示例不是已给本项目接受的 die，也不表明当前可以下单。[wafer.space slot 规范](https://mith.ro/gf180mcu-project-template/)

## 7. 线宽为什么要由电流决定：一个 7 mA 算例

金属线有电阻：`R ≈ Rsheet × L/W`，压降 `ΔV = I × R`；电源/地压降减少 LED 电流镜的 compliance，还会改变 VGS。接触和 via 同样有限流能力，不能只把 Metal5 加宽却保留一个 via。

以下只示范如何查规则，不是新版布线结果。GF 公开 DRM 14.2 的单向电流规则，125°C 下给普通金属0.67 mA/µm、11 kÅ顶金属1.5 mA/µm，0.26 µm top-via相关规则给0.18 mA/via。按其宽度与电流定义，7 mA 的**一阶下界**为：

| 7 mA 持续单向电流 | 计算 | 最低算术结果 |
| --- | --- | ---: |
| 普通金属线宽 | 7 / 0.67 | 10.45 µm |
| 11 kÅ 顶金属线宽 | 7 / 1.5 | 4.67 µm |
| 理想均匀分流的 via 数 | ceil(7 / 0.18) | 39 |

条件来自原始表14.3/14.4的125°C、单向电流列；实际还要考虑 via 电流不均、current crowding、温升、脉冲峰值、寿命定义、层转换、冗余与设计裕量。上表不能证明7 mA可靠性，也不能把 PWM duty 直接乘到峰值后免除瞬态检查。[GF DRM 14.2 电迁移规则](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_2.html)

这与前一版报告的 gate-drive 结果有关：输出 MOS 变大以后，gate 电容更大、最短脉冲更难建立；源/漏互连的高电流能力和栅驱动的高速充放电能力应分别设计。阵列扩大时，共用供电段承受的是多像素总电流，而不是一只 LED 的电流。

## 8. 给厂家什么：先分清谁负责设计

“ASIC 厂家”可能指设计服务公司、foundry、MPW组织者或封装测试公司。交付起点不同，费用和责任也不同。

| 合作模式 | 我们交付 | 对方负责 | 必须写清的接受范围 |
| --- | --- | --- | --- |
| 设计服务/turnkey ASIC | 规格、接口、LED条件、验证要求、已有电路与RTL、目标封装 | 补齐设计、版图、签核，协调制造/封测 | 哪些设计由谁签核，测试覆盖、回片失败/改版边界 |
| 自己设计，经 MPW/service制造 | 最终被接收的 GDS/OASIS及元数据、报告、选择的封装/测试方案 | 合版、制造协调，按合同交付bare die/封装件 | 哪些检查只看可制造，是否含探针/封装/功能测试 |
| 直接 foundry 项目 | 按具体PDK/release与tapeout表单交付完整database | 制造、约定的工艺检查与wafer交付 | PDK许可、工艺选项、rule deck、waiver、yield与质量约定 |
| OSAT/封装测试 | die/pad map、bonding drawing、package、wafer map、测试程序和limits | 切割、键合/封装、约定的测试 | pin1方向、pad坐标、wire/bump、热/电流、筛选和追溯 |

本项目可以先独立完成公开设计和验证，再把一个**具体冻结的测试芯片包**交给认可该版本的制造通道。供应商不会仅凭技术报告或RTL自动知道每个模拟器件怎样制造。GF公开essential checklist要求层级GDSII、所有drawn/设计者生成层，以及投片前DRC通过；MPW平台可能另接受OASIS，但要按该平台规范交付。[GF DRM6](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_06.html)

### 建议准备的冻结交付包

这是一份工程交付建议；不声称每家厂商都强制要求相同文件。最终以接收方release checklist为准。

| 包内内容 | 目的 |
| --- | --- |
| `chip_top.gds` 或被接受的 OASIS；top name、dbu、origin、layer map、die size | 消除层号、单位、顶层和尺寸歧义；所有几何来自同一release |
| 工艺选项表 | 精确的 process/PDK版本、5LM_1TM_11K、器件库、MIM/resistor等实际选项 |
| golden schematic CDL/SPICE、数字gate netlist、必要IP完整视图 | LVS/设计审查；是否交厂家由合同和流程定义 |
| DRC/LVS/ERC、density/antenna、PEX+仿真、STA/SDF、EM/IR、可靠性检查报告 | 记录规则版本、开启模式、corner、约束、结果及所有waiver；不能只给截图“0 errors” |
| source/工具/deck版本、输入输出SHA-256、生成命令、变更和签核记录 | 证明交付与被检查的数据完全一致 |
| pad map、pin table、bonding图、package/COB/PCB说明 | 让封装件引脚与芯片pad一一对应，供电/LED电流回路完整 |
| 测试计划、测试程序、limits、probe/ATE/板级连接、wafer map约定 | 让“样片返回”变成“有可判定的测量结果” |
| 商务/接收表单 | die数、封装数、测试范围、排期、运输、责任及变更截止；需书面确认 |

提交前必须冻结这一组文件；若DRC后再加入fill、换pad、改一个管宽，应重新完成受影响检查。封装会新增电阻、电容、电感，板级电源和LED也会引入边界，不能只看片内PEX。

## 9. “能制造”和“能用”需要两套证据

wafer.space 的公开 precheck 为一个可学习的制造通道示例：检查单一top、原点、1 nm dbu、最高M5、slot尺寸；检查density、零面积polygon、antenna、Magic与KLayout DRC，COB模式另检查标记和pad开口。**它的README清单没有LVS、电流精度、PWM、环路稳定性、启动安全或光学指标。** 因此平台通过不能取代设计验证。[wafer.space precheck原始清单](https://github.com/wafer-space/gf180mcu-precheck#gf180mcu-precheck)

公开模板确实采用gf180mcuD，并提供数字全流程、模拟独立pad ring和Icarus/cocotb测试入口。它可以作为后续研究起点；本项目并未导入最新模板后获得制造接受，也没有对供应商提交数据。需要锁定接收方要求的具体commit和precheck版本，而不是盲目使用latest。[项目模板](https://github.com/wafer-space/gf180mcu-project-template)

| 要回答的问题 | 需要完成的工作 | 本项目目前的证据缺口 |
| --- | --- | --- |
| 电路在给定条件下能工作吗 | DC/PVT、失配、启动/掉电、环路/噪声、负载与最小PWM、fault负对照 | 新增模块仍是pre-layout；真实LED动态参数和部分稳定性/失配未闭合 |
| 数据能制造吗 | 正确stack、全chip DRC/LVS/ERC、density/antenna、fill、pad/seal/marker、制造通道precheck | 旧共同top检查有声明范围；新top和制造precheck尚未完成 |
| 长期工作会坏吗 | 全端子电压、HCI/TDDB、EM/IR、热、ESD、latch-up及适用寿命条件 | 无硅片可靠性结果；体/PG/封装边界未全面验证 |
| 封装后能接电并测量吗 | pad map、封装/PCB、去耦、限流、probe/test接口、pin1、电源顺序 | 尚无封装与板级release |
| 回片能判定好坏吗 | 参数分布、测试limits、温压角、故障注入、实测光脉冲和测量不确定度 | 无silicon/optical measurement；仿真一致性不代表产率 |

“保证”在工程上应落实为明确的接受条件、覆盖的失效模式和测量方案；任何一套仿真都不能提前保证所有样片、所有工况可用。研究test chip尤其应保留失效可观测性，为第一次回片留下学习和改版空间。

## 10. 第一颗测试芯片必须能被观察和控制

第一版建议明确下面这些接口，但本章不把它们当作已经实施的pinout：

- 分开的logic/reference供电与LED输出供电边界、VSS回流；pad cell的电压/电流和ESD必须匹配，不能把普通数字output pad当作任意7mA模拟LED通路。
- 外部`VSET`/`RSET`可访问，明确其输入范围及容差；测试模式允许外置可靠参考接管，帮助区分参考源、镜像支路和LED失效。
- `fault`与默认禁止状态；fault断线、停钟、重置、上电未就绪时的状态；恢复授权不能只依赖一个软件写寄存器。
- 实际`POR/brownout`或声明由外部供电监控提供的ready/inhibit。当前仿真由外部事件输入驱动fault/ready，不等于已有片上电压传感器。
- 参考电流/偏置、LED阴极、protected PWM/状态的测试访问；高阻模拟节点加测试pad会增加寄生和泄漏，应使用合适的缓冲/测试开关并纳入仿真，不能直接任意引出。
- 唯一chip/revision标记、识别寄存器或其他可测身份；每块样片和测试数据关联lot、die、封装及版本。

Bond pad的开口、pitch、面积和下方连接，还受到探针与封装厂的能力限制；GF文档把这类装配约束明确留给设计者考虑。[GF Bond Pad说明](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_09.html)

### 回片后的测量顺序

先检查pin/pad和短路，再用限流供电测静态电流；随后测reference的VSET/RSET传递和compliance；用电子负载/电气LED模型确认单像素镜像与PWM；最后接有已知允许电流的真实LED。逐步测试启动/掉电/停钟/fault，记录LED端电压、电流、光脉冲和温度。电路和仪器带宽应覆盖所测瞬态；不能用低带宽电流表证明纳秒级overshoot不存在。

晶圆探针可以筛选电气连接、漏电、参考和数字功能；封装终测验证引脚与功能；characterization覆盖温压、负载、startup和可靠性边界。若没有片上LED，foundry生产硅驱动器并不自动提供MicroLED光学测试，需要在封装/板级系统中另测。

## 11. 制造发生了什么，为什么设计文件会变成实物

接收方检查冻结几何后，按层映射和工艺规则生成掩模数据；多个设计可在MPW中拼入同一reticle。晶圆厂依其既定流程完成阱和有源器件、互连金属/通孔、钝化等加工；随后进行约定的wafer测试，再切割出die。die可交付裸片，也可由封装厂完成wire-bond、flip-chip或其他装配，最后做约定测试。

**GF180这条加工链会做出硅driver；它不会凭一份driver GDS在硅上额外长出我们未设计制造的InGaN发光层。** 外置LED、CMOS背板与LED异质集成三种交付形式应分别签订技术边界。wafer.space公开资料分别描述bare die与Chip-on-Board形式，可作为包装边界的实例；它的广告、数量和网页时刻不是本项目采购承诺。[制造服务技术与封装说明](https://wafer.space/)

## 12. 当前研究的推进顺序与通过条件

| 顺序 | 具体输出 | 进入下一阶段的条件 |
| --- | --- | --- |
| 1. 完善单像素电路 | 实际reference、startup隔离、独立fault、LED电荷处置及失败对照 | 保留原guard，启动失败有解释和修改后可复算结果；明确电源/外部控制前提 |
| 2. 闭合模拟验证 | loop stability、供电/负载/温度、mismatch、端子电压、掉电/恢复、最小脉冲 | 预设指标有覆盖矩阵、边界和日志；真实LED动态/光学未知单独标记 |
| 3. 新版hard macros | 允许PCell、匹配、井体/tap/guard、实际R/C、LEF/CDL/GDS | macro DRC/LVS，PEX后重新完成第1/2阶段 |
| 4. 完整test-chip top | 实际安全存储、pads/ESD/POR边界、供电、测试访问、seal/marker/fill | 新top完整连接与全规则检查，实际buffer/PG/封装寄生和签核回归 |
| 5. 制造通道审查 | 被接受的PDK/deck/slot/package和冻结交付包 | 接收方书面确认范围、版本、全部未决项/waiver；报价排期另确认 |
| 6. 硅片与LED验证 | probe/封装/板级测试、参数分布、启动保护、光电测量 | 用实测判定模型、功能和可靠性；有依据后再扩4×4 |

当前方向仍是**先完成可复现、可观察的一个像素，再扩展阵列**。高速光通信另需要数据接口、时钟/串化、快速偏置/调制driver、LED动态与接收链验证；当前PWM示范芯片与已有6V MOS不能直接获得某Gb/s通信保证，也不能仅凭工艺节点判定是否需要另一种材料。
