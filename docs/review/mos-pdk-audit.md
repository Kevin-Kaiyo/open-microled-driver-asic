# 单像素 MOS、PDK 与物理实现独立检阅

日期：2026-10-03。审阅起点为 `e26e2f6`；本报告的独立实验使用锁定完整 `gf180mcuD` PDK、ngspice 47，以及该版本的六管 schematic、几何抽取网表和 RC 网表。审阅后根流程已修复下述 LVS 判定缺陷，并重新取得完整版图流程成功证据。脚本和原始结果保留在本仓库，不改变原有 MicroLED 参数。

**判断：当前器件型号、尺寸单位、基本偏置和单像素电流镜方向成立，可以继续研究这个单像素；尚不能把这些结果解释为准确的产品电流、像素间一致性或可流片保证。下一步优先处理真实 LED 数据、非理想 reference、精度/温度/失配指标和验证门槛，再优化版图或扩阵列。**

## 1. 先处理会影响研究判断的问题

### 1.1 已修复：LVS 曾可能把尺寸错误判成通过

审阅时的 `run_layout.py` 仅搜索 `Final result: Circuits match uniquely.`。真实负对照把 MOUT 的 W 从 10 µm 改为 20 µm 后，Netgen 返回 exit 0，并同时输出这句连接匹配结论和 `Property errors were found.`。因此旧 runner 会把“连接匹配但尺寸错误”误报通过。另一负对照把 MOUT gate 接到 bias，得到正确的连接不匹配结果。

根流程现已增加严格报告检查：要求唯一 final result，同时拒绝 property errors，并以这些真实日志验证分类。原始六管的连接和 W/L 本身正确；本问题是自动门禁的漏洞，不是已经发现原始版图画错。证据：[三组 LVS 对照](../../evidence/review/mos-lvs-controls.json)、[修复后分类](../../evidence/review/lvs-guard-checks.json)。

