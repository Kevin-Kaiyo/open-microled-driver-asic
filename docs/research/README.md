# 当前研究资料入口

**先读阶段复盘（2026-10-25）**：[显示PWM与高速光通信的架构、性能和路线选择](architecture-decision-review-20261025/index.html) / [完整Markdown](architecture-decision-review-20261025/report-complete.md)。回答当前电流/灰度/频率/延迟、通信能耗/速率/BER、阵列、QSPI与制造成本；比较同条件结果并保留未知，不新增EDA/实测资格。

**当前入口（2026-10-24，参考与启动修订）**：两种应用分开阅读，负载及判据各自冻结。

- [显示 PWM：参考源、受控启动与恢复时间](pwm-reference-startup-20261024/index.html) / [证据与复现](pwm-reference-startup-20261024/README.md)。原 39 MOS PEX，加外部补偿/阻尼和 15 nF 滤波；保留 100/47 nF 失败与自主 POR 未完成边界。
- [高速 B：真实参考、供电与启动保护](nrz-b-reference-power-20261024/index.html) / [证据与复现](nrz-b-reference-power-20261024/README.md)。新 21 MOS 实际 GDS/PEX、参考电阻容差、固定 0.5 Gb/s 和完整端口能量；明确提前释放过压、掉电体结正向偏置与外部基准依赖。

以下报告为各自日期的历史快照，较早的“当前/最新”文字只描述当时状态。

当前新增阶段：[2026-10-24 供电、电阻角与封装扰动研究报告](driver-robustness-20261024/index.html)，附[实际GDS](driver-robustness-20261024/layout-viewer.html)与[复现入口](driver-robustness-20261024/README.md)。显示PWM与高速NRZ分别使用各自冻结负载。旧9–11mV余量不足；新厚栅氧核心改善相对器件限值的余量，A辅助电源扰动与PWM启动数值闭合仍有明确缺口。

历史阶段：[2026-10-23 单通道 NRZ 慢热接收与快冷端电压修正](highspeed-nrz-pvt-20261023/index.html)，附[真实 GDS 查看器](highspeed-nrz-pvt-20261023/layout-viewer.html)与[复现说明](highspeed-nrz-pvt-20261023/README.md)。本轮限定在冻结负载与接收代理下的实际版图 RC 实验，未完成光学或生产签核。

**单通道 NRZ 版图与寄生验证（2026-10-20）：[中文研究报告](highspeed-nrz-pex-20261020/index.html) / [真实 GDS 分层查看器](highspeed-nrz-pex-20261020/layout-viewer.html) / [证据与复现](highspeed-nrz-pex-20261020/README.md)。** 从实际电路、器件几何和金属层，逐步解释 GEOM/C/RC 控制、提取器电容问题、波形、接收余量与逐电源能耗。两版核心通过固定公开规则下的 DRC/LVS；279 条结果包含既有基线复用。典型 RC 最高离散通过点 A 2 Gb/s、B 0.5 Gb/s；慢热接收失败和快冷过冲尚待解决。电容模型经过审计组装，空间分配仍为近似；没有制造签核或光学 BER 测量。

**单通道 NRZ 晶体管比较（2026-10-19）：[中文研究报告](highspeed-nrz-20261019/index.html) / [网表、数据与复现](highspeed-nrz-20261019/README.md)。** 实现 GF180 电压驱动与电流转向两版电路，统一静态 LED 曲线、动态负载假设、数据序列与接收条件，检查速率、逐电源取能/回灌、MOS 角落、电容敏感性及数值收敛。属于 pre-layout 电气与接收代理实验；真实光学 BER、完整高速版图和流片验证仍未完成。

