# 阵列接口与制造边界：官方来源复核

日期：2026-10-25（日本时间）。范围：只读现有工程、核查公开第一方资料；未跑 EDA、未修改电路或旧证据。研究定位为实验方法验证和教学，不作商业产品性能排名。本文件不包含任何厂商命令编码或寄存器协议的移植。

## 结论

1. **本次证据不能支持“多数显示驱动厂家采用 QSPI”。** QSPI 确有商业显示控制器和穿戴 TFT 应用，但恒流 LED 阵列驱动也明确采用 CCSI、单数据线串行接口、SPI 或 I²C。这里是目的性器件样本，不能统计市场份额，也不能反过来推断“多数不采用 QSPI”。
2. **SRAM、双缓冲和物理接口是独立选择。** TLC6983 明确用双 BANK 隔离显示与下一帧写入，却不是 Quad SPI。具备 SRAM 不自动等于双完整帧；有双缓冲也不自动消除跨时钟、半帧提交或低带宽问题。
3. **GF180 的可制造工艺、公开 PDK 的状态、某个 MPW 的接单规则、当前电路的通过项、LED 键合能力是五层证据。** 可以研究试验芯片路径，不能据此声称当前宏已可量产或可直接变为几微米 pitch 的显示背板。没有针对本项目的有效报价、良率和测试方案，就不能给项目制造单价，也不能承诺降成本且性能完全不变。

## 一、接口、存储与双缓冲：证据表

下表为依据官方资料独立编排的事实摘录；容量、频率和拓扑按来源条件解释。它不是厂商排名，未将寄存器存储、灰度帧 RAM、图形对象 RAM 混为一类。页面数均指 PDF 印刷页；资料获取日期统一为本文件日期。