Netgen setup 只比较指定的属性。这里 W/L 采用 1% tolerance，D/S 允许交换，AS/AD/PS/PD、SA/SB/SD、NF 等被删除，故“器件属性匹配”应明确为此 deck 接受的连接、类别与 W/L 等属性，不应理解为所有寄生或版图环境均匹配。见[锁定官方 setup，第 110–145 行](https://github.com/fossi-foundation/open-pdks/blob/54435919abffb937387ec956209f9cf5fd2dfbee/gf180mcu/netgen/gf180mcu_setup.tcl#L110-L145)。

### 1.2 1:1 尺寸不等于 100 µA 精度保证

Nominal full-on 独立 DC 解为：schematic **101.299594 µA**，带实际 diffusion geometry、但无连线 RC 的抽取网表 **101.299594 µA**，完整 extracted RC **101.236512 µA**。它们相对于理想 100 µA reference 本来已有约 +1.24%～+1.30% 偏差。电流镜两侧 VDS 不相同，输出电阻有限；当前结果符合这一结构的物理行为。

因此，已用的“pre/post 差值小于 1%”只约束版图改变多少，不能作为“输出相对于目标电流的精度小于 1%”的检查。若下一步要承诺 ±1%，现有 nominal 数据已经不能满足；应先确定精度预算，再决定加长 L、调比值、使用 cascode/反馈或校准。cascode 又会增加 headroom，不能只按精度选择。

现有 schematic 的 AS/AD/PS/PD 默认 0；真实抽取的 MREF/MOUT 则为 AD=AS=4.4 µm²、PD=PS=20.88 µm。这意味着原 pre/post transient 差值包含 junction geometry 和 wiring RC 两种变化。本次额外的 DC 中间对照证明 nominal DC 差值主要来自 wiring resistance；它没有证明边沿变化也只有这一来源。

### 1.3 理想 reference 和关闭的 mismatch 是关键研究前提

IREF 是理想 100 µA 源，MOS 的 global/statistical mismatch 开关均为 0；两者不会自行展示真实基准精度、随机失配、启动或电源顺序问题。所有像素共用理想值时出现一致电流，也不能证明制造后的 matching。

对现有 10/2 µm NMOS，锁定 wrapper 的局部 Vth 随机项给出单管 σ 约 **1.993 mV**，独立两管差值 σ 约 **2.818 mV**。结合 nominal `gm/ID ≈ 2.66 V⁻¹`，仅做一阶传播会得到约 **0.75% 的电流比 1σ**。这是根据模型公式和工作点计算的量级估计，**没有运行 Monte Carlo，也不是 yield 保证**；尚未计入系统性梯度、版图环境和真实 reference。它已经提示：研究重点不宜只停留在约 0.062% 的 nominal RC 差值。

官方文档将固定 corners 主要定位于逻辑延迟，且明确不能覆盖所有模拟敏感方向；FF/SS 不替代 FS/SF、跨条件组合与 mismatch。[固定 corner 定义](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_2_4.html)、[统计模型入口](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_9.html)。

## 2. 已确认的器件、单位与电压边界

| 项目 | 核查结果 | 实际含义 |
|---|---|---|
| 完整 PDK | Open PDKs `54435919abffb937387ec956209f9cf5fd2dfbee`；9 项锁定文件 SHA-256 全部相符 | 当前使用的 model、Magic/Netgen deck 与锁定记录相符 |
| MOS 名称 | `nfet_06v0` / `pfet_06v0`；旧 subset 为 `nmos_6p0` / `pmos_6p0` | 两套文件版本和别名不能混写，但当前配套调用正确 |
| W/L 单位 | schematic `10u/2u`，Magic PCell `10/2` µm，抽取为 `10u/2u` | 没有发现 10⁶ 倍单位错误；必须使用 drawn W/L |
| 本次尺寸 | MREF/MOUT 10/2 µm；MPASS/MCLAMP/MINV_N 2/1 µm；MINV_P 4/1 µm | 均落在当前 model bin 范围内且长于本家族最短 L |
| NMOS model bin | `nfet_06v0.0`：W 0.3–100.001 µm，L 0.7–50.001 µm | 模型接受范围，不等于整个矩形范围都有独立测量验证 |
| PMOS model bin | `pfet_06v0.0`：W 0.3–100.01 µm，L 0.5–50.01 µm | 6 V PCell/器件最小 L 为 0.55 µm；本次 L=1 µm 不触边界 |
| Body 连接 | NMOS bulk→VSS；PMOS bulk→vlogic；抽取包含相应 ties | 连接正确；RC 下内部 source 与 bulk 不再严格等势 |
| Model 内容 | NMOS BSIM4 v4.5、PMOS v4.6；`igcmod=igbmod=0`、`wpemod=0`（NMOS）、无本项目热/老化模型 | 不可用本仿真直接推断 gate leakage、氧化层寿命或 well-proximity matching |

直接来源是[锁定 primitive model](https://github.com/fossi-foundation/globalfoundries-pdk-libs-gf180mcu_fd_pr/blob/41918f5a2356b9fb49a897ecc4fb4716b0ab1041/models/ngspice/sm141064.ngspice)：`nfet_06v0.0` 第 37534 行附近、`pfet_06v0.0` 第 37949 行附近、mismatch wrappers 第 47125–47210 行附近。安装文件 SHA 在 [PDK lock](../../layout/pdk-lock.json)。关于 drawn dimensions，见[Model Features and Limitations §2.2](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_2_2.html)。

**“6 V MOS”是器件家族名称。** 官方 DRM §14.1 分开讨论供电过冲、drain 的 HCI 条件及 gate-to-any-terminal 氧化层电压，公开文本对 5 V/6 V thick oxide 写有 6.5 V/6 V 的 DC gate-node 限值。不能把 6.6 V 的 Ioff 测试电压、8.5 V 的 BVDSS 最小规范或名字中的 6 V 当作任意端子、任意占空比的长期工作许可。当前 5 V LED rail 与 3.3 V logic 的选择有合理裕量，但 startup/open LED/外部 ESD 仍须另外检查。[DRM §14.1](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html)、[6 V electrical specifications，含测试条件](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_2.html)。

## 3. 独立计算和新增实验

复现入口：`build/layout/venv/bin/python scripts/review/mos_audit.py`。脚本独立计算 diode 的 IS、运行 ngspice OP 和端子差值，不复用 phase1 的平均电流计算函数。输出为 [MOS DC 审阅数据](../../evidence/review/mos-audit.json)、[端子 transient 数据](../../evidence/review/mos-terminal-transients.json)；raw decks/logs 在 `build/audit_mos/`。

### 3.1 Nominal 内部工作点

条件：完整 PDK typical、27 °C、VLED=5 V、vlogic=3.3 V、理想 IREF=100 µA、同一 synthetic LED、PWM 全开。

| 量 | schematic | extracted RC |
|---|---:|---:|
| LED branch current | 101.299594 µA | 101.236512 µA |
| 外部 bias | 1.381714 V | 1.384278 V |
| 外部 gate monitor | 1.381714 V | 1.384147 V |
| 外部 led_k 对 ground | 2.198934 V | 2.198986 V |
| MOUT 内部 VDS（以较低电位端为 NMOS source） | 2.198934 V | **2.195460 V** |
| MOUT 内部 VGS（同上） | 1.381714 V | **1.382167 V** |
| MOUT 模型 VTH | 0.700989 V | 0.701723 V |
| MOUT 模型 VDSAT | 0.489479 V | 0.489420 V |

抽取文件的 D/S 与 schematic 允许交换，ngspice `@m...vgs/vds/vbs` 会按**实例端子顺序**报告负值；不能把负的原始 `vgs` 当成 NMOS 关断。本表根据实际 terminal 节点重新确定 electrical source。输出器件正常处于较充分的 saturation；`led_k` 对 global ground 也确实不能直接代替内部 VDS。

静态关闭 PWM 后 reference 仍消耗约 100 µA 的 logic rail 电流，即 **0.33 mW**。全开时两电源总输出约 **0.83618 mW**。这些数值尚未包含数字逻辑、现实 reference 电路及封装；PWM 电流亮度调低不会让整个系统功耗严格按 duty 同比例缩放。

### 3.2 DC 条件矩阵：270 点

组合为 5 个固定 corners（typical/ff/ss/fs/sf）× 3 个温度（−40/27/125 °C）× 3 个 logic rails（2.97/3.3/3.63 V）× 3 个 LED rails（4.5/5/5.5 V）× PWM on/off。另有 6 个 nominal 网表对照与 12 个 compliance 点，共 **288 个独立 OP 解**。

| 检查量 | 本次模型结果 | 解释边界 |
|---|---:|---|
| full-on 最小电流 | 100.078794 µA | SS、125 °C、logic 2.97 V、LED rail 4.5 V |
| full-on 最大电流 | 102.385418 µA | FF、−40 °C、logic 3.63 V、LED rail 5.5 V |
| bias 范围 | 1.197416–1.593896 V | 支持当前 gate-pass 驱动在这一 DC 矩阵内工作 |
| 任一器件任意两端最大差值 | 4.367611 V | SS、125 °C、logic 3.63 V、LED rail 5.5 V、off；低于 6 V |
| 最大 off branch current | 199.895 pA | FF、125 °C；包括模型/默认 gmin，不是实测 leakage 指标 |

−40～125 °C 来自工艺文档的常用设计范围；低于 0 °C 的 HCI 提醒仍适用。本矩阵扩大了检查覆盖，但 diode 的温度行为还是未测量假设、reference 还是理想值，不能命名为产品 PVT qualification。输出范围相对 reference 为约 +0.079%～+2.385%，也再次说明当前证据不支持 ±1% 精度。

### 3.3 MOS-only compliance：把负载假设暂时移出计算

直接用 DC 电压源固定外部 `led_k`，保留理想 reference 和完整 RC，测得：

| 外部 led_k | 输出电流 |
|---:|---:|
| 0.3 V | 77.6513 µA |
| 0.5 V | 94.6167 µA |
| 0.6 V | 96.6768 µA |
| 0.7 V | 97.6234 µA |
| 0.8 V | 98.2128 µA |
| 1.0 V | 98.9934 µA |
| 1.4 V | 99.9794 µA |
| 2.2 V | 101.2378 µA |
| 3.0 V | 102.1672 µA |

**VDS 超过约 0.49 V 的模型 VDSAT，并不等于电流已进入 ±2% 的准确范围。** 在当前 nominal 离散点中，0.8 V 才达到至少 98 µA，而更高 VDS 又使电流上升。这是为实际 LED Vf/rail 选择电压预算时应使用的证据；跨 PVT 的精确最低 compliance 尚需按最终允许误差搜索。

### 3.4 三个代表条件的 transient terminal stress

另外在 nominal、DC 最大端子电压条件和最大 on-current 条件下，使用 10 ns PWM 边沿、64 µs 高脉冲、最大步长 2 ns，直接记录六 MOS 全部 36 个端子对的最大/最小值。任一两端最大绝对差分别 **3.57399、4.36768、3.79879 V**，未在这三次波形中出现 6 V 过压。它们由正常 DC 工作点启动；尚未覆盖电源爬升/掉电顺序、开路 LED、外部 ESD、封装寄生或全部角落的瞬态。

## 4. DRC、PEX 和 matching 能证明到哪里

已存档的 Magic `drc(full)` 错误数 0、Netgen LVS、GDS 回读一致和 7/7 net RC 抽取具有相应的真实报告；本次没有发现伪造输出或单位异常。`full` 是 Magic style 名字。GF 官方还单列了未编码规则，包括 matched-pair 和部分可靠性准则，因此零 DRC 不覆盖它们。[官方未编码规则列表](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_16.html)。

当前 `extract do resistance` 用法与 Magic 8.3.684 相符；官方说明从 8.3.597 起可在常规抽取时顺序执行电阻抽取，无须再调用独立 `extresist`。目前 thresholds 全设为 0，报告 7/7 nets，网表确有 59 R 和 43 C。它是公开名义 RC 提取，尚无 RC corners、独立抽取器相关性或测量校准。[Magic extresist 官方说明](https://opencircuitdesign.com/magic/commandref/extresist.html)。

实际 cell bounding box 为 95.00 × 26.66 µm，即 **2532.7 µm²**，不包含完整 chip/pads。MREF/MOUT 同尺寸同方向、相邻中心距 15 µm，有 ties/guard rings；当前实现没有 common-centroid、dummy device 或系统性 mismatch 量化。官方 matching 指南把环境、方向、金属长度、邻居偏置、应力和随机失配分开讨论；尺寸相等和 DRC/LVS 成功均不能替代 matching 指标。[官方 matched-pair 指南](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_10_6.html)。

下一步保持单像素范围，按顺序建立四道门槛：

1. 选定可追溯 LED/发光面积与电流密度，获得 I–V、C–V/动态和温度证据，先写允许电流误差、功耗与最短 pulse 的指标。
2. 将理想 reference 换成明确的实现/误差模型，纳入 accuracy、drift、compliance、启动和电源顺序；据此决定 simple mirror 是否仍合适。
3. 在同一 PDK 下完成模型受支持的 mismatch 与相关性检查、跨 PVT 的 compliance/short-pulse 检查，把平均值、峰值、off leakage、功耗分别验收。
4. 再做 matching/routing 优化，并补独立物理规则和系统集成的检查。只有单像素达到已经声明的电气指标，才把相同规则扩到 4×4。

以上检查支持当前研究路径的“可以继续”，不支持“所有物理前提已经由真实器件测量确认”。把未确认前提变成可测量的下一步，才是减少扩阵列返工的关键。
