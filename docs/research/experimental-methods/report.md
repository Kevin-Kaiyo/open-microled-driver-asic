# MicroLED 实验性研发方法验证

## 从研究假设到可复现实验

**项目定位：开放的实验性研发方法验证与教学。**<br>
文档修订：2026-10-06 · 工程阶段：单像素 v0.4

本项目用一条可运行的 MicroLED 驱动路径，验证怎样提出问题、选择模型、实施电路、检查版图、复算结果，以及识别假设失效的边界。研究指标由实验问题和可取得的数据确定。

> 每项结论都应能回答：输入是什么，改变了什么，测量了什么，依据什么门槛判断，以及结论适用于哪些条件。

| 方法问题 | 当前可以使用的实验基础 |
| --- | --- |
| 数字命令怎样变成电流 | Registered PWM → 实际事件／PWL → 晶体管驱动 → LED电气模型 |
| 版图是否改变结果 | 公开PDK、真实layout、所执行DRC/LVS、selected joint signal PEX |
| 怎样发现不合理假设 | reference启动、供电余量、最低码、控制延迟及错误网表对照 |
| 怎样让他人检查结论 | 源码、版本、source hash、原始运行定位、指标分母和独立复算 |

本轮修改项目表述与研究资料。工程基线仍为单像素 v0.4；新的frame／mask、缓冲和反馈方案属于待实施实验。先读本报告理解方法，再按需要查阅[28页工程报告](../research-report.md)中的器件、电路、版图与数值细节。

<!-- PAGE -->

## 1　把系统拆成可检验的部分

先区分三条路径：**数据决定何时动作，电源提供能量，反馈帮助判断状态。** 这样才能把时序错误、供电不足和负载模型误差分别定位。

<div class="flow">
<div class="node"><b>1 → 实验输入</b>固定图案、合成mask、时间戳与预设故障</div>
<div class="node"><b>2 → 命令模型</b>定义范围、映射、校验及允许的状态变化</div>
<div class="node"><b>3 → 时序控制</b>帧提交、PWM周期、reset与关断事件</div>
<div class="node"><b>4 → 电路模型</b>reference、开关、电流镜与实际寄生</div>
<div class="node"><b>5 → 负载模型</b>synthetic参数或可追溯静态I–V数据</div>
<div class="node"><b>6 → 观察与判断</b>电流、电荷、延迟、能量及适用范围</div>
</div>

图中1／2层的整帧实验是后续方案；当前已运行的路径从单像素输入进入PWM和电气模型。反馈到控制逻辑的闭环仍待实现。

| 路径 | 独立记录的变量 | 最容易混淆的结论 |
| --- | --- | --- |
| 数据／时序 | command、accept、commit、PWM edge | 帧到达不代表已经生效；图案更新率不等于PWM频率 |
| 供电／能量 | rail、IREF、headroom、端口功率 | 理想电源完成仿真不代表真实reference可以启动 |
| 负载／测量 | LED I–V来源、温度、动态参数、积分窗口 | 平均电流是电气代理量；真实光输出需要独立数据 |

PWM是以开关时间比例调节平均电流的方法；PEX是从版图提取寄生参数；PG指电源网络。先明确每个量的单位、方向与分母，再比较结果。

<!-- PAGE -->

## 2　目前已完成哪些实验

| 阶段 | 已保存的结果 | 能说明的范围 |
| --- | --- | --- |
| 数字逻辑 | 518完整frames、133159 checks；95 mapped cells、19 FF | 单像素PWM与映射；整帧接收／缓存尚待实施 |
| 模拟layout | 六MOS pixel；模拟macro 95×37.66 µm；所执行DRC/LVS、RC回归通过 | 锁定PDK／规则下的局部实现；制造接受另需证据 |
| 共同physical top | 305×180 µm span、19ports、实际GDS抽取和LVS | 两macro及连接；span不是die或pixel pitch |
| Selected joint PEX | 五种实际RC style；12MOS、45 signal R、77显式C、34邻居端口 | PG／body及PG-only C仍理想化；邻居按声明条件截断 |
| 主电气实验 | 37 transient／12 DC、146 guards；full-on100.112984…101.423393 µA；最低码最大面积误差0.700133% | 声明模型／测量窗内满足预设目标；不是完整PVT×RC交叉矩阵 |
| 边界与复算 | 三批总66 transient／28 circuit DC，另3 synthetic校准；18项真实错误对照 | 数值完成、工程门槛与适用范围分别记录 |
| 真实静态数据 | 一条黄色20 µm InGaN/diamond曲线；100 µA时Vf3.767910 V | 静态负载有出处；原测量温度、动态／热／光学仍需补充 |

当前联合模型包含末级buffer六MOS和analog pixel六MOS。它研究信号路径与局部电流响应；完整PG、上游logic全部瞬态、实际reference、pad／ESD／package和实物测量仍是后续实验对象。

证据：[joint PEX](../../../evidence/joint-pex/summary.json)、[主研究](../../../evidence/robustness/main-summary.json)、[总研究](../../../evidence/robustness/summary.json)、[独立审查](../../../evidence/research/v04-review.json)。每份证据的运行数、检查数和模型样本数都有自己的分母。