| ID / 官方资料与定位 | 器件类别与接口事实 | 存储与更新事实 | 支持的窄结论 / 不支持的外推 |
|---|---|---|---|
| I1 TI [TLC6983 datasheet](https://www.ti.com/lit/ds/symlink/tlc6983.pdf)，SLVSEJ1A，2022-05 修订，p1、§8.6.1.1、p29 Fig.8-22；[产品页](https://www.ti.com/product/TLC6983) 当前标为 ACTIVE | 48 恒流源、16 扫描开关的共阴极 LED 矩阵驱动；CCSI，SCLK/SIN/SOUT 三线；外部 SCLK 最大 25 MHz、双边沿传输 | 内部 BANK A/B，一组用于当前显示，另一组写下一帧；VSYNC 时交换职责 | 明确证明双 BANK 不依赖 QSPI。CCSI 不是把“四根数据线”换个名字；不能因为支持 mini/micro-LED 应用就称其为细 pitch CMOS 像素背板 |
| I2 TI [TLC5958 datasheet](https://www.ti.com/lit/ds/symlink/tlc5958.pdf)，SLVSCE7A，2014-09，p1、p15 block diagram、p16 §10.3 | 48 通道、16-bit PWM LED 驱动；串行输入 SIN、串行输出 SOUT、SCLK、LAT 等；数据传输标称上限 25 MHz，另有 GCLK | 48 Kbit 总灰度存储；图示每 BANK 为 16 bit × 48 channel × 32 line，共两 BANK；显示期间向另一 BANK 更新，帧边界交换 | 可支持“缓冲让主机传输与显示扫描分开”。不能将带 latch 的专用串行口不加验证地当成标准 SPI/QSPI 外设 |
| I3 TI [LP5860 datasheet](https://www.ti.com/lit/ds/symlink/lp5860.pdf)，Rev.A；[官方产品页](https://www.ti.com/product/LP5860)，资料日期 2021-11-29，Features / Interface options | 18 恒流 sink、11 扫描开关、198 LED dots；IFS 选择最大 1 MHz I²C 或最大 12 MHz SPI | 官方明确有可寻址 SRAM、逐点 8/16-bit PWM；这里未据此声称存在双完整帧 BANK | 直接的 SPI/I²C 加 SRAM 实例；存储存在不等于已证明 tear-free 双缓冲 |
| I4 Lumissil [IS31FL3731 datasheet](https://lumissil.com/assets/pdf/core/IS31FL3731_DS.pdf)，Rev.G，2024-10-24，p1、frame registers 章节 | 144 单色 LED，400 kHz I²C；内部 1/9 扫描方式、每点 8-bit dimming | 可存 8 帧并按帧间延迟自动播放 | 是多帧存储的另一种用途。8 帧动画存储不能无条件叫作本项目所需的两 BANK 原子提交；也不是高速光通信驱动 |
| I5 ST [STP16CPC26 产品页](https://www.st.com/en/power-management/stp16cpc26.html)与[datasheet](https://www.st.com.cn/resource/en/datasheet/stp16cpc26.pdf)，DS7104 Rev.7，2023-06；产品页明确 volume production | 16 路恒流 sink，串行数据、shift register 与 data latches，时钟最高 30 MHz；OE 控制亮度 | 所述结构是 16-bit 移位寄存器及输出锁存器；未宣称完整 frame SRAM | 这是明确量产的非 QSPI 反例。移位寄存器加输出锁存与大容量帧 SRAM 应分开计算 |
| I6 Bridgetek [BT817/8 datasheet](https://brtchip.com/wp-content/uploads/2022/04/DS_BT817_8.pdf)，v1.2，BRT_000302，p1、§4.1.1 p11、§4.3 p19、§5 | HMI 图形/视频显示控制器；主机 SPI 支持 single/dual/quad，时钟最高 30 MHz；显示输出为 parallel RGB | 1 MByte graphics RAM；图形引擎按 display list 构造行缓冲，具有 display-list swap 控制 | 是可核查的 QSPI 正例，但器件类别不是 LED 恒流阵列驱动。graphics RAM、display-list swap 与双份原始 framebuffer 不能画等号 |
| I7 Sitronix [2022 年报英文版](https://www.sitronix.com.tw/wp-content/uploads/2023/06/2022ar-EN.pdf)，技术发展表中 2021 年项目 | 公司原始年报列出用于穿戴设备的 QSPI TFT display driver | 本次未获取该项对应、可公开核对的具体 IC datasheet/存储组织 | 只证明这一产品方向存在；不证明具体 SRAM/双缓冲规格，更不证明“多数厂家”或 MicroLED 背板市场份额 |

**接口名的必要澄清。** I6 §4.1.1 的 Quad 模式是四条数据线，而不是“整个连接有四根线”。四线 SPI 常把时钟、片选和数据/命令等控制线计入线数；应读实际 pin table 与时序，不能按中文“四线”判定。还要区分主机→显示控制器、控制器→LED driver、driver→像素/扫描行三个链路。上述官方来源仅用于识别能力；本项目协议仍应独立设计。[I1、I5、I6]

**资料再用边界。** 这里保留精确 URL、版本、页码及必要事实表，未复制厂商协议、原理图或大段正文；原 PDF 的版权仍归各发布者。原图公开转载许可本轮未核实，所以没有把厂商原图收入公共仓库。数字和接口事实摘录不是对数据手册整页重新发布的授权。

## 二、对当前阵列路线的工程判断（推断，未实现）

现有 [project-brief](../../docs/project-brief.md) 将 Serial Interface → Command Decoder → Register Bank → Pixel Memory → PWM → Driver 列为长期结构，SPI/QSPI-like 仍为研究项，且明确要求独立协议。旧报告[4×4 预算](../../docs/research/research-report.md)已区分 60 Hz 图案更新、3.90625 kHz PWM 帧与串行链路：16 路 9-bit 命令、两缓冲仅有 288 bit/36 byte **有效载荷存储**，没有实现为 SRAM 宏。本文不将预算升级成已实现接口。

推荐判断顺序是先固定阵列/更新合同，再选择 lane 数：

`有效载荷速率 = 行数 × 列数 × 每像素通道数 × 每通道更新位数 × 更新频率`。

协议、地址、校验、片选空隙、读回、总线仲裁和主机软件开销另计；无压缩时所需接口时钟至少为载荷速率除以 `数据 lane 数 × 每周期传输次数 × 实测效率`。**这些是独立算术场景，不是实现结果：**

| 假设 | 原始更新载荷 | 对接口选择的含义 |
|---|---:|---|
| 64×64、单色、8 bit、60 Hz 全帧更新 | 1.96608 Mbit/s | 即使留开销，也没有因载荷本身必须采用 QSPI 的证据 |
| 128×128、RGB、每色 16 bit、60 Hz 全帧更新 | 47.18592 Mbit/s | 25 MHz 单 lane SDR 原始上限即不足；四 lane SDR 的理论上限为 100 Mbit/s，但仍要验证完整事务效率与时序 |
| 同一图案在本地重复 PWM | 无需每 PWM 帧重新传入整幅图 | 本地存储与 PWM 自主运行可降低持续接口负担；不能混同视频更新频率与 PWM 时钟 |

对当前小规模方法验证，较合理的候选是：**先定义一个简单可回读的单 lane SPI 版本，保留以后增加四 lane 的数字架构边界；先验证两缓冲的完整帧提交，再决定存储用寄存器还是已表征 SRAM 宏。** 这不是永久排除 QSPI。如果目标尺寸、延迟、主机带宽或 pad 预算改变，应重新计算。

两缓冲最少需要明确：显示 BANK 不允许被部分覆盖；完成一帧后才提交；提交在本地安全边界生效；跨时钟握手不能丢事件；坏帧、超时、主机停止和 reset 有确定行为。错误检测、bank ID、帧完整性规则应独立定义，不能照搬上表厂商命令。接收端完成写入的峰值速率不等于显示端能无冲突地读出数据；SRAM 的端口数、访问周期、每个扫描周期的读预算也要算。

**SRAM 成本不能仅用容量位数估计。** 小阵列用触发器可能更易验证；阵列增大后会增加面积/功耗。换 SRAM 可降低密度开销，但需要对应 GF180 变体、供电、端口、时序/PVT、GDS/LEF/LVS、模型与测试证据。本轮没有为当前阵列选定或验证 SRAM compiler，不能声称已经取得某个面积或能耗收益。

## 三、GF180、MPW 与生产不是同一个“通过”

| ID / 第一方来源 | 可核查事实与条件 | 本项目能用来判断什么 / 不能判断什么 |
|---|---|---|
| M1 Google/GlobalFoundries [GF180MCU PDK README](https://github.com/google/gf180mcu-pdk/blob/main/README.rst)，当前页 Current Status | 工艺为 0.18 µm、3.3 V/6 V MCU；原工艺及衍生前 PDK 有商业制造历史；当前开源分发仍标 experimental preview/alpha，并明确不面向 production settings、试验芯片也不作保证 | 可用作开放研究起点；不能用“成熟180nm工艺”覆盖公开分发版本、规则覆盖、器件表征及本设计的未验证项 |
| M2 GF [Tapeout checklist §6](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_06.html)、[bond pad §9.1](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_09_1.html)、[solder bump §9.4](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_09_4.html) | 要求层次 GDS、完整所需层、DRC；pad 章节覆盖 wire bond/gold bump，solder bump 为另列的委外 bumping 范畴 | 当前局部 DRC/LVS 通过是必要的局部证据；公开普通 pad/solder-bump 章节不等于几微米 LED hybrid-bonding 工艺认证 |
| M3 MPW 服务提供方 [wafer.space 当前官网](https://wafer.space/)；Run 3 / Slot Comparison / Packaging | 页面列 GF180 Run 3、不同 slot、默认/定制 pad ring、bare die 与 COB 选项；quarter slot 的 die 1.94×2.53 mm、默认 core 1.73 mm²、48 I/O；core 与 die 不同 | 证明公开 MPW 服务路径存在，不构成本项目已获接单、良率保证或 LED 集成报价。具体 PDK 分支/提交、metal stack、规则与豁免必须由服务方确认 |
| M4 GlobalFoundries [Manufacturing services](https://gf.com/manufacturing/services/) 与 [Advanced packaging](https://gf.com/technologies/advanced-packaging/) | 官方把 wafer、probe、bump、assembly/package/test 及 OSAT 协作分别列为服务 | 生产交付包括独立封装与测试环节；不能从裸晶面积推导含 LED 阵列的成品成本，也不能据泛化能力声明 GF180 特定组合可直接做 hybrid bonding |

**时效与报价边界。** M3 当前页面顶部仍有“from $2/die”早鸟宣传，但同页已明确早鸟结束，标准价格另列；动态倒计时文字还与列出的截止日期不一致。因此本研究不引用促销单价作项目预算，不把网页倒计时当确定可订购状态。即使公开 slot 标价可查，它也不是本项目的书面完整报价。须取得对面积/数量、pad/ESD、scribe/seal ring、wafer 或已切割 die、probe/test、封装、税运、交付与重投片条件的有效报价后再给成本数字。

**本工程现状（只读事实）。** [最终 NRZ 物理摘要](../reference-v2-layout/nrz-switched-keeper-summary.json)的 348.99×340.06 µm、0.118678 mm² 是 21 MOS/RIN 联通实验宏 bounding box，明确不是 chip area；GDS SHA `363e51112c60692538da2130c99664d22a24c15fa0ca9327c244494938b4065c`。它不含完整 pad/ESD/测试/量产封装。显示路径仍为单像素实际 PEX 及外部补偿/参考条件；两路线不能相互替代。[analog/models/pdk-lock.json](../../analog/models/pdk-lock.json)只锁定模型子集，不是全部制造交付。现装 full-PDK 的 `SOURCES` 记录 open_pdks `54435919abffb937387ec956209f9cf5fd2dfbee`；这仍不证明与任何当期 shuttle 的正式接收配置相同。

## 四、LED hybrid bonding 与阵列密度

**第一方研究实例 H1：** MICLEDI CTO Soeren Steudel，[MicroLED Display Integration on 300mm Advanced CMOS Platform](https://epic-photonics.com/wp-content/uploads/2022/02/4.3-Soeren-Steudel_MICLEDI.pdf)，作者在 EPIC 2022-09-07/08 会议的演示文稿，p6、p9、p11–13。来源为技术开发方的会议报告，属于作者报告的研发结果，不能等同第三方量产认证。

必要的数值/条件摘录如下，避免只抽取“3 µm”而省略关键脚注：

| 原资料定位 | 披露值/条件 | 解释与限制 |
|---|---|---|
| p11，Display Integration | 3 µm 六角 pitch；300 mm wafer 的 overlay variation <200 nm | 此处同时明确 **pathfinder lot 没有 active CMOS，只有 passive matrix**；不能据此说已验证同 pitch 完整有源驱动阵列 |
| p12，Wafer Mapping Data | 50×100 被动测试阵列，3 µm pitch / 2 µm MESA；报告超过90%的测试阵列可点亮 | 分母是测试阵列，不是逐像素良率；“点亮”也不是逐点电流一致性、寿命或成品良率 |
| p9，集成流程 | LED wafer 与 CMOS wafer 的 W2W hybrid bonding；另有减薄、正面工艺、测试、切割、封装 | LED-CMOS 接合是额外工艺流程，不能由一个 GF180 CMOS GDS 自动生成 |

**工程推断：** 密度至少同时受像素电路、供电回路/走线、发光区、接点数量与 pitch、对准精度、planarity/表面洁净度、后处理热预算、LED/CMOS 缺陷与测试策略约束。上述报告的 <200 nm 对准与 3 µm pitch 是其特定流程条件，既不是 GF180 标准服务保证，也不是所有键合工艺的统一门槛。

先共享外围 reference、时钟/计数器、bank control 等可以减少每像素重复逻辑，但不能消除每像素需要的开关/驱动、电流分配和 LED 接点。当前宏含共用参考、保护和互连空间，不能将其面积机械除以某个像素数；也不能把缩短 MOS L 当成所有模拟 W、匹配、输出电阻和补偿均可同比缩小。反过来，当前大宏不证明所有 180 nm 像素架构都不可能达到更小 pitch。

需要先选定输出目标：PCB 上的外接 LED 小阵列、分区 driver 芯粒、还是每像素接合的微显示背板。三者 pad/互连、允许尺寸、测试和成本完全不同。当前最接近可复验的下一阶段是外接 LED 的小规模试验阵列；若直接转向细 pitch hybrid bonding，应先取得合作方的具体 stack/接点图、对准/热约束与测试方案，再冻结像素面积，不能倒过来先承诺密度。

## 五、降成本候选与性能代价（工程推断）

| 候选方法 | 可能减少什么 | 为什么不能先承诺“不牺牲性能” | 最小验证证据 |
|---|---|---|---|
| 保持小试验阵列，使用适合的 MPW slot 与现成测试封装 | 一次试验的掩模/制造分摊、开发风险 | 固定 slot 价格不与宏面积连续成比例；较少 I/O 可能限制并发测量，COB 不等于 LED 键合封装 | 服务方实际报价与 pad/测试映射；不删除关键观察端口 |
| 每块阵列共享 reference/偏置/计数器 | 重复器件、静态功耗与部分面积 | 可能增加分配 IR drop、串扰、同时切换、失配和单点失效；已知启动与体结问题不能因共享而消失 | 实际阵列供电 PEX、全开/棋盘/孤点负载、PVT/失配、掉电与故障隔离 |
| 使用本地缓存、分区/部分更新，先用足够的单 lane 接口 | 主机传输、I/O 活动及可能的 pad 数 | 相同帧率不一定意味着相同最坏更新延迟；稀疏图案节省不能外推全帧随机更新 | 最坏事务带宽、丢帧/撕裂检查、CDC、复位/超时测试 |
| 去除不参与选定功能的重复电路/无效面积 | 可在功能保持时减少开销 | 必须证明所有原门槛保留；删掉保护、减小补偿/余量不能称无代价优化 | 同电路/同指标单因素对照、独立 DRC/LVS/PEX 与完整电气回归 |
| 选择适当存储宏/像素架构或另一工艺节点 | 数字密度/接口功耗；可能减小 die | 新节点可能降低耐压/模拟余量，增加 level shift、掩模和验证成本；小量试验未必更便宜 | 对应工艺的实际面积、时序/功耗、器件端压、可制造版图及有效报价 |
| 提高测试覆盖、筛选及封装/键合良率 | 减少组装后报废 | 增加前期测试时间和设施；未知真实良率时只能是方向 | 测试覆盖率、缺陷分布、已知良品筛选、实际良率和单位测试成本 |

可以争取在**明确规格范围**内降低浪费，同时维持已定义指标；没有依据保证所有性能维度完全不变。验证应同时保留电流精度、最低 PWM 电荷、恢复/启动、噪声与串扰、吞吐/延迟、功耗、温升、体结/可靠性和可测性。以“总体性能”一句话替代这些合同，会把成本转移隐藏成优化。

## 六、证据限度与后续问题

- 已核查的是官方已发布规格和研发报告，非对量产销量、份额、客户设计数量的调查。I1/I3 的 ACTIVE 与 I5 的 volume production 可确认商业产品身份，不能推知其市场占比。
- 尚无本项目的 foundry/MPW 正式接收确认、生产 SRAM 选择、实际 LED 接合规则和完整成本报价。本轮不提供估价，不将公开促销标价当成项目承诺。
- 下一步只需先固定三个输入：阵列规模/颜色/灰阶与更新延迟合同；外接 LED 还是直接键合的物理形式；需要保留的测试/保护接口。然后用独立协议与小阵列试验验证接口/存储，而不复制厂商协议或预设商业竞争目标。

本文件所有链接均指向器件厂商、PDK 发布者、服务提供方或原作者的会议资料；搜索中的经销商转载、论坛意见和市场综述未作为结论证据。外部资料只支持其对应的窄事实，表中工程判断均单独标为推断。
