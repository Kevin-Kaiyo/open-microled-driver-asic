# 单像素的 reference 与 mismatch：先分开误差，再决定改什么

日期：2026-10-04。读者先看[单像素指标](../specifications/single-pixel-v0.2.md)与[物理前提审阅](../review/README.md)。本页针对 synthetic LED 教学基准；[公开实测 LED](measured-led.md)是另一个有独立限制的负载实验。

**当前采用 W20/L4 µm，最终优先证据是实际新版图重新提取的 RC（第 6 节）。** 在声明的 synthetic LED/reference 条件下，1080 点 deterministic PVT 为 99.28026–102.07565 µA；五组 MC 各 256 个样本均无 ±5% 超限；三条件最低码电荷最大误差 0.76830%，满足 ±2%。这是一组有明确条件的模型验证，不能推出制造良率或真实 LED 动态已获验证。

修改的原因保留在历史数据中：**旧 W10/L2 的 deterministic PVT/reference 扫描通过 ±5%，但最差高电流条件叠加 PDK 随机失配后，4/256 个样本超过 105 µA。** 因此“固定 corner 通过”不足以判定预算闭环。本页依次记录旧版失败（第 4 节）、同种子概念候选（第 5 节）、实际 layout/RC 复验（第 6 节），没有改变 ±5% 门槛。

## 1. 本轮的问题与不变量

电路仍然是六 MOS 单像素，输出目标 100 µA。MREF 与 MOUT 是 1:1 电流镜，PWM 电路把输出管 gate 接到 bias 或地。先不增加 cascode 或片上 reference generator：本轮要确定问题来自 reference、共同工艺变化还是管间失配，以及简单尺寸调整能改善多少。

复用已锁定 full PDK、原始提取网表以及原 synthetic LED：27°C 时目标 `Vf=2.8 V @ 100 µA`，`N=3`、`Rs=50 Ω`，使用原始模型的电容和温度行为。这些 LED 参数仍是教学假设。冻结的旧提取网表有 6 个 wrapper、59 个 R、43 个 C。

目标与条件在运行前已写入指标：

| 项目 | 本轮设定 |
|---|---|
| Absolute full-on current | 相对 100 µA 的误差 ≤±5% |
| Lowest-code charge | `Q1/(Ifull × 1 µs)−1` 的绝对值 ≤2%；Ifull 必须是同一条件实测的 DC 模拟电流 |
| MOS/reference 温度 | 0、27、85°C |
| 电源 | Vlogic=2.97/3.3/3.63 V；VLED=4.5/5/5.5 V |
| Fixed corners | typical、ff、ss、fs、sf；这是离散确定性条件，不是概率分布 |
| Monte Carlo | 每组 256；种子 20261004–20261259；各组共用相同种子便于配对 |

## 2. 统计开关确实启用了什么

完整 PDK 的 primitive commit 为 `41918f5a2356b9fb49a897ecc4fb4716b0ab1041`，open_pdks build 为 `54435919abffb937387ec956209f9cf5fd2dfbee`。模型 SHA-256 为 `677822db50bf8968f77854bb455006ac5c245deb46ecfc8b352934e752135c46`；运行前检查 [full-PDK lock](../../layout/pdk-lock.json) 的 9 个文件。实际工具是 ngspice 47，见[版本记录](../../evidence/characterization/ngspice-version.log)。

官方网页的 [Statistical Model Usage](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_9_2.html) 仍没有完整调用示例。因此配方来自**锁定的源代码加实际开关对照**，不把网页空白处当作已获得验证的 recipe。

| 模拟人口 | `.lib` | `sw_stat_global` | `sw_stat_mismatch` | reference |
|---|---|---:|---:|---|
| Local only | typical | 0 | 1 | 理想 100 µA |
| Global only | statistical | 1 | 0 | 理想 100 µA |
| Global + local | statistical | 1 | 1 | 理想 100 µA |
| Global + local + nominal bounded reference | statistical | 1 | 1 | 有限 Rout，gain/TC/line error=0 |
| 条件式 low/high MC | 对应最差 fixed corner | 0 | 1 | 对应 reference 误差边界 |