<!-- PAGE -->

## 3　从已有边界形成研究假设

好的实验既要确认预期行为，也要让不合理假设暴露出来。以下数值来自既有运行。

| 观察 | 待验证假设 | 下一项可检验实验 |
| --- | --- | --- |
| enable在20 µs拉低，258.5 µs才关断 | 正常帧提交与独立关断需要不同控制路径 | 定义关断时限，检查clock stall、reset、timeout与实际branch current |
| 理想IREF在LED-first启动探针中主动供能1.093095 nJ | reference的compliance和启动行为会改变边界结果 | 用可实现reference替换理想源，先DC校准，再做同条件耦合回归 |
| static LED＋假设10 kΩ供电探针为88.265992 µA | 供电压降能使输出管失去恒流余量 | 固定负载，逐级改变外部阻抗／rail，记录current与节点电压 |
| TT最低码reference rail持续330 µW，LED branch约1.963 µW | 固定bias成本可能主导低占空比功耗 | 分开reference、LED、logic及PG能量，研究共享reference的假设 |
| 缺少同器件动态与温度数据 | 静态拟合准确不能直接预测短pulse光输出 | 测I–V(T)、低电流区、charge／pulse与光学输出，并保留不确定度 |

10 kΩ是用于寻找失效边界的负对照，不是板级电源建议。330 µW属于声明reference rail的分账，不能再与其内部BIAS注入重复相加。行为源满足headroom限制也不代表实际reference已实现。

下一轮应写清楚单一主要自变量、固定条件、测量窗口、通过门槛及失败处理。一次改变多个边界时，结果只说明组合变化；需要中间对照才能归因。

详细条件与失败记录：[电源／控制边界研究](../robustness.md)、[实物验证计划](../bench-validation-plan.md)。

<!-- PAGE -->

## 4　后续逻辑实验：从图案到单像素

建议用**独立合成图案或mask → golden frame →完整帧校验 → pending／active buffer → atomic commit → selected pixel →现有RTL／PWL →联合电气模型**，验证各层时间与状态能否一致追踪。这条上层路径尚未实现。

| 模块 | 最小实验内容 | 预先规定的检查 |
| --- | --- | --- |
| 图案／mask | 固定坐标、固定seed、明确有效域 | 相同输入产生相同frame；越界与优先级有确定结果 |
| 命令／完整性 | 项目独立定义length、code range、frame ID | 坏长度、重复、乱序、部分帧有expected state |
| 双buffer／commit | 收齐并校验后，在指定边界交换 | 半帧不能污染active数据；commit时刻可重放 |
| selected pixel | 从logical plane选一个坐标并量化 | code、duty、实际PWM事件保持对应；记录量化损失 |
| 控制异常 | timeout、reset、停钟与enable变化 | 区分软件期望、RTL事件和电路响应；尚未实现的保护继续标注 |

第一轮可以选择16×16 **logical plane**、60 Hz命令更新、12-bit command。这些是独立的计算／功能实验条件；现有电气后端仍为一个pixel、256-slot PWM。软件数组大小不能作为真实阵列实现证据。

图案实验可以表示遮光区域、灰度阶梯或移动边界，用来检查坐标映射与延迟。合成物体box不是camera识别结果，未校准的投影图也不是实际光场。

最小成功标准是：一个正常case和一个错误case都能复现，输出frame hash、accept／commit时间、selected duty、PWM事件与电荷积分。后续是否增加RTL或硬件，由尚未回答的实验问题决定。

<!-- PAGE -->

## 5　让验证链能够被独立检查

| 层与方法 | 主要问题 | 必须保存的证据 |
| --- | --- | --- |
| Python功能模型 | 图案、mask、状态、buffer是否符合独立定义 | config／seed、输入输出hash、case分母、负对照与预期状态 |
| RTL／Icarus与timing流程 | command何时成为输出，reset／commit是否正确 | actual event trace、clock条件、新模块回归与约束 |
| ngspice＋锁定模型／PEX | current、pulse、compliance、startup如何变化 | DC校准、实际网表、原始波形、窗口／步长与失败日志 |
| 光学／热敏感度模型 | 假设变化是否影响研究判断 | 参数来源、适用域、单位与敏感度；待实测校准状态 |
| 实物电测／光测 | 仿真能否预测同条件下的观察 | 样品、仪器、校准、温度、raw数据和测量不确定度 |

给每次运行一个run ID；scene／config、frame、commit事件、selected pixel trace与analog case沿用同一身份。重电气仿真先聚焦受选pixel和必要边界点，完整logical plane采用轻量功能模型。

### 四类证据分别判定

1. **模型执行正确**：代码、映射和数值计算与定义一致。
2. **结果数值稳定**：窗口与步长细化后变化满足预设门槛。
3. **物理假设可信**：参数有测量依据，外推区及误差明确。
4. **系统实现成立**：真实接口、电源和测量条件下得到对应证据。

