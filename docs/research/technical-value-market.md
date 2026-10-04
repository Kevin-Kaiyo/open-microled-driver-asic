# 技术、价值与市场：先把可验证的能力做成可用的平台

更新：2026-10-05。定位判断基于已完成的 v0.3 单像素能力与本次核查的公开第一手资料；不是市场规模预测、客户订单或 ASIC 产品认证。面向入门读者的完整技术链路见[研究报告](research-report.md)。本页的来源、条件与判断逐项保存于 [sources](../../evidence/strategy/sources.json)、[claim ledger](../../evidence/strategy/claim-ledger.json)。

**建议把这个项目定位为“可复现的 MicroLED 器件电测与驱动共设计平台”，以教学和小阵列研究为主线。** 当前最有价值的成果，是让读者从一个灰阶命令出发，检查 PWM、电流镜、器件数据、金属连接和误差，再知道哪些假设仍需测量。这条链路可以支持工程训练、公开器件模型和低电流驱动研究。直接进入几微米 pitch 的商业微显示背板，或把现有亮度 PWM 改称 Gbps 光通信驱动，都会跳过尚未解决的面积、供电、动态负载和系统验证问题。

## 1. 入门：技术、价值、市场分别回答什么

**技术**回答“在给定条件下能做什么”：例如在仿真中让约 100 µA 电流受 PWM 控制。**价值**回答“这项能力替谁减少什么问题”：例如帮助器件工程师区分低灰阶误差来自 LED、电流参考还是驱动时序。**市场**回答“谁愿意持续使用、贡献数据或为这种帮助付费”：目前还没有完成需求访谈或付费验证，因此后两项中的用户与购买行为是待验证假设。

一个“能点亮”的电路只是起点。做教学时，读者还要看得懂、跑得起来、发现错误；做器件研究时，需要可更换的真实负载数据和测量条件；做商业产品时，还需可靠性、封装、测试、供货与成本。它们需要的证据逐级增加，不能由一个通过的仿真替代。

本项目 v0.3 的约 100 µA 电流、1 µs 最短 PWM slot、共同 routed macro top 与有条件的 DRC/LVS 是真实可检查的设计工作。真实 LED 的 I–V 是公开测量数据；它仍没有完整 C–V、I–V(T)、反向区和光学模型。新的研究结果应按各自报告读取，不能借用本页的商业比较升级验证等级。

## 2. 工艺为什么适合当前学习目标

