# 车灯 MicroLED 对标研究

## 从单像素 ASIC 到 ADB 与道路投影

**主要对象：ams OSRAM EVIYOS、上海晶合光电「画芯」系列**<br>
研究日期：2026-10-06 · 工程基线：one-pixel v0.4<br>
基线 commit：`3a9ca422b78b57ef6cd0b5eea163c68321375660`

> 当前已经跑通单像素的数字逻辑、模拟驱动、版图和局部联合寄生仿真。下一步最有价值的方向，是把它接到一个可检查的独立车灯控制模型，逐步研究帧更新、故障响应、真实供电与光输出。

本报告回答三个问题：现在做到了什么；两家产品公开到什么深度；我们如何建立可验证的平台。先读第2页理解系统，再读产品与差距；工程读者继续核查参数条件、预算和退出判据。

| 当前已建立的证据 | 尚未建立的能力 |
| --- | --- |
| Registered PWM、逻辑映射与数字 physical；六 MOS 模拟 pixel layout；共同 GDS 的所执行 DRC/LVS；12-MOS selected signal PEX | 灯具 ECU、视频接收、整阵列缓存与控制、真实 reference／POR／故障关断、完整 PG、白光车灯模型、实物与光学测量 |
| v0.4 主研究37次 transient／12次 DC、146项预设 guards通过；三批总66 transient／28 circuit DC | 全 PVT×RC 交叉矩阵、整片电气 signoff、pad／ESD／package、制造接受、车规与道路批准 |

本轮是**应用对标与方向研究**：查验既有证据和来源身份，新增产品分析与平台路线；没有重跑整套物理流程，也没有把软件方案写成已完成的 ECU 或商业 ASIC。既有28页 v0.4工程报告继续保留。

<!-- PAGE -->

## 1　先理解整体架构

ADB（Adaptive Driving Beam，自适应远光）决定哪些方向应照亮、哪些区域应遮光。道路投影还需要生成符号并映射到路面。MicroLED 光源执行像素亮度命令；环境感知和配光计算属于系统上游。

<div class="flow">
<div class="node"><b>1 → 场景与车辆状态</b>物体位置、车辆姿态、速度、模式与时间戳</div>
<div class="node"><b>2 → 灯 ECU／Host</b>遮光 mask、基础光型、投影图、坐标映射与优先级</div>
<div class="node"><b>3 → 数据控制器</b>帧接收、校验、缓存、提交与诊断管理</div>
<div class="node"><b>4 → Pixel driver</b>将本地亮度状态转换为 PWM／电流控制</div>
<div class="node"><b>5 → MicroLED 光源</b>电流产生光；转换层、封装和散热影响性能</div>
<div class="node"><b>6 → 光学与道路</b>透镜把像素映射到角域；得到光束与投影</div>
</div>

上图为本项目原创的**功能分层**，不是任一厂商完整内部图；物理接口与责任分配必须逐型号确认。

| 要分开的三条路径 | 需要检查什么 |
| --- | --- |
| 数据路径：场景 → 帧 → pixel | 帧是否完整、何时生效、是否延迟或过期；camera更新、图像更新、PWM周期各自计时 |
| 能量路径：电池侧 → 转换电源 → LED／logic | 供电余量、同时点亮、启动、热与功耗；具体车载保护及 rail 要由器件条件决定 |
| 反馈／保护路径：温度、供电、诊断 → 控制 | 检测到什么故障、何时停止或降级、如何恢复；正常帧更新不代替故障关断 |

**三个常见误解：**像素数不是光通量；接口名称不是完整协议；PWM carrier不是摄像头或图像 frame rate。像素电流的平均值只是一种电气代理量，要得到照度、亮度与防眩效果还需要真实光学模型和测量。

<!-- PAGE -->

## 2　EVIYOS：先固定产品身份

EVIYOS 是产品家族。当前新设计研究应优先核对 **HD25 gen2**；第一代用于理解已商业化路线和历史装车。工业用 EVIYOS Shape 的流明与对比度不能移作车灯 HD25 规格。