**高速通信驱动路线（2026-10-19）：[中文交互研究报告](highspeed-driver-routes-20261019/index.html) / [来源与复现](highspeed-driver-routes-20261019/README.md) / [Blender 封装概念](highspeed-driver-routes-20261019/package-concept.blend)。** 原创绘制受限摆幅电压驱动、恒流转向 OOK、分段电流 DAC/PAM4 三套 MOS 电路与芯片功能分区，加入器件表征平台、8 条原始文献索引和速率—能耗解析预算。本轮属于概念设计与可复算研究；没有新增高速 SPICE、DRC/LVS/PEX 或光链路 BER 证据。

**逐层展开与 PWM 动画（2026-10-18）：[64秒中文教学动画与逐步讲解](blender-pwm-animation-20261018/index.html) / [MP4](blender-pwm-animation-20261018/animation.mp4) / [可编辑 Blender 场景](blender-pwm-animation-20261018/pwm-layer-animation.blend)。** 从金属层、Contact、Via1/Via2，进入六只像素 MOS 的原理图与实际版图编号对应，再展示 PWM 高、低电平及栅极充放电。9,074 个 GDS 多边形、图层展开和全帧路径状态通过 102 项可视化检查；动画箭头是工作原理示意，不是电流密度或新电路仿真。

**三维可视化尝试（2026-10-18）：[Blender 模型与三幅教学渲染图](blender-layout-20261018/index.html) / [可编辑场景](blender-layout-20261018/single-pixel-r5.blend)。** 使用当前 r5 模拟宏真实 GDS 平面图形与锁定 Magic 名义层高，Z 放大12倍；包括器件接触孔和跨层通孔。可视化不新增电气或制造验证。

**最新实作（2026-10-15）：[18页研究报告](single-pixel-closure-20261015/report.pdf) / [HTML](single-pixel-closure-20261015/report.html) / [继续开发入口](single-pixel-closure-20261015/README.md)。** 启动数值判据与完整窗口回归、39MOS参考/保护新版图、数字恢复存储物理实现、共同顶层DRC/LVS/6512网络PEX已经完成对应检查。模拟宏启动最大0.656338 nA，DC/保护/最低PWM码通过；全共同顶层动态、电源扰动抑制和制造签核仍待完成。

以下较早资料是历史快照；其中“新模块未入版图”的状态已由本轮推进，但旧失败证据不改写。

**最新总框架（2026-10-14）：[28页研究报告](product-framework-20261014/report.pdf) / [带目录HTML](product-framework-20261014/report.html) / [完整资料入口](product-framework-20261014/README.md) / [真实二维及三维分层版图](product-framework-20261014/layout/viewer.html)。** 按架构→数字逻辑→buffer→像素／电流控制→LED→保护→版图／材料→高速通信→验证→流片／测试组织；有验证计划、流片包模板、逐层证据与教学眼图。三维仅为实际XY和相对Z投影；新参考／保护未入旧GDS，原启动收敛失败仍保留，无新晶体管或物理签核批次。

**最新单像素开发与流片教学（2026-10-14）：[启动修复与ASIC流片路线](startup-tapeout-20261014/report.md) / [18页PDF](startup-tapeout-20261014/report.pdf) / [完整制造教学](startup-tapeout-20261014/fabrication-chapter.md)。** 实际修改参考输出隔离，保留四MOS失效和严格电荷收敛失败；新TG方案的启动峰、正常最低码、停钟fault和恢复分别验证。补充工艺材料、五层金属、面积算法、hard macro布局、厂家交付及回片测试，明确新模块的pre-layout和制造接受缺口。

**最新研发与教学报告（2026-10-13）：[参考源、保护关断与驱动架构](reference-safety-20261013/report.md) / [PDF](reference-safety-20261013/report.pdf) / [详细架构章节](reference-safety-20261013/architecture-notes.md)。** 从理想IREF走到真实参考电路，再连接LED电流、PWM与独立保护；解释0.1～7 mA的输出余量、栅极电荷和电流DAC方案，区分电气一致性与光学均匀性，并分层讲解高速OOK／DAC的数据路径。新增晶体管及RTL实验保留失败与输入hash，旧布局/PEX不被新模块仿真升级。