`design.ngspice` 注释声称默认 1/1，但实际赋值是 0/0；本流程在 include 后**显式覆盖开关**。Global MC 必须选含共同随机参数的 `statistical` library。只在 fixed corner 上打开 global 开关，不能假设就产生了预期的 global Monte Carlo。来源：[锁定的 design.ngspice](https://github.com/fossi-foundation/globalfoundries-pdk-libs-gf180mcu_fd_pr/blob/41918f5a2356b9fb49a897ecc4fb4716b0ab1041/models/ngspice/design.ngspice#L22-L70)、[锁定的 sm141064.ngspice](https://github.com/fossi-foundation/globalfoundries-pdk-libs-gf180mcu_fd_pr/blob/41918f5a2356b9fb49a897ecc4fb4716b0ab1041/models/ngspice/sm141064.ngspice) 中 `.LIB statistical` 与 `.subckt nfet_06v0`。

6 V NMOS wrapper 对每个实例设置 `delvto`；其标准差可用 µm 单位写成：

\[
\sigma_{Vth}=\frac{0.7071\times0.01155}{\sqrt{(L-0.4)(W+0.5)}}\ \mathrm{V}.
\]

这里是**单个实例**的 threshold 标准差；两个独立实例的差值标准差还要考虑两者方差之和。该 wrapper 的 NMOS `par_k=0`，不能声称同时验证了非零的 NMOS mobility mismatch；PMOS wrapper 使用它自己定义的失配参数。共同工艺变化来自 statistical library 的共享随机参数。不要把这个模型的覆盖范围扩展到所有真实失配来源。

每个样本启动独立 ngspice 进程，先 `setseed`，再 `reset` 重建模型，最后 `op`。这样源文件中的 `agauss` 在受控种子下重新求值；不是在同一个已经抽好参数的电路上重复 `op`。语义来源：[ngspice manual](https://ngspice.sourceforge.io/docs/ngspice-manual.pdf)，2026-09-28 版，§13.5.65 Reset、§13.5.77 Setseed、§18.2 Random parametric variation。网页手册为 47+ 开发版；本次实际执行与重复性证据来自安装的 47。

六项实际控制全部通过：0/0 的 8 个种子输出完全一致；statistical 0/0 与 typical nominal 一致；同种子重跑完全一致；256 个不同种子产生 256 个不同 MOUT `delvto`；local σ 与 wrapper 相符；global-only 改变模型 Vth，而所有局部 `delvto` 保持零。

旧 W10/L2 的理论单管 σVth=1.99255 mV；256 个样本的 MOUT=2.03182 mV、MREF=1.95098 mV，两管抽样相关系数 −0.02694。完整控制值见[原始 summary](../../evidence/characterization/reference-matching-summary.json)。

## 3. Reference 预算是怎样写出来的

[External reference 行为源](../../scripts/characterization/external_reference.spice)表达“外部已校准电流源应满足怎样的规格”。它没有引用某个未选定零件的保证值，也没有实现片上 reference generator。

设 `H=Vlogic−Vbias`，在 H≥1 V 的有效区：

\[
I_{ref}=100\,\mu\mathrm{A}\,[1+e_{cal}+a_T(T-27)+a_V(V_{logic}-3.3)]
       +\frac{H-1.9}{10\,\mathrm{M}\Omega}.
\]

| 参数 | 候选预算 | 含义 |
|---|---:|---|
| 校准点 | 27°C、Vlogic=3.3 V、H=1.9 V | 与 model 的温度和电压校准点一致 |
| 校准后 gain error | ±0.5% | 不是 MOS mismatch，也没有假设它服从高斯分布 |
| Temperature coefficient | ±25 ppm/°C | 距 27°C 的增量；到 85°C 为 ±0.145% |
| Line sensitivity | ±3000 ppm/V | ±0.33 V 对应 ±0.099% |
| Output resistance | 10 MΩ | H 每变化 1 V，电流变化 0.1 µA，即 0.1% |
| Minimum headroom | 1.0 V | 以下只用示意线性 dropout，不能作为真实器件特性 |

0.5%、0.145%、0.099% 不能不分条件地合并成一个已测量的精度。脚本逐一枚举误差符号，电路求解 H，再求实际 Iref。Gain/TC/line 都是**界限检查**，没有虚构其生产概率或与 MOS 的相关性。本模型也没有 reference 的噪声、带宽、真实 startup 或校准电路。

误差分开保存，方便定位：

\[
\frac{I_{out}}{100\,\mu A}
=\underbrace{\frac{I_{out}}{I_{ref}}}_{\text{current-mirror ratio}}
 \underbrace{\frac{I_{ref}}{100\,\mu A}}_{\text{reference error}}.
\]

例如旧版最差高电流 deterministic 条件中，Iref=100.71811 µA，mirror ratio=1.0229073，因此 Iout=103.02530 µA。MC 的最坏观察样本 Iref=100.71771 µA，而 mirror ratio=1.0465628，产生 105.40741 µA。此时主要增加的是镜像比误差，不宜把它归咎为 reference 的 5% 漂移。

## 4. 旧 W10/L2：确定性通过，条件式失配暴露缺口

1080 个 deterministic OP = 5 corners × 3 temperatures × 3 logic rails × 3 LED rails × 2 gain signs × 2 TC signs × 2 line signs。全部落在 95–105 µA。Reference headroom 为 1.39300–2.42056 V，全部高于声明的 1 V；示意 dropout 未触发。这是对离散网格的检查，不是连续范围的数学证明。

| 边界 | 条件 | Iref / µA | Iout / µA | 总模拟供电 / mW |
|---|---|---:|---:|---:|
| 最低 | ss、85°C、2.97/4.5 V、gain −0.5%、TC −25、line +3000 | 99.20598 | 99.34163 | 0.74168 |
| 最高 | ff、0°C、3.63/5.5 V、gain +0.5%、TC −25、line +3000 | 100.71811 | 103.02530 | 0.93225 |

上表电源顺序是 Vlogic/VLED。供电功率包含此模拟电路及 reference 行为源从电源吸取的功率，没有数字标准单元宏、pad、封装或光学功率。

| 旧版 MC 人口，每组 n=256 | Iout 均值 / µA | 样本 σ / µA | 观察到的 min–max / µA | ±5% 外个数 |
|---|---:|---:|---:|---:|
| Local only | 101.27397 | 0.79380 | 99.44441–103.32699 | 0/256 |
| Global only | 101.23562 | 0.06550 | 101.08671–101.44007 | 0/256 |
| Global + local | 101.13989 | 0.81774 | 98.84725–103.40141 | 0/256 |
| Nominal bounded reference + global/local | 101.14146 | 0.81787 | 98.84526–103.39962 | 0/256 |
| Low 条件 + local mismatch | 99.37199 | 0.64750 | 97.87852–101.04542 | 0/256 |
| High 条件 + local mismatch | 103.06817 | 0.90409 | 100.98505–105.40741 | **4/256** |

Global-only 电流散布较小，与理想 reference 下共同变化在 1:1 镜像比中较大程度抵消的电路机制相符；不意味着该工艺全局 variation 很小。High 条件超限种子为 `20261022`、`20261141`、`20261148`、`20261257`。4/256=1.5625% 仅是**这个条件下有限模型样本的观察比例**，不是产品缺陷率；0/256 同样不是零风险、100% yield 或六西格玛结论。

### 旧版最低码电荷校验

另外运行注册输出后的真实 RTL duty=1 事件，经 10 ns nominal 输入斜率驱动同一个晶体管/RC/LED 链路。积分窗口为 514.5–1538.5 µs，共 4 个稳态 frame；逐帧积分时对边界作插值。分别用最大步长 50 ns 与 10 ns 检查数值收敛。

| 条件 | 最大步长 50 ns 的最大绝对面积误差 | 最大步长 10 ns | ±2% |
|---|---:|---:|---|
| Nominal bounded reference | 0.2223282% | 0.2223285% | 通过 |
| Low deterministic 条件 | 0.4756392% | 0.4756391% | 通过 |
| High deterministic 条件 | 0.0652441% | 0.0652435% | 通过 |

这里比较的是相对于**同条件 Ifull** 的电荷，绝对电流 ±5% 仍需单独满足。没有把整套 1536 MC 样本都执行 transient；上述三点不代表随机失配下的完整最低码良率。真实 LED 的结电容/光学动态仍未知。

## 5. 尺寸候选与决策门槛

候选只把 MREF/MOUT 从 10/2 改成 20/4 µm，W/L 仍为 5，不增加管数。根据锁定 wrapper，单管 σVth 从 1.99255 mV 降为 0.95068 mV，即旧值的 0.47712 倍。两管的全部 256 对同种子抽样与该比例的最大偏差为 1.31×10⁻¹⁸ V，确认比较的是同一组随机数在新几何下的缩放。更长沟道也改变镜像比随输出电压的行为，不能只用面积平方根关系代替完整电路计算。

面积代价明确：两个镜像管的 W×L 总和从 40 到 160 µm²，为 4 倍；全六管 gate 几何和从 50 到 170 µm²。**这不是整个 layout cell 面积比。** 概念阶段不能确定新的接线和结几何；第 6 节补上实际 layout 面积与最低码动态成本。

为使候选比较可归因，[冻结旧网表](../../scripts/characterization/candidates/pixel_driver_rc_w10_l2.spice)与[概念候选网表](../../scripts/characterization/candidates/pixel_driver_rc_w20_l4.spice)之间只改 X2/X4 的 W/L；AD/AS/PD/PS 与 59 R/43 C 保留旧值。因此候选阶段仅作为 **DC/model MC** 选择依据，不把它命名为新提取版图或用它宣称新动态达标。

候选与旧版使用相同种子、相同 reference 预算和 1080 点网格。先比较 nominal local、global/local 与 bounded reference 人口，再在候选自己的最低/最高 deterministic 条件各跑 256 个 local mismatch 样本。门槛始终为 ±5%；只有改善明确，才进入实际 layout 的 DRC/LVS、重新提取和动态复验。

### 20/4 的实跑结果与选择

| 项目 | 冻结旧 10/2 | 概念候选 20/4 |
|---|---:|---:|
| Nominal、理想 reference 的 DC Iout | 101.23651 µA | 100.69284 µA |
| 1080 点 deterministic Iout 范围 | 99.34163–103.02530 µA | 99.27799–102.07305 µA |
| Nominal local-only σIout | 0.79380 µA | 0.38445 µA |
| Nominal global/local σIout | 0.81774 µA | 0.39710 µA |
| High 条件 + local σIout | 0.90409 µA | 0.43307 µA |
| High 条件 + local 观察到的最高 Iout | 105.40741 µA | 103.21153 µA |
| High 条件 + local 超限个数 | 4/256 | 0/256 |
| 两镜像管 gate 面积合计 | 40 µm² | 160 µm² |

| 20/4 MC 人口，每组 n=256 | Iout 均值 / µA | 样本 σ / µA | 观察到的 min–max / µA | ±5% 外个数 |
|---|---:|---:|---:|---:|
| Local only | 100.71060 | 0.38445 | 99.82358–101.70324 | 0/256 |
| Global + local | 100.64604 | 0.39710 | 99.52857–101.74060 | 0/256 |
| Nominal bounded reference + global/local | 100.64855 | 0.39734 | 99.52753–101.74004 | 0/256 |
| Low 条件 + local mismatch | 99.29269 | 0.31895 | 98.55650–100.11591 | 0/256 |
| High 条件 + local mismatch | 102.09311 | 0.43307 | 101.09400–103.21153 | 0/256 |

20/4 的 deterministic 最低/最高仍是第 4 节列出的条件。最高点 Iref=100.71863 µA、mirror ratio=1.0134476，比旧版的 1.0229073 更接近 1。整个 1080 点网格的 reference headroom 为 1.41231–2.42568 V，仍未进入 dropout。Nominal reference+MC 的变化没有人为放宽 reference 误差界限。

同时，从同一 deterministic 表取 typical、27°C、Vlogic=3.3 V、gain +0.5%、TC +25、line +3000 的 VLED=4.5 与 5.5 V 两端，Iout 增量由 1.32793 µA 降为 0.81123 µA。这支持较长管改善此负载下的电源敏感度；它是**整个支路的有限差分**，不等同于单只 MOS 的小信号 ro。

**这一阶段选择 20/4 进入实际版图验证。** 在相同 reference 预算和随机数下，其失配散布约减半，原高边界观察超限消失，且 deterministic 系统误差也下降。代价为镜像管 gate 面积 4 倍与更大 gate charge；收益足以支撑这一步修改，无需先增加 cascode 或继续放大至 30/6。选择并不构成所有未抽样条件达标的保证。随后按第 6 节核验实际 cell 面积和新提取网络的最低码动态；系统性匹配与实测负载完整验证仍有边界。

候选记录：[summary](../../evidence/characterization/candidate-w20-l4-summary.json)、[独立 CSV 重算检查](../../evidence/characterization/candidate-w20-l4-validation.json)、[1080 点 PVT/reference](../../evidence/characterization/candidate-w20-l4-reference-pvt.csv)、[high MC](../../evidence/characterization/candidate-w20-l4-mc-conditional_high.csv)。Raw directory 为 `build/characterization/candidate-w20-l4-52vez10e`；共 2362 个 OP，其中 1280 MC、1080 PVT、2 个 nominal reference 对照。

## 6. 最终优先证据：实际 W20/L4 layout 与 RC

实际电路和 layout 已改为 20/4，并重新完成提取。输入 RC SHA-256：`1de567fdc5697cd36f5879aa92c24b3b96d0b4f09f33b4a4720afb4aeeecd5b8`；[冻结快照](../../scripts/characterization/candidates/pixel_driver_rc_actual_w20_l4.spice)与它逐字节相同。两个镜像管的 AD/AS 从 4.4 变成 8.8 µm²，PD/PS 从 20.88 变成 40.88 µm；59 个 R 与 43 个 C 也使用重新提取的数值，其中 37 条 R、43 条 C 记录相对概念网表发生变化，已经不再沿用旧结几何/RC。

对应的 [layout summary](../../evidence/layout/summary.json) 记录 Magic `drc(full)`=0、严格 Netgen unique LVS 且无 property errors，GDS roundtrip DRC/LVS 通过，7/7 nets 进入 RC 提取。属性比较仍受已声明的 W/L tolerance 与忽略项限制，见[版图说明](../layout/README.md)；这些本地公开规则结果不是 foundry signoff。

在新 RC 上重新执行相同 1080 点网格及五组 × 256 的 MC，不复用概念候选的电气结果：

| 实际 20/4 MC 人口，每组 n=256 | Iout 均值 / µA | 样本 σ / µA | 观察到的 min–max / µA | ±5% 外个数 |
|---|---:|---:|---:|---:|
| Local only | 100.71316 | 0.38428 | 99.82651–101.70537 | 0/256 |
| Global + local | 100.64862 | 0.39693 | 99.53157–101.74270 | 0/256 |
| Nominal bounded reference + global/local | 100.65111 | 0.39717 | 99.53051–101.74213 | 0/256 |
| Low 条件 + local mismatch | 99.29495 | 0.31883 | 98.55902–100.11788 | 0/256 |
| High 条件 + local mismatch | 102.09570 | 0.43287 | 101.09706–103.21357 | 0/256 |

Nominal 理想 reference 下 DC Iout=100.69540 µA，使用 nominal bounded reference 后为 100.69790 µA。1080 点 deterministic Iout 为 **99.28026–102.07565 µA**，reference headroom 为 1.41211–2.42548 V。最高点仍在 ff、0°C、Vlogic/VLED=3.63/5.5 V，对应 Iref=100.71861 µA、mirror ratio=1.0134736。新的五组 MC 均值比概念候选仅增加 2.26–2.59 nA，失配改善没有被实际提取消除。

### 新增 gate charge 是否破坏最低码

这部分独立重跑了实际 RTL 事件、bounded reference 和新提取网络。保持原积分窗口和 4 个稳态 frame，再次对最大步长 50 ns/10 ns 做收敛检查：

| 条件 | 50 ns 最大步长的最大绝对面积误差 | 10 ns 最大步长 | ±2% |
|---|---:|---:|---|
| Nominal | 0.3139998% | 0.3140000% | 通过 |
| Low deterministic 条件 | 0.7682971% | 0.7682972% | 通过 |
| High deterministic 条件 | 0.1671716% | 0.1671714% | 通过 |

旧 10/2 的最大观察面积误差为 0.47564%，新 20/4 为 **0.76830%**：动态代价确实增加，但在这三条件仍低于预设 2%。步长细化的变化小于 0.0000002 个百分点。这里没有对所有 MC 样本做 transient，也没有把 synthetic LED 电流积分升级为真实光输出。

### 实际占用面积

独立读取前后 GDS top-cell bounding box：[面积记录](../../evidence/characterization/actual-w20-l4-area.json)。旧版为 `95 × 26.66 = 2532.7 µm²`，新版为 `95 × 37.66 = 3577.7 µm²`，增加 **41.26%**。这里是当前模拟 cell 边界面积，未包括数字宏、pad/ESD、芯片级 power mesh、fill 和摆放约束；也不是把两个管子的 gate 面积当成整块芯片面积。

**在本次声明的模型条件下，20/4 达到了保留相同六 MOS 拓扑、减少观察到的电流误差并维持最低码预算的目的。** 采用实际提取结果作为当前设计基准；10/2 与概念候选保持为可追溯的对照。

最终证据：[actual summary](../../evidence/characterization/actual-w20-l4-summary.json)、[1080 点表](../../evidence/characterization/actual-w20-l4-reference-pvt.csv)、[high MC](../../evidence/characterization/actual-w20-l4-mc-conditional_high.csv)、[独立复算](../../evidence/characterization/actual-w20-l4-validation.json)。Raw directory 为 `build/characterization/actual-w20-l4-apab0a2p`，包括冻结的 LED/reference/RTL/testbench/replay 输入；共 2362 个 OP 和 6 次 transient。独立检查使用 Python 标准库重新计算 CSV 的均值、样本 σ、比例、边界，以及分段线性 waveform 积分；13 项均通过。五组人口的全部六只管 `delvto/mulu0` 也与概念候选的同种子值逐项相等，确认没有因提取后实例变化而悄然换掉随机对照。

## 7. 证据、复现与下一步

原始 10/2 输出保持历史证据，不随新设计改写：[summary](../../evidence/characterization/reference-matching-summary.json)、[1080 点 reference/PVT](../../evidence/characterization/reference-pvt.csv)、[最差 high MC](../../evidence/characterization/mc-conditional_high.csv)。其 raw directory 为 `build/characterization/reference-my9116p4`。源文件 hash 记录了实际模型、RC、reference、RTL、testbench 与脚本，原始运行共有 2636 次 ngspice 调用：1536 次 MC、1080 次 PVT、10 次机制/重复性控制、1 次 nominal reference、3 次 LED DC calibration、6 次 transient。

执行脚本是[原始 characterization](../../scripts/characterization/run_reference_matching.py)与[候选对照](../../scripts/characterization/compare_mirror_candidates.py)。原始脚本默认读取当前 `evidence/layout/pixel_driver_rc.spice`：**后续 layout 更新后，直接重跑意味着测试新设计，不能拿它覆盖旧版报告再称为旧版复现。** 若复现历史 10/2，在 Python import 后将 `PIXEL` 指向冻结旧网表、`EVIDENCE` 指向新的输出目录，再调用 `main()`。候选脚本默认读取冻结候选，保护历史 summary 和原始 CSV。

```sh
build/layout/venv/bin/python scripts/characterization/compare_mirror_candidates.py
```

实际提取复验使用[独立 runner](../../scripts/characterization/run_actual_mirror.py)；必须显式给出期望 RC hash，才能开始冻结与模拟：

```sh
build/layout/venv/bin/python scripts/characterization/run_actual_mirror.py \
  --rc-sha256 1de567fdc5697cd36f5879aa92c24b3b96d0b4f09f33b4a4720afb4aeeecd5b8
build/layout/venv/bin/python scripts/characterization/validate_actual_mirror.py
```

新尺寸的实际提取验证已完成。下一步应把 external reference 候选预算落实为可测试的实际电路/器件，补齐真实 LED 的温度与动态数据，继续独立物理检查，并根据这些结果判断是否需要校准或更高 output resistance。原模型没有包含系统性布局梯度；对称性、邻近环境、金属覆盖与机械应力需要单独处理，参考 [GF180 matching guideline §10.6](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_10_6.html)。匹配规则是设计指导，不能替代随机统计或制造验证。

这份证据可支持“单像素该先改善哪一处”的工程决策。4×4 阵列的一致性、共享 reference、通信与供电耦合，仍须在单像素的声明条件闭环之后另行设定。