| 对象 | 官方公开内容 | 2026-10-06目录／历史状态 |
| --- | --- | --- |
| HD25 gen1／EVIYOS 2.0，KEW GBBMD1U | 320 columns×80 lines＝25,600 pixels；40 µm pitch | 2023量产公告；当前目录 Not for new design |
| gen1，KEW GBCLD1U | 240×80＝19,200可用 pixels | 当前目录 Discontinued；不能以25,600替代有效像素数 |
| HD25 gen2，KEW GBBMD2U | 25,600 pixels；40 µm pitch；LED／IC hybrid | 当前目录 Full production；Product Information日期2025-10-31 |
| KEW GBXXD1U Companion ASIC | 产品组合必需的外置 digital ASIC | 专用组合器件；不等于光源内的 pixel driver IC |

来源：[gen1目录](https://ams-osram.com/products/leds/white-leds/osram-eviyos-hd-25-gen1-kew-gbbmd1u)、[19k目录](https://ams-osram.com/products/leds/white-leds/osram-eviyos-hd-25-gen1-kew-gbcld1u)、[gen2目录](https://ams-osram.com/products/leds/white-leds/osram-eviyos-hd-25-gen2-kew-gbbmd2u)、[Companion目录](https://ams-osram.com/products/drivers/led-drivers/osram-eviyos-hd-25-kew-gbxxd1u-companion)。目录状态是核查日快照，不能作为长期采购保证。

### 装车案例的分母也必须固定

[Marelli 2023公告](https://www.marelli.com/en/news/marelli-launches-h-digi-microled.html)确认 h-Digi microLED 模组使用 EVIYOS 2.0并已 series production；[ams OSRAM后续说明](https://ams-osram.com/news/blog/launch-of-new-version-of-eviyos-multipixel-led)将 Touareg／Tiguan 与 EVIYOS关联。Volkswagen公开的 Touareg 每侧中央 HD module 为 **19,200 pixels**，另有16-pixel module。整灯、整车和光源的像素数不能混用。[Volkswagen像素说明](https://www.volkswagen-newsroom.com/en/the-new-touareg-world-premiere-16049/the-new-iqlight-hd-matrix-headlights-16052)

Porsche Cayenne／HELLA 的16,384 pixels/chip属于另一条系统路线；它的灰阶、GMSL或配光重算周期不能借给 EVIYOS。装车案例能证明商业应用存在，不能替代某一订货料号的完整 electrical datasheet。

<!-- PAGE -->

## 3　EVIYOS：芯片与控制的真实边界

公开资料支持 **MicroLED array＋集成 CMOS driver IC＋外部 Companion ASIC** 的分工。LED array的 monolithic结构与 LED／CMOS异质集成是不同概念；不应将整套产品写成一颗单片 ASIC。[原厂集成说明](https://ams-osram.com/innovation/how-ingenuity-and-expertise-led-to-the-development-of-our-multi-pixel-led)

| 控制层 | 已公开 | 本轮仍未知 |
| --- | --- | --- |
| ECU／Host → Companion | gen1 PI p.3：UART、RGB8、SPI/CSI video option；gen2 PI p.3：UART、RGB8、SPI video interface option | 各接口的准确用途、physical voltage／pinout、clock／有效带宽、packet／register、同步与错误规则 |
| Companion → 集成 driver | 外置 digital ASIC与光源内 driver的分工 | 内部链路、寻址、clock、memory所在位置、缓存与commit机制 |
| 每 pixel 电路 | individually controllable；公开开发者说明有局部电流驱动 | current source／sink极性、MOS拓扑、尺寸、DAC、PWM位数／频率、扫描与失配校正实现 |
| 校正与诊断 | PI注明 brightness correction；公开 package示意有通信／诊断接口 | 校正表、写入／温度补偿、open／short判据、fault寄存器、watchdog及保护响应 |

接口依据：[gen1 Product Information p.3](https://look.ams-osram.com/m/635ee3453a471790/original/KEW-GBBMD1U.pdf)、[gen2 Product Information p.3](https://look.ams-osram.com/asset/b9a583a0-b1d7-4a08-8a3e-184f6eb4f558/KEW-GBBMD2U.pdf)。**RGB8是接口名称，不能据此断言白光 emitter是RGB，或pixel PWM恰为8 bit。** 本轮没有取得可绑定型号的灰阶、PWM carrier或video frame rate规格。

### 能复现到哪一层

现在可以独立实现帧接收、状态缓存、PWM／电流驱动、错误帧与关断功能，研究同类系统问题。没有合法完整接口与器件验证前，交付名称应为“独立功能模型”；没有原厂RTL、schematic／PDK或同器件测量前，不能称“EVIYOS backplane复刻”或性能等价。

商业光源的40 µm pitch不能约束本项目 GF180单像素直接达到同面积。我们的模拟 macro为95×37.66 µm，且尚有共享逻辑、PG、pad和封装等成本未完成。

<!-- PAGE -->

## 4　EVIYOS：参数必须带条件

| 参数／声明 | 可检查的公开条件 | 使用限制 |
| --- | --- | --- |
| gen1 luminance | PI p.3列75…100 MNits | 表中1.97 mA，room temperature，after brightness correction |
| gen2 luminance | 2025-10-31 PI p.3列75…110 MNits | 保留同样表条件；电流的完整计量边界与全阵列工作包络仍需补充 |
| gen2改进宣传 | 2024-10-14 blog称 minimum85 MNits | 与后续 PI范围存在差异；bin／revision／条件未闭合前不合并 |
| 温度范围 | PI列 hybrid Tj−40…150°C，Companion Tj−40…125°C | Tj是结温范围，不是环境温度，也不是完整热模型或本项目验证范围 |
| AEC声明 | gen2 PI列光源 AEC-Q102 attachment003、Companion AEC-Q100 | 文件声明；未提供本轮可审查的qualification原始matrix，不能扩展为ASIL或整灯道路批准 |

来源：[gen1 PI pp.2–3](https://look.ams-osram.com/m/635ee3453a471790/original/KEW-GBBMD1U.pdf)、[gen2 PI pp.2–3](https://look.ams-osram.com/asset/b9a583a0-b1d7-4a08-8a3e-184f6eb4f558/KEW-GBBMD2U.pdf)、[gen2改进说明](https://ams-osram.com/news/blog/launch-of-new-version-of-eviyos-multipixel-led)。早期gen1 PI在光源qualification后仍写planned，不能用那份历史文件宣布当时已完成。

### 不同光学量不能直接排名

`nit = cd/m²`描述发光面的 luminance；`lm`描述 luminous flux；`lux = lm/m²`描述受照面的 illuminance。EVIYOS的MNits与画芯报道的流明不能直接排“谁更亮”；需要统一发光／光机出口位置、点亮比例、温度、电流／duty、光学损耗和测量方法。

### 原厂资料本身也需要检阅

Companion页面的“datasheet”链接实际返回2024-07-26 preliminary LED PI，不能当独立 ASIC寄存器手册。gen2网页与PDF的完整type字母拼写不同；PI还列19,200配置，而当前订货说明只明确25,600。这些差异是资料身份问题，尚不能判为器件缺陷。详见[逐项检阅与原文定位](headlamp-products.md)。

<!-- PAGE -->

## 5　画芯：型号线索与证据状态

研究对象是**上海晶合光电科技有限公司**，与晶合集成／晶合半导体、晶能光电分开。[IFAL厂商采访](https://www.ifal-forum.com/nd.jsp?fromColId=2&id=1197)确认公司身份及4万像素、CMOS与封装研发方向；2025年内样片目标属于当时计划。合作存在也由[乾照2026半年报，PDF第11页](https://disc.static.szse.cn/disc/disk03/finalpage/2026-08-24/6c91b020-cacf-4c2d-ad96-798be34e283d.PDF)确认，但其ADB段未点名画芯，不能据此指定型号量产。

下表是**待原厂核实的报道线索**，不是本项目采用的器件规格。来源：[2026 ALE新品媒体记录](https://finance.sina.com.cn/tech/roll/2026-03-27/doc-inhsmtiq5229790.shtml)。

| 名称 | 报道陈述 | 未闭合的问题 |
| --- | --- | --- |
| 画芯一号 | 40,000 pixels、40 µm、≥2,500 lm @50 W | 最终料号／行列数；功率输入位置、光学出口、温度与点亮比例；正式保证范围 |
| 画芯二号 | >100,000 pixels；原计划2026 Q3 | 是否按期推出、最终型号／接口／性能；不能因日期已过视为已交付 |
| 画芯三号 | 主照明、≥3,500 lm @50 W；原计划Q2 | 点亮陈述与正式产品交付不同；像素布局／测量条件未知 |
| 画擎一号 | [联合发布报道](https://m.gasgoo.com/news/70451636.html)：双光机、视频与拼接；总输出≥200 W | 控制器层功率不能当单个光源／ASIC功耗；2025同名模组与2026控制器的版本映射未知 |

[2026-09-28 LEDinside报道](https://www.ledinside.cn/news/20260928-62681.html)转述9月24日画芯一号完成 AEC-Q102可靠性验证的公司公告。**本轮未取得原厂原文或BACL报告编号／结论页／样本与批次，记录为“公告被报道，原始验证待确认”。** 不继续把3月Q2计划当当前状态，也不将该报道升级为独立认证确认、ASIL或量产装车。

目前没有核实到画芯具体料号与正式车型、年款及灯具版本的官方映射。不能挪用公司既有普通LED模组装车数据。完整身份与来源分层见[画芯专题](huaxin-products.md)。

<!-- PAGE -->

## 6　画芯：避免从像素数猜芯片

一手访谈和合作资料支持 CMOS驱动、先进封装与高像素数字光源的研发方向。媒体提到数模混合与异质堆叠，可以作为寻找原厂资料的线索；它们尚不构成可复现的晶体管级实现。

| 要解析的层 | 当前可支持的结论 | 仍需原厂资料 |
| --- | --- | --- |
| MicroLED emitter／光源 | 4万像素研发方向有厂商访谈 | 最终行列数、active area、转换层、每pixel额定current／Vf、光场与串扰 |
| CMOS backplane／ASIC | 合作与研发方向可追踪 | node／foundry、memory、clock／scan、PWM／DAC、reference／current拓扑、diagnostic粒度 |
| 光源控制器／画擎 | 报道存在视频生成、双光机与拼接 | MCU／SoC／FPGA具体分工、power stage、frame commit、thermal／fault策略 |
| 外部接口 | 本轮未取得完整公共接口说明 | 电压、pinout、video／control／diagnostic链路、clock、packet、SDK与许可证 |
| 可靠性与装车 | 存在最新验证公告的媒体记录 | 报告身份／样本／批次、适用料号、真实出货与车型映射 |

### “CMOS驱动”不足以决定电路

高密度array需要把大量像素连接与局部控制放到集成结构内，避免每pixel都从封装引出。但**是否每pixel储存亮度、按行扫描、采用何种PWM或电流调制**必须逐产品确认。4万像素既不能推出4万个独立counter，也不能推出某种SRAM容量或模拟MOS数量。

画擎是系统级名字，画芯是光源产品名字。控制器输出≥200 W的报道不支持“ASIC耗电200 W”；50 W÷40,000也不能反推出恒流设定，因为缺少rail、duty、点亮比例、conversion及功耗边界。

上海大学2026-09采购意向中的150 nm／8英寸流片没有关联画芯型号，不能据此确定画芯制程。公司较早的PCB／分散LED投影专利也不能证明4万像素backplane实现。

**当前可以复现功能问题：**图像到像素状态、帧一致性、电流／PWM、错误更新、供电／热限制。商业寄存器、内部ASIC、封装工艺与可靠性机制继续标为待确认。

<!-- PAGE -->

## 7　两家产品与我们的逐项对照

“未知”表示本轮保存的公开资料不足；不表示厂商没有实现该功能。“提议”表示我们可搭建的下一步，不是已有成果。

| 对比项 | EVIYOS | 画芯／画擎 | 当前仓库／下一步 |
| --- | --- | --- | --- |
| 产品成熟度 | 官方量产目录与历史装车关联可核实 | 研发／合作一手证据；型号参数及最新可靠性主要待原厂核实 | 单像素simulation／physical研究，无silicon或装车 |
| 分辨率／pitch | HD25 gen2公开25,600／40 µm | 一号4万／40 µm为待核报道；一手确认4万研发方向 | 1 electrical pixel；模拟macro不等于商业pixel pitch |
| LED／driver集成 | hybrid＋集成driver＋外部Companion | CMOS／封装方向可追踪，实际结构细节未知 | 分离PWM与analog macro的共同GDS；无LED bonding／package |
| Host与接口 | UART／RGB8／SPI等名称公开；精确协议未知 | 画擎功能线索；接口／协议未知 | duty／enable直接输入；提议独立frame contract |
| 数据／灰阶 | 灰阶、carrier、frame rate未绑定型号 | 对应数值未知 | 256 slots、257状态；无commercial buffer／receiver |
| Analog与校准 | individual control；brightness correction条件公开；拓扑未知 | 额定current／PWM／校准未知 | 六MOS100 µA mirror；真实reference、校准与current feedback未完成 |
| E/E与保护 | ECU／Companion／光源分层；完整power／fault实现未知 | 控制器与光源分层待版本确认；完整E/E未知 | 无vehicle bus、DC-DC、POR、hard blank、watchdog或thermal loop |
| 光学／热 | 白光产品与Tj声明公开；具体光机条件须确认 | 流明／功率线索未统一测量边界 | 黄光static I–V与synthetic dynamics；无光学／thermal测量 |
| 验证与开放深度 | 产品PI和系统公告；未获商业ASIC模型 | 厂商访谈与合作证据；未获完整datasheet／模型 | 开放源码、锁定PDK及selected PEX；可追踪失败与复算 |

公开结构可帮助我们确定系统边界；要比较数值性能，必须先取得同一测量节点、同一pattern与温度条件。不能以平台开源程度、局部DRC通过或像素数替代实际车灯性能。

<!-- PAGE -->

## 8　当前工程：已完成到哪一步

本轮对既有v0.4文件身份和JSON进行核查。**应用文档增补前**，基线current-manifest的554项文件hash全部一致；其2504项是artifact检查，不是电气样本数或安全覆盖率。随后更新入口、roadmap和文档校验／导出脚本，最终current索引单独刷新；基线manifest仍可从上述commit追溯，旧run身份不改。工程结果应追到各自raw输出、条件及检查分母。

| 阶段 | 已有结果 | 适用边界 |
| --- | --- | --- |
| RTL／mapping | 518完整PWM frames、133159 checks；95 mapped cells、19 FF | 单pixel、同步reset；无视频接收／CDC／大阵列memory |
| Analog layout | W/L20/4 µm mirror；95×37.66 µm macro；所执行DRC/LVS、RC replay通过 | 选定公开PDK／decks；不等于全制造规则接受 |
| Joint top | 305×180 µm span、19ports、共同GDS实际提取与严格LVS | span不是die面积或pixel pitch；无pad／ESD／完整package |
| Selected joint PEX | 五种actual RC style；每种12MOS、45 signal R、77显式C、34neighbor ports | PG／body与PG-only C投影到理想rail；邻居按合同截断 |
| 主电气研究 | 37transient／12DC、146 guards；full-on100.112984…101.423393 µA；最低码最差面积误差0.700133% | synthetic LED、声明窗口／conditions；nominal三MOS包络＋两组额外RC组合，非完整交叉穷举 |
| 总电气与审查 | 66transient／28circuit DC＋3synthetic calibration；独立复算与18项错误对照 | boundary数值完成不表示全部工程通过；不构成system qualification |
| 真实静态负载 | 一条traceable黄色20 µm InGaN/diamond I–V；100 µA时Vf3.767910 V | 原测量温度、dynamic／thermal／white conversion未知；不是车灯额定模型 |

我们的信号仿真从真实输出级进入analog pixel，能研究PWM电荷与电流，但没有真实供电网格、邻居全电路、上游logic全部动态功耗或analog→RTL反馈闭环。

证据入口：[joint PEX](../../../evidence/joint-pex/summary.json)、[主研究](../../../evidence/robustness/main-summary.json)、[总研究](../../../evidence/robustness/summary.json)、[独立审查](../../../evidence/research/v04-review.json)。详读[28页工程报告](../research-report.md)。

<!-- PAGE -->

## 9　已有失败决定研究优先级

这些是**本平台的实际发现**，不是对两家商业器件的推断。应先解决它们，再扩大真实阵列。

| 已观察边界 | 工程含义 | 下一步验证 |
| --- | --- | --- |
| enable在20 µs置0，258.5 µs才关；等待238.5 µs | 现有enable是正常PWM边界更新；不能直接充当紧急blank | 分开正常commit与fault override；先定义允许延迟，再做clock stall／reset／timeout等注入 |
| LED-first／early理想IREF主动供能1.093095 nJ | 理想源隐藏真实启动与headroom限制；compliant行为源仍不是实际generator | 实现可达到的reference／startup／power-good，DC校准后coupled regression |
| 真实static LED＋假设10 kΩ供电探针：88.265992 µA | 不满足±5% current target；供电余量影响恒流 | 该10k是负对照，不是推荐PDN；采用目标器件rail与阻抗数据重建条件 |
| TT最低码reference rail持续330 µW；LED branch约1.963 µW | current很小不意味着总系统低功耗；共享reference值得研究 | 完整PG、真实reference及上游logic功耗分账；不能直接乘商业pixel count |
| 缺少同器件dynamic／optical模型 | current积分不能代表最低灰阶的真实光输出 | I–V(T)、C／charge／pulse、白光转换与光学输出分开校准 |

### 为什么不能“把现有pixel复制4万次”

复制会引入shared reference loading、PG压降、clock／memory／frame distribution、同时切换、热和封装。现有模型只选择12MOS及部分signal RC；没有建立这些全阵列条件。小pixel nominal pass不能自动外推commercial backplane。

4×4 physical的进入条件继续使用现有roadmap：单像素在可实现reference、选定load和误差／功耗／pulse预算下闭环，并有具体实验任务。另一方面，可以先用轻量软件表示完整logical image，研究帧与mask；这不等于4×4或数万像素ASIC完成。

来源：[边界研究与功耗分账](../robustness.md)、[bench计划](../bench-validation-plan.md)、[阶段退出条件](../../roadmap.md)。

<!-- PAGE -->

## 10　建议搭建的电子电气架构

这是**独立参考架构提议**。每个接口由我们定义并记录，未宣称与EVIYOS或画芯商业协议兼容。

| 层 | 第一轮实现 | 后续硬件／资料条件 |
| --- | --- | --- |
| 场景／ADAS输入 | 带时间戳的synthetic物体box／轨迹，姿态假设 | 真实camera、识别／tracking与标定数据另行验证 |
| Vehicle supervisor | 软件消息回放：mode、validity、timestamp、enable、fault | CAN／LIN／Ethernet等按目标系统条件选择；目前无实际bus |
| Host／灯ECU | mask、基础beam、projection、mapping；golden frame | MCU／SoC／FPGA选型由算法、带宽和fault要求决定；不默认已拥有硬件 |
| Frame management | pending／active双buffer；完整帧校验后atomic commit | 再进入receiver／CDC／buffer RTL与实际transport；控制链与video payload分开 |
| Pixel execution | 选择一个logical pixel，量化为现有duty，生成原RTL trace | 后续本地状态、current set／calibration、diagnostic feedback；商业灰阶未复现 |
| Power／protection | 明确ideal假设；继续one-pixel reference／headroom／blank研究 | 电池侧保护、DC-DC、logic／LED rails、PG、package和thermal逐步补齐 |

### 控制权要清楚

基础照明、ADB遮光和投影图不能各自覆盖对方而没有优先级；模型应记录是谁产生最终pixel command。帧过期、损坏、重启或输入失可信时，要有可执行状态转移。具体降级光型与允许响应时间需要真实应用需求；本报告不指定ASIL或法规允许的投影内容。

Vehicle supervisor的数据较小；逐pixel图像是另一条payload链。看到CAN接口不能推出CAN承担全部图像；看到SPI名称也不能推出其有效带宽足够。硬件BOM先由公开electrical constraints与实验任务决定，不能从宣传图猜型号。

建议第一场景选**可确定box的ADB遮光**，同时保留projection输入；先证明mask、帧一致性和延迟可检查，再加入复杂camera或道路图形。

<!-- PAGE -->

## 11　仿真平台：从一条路径开始

第一轮建议执行：**synthetic scene → mask／frame → ECU双buffer／atomic commit → selected pixel →现有RTL／PWL →冻结v0.4 joint PEX →电荷与scope report**。这些上层功能本轮尚未实现。

| 模型／工具层 | 适合回答的问题 | 所需交付证据 |
| --- | --- | --- |
| Python functional／ECU golden model | mask位置、优先级、frame hash、更新／提交时刻、完整性与量化 | 同输入固定结果；frame ID／时间戳、partial／乱序／坏帧负对照 |
| RTL／Icarus；映射及timing流程 | receiver、state、CDC、commit／blank在clock下是否正确 | 新RTL独立回归和timing；旧单pixel通过不代替新模块 |
| ngspice＋锁定GF180模型／actual PEX | current、最低pulse电荷、compliance、startup和局部RC | DC calibration、predeclared guards、步长／窗口复算及失败raw日志 |
| Rail／thermal／optical模型 | 同时点亮敏感度、热限幅、PSF／mask泄漏 | 先明确假设；以后以同器件数据校准，不能先输出“实测流明” |
| 实物电测／光测／HIL | 真实接口、供电、response、光输出和温度 | 可获取器件与实际板卡、instrument／校准、raw数据和误差；目前未执行 |

### 如何把各层结果连起来

每个run保存scene／config hash、frame hash、accept／commit event、selected pixel command、实际PWM edge和analog case ID。同一命令在各层能追踪到同一像素和同一时间。重电气仿真先只运行受选单pixel和必要边界点；全logical image用轻量functional模型。

最小退出条件：一个正常scene和一个故障对照可用一条命令复现；坏帧不会污染active frame；latency分段记录；off／low／mid／full及mask transition可重放；量化误差与电荷积分并列；所有未测硬件／光学状态明确列出。

这条路径成功后的名称是“独立ADB／投影functional pipeline＋selected-pixel electrical simulation”。后续再分别升级实际reference／protection、供电网格、实物和阵列physical。详细合同与预算见[平台缺口分析](platform-gap-analysis.md)。

<!-- PAGE -->

## 12　计算：带宽、缓存与灰阶

以下为**独立预算场景**，不声称商业产品采用12-bit或60 Hz。每pixel一标量、uncompressed full frame、bit-packed；不含packet、blanking、诊断、line coding、retry及仲裁。25,600和40,000只是对标尺度。

```text
payload bits/frame = N × b
payload bit/s = N × b × f_update
double buffer bytes = 2 × ceil(N × b / 8)
wire bit/s ≥ payload bit/s / η       # η 为实际链路有效效率
```

| 假设N／b=12 | 单帧bytes | 双buffer bytes | 60 Hz payload Mbps | 100 Hz payload Mbps |
| ---: | ---: | ---: | ---: | ---: |
| 256（16×16 logical模型） | 384 | 768 | 0.18432 | 0.3072 |
| 25,600 | 38,400 | 76,800 | 18.432 | 30.72 |
| 40,000 | 60,000 | 120,000 | 28.80 | 48.00 |

25,600／12-bit／60 Hz若再假设η=0.8，wire预算至少23.04 Mbps；它不是实际SPI clock规格。若每pixel用16-bit内存容器，双buffer为102,400 bytes；内存表示与wire packing需分开定义。

### Command位宽与PWM分辨率分开

现有1 MHz／256 slots对应PWM3906.25 Hz，duty0…256有257种状态；9-bit输入包含clamp区间，不是9-bit均匀灰阶。b-bit command可先映射：

`duty = round_half_up(256 × g / (2^b − 1))`

归一化量化误差绝对值≤1/512≈0.195313%，但低码相对误差可能很大，多码映射到同一duty。这只是数学误差，不包含current／pulse／optical误差。

若以后用uniform slots做10／12-bit PWM，1 MHz下carrier分别976.5625／244.140625 Hz；保持3906.25 Hz的理想clock预算则为4／16 MHz。**这些仅为计数器关系，未完成新RTL、timing或电气／光学验证。** 数值与10-bit预算详见[平台分析](platform-gap-analysis.md)。

<!-- PAGE -->

## 13　后续方向与决策门槛

**判断：优先把项目建成可复现的车灯控制与器件验证平台。** EVIYOS作为公开资料较完整的主参考；画芯作为国内路线持续跟踪。当前直接追求商业pitch／数万像素backplane，会跳过最需要解决的电源、控制与实测问题。

| 顺序 | 要完成的工作 | 允许升级的结论 |
| --- | --- | --- |
| A：固定benchmark | 按料号／版本补电流、灰阶、frame、rail、thermal／optical条件；画芯补原厂资料及最新qualification身份 | 同层、同条件的产品对比；没有数据的项继续未知 |
| B：独立功能路径 | scene／mask、golden frame、buffer／commit／fault negatives，与既有selected pixel replay连通 | 可运行控制模型＋局部电气回放；不称commercial protocol compatible |
| C：单pixel工程闭环 | 实际reference／startup、保护blank、PG／neighbor、可获取emitter的数据与bench | 逐项current、延迟、功耗和动态／光学实测；根据实际通过范围报告 |
| D：有需求的4×4 | 共享reference、array state、PG／clock、同时切换、physical及coupled regression | 真实小阵列实现；各pixel／whole-array证据独立 |

### 技术—价值—市场视角

技术价值在于把“场景什么时候变成真实电流”追清楚，量化帧一致性、latency、minimum pulse、reference与供电边界。教学价值在于同一问题可从架构、RTL、电路、版图读到证据，而失败也能重现。

潜在使用者是器件／驱动研究团队、车灯控制开发者和教学实验室。早期可交付物是开放的functional contract、fault与latency测试、器件model card和selected electrical regression。它们是否节省实际开发时间，需由具体任务与外部复现证明；尚未验证付费需求、市场规模、BOM成本优势或量产收益。

下一次重要决策应基于两项事实：能否取得一个真实产品／emitter的合法数据与可测样品；能否让一个具体ADB控制问题从scene到current可复现。拿到证据后再决定FPGA／板卡、阵列扩展或MPW。无需先采购大型平台或声称商业替代。

<!-- PAGE -->

## 14　阅读、来源与复现入口

| 需要深入核查的内容 | 入口 |
| --- | --- |
| EVIYOS版本、接口、装车与条件冲突 | [headlamp-products.md](headlamp-products.md)／[逐claim来源ledger](../../../evidence/automotive/headlamp-sources.json) |
| 画芯／画擎、一手与转述、型号状态 | [huaxin-products.md](huaxin-products.md)／[逐claim来源ledger](../../../evidence/automotive/huaxin-sources.json) |
| 七层缺口、完整预算与退出判据 | [platform-gap-analysis.md](platform-gap-analysis.md) |
| 既有工程源、assumptions、raw定位与失败 | [v0.4研究入口](../README.md)／[工程报告](../research-report.md) |
| 本轮文档、计算与发布核查 | [验证记录](../../../evidence/automotive/validation.json) |

### 来源等级和公开范围

原厂PI／目录、OEM／Tier1公告、厂商直接访谈、合作方财报分别记录支持的窄结论。媒体报道保留为线索，未取得原始证据前不转成设计输入。公开资料的访问时间、型号、页码与不支持的推断保存在ledger；产品目录会变化，研究状态以2026-10-06快照为准。

厂商PDF与原始页图保留于git-ignored `build/automotive/`作为私有只读证据，未清权原图不进入public Git。公开报告采用原创文字、功能分层与计算，来源link与hash可追踪；第三方产品资料不是本项目开源资产。

### 报告导出

```sh
build/layout/venv/bin/python scripts/research/render_automotive.py
REPORT_PLAYWRIGHT_MODULE=/path/to/playwright \
REPORT_CHROME_PATH=/path/to/chrome \
node scripts/research/print_automotive.cjs
```

导出脚本只重建本报告HTML／PDF，不执行商业器件、ASIC或光学验证。PDF版需核对页数、浏览器geometry和逐页渲染；文字更新后旧hash与视觉审查状态不能直接继承。当前工程v0.4证据不因本轮产品研究而升级。