**原理图入门：[PWM 栅极控制的 NMOS 电流镜](six-mos-pwm-tutorial-20261012/README.md) / [可切换电路与电流路径](six-mos-pwm-tutorial-20261012/tutorial.html) / [高速通信驱动技术路线详解](six-mos-pwm-tutorial-20261012/high-speed-notes.md)。** 按实际网表标清六只晶体管的 D/G/S/B、PWM 两种稳态及主要栅极充放电路径；另画独立电流舵教学电路和可选 cascode。“六 MOS”只是器件数量，不是行业统一架构名称。本资料不新增 EDA、速率或光学验证结果。

**晶体管、电路与布线设计：[2026-10-12深入研究](driver-circuit-layout-20261012/report.md) / [14页PDF](driver-circuit-layout-20261012/report.pdf) / [来源与数据](driver-circuit-layout-20261012/index.html)。** 从器件职责、gate-bias PWM与current steering，推进到尺寸/匹配、headroom、PG/return及via/工艺；保留15条直接相关来源、独立计算和现有工程证据范围，给出单像素受控实验顺序。无新增EDA或测量；设计示意不代表已实施。

**材料与驱动技术先读：[2026-10-12研究报告](driver-literature-20261012/report.md) / [PDF](driver-literature-20261012/report.pdf) / [可搜索索引](driver-literature-20261012/index.html)。** 新10页解释MOS/CMOS、材料/工艺、显示/通信架构和公开产品身份边界；21篇研究论文（13篇关键全文、8篇仅摘要）及官方资料共35条来源，含原数据条件、DOI/作者稿与定位。检索按研究问题选取，不是穷尽综述、市场占比或性能排名。它是资料研究，无新电路/EDA/测量结果。

**先掌握方向：[从事实到研究决策（2026-10-11）](decision-review-20261011/report.md) / [PDF](decision-review-20261011/report.pdf) / [HTML](decision-review-20261011/report.html)。** 新9页报告按问题、方法、依据、条件/数据和决策组织：第2页讲架构，第3–6页核查证据与边界，第7–8页给出受控实验顺序和失败分支，第9页追溯来源。保留单像素；先定位source/output compliance，再实现reference/fault，随后复验实际PG/body/邻居；同器件LED测量准备并行。该报告是既有结果复核与研究判断，没有新增EDA或升级silicon/光学证据。[复现与验收](decision-review-20261011/README.md)

**建议先读：[模型、方法与实际结论（2026-10-08）](readable-audit/report.md) / [PDF](readable-audit/report.pdf) / [HTML](readable-audit/report.html)。** 以当前checkout为基线的只读研究说明：从问题与证据等级，连到电路、参数、实际配置、波形解释、失败／修正与待验证建议。配套[10项技术疑点](readable-audit/questions.md)、[快照／附件说明](readable-audit/README.md)和[实际操作与当前状态（2026-10-10）](readable-audit/process-status.md)。旧报告与既有run保留；这次文档审查没有新EDA实验。

更新：2026-10-07。项目以实验性研发方法验证与教学为定位。物理／电气后端为单像素v0.4，新增frame experiment v0.1。

先读[当前进度与控制实验](control-experiment/progress.md) / [PDF](control-experiment/progress.pdf) / [HTML](control-experiment/progress.html)：已有阶段 → 完整帧提交 → 量化 → 电气回放 → 后续缺口。已实现Python帧接收模型与单像素RTL／PEX联动；[帧合同](../specifications/frame-experiment-v0.1.md)、[证据及独立复算](../../evidence/control/README.md)可逐层核查。

[2026-10-06方法说明](experimental-methods/report.md) / [PDF](experimental-methods/report.pdf) / [HTML](experimental-methods/report.html)保留当时计划快照；[当前平台计划](experimental-methods/platform-plan.md)跟踪已实现范围和后续门槛。