GF180MCU 官方材料把它称为 **0.18 µm、3.3 V/6 V MCU process**；公开文档还列出其他器件族。较高电压和公开模型有利于从晶体管、电流镜到 LED headroom 的教学，代价是当前所用长沟道匹配器件和高压数字单元并不追求最小像素面积。GF 的 BCD 是另一组商业平台，不能把本项目的 GF180MCU 当作所有 180BCD 功率器件能力的代表。[GF180MCU 官方 README](https://github.com/google/gf180mcu-pdk/blob/main/README.rst)、[GF BCD 平台](https://gf.com/technologies/power/bcd/)。

GF 官方目前将 display driver / microdisplay backplane 能力列在 28、40、55 nm 平台。这说明商业显示设计会选择适合密度、存储、泄漏、模拟电压及集成方式的工艺；它不证明 180 nm 不能研究 LED，也不证明只有缩小制程就能完成好背板。[GF Feature-rich CMOS，Display](https://gf.com/technologies/cmos/feature-rich-cmos/)。

维护与制造资格也要分开。2026-10-05 浏览时，Google 的 GF180MCU 原仓库标记于 2026-09-23 archived，README 仍写 experimental preview / alpha、test-chip 使用不作保证。这不自动否定本项目锁定文件的模拟结果，但下一阶段必须确认实际维护分支、完整 PDK、规则与候选制造服务的匹配。公开模型、开放许可证与生产接受是三件事。[官方仓库状态与 README](https://github.com/google/gf180mcu-pdk/blob/main/README.rst)。

## 3. 三条应用方向的适配判断

下表是工程判断，不是已验证的销售市场。这里的“用户”指需要解决问题的人；尚未确认谁会购买。

| 方向 | 潜在用户的问题 | 当前适配 | 最大缺口 | 当前决定 |
|---|---|---|---|---|
| 教学 / 器件电测 / 1–16 路研究驱动 | 学会完整验证链；检查 µA 电流、短脉冲与器件模型 | 高：一像素可复现，错误可追溯 | 实际 reference、LED 动态/温度、bench 数据和外部复现 | 优先推进 |
| 商业 LED 矩阵或高密度微显示 | 像素一致性、低灰阶、面积、总功耗、接口、诊断与可靠供货 | 小研究阵列可借鉴；量产矩阵与微显示现阶段低 | 阵列未实现；高密度集成、存储、校准、封装、光学与量产资格 | 先测需求，再决定重新架构 |
| 高速可见光通信 VLC | 电光带宽、驱动摆幅、接收 SNR、BER 与链路能耗 | 当前亮度 PWM 低 | RF/高速驱动、实测 S 参数/动态、接收机与光链路 | 独立研究分支，暂不合并目标 |

小阵列研究并不要求驱动电路和发光 mesa 有相同 pitch。可以先在测试芯片或板级系统中，把外接 LED 的电流/时间误差测清楚。若用户真正需要的是在每个 4 µm 像素下面放完整电路，就必须重新选择 pixel architecture、存储位置、工艺与互连方式，不能把当前 macro 直接复制过去。

## 4. 官方 benchmark：比较条件比比较数字更重要

这些资料展示不同应用已经要求哪些能力。它们的数值不可直接排成性能榜。

| 公开对照 | 数据及条件 | 对本项目的启示 | 不可比之处 |
|---|---|---|---|
| TI LP5860，Rev. A，2021-11，p.1、p.7 §7.5 | 18 sinks × 11 scan = 198 dots；100 µA 全开时 device error ±7%、channel error ±5.5%；50 mA 才是两项 ±3% | 低电流精度可以成为研究问题；先比较同一电流与负载条件 | 量产 data-sheet bounds 对比有限模型样本；scan matrix 对比独立 pixel |
| JBD AM-µLED 0.1 Series，官方产品页，版本/日期未标 | 厂商列 500×380、4 µm pitch、10 bit、480 Hz、典型 50 mW | 商业微显示是密度、存储、光学和功耗的整套要求 | 未公开典型功耗对应的图案/亮度；不能把 50 mW 除以像素数后与本电路排名 |
| Hsiao et al.，Scientific Reports，2024-03-25 | 作者报告 30 µm×8 yellow array 的 NRZ-OOK 超过 1 Gbit/s、OFDM 1.5 Gbit/s | 通信需实测电光链路及匹配的驱动和接收条件 | 本项目没有 optical link、BER 或同样器件/偏置条件；PWM slot 不是通信 symbol |

来源：[TI data sheet](https://www.ti.com/lit/ds/symlink/lp5860.pdf)、[JBD 官方 0.1 产品页](https://www.jb-display.com/product_des/16.html)、[Hsiao 原论文](https://doi.org/10.1038/s41598-024-57132-9)、[作者所在大学的摘要](https://scholar.nycu.edu.tw/en/publications/advancing-high-performance-visible-light-communication-with-long-/)。论文 online date 采用[出版社 Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1038%2Fs41598-024-57132-9)，避免把大学索引中的 December 当成首次发表日期。JBD 直接打开返回 403，本轮可读内容来自公开搜索索引；规格按厂商宣称保留，完整购买规格需另取正式 data sheet。

特别注意 TI 的 100 µA 行：p.7 §7.5 的条件为 VCC=3.3 V、VLED=3.8 V、VIO=1.8 V、所有 channels on、PWM=100%；常规器件 TA=−40…85°C，typical 值是 25°C。Device error以芯片平均电流相对设定值为分母；channel error以各路电流相对芯片平均值为分母。本项目±5%比较单支路与100 µA目标，分母与统计人口也不同。Headline 的 ±3% 不能直接套在 100 µA。**本项目的 ±5% 目标只在已声明模型/网格里检查，当前不能据此宣称精度优于 TI。** 价值假设是：公开方法能否在实际低电流条件下解释误差并给出有用改进。

## 5. 从一像素到 4×4：先做四本账

以下都是可复算的**预算场景**，不是已完成阵列。原始量来自冻结 v0.3 的 [analog GDS area](../../evidence/characterization/actual-w20-l4-area.json)、[measured static load](../../evidence/characterization/measured-load-summary.json)、[PWM RTL](../../rtl/pixel_pwm.v)。运行 `scripts/strategy/budget.py` 生成 [JSON](../../evidence/strategy/budget.json) 与 [CSV](../../evidence/strategy/budget.csv)，其中保留输入 hash 和所有排除项。

### 5.1 面积账：不能把集成 macro span 当作 pixel pitch

当前共同 top 的 305×180 µm 是两个 macro 加顶层布线的**跨度**，不是 pad ring、die size 或一个可线性复制的像素单元。当前模拟 cell bbox 为 95×37.66=3577.7 µm²；16 个冻结副本的面积和是 **0.0572432 mm²**。这只包含模拟 cell 的副本边界，没有数字存储/控制、通信、参考分配、routing、pads/ESD、fill 和电源网。因此它既不是完整 4×4 面积的预测，也不意味着16倍共同 top 是合理布局。

4 µm 方形 pixel site 的面积为16 µm²。当前模拟 cell bbox 是其223.606倍；单个 MOUT 的 gate 几何20×4=80 µm²也已超过该 site。这只证明**冻结的当前电路不适合原样塞进4 µm site**，不证明所有 GF180 电路或所有 MicroLED 架构都不可能小型化。共享 reference、较小器件和校准可能换面积，但需要新误差预算和真实版图。

### 5.2 功耗账：变暗不等于全部电路都省电

在公开静态 I–V、MOS 27°C、Vlogic=3.3 V、VLED=5 V、理想 IREF=100 µA 条件下，IOUT=99.788467 µA。单路 LED rail 输入498.942337 µW，加 analog/control/reference rail 330.000012 µW，共828.942349 µW。它不含数字宏和实际 reference generator；也不是光输出。

若16路各保留一个持续100 µA reference支路，则仅这部分电源输入就是：

\[
P_{bias}=N V_{logic} I_{ref}=16\times3.3\times100\,\mu A=5.28\,mW.
\]

以静态电流乘 duty 作一级近似：

\[
P_{analog+LED}\approx N V_{logic}I_{ref}
                       +V_{LED}I_{full}\sum_{i=1}^{N}D_i.
\]

16路全开约 **13.2631 mW**；全为duty=1/256时约 **5.3112 mW**；全为25%时约 **7.2758 mW**。关灯但保持bias仍有5.28 mW reference floor，其他泄漏、切换和实际reference功耗需另加。此近似没有真实LED动态/温漂，不替代 transient 或实测能耗。

若未来只保留一个共享100 µA reference，数学上的这一项可由5.28降至0.33 mW；其16路全开预算约8.3131 mW，最低码约0.3612 mW。这是**架构假设**，不是已验证省电结果：共同bias的fanout、startup、noise、gate charge、失配、routing RC和跨通道耦合都要重新验证。优先研究共享reference，理由是它瞄准了低灰阶时显著的固定成本，而不是为了增加功能数量。

### 5.3 数据账：视频更新、PWM与通信是三个速度

目前每帧256个slot，1 MHz slot clock对应3906.25 Hz PWM。9-bit duty包含0…256，共257个精确命令；代码257…511会clamp。未来若用常见8-bit图像数据，需要先定义它怎样映射到这个命令范围。

若16路每路保存一个9-bit命令，单buffer144bit=18byte；double-buffer288bit=36byte。这是**有效数据量**，还没计enable、错误状态、计数器、地址、协议逻辑，也不是已经实现的SRAM。

\[
B_{payload}=N\,b\,f_{update};\quad
B_{wire}=f_{update}(H+N\,b_{wire}).
\]

| 4×4 场景 | 更新频率 | 每次有效数据 | raw payload | 提议packet的wire预算 |
|---|---:|---:|---:|---:|
| 单色视频/测量图案 | 60 Hz | 16×9=144 bit | 8.64 kbit/s | 17.28 kbit/s |
| 每个PWM帧更新 | 3906.25 Hz | 144 bit | 562.5 kbit/s | 1.125 Mbit/s |

Packet仅为独立提议：4byte头/校验+每像素2byte，总288bit，尚未实现。若未来SPI为1MHz，一包需288µs，大于256µs PWM帧，因此不能保证每PWM帧更新；60Hz更新则有很大带宽余量。这里的SPI速度与当前1MHz PWM clock不是同一个接口。正式协议还要计片选间隔、时钟偏差、frame boundary提交和错误处理。

以VGA作不同规模的独立预算：640×480、8bit单色、60Hz的raw payload为147.456Mbit/s；RGB各8bit则442.368Mbit/s。两者都没有包括blanking、编码或协议开销。这解释为什么微显示需要不同的存储与高速接口架构；它不证明本项目达到这些速率。

### 5.4 尺寸与光学账：电流相同，物理条件未必相同

20×20 µm² mesa在100 µA时，按完整方形面积算的平均电流密度为25 A/cm²。如果假设缩到4×4 µm²并保持同样100 µA，则密度会变为625 A/cm²，增加25倍。后一项仅为几何假设，不是JBD器件的电流条件。实际有效发光面积、电流拥挤、温升、sidewall损失与EQE都会改变结果，不能沿用同一个LED电气模型来预测小像素亮度。

## 6. 市场价值：先验证工程师愿意用的工作流

本项目的差异化假设应具体到一种工作流：**拿到一份可公开的LED测量数据，建立有边界的model card，连接可检查的ASIC驱动，再把误差定位到reference、mirror、PWM、寄生或LED本身。** 公开模型和失败对照比单独提供一个PWM模块更有复用价值。这个判断来自当前工程资产与官方benchmark，并不是已经发生的客户行为。

先验证三类用户的问题：

| 用户假设 | 需要验证的实际问题 | 最小交付 | 价值证据 |
|---|---|---|---|
| 刚入门的半导体工程师 / 教师 | 能否理解并独立复现从spec到DRC/LVS/电流误差的链路 | 三层讲义、一像素baseline、故意断线/错误属性例子 | 外部读者成功复现并解释至少一个失败；记录卡点和耗时 |
| MicroLED器件实验室 | 是否缺少便于与驱动联合评估的公开动态/温度模型 | 单器件measurement schema、model card、拟合与边界检查 | 真实数据、测量不确定度；同条件预测与holdout测量的误差 |
| 小阵列驱动 / mixed-signal研究团队 | 100 µA附近的匹配、reference和短脉冲预算是否限制实验 | 1→16路需求书、共享bias假设与bench方案 | 用户提供具体current/pulse/temperature/power需求；模型或bench改进能改变设计决定 |

“能教学”应以读者能复现和解释为证据；“能服务实验室”应以数据与误差预测为证据；“能商业化”还要验证持续使用、交付维护成本及采购意愿。GitHub star、厂商宣传或市场增长报道都不能替代这些证据。本轮没有执行外部访谈、发信、采购或投片。

## 7. 可执行的方向门槛

这些是建议的下一轮决策门槛，尚未宣称满足。先固定真实用户需要的规格，再展开新架构。

| 决策 | Go所需证据 | No-go / 转向触发 | 下一步 |
|---|---|---|---|
| 完成单像素平台 | 完整joint PEX与供电/启动、非理想reference预算；至少一组traceable LED动态与温度数据；维持既定±5% current/±2% lowest-code目标或透明重定spec | 模型没有目标pulse/voltage/temperature范围的数据；误差无法定位 | 缩窄声明范围，先测量或修模型 |
| 进入4×4研究芯片 | 单像素条件闭环；16路用户需求、packet/commit/reset定义；shared bias、simultaneous switching、功耗与面积预算；按同规则做array验证 | 单像素尚未闭环；供电或固定bias功耗已超用户预算 | 保留一像素/分立测试载体，修改reference与架构 |
| 证明教学/研究需求 | 建议先与5名目标用户访谈；至少2个独立使用场景；1名外部入门读者复现baseline并解释错误；至少1个可追溯LED数据合作意向 | 只有一般性赞同，没有数据/复现/具体实验任务 | 保持开放教学作品，停止扩大商业功能 |
| 评估MPW投入 | 候选provider明确接受exact variant/decks/pins/voltage；取得报价、封装/测试责任；总预算≤用户自定B，silicon测量能回答明确问题 | provider不接受、5V/analog访问不匹配、无bring-up/measurement方案或超B | 不提交；继续模拟或先做board-level电测 |

需求访谈只需围绕五个问题：实际要驱动多少路/多少µA；最短pulse与准确度；电源/温度/LED数据是否已知；现在用什么方法、哪里耗时或失败；若本平台把这个问题解决，愿意如何实际使用/贡献数据/采购。采访数量是本项目建议的最小学习目标，不是统计代表性或客户名单。

## 8. 成本账与开放制造入口

公开GF180社区shuttle存在；Tiny Tapeout官方[芯片列表](https://www.tinytapeout.com/chips/)在访问日列出GF系列run。其[Analog Specs](https://tinytapeout.com/specs/analog/)的一些限制和报价段落明确标成sky130A，不能套成本项目的GF180、Metal5、5V LED rail或19-port top。Analog page列出的通用PDK名称也不能替代GF run的模板、rails、pin path RC和接受条件。先向实际候选服务确认，公共入口本身不构成可提交资格。

当前没有匹配本设计的有效制造报价，因此不填一个看似精确的“单芯片成本”。可审阅的预算应为：

\[
C_{project}=C_{design\ effort}+C_{MPW}+C_{package/PCB}
            +C_{measurement}+C_{logistics}+C_{rework}.
\]

MPW报价需要注明area/tile、模拟pin、工艺、截止日期和交付数量；measurement要包含电流/脉冲、温度与光学所需设备或使用费。若未来评估销售，单位经济应先写成 `NRE/Nusable + variable cost + support`，其中usable数量由实际交付和测试决定；不能把有限MC样本当成yield，或把一轮shuttle的价格当成量产成本。

优先顺序因此很明确：**完成一像素的真实负载与供电闭环 → 让一位外部初学者独立复现 → 获取有实际条件的器件/用户需求 → 决定4×4与共享reference是否值得实现 → 最后评估带明确测量目的的MPW。** 高密度显示与高速VLC保留为将来需要新spec和新证据的研究方向。

## 9. 证据包与复算

- [sources.json](../../evidence/strategy/sources.json)：原始名称、组织、版本/日期、访问状态、locator与public reuse边界。
- [claim-ledger.json](../../evidence/strategy/claim-ledger.json)：company claim、research experiment、当前project evidence、calculation和direction hypothesis分开记录。
- [budget.json](../../evidence/strategy/budget.json) / [budget.csv](../../evidence/strategy/budget.csv)：输入hash、精确几何、数据/功耗预算；所有array项标成未实现场景。
- [budget.py](../../scripts/strategy/budget.py)：用标准库Decimal复算，不修改任何模型或已有电气结果。

第三方产品图片、框图和数据手册页面没有在本公开仓库中重发布；本页只整理必要的事实数值、引用与独立计算。Original TI data sheet的本地阅读副本位于ignored `build/strategy/`，不作为本项目自有证据图。可公开复用的LED数值曲线遵循其原NOTICE；本页没有将厂商图片换色后当原创。