一类检查通过不会自动建立下一类结论。独立复算需要读实际raw数据；故意改错输入后检查应能拒绝，才能说明检查机制确实有效。

<!-- PAGE -->

## 6　用独立预算选择实验规模

下面统一采用12-bit单标量命令、uncompressed full frame、bit packing。像素数只是实验变量；packet、line coding、retry和诊断开销尚未包含。

```text
payload bits/frame = N × b
payload bit/s = N × b × f_update
double buffer bytes = 2 × ceil(N × b / 8)
wire bit/s ≥ payload bit/s / η
```

| 假设logical N | 单帧bytes | 双buffer bytes | 60 Hz payload bit/s | 100 Hz payload bit/s |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 2 | 4 | 720 | 1,200 |
| 16 | 24 | 48 | 11,520 | 19,200 |
| 256 | 384 | 768 | 184,320 | 307,200 |

N=1的12-bit payload占两个byte的存储容器；表中bit/s仍是有效12-bit数据率。真正按两个byte发送时，还需把4个padding bits算入wire。N=256、60 Hz若假设总体有效效率η=0.8，wire预算至少230,400 bit/s。

### 命令位宽与PWM状态数分别计算

当前1 MHz／256 slots对应3906.25 Hz PWM，duty0…256有257个状态。b-bit command可先量化：

`duty = round_half_up(256 × g / (2^b − 1))`

归一化绝对量化误差≤1/512≈0.195313%；低码相对误差可能很大，多个command会映射到同一duty。该数学误差不包含current、pulse或optical误差。

若采用uniform slots，1 MHz下10／12-bit PWM分别为976.5625／244.140625 Hz；保持3906.25 Hz需4／16 MHz的理想clock预算。这些只是计算关系，后续还须实际RTL、timing和短pulse验证。

<!-- PAGE -->

## 7　下一步的退出条件

| 实验阶段 | 需要完成 | 允许得出的结论 |
| --- | --- | --- |
| 当前资料与模型 | 问题、来源、假设、单位、版本和测量域明确 | 输入可检查；未知参数仍保留为假设 |
| 功能路径 | frame／buffer／commit与selected pixel回放可复现 | 独立功能模型和局部电气链成立 |
| 单pixel完善 | actual reference、startup、保护控制、PG／邻居边界 | 在新声明条件下的current／pulse／能量结果 |
| 同器件bench | 动态、温度、电气及光学数据与仿真对齐 | 相应测量范围内的预测误差与不确定度 |
| 小阵列研究 | 共享reference、PG、clock、同时切换假设有明确问题 | 通过新array级验证后才记录阵列实现结果 |

4×4的进入条件继续是单像素条件闭环，以及一个确实需要多通道回答的实验问题。扩展前先说明新增通道会帮助验证什么，而不是把规模本身作为进展。

实物实验先确认可获取的负载、供电和测量条件。制造实验需匹配PDK／规则、接口、封装和provider要求，并准备能回答明确问题的bring-up计划；所需条件尚未具备时继续模型和板级研究。

### 如何评价这个开源项目的价值

评价依据是他人能否复现实验、解释一个失败、定位模型边界，以及把方法用于新的可追溯数据。教学材料应从问题、架构、代码、电路、版图一直连接到结果；每一步都说明“观察支持了什么”。

这让平台的迭代由实验反馈驱动：先识别最影响结论的未知量，再取得数据或修改模型，最后检查新证据是否改变原来的判断。

<!-- PAGE -->

## 8　资料与复算入口

| 阅读目的 | 当前入口 |
| --- | --- |
| 深入理解器件、逻辑与版图 | [28页单像素研究报告](../research-report.md) |
| 查看可实施的实验计划 | [平台计划与数据合同](platform-plan.md) |
| 检查原始工程条件 | [联合PEX](../joint-pex.md)、[电源／控制边界](../robustness.md) |
| 从模型走向数据 | [实测静态LED说明](../measured-led.md)、[bench计划](../bench-validation-plan.md) |
| 查看研究价值与预算 | [实验方法与研究价值](../technical-value-market.md)、[roadmap](../../roadmap.md) |
| 检查本轮资料修改 | [修订与文档验证](../../../evidence/methodology/validation.json) |

代码和模型继续使用独立定义、公开PDK以及具有明确许可的科学数据。保留原始出处、模型notice和source hash，使读者能区分本项目实验与引用来源。历史运行记录说明当时输入和结论，当前项目范围以本次修订后的研究入口为准。

```sh
build/layout/venv/bin/python scripts/research/render_methods.py
REPORT_PLAYWRIGHT_MODULE=/path/to/playwright \
REPORT_CHROME_PATH=/path/to/chrome \
node scripts/research/print_methods.cjs
```

报告导出只生成阅读资料。它不执行电路或实物实验；更改model／parameter后仍须按工程规则运行DC校准和耦合回归。

本报告的逻辑扩展与预算均保持“待实施／假设”标记。已有工程数据继续使用各自冻结条件，文档定位修订不改变这些结果的验证等级。