已有[分层研究报告](research-report.md)按“总览 → 初学者基础 → 工程验证 → 实验方法与研究价值”逐步深入。另有便于阅读的 [PDF](research-report.pdf) / [HTML](research-report.html)。入门读者先理解电流、PWM和MOS；工程读者再核查模型、units、测量分母、失败与寄生；研究方向见[实验方法与研究价值](technical-value-market.md)。旧教学 PPT 和检阅保留为历史快照。

| 内容 | 可检查的深入资料 |
| --- | --- |
| 研究指标与范围 | [v0.2 specification](../specifications/single-pixel-v0.2.md) / [v0.3集成条件](../specifications/single-pixel-v0.3.md) / [v0.4 joint PEX](../specifications/joint-pex-v0.4.md) / [v0.4电气门槛](../specifications/electrical-v0.4.md) |
| 实测 LED 静态模型 | [来源、拟合、单位计算和边界](measured-led.md) |
| Reference 与镜像管面积选择 | [误差预算、PDK Monte Carlo、实际 PEX 复验](reference-and-matching.md) |
| 模拟 physical implementation | [版图、DRC/LVS、PEX 和 macro views](../layout/README.md) |
| 数字逻辑与映射 | [Registered PWM 与 gate-level regression](../digital/README.md) |
| 数字布局布线与独立 DRC | [Physical implementation](../digital/physical.md) |
| 共同 top 与跨宏连线 | [实际 GDS / LVS / DRC / 负对照](../../evidence/integration/README.md) / [独立集成审查](integration-review.md) |
| 真实输出级与输入负载 | [buf_2 晶体管、charge / AC、实际 RC 与 slew 条件](interface.md) |
| v0.4实际联合信号PEX | [output12 junction、12MOS／45R／77C、5个RCstyle、真实接入点与投影ledger](joint-pex.md) |
| v0.4电源／控制与负载边界 | [同条件pre/post、startup、reference、reset／enable、series-R、邻居截断及失败](robustness.md) |
| 从模拟走向实物测量 | [bench验证计划、所需数据、测量分母与退出条件](bench-validation-plan.md) |
| 实验方法与研究价值 | [研究问题、4×4预算与后续实验的进入条件](technical-value-market.md) |
| 独立控制与电气实验 | [frame experiment v0.1](control-experiment/progress.md) / [帧合同](../specifications/frame-experiment-v0.1.md) / [当前平台计划](experimental-methods/platform-plan.md) |
| 完整工程路线 | [阶段退出条件](../roadmap.md) |

记录规则：原始生成输出在 `build/`，紧凑结果与输入 hash 在 `evidence/`。同一条实测曲线、固定 corner 网格、随机模型抽样和动态假设各自有条件和分母。平均 branch current 是电气代理量，尚未测量真实光输出。

v0.4联合signal模型整体替换旧buf／analogRC／SPEF／link路径，包含真实输出级结几何并从实际M3右端接入；PG／body电阻和PG-only电容仍投影到理想rails。语义复现依据端口、数值、重数和拓扑，而不是Magic输出的记录排序字节。启动能量属于声明的selected十二MOS模型加外部假设，不能称全芯片PG或系统功耗；物理4×4、receiver RTL及硬件／实物测量仍未实现；新增控制功能模型只选一个pixel做晶体管回放。

历史材料：[2026-10-03 检阅](../review/README.md)记录旧10/2µm问题；[教学PPT](../teaching/open-microled-single-pixel-teaching-v2.pptx)用于初始架构；[v0.2报告](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/tree/7ad33e16cfc26a8e785061ef1713156d36d97259/docs/research)保留独立macro；[v0.3报告](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/tree/f4d478707f055cf1015267e14a2a56e28c3e9991/docs/research)保留共同物理top及分块接口。旧manifest锁定当时输入，不能当当前source inventory；v0.4保留所有旧证据，新增联合signal PEX与电气边界研究。

2026-10-06文档定位修订的evidence/methodology记录保留当时hash；其verify_methods.py针对该历史快照。当前控制实验使用scripts/control/validate.py，当前全库身份使用current-manifest.json。
