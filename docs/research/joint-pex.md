# 单像素 v0.4：从共同版图到可检阅的联合寄生模型

2026-10-05。先读[本轮预设目标](../specifications/joint-pex-v0.4.md)，再查看[公开模型索引](../../evidence/joint-pex/summary.json)。结果对应现有单像素，不扩展 4×4。

## 这一步为什么必要

v0.3 已有共同版图、实际跨宏连线和六 MOS 缓冲器 schematic 仿真。但 schematic 只描述晶体管与连接，未描述输出单元实际扩散区、其内部线、电源接触、数字宏输出走线和附近导体的寄生。v0.4 从同一份冻结 GDS 重新读取几何，再提取 R/C；新的电气小模型包含实际输出级六 MOS 和模拟像素六 MOS。

容易理解的顺序是：前级逻辑产生电平 → `output12/buf_2` 放大驱动能力 → 数字宏内线 → 跨宏线 → 模拟输入 inverter/clamp → 电流镜 → LED cathode。电阻描述电荷在导体中移动的阻碍；电容描述导体及 MOS junction 储存的电荷。电气亮度仍用平均 branch current 表示，不是光学测量。

## 实际输出级与几何

输出级确定为数字 `output12`，型号 `gf180mcu_fd_sc_mcu7t5v0__buf_2`。共同坐标中 R180 origin 为 `(162.32,111.24) µm`，bbox 为 `(157.84,107.32)…(162.32,111.24) µm`。这由实际 instance transform、DEF/LEF 与六 MOS gate 区域共同对应，不能以任意同型号 cell 代替。

每个 NMOS 为 W/L=`0.82/0.60 µm`，每个 PMOS 为 `1.22/0.50 µm`，共三个 NMOS、三个 PMOS。输入 inverter 驱动第二级，两组输出 MOS 并联增加驱动能力。六 MOS 的 drain/source 对调在电路拓扑中可以等价，但 AD/AS 必须跟着对应的实际扩散端走，不能只比总数。独立检查使用 `.ext` 的 geometry 与原始 flat SPICE，逐一核查 gate、body、W/L、AD/AS/PD/PS。

| 实际扩散分配 | NMOS | PMOS |
| --- | --- | --- |
| 面积取值，µm² | 0.2132 / 0.2911 / 0.3608 | 0.3782 / 0.4941 / 0.5368 |
| 周长取值，µm | 1.34 / 1.53 / 2.52 | 1.84 / 2.03 / 3.32 |

这些是 PDK extractor 对共享扩散区分配到各 device terminal 的数值，不应相加后当成彼此独立的新增 layout 面积。Magic 内部坐标单位为 `0.005 µm`，面积乘 `0.005²`，周长乘 `0.005`；SPICE 中 `p` 在面积参数里是 `10^-12 m²`，`u` 在长度参数里是 `10^-6 m`。

MOS junction 电容由实际 AD/AS/PD/PS 交给 device model 计算，没有再手工加一份 junction C。实际 pinned extraction deck 在 capacitance 段禁用 active area/perimeter-to-substrate 提取，并将 MOS channel 从这些 substrate 寄生类别排除；金属到 gate/poly/diffusion 的互电容仍属于布局寄生。这个区别避免把 model junction/channel 与显式导体 C 混成两份相同的电荷。

## 新模型的边界

冻结模型为 `output_pixel_pex`。`I` 位于实际 buffer 输入 pin `(161.48,109.84)`；`PWM_DRIVE` 位于 Z pin `(159.24,108.72)`；`PWM` 位于模拟宏右边的真实连接位置 `(119.99,111.52)`；`PWM_MON` 是跨宏观察点。模拟宏原来的 standalone PWM formal pin 位于左侧 x=25，不能直接复用为本次右侧接入位置。

模型有 12 MOS、45 signal R、77 聚合后的显式 C，以及 34 个显式邻居端口。它同时包含缓冲器 signal metal/diffusion R、数字输出走线、跨宏段及模拟 signal 内部 R/C。**使用时只实例化这一份联合模型，不再叠加旧 buffer schematic、数字 SPEF、旧 link RC 或旧 analog RC。** 否则会重复计算同一段电荷或路径。

VDD/VSS 为理想边界；所有 source/body/PG 电阻投影到这些固定电位，PG-only 固定电位电容也省略。signal↔PG 电容保留。因此此模型并没有验证电源压降、well/substrate impedance 或芯片 IR/EM。原始完整 hierarchy 和 nominal flat R/C 保留在[压缩原始包](../../evidence/joint-pex/raw)，其中包含实际 source/body/PG 电阻，可以继续研究更完整的电源边界。

34 个邻居均有实际 hierarchy 身份：部分是 duty/enable 输入，更多是邻近 `fillcap` 的内部浮动导体及前级 FF/逻辑内部 node。主比较中的全零理想 clamp 是**明确的截断条件**，不代表实际内部逻辑状态，也不证明浮动节点行为。固定 0 V 与固定 VDD 的线性电容稳态等价，不能凭两者结果接近就排除浮动/活动邻居风险。邻居驱动器及其分布阻抗未进入主模型；后续敏感性探针必须单独说明输入源和假设。

## 负电容怎样处理

实际 hierarchical raw 有 661 条负 C，其中包含重叠修正；不能把它作为可直接使用的全芯片 transient 网表，也不能逐条把负值裁成零。随后实际执行 flat 提取，避开层次重复；nominal raw 有 5,644 MOS、18,451 R、36,028 C，仍有 19 条很小的负 C。

逐个追踪端点表明，这 19 条均位于固定 PG-only 边界。导出时先按实际 raw-R component 和 `.res.ext killnode/rnode` 归一，再对相同端点 C 做**代数求和**；每条原始 R/C 的保留、重映射或省略都有 [ledger](../../evidence/joint-pex/nominal/projection-ledger.json.gz)。19 条 signed 值随 PG-only 固定电位项一起省略，未作 clipping。最终 dynamic 网络没有负 C；每条 R>0、C≥0，因此每个电容的二次型为 `C×(Va−Vb)²≥0`，总 C matrix 为 positive semidefinite。独立复算核查原始值、重数、端点和导出的严格 multiset，而不是以仿真收敛代替物理判断。

## 真实 R/C 工艺条件

使用 pinned `gf180mcuD.tech` 声明的 `ngspice()`、`ngspice(hrhc)`、`ngspice(lrhc)`、`ngspice(hrlc)`、`ngspice(lrlc)`，五种实际 native Magic 8.3.684 提取均成功，`drc(full)=0`。这是 extraction R/C 条件；MOS TT/SS/FF 是另一组模型条件，两者不能互换。

| RC 条件 | Z pin→真实模拟接入点等效 R，Ω | 联合模型全部显式 C，fF | PWM component incident C，fF |
| --- | ---: | ---: | ---: |
| nominal | 17.394804 | 86.12439 | 22.84770 |
| HRHC | 39.700423 | 98.58589 | 28.45917 |
| LRHC | 7.089146 | 98.55779 | 26.77575 |
| HRLC | 39.700423 | 81.11626 | 21.72851 |
| LRLC | 7.089146 | 81.09498 | 20.47381 |

R 用独立 1 A nodal solve 求解整个导出 signal 图，包含完整路径，不能与旧 30 µm link 的 4.81871 Ω 再相加。显式 C 总量不含 MOS model intrinsic/junction C；它也不是全部压在 PWM 上的等效输入电容。不同 RC 条件的相同电容类别仍可能因 RC 分布和端点重分配有小幅差异。

例如 nominal M1–M4 为 90 mΩ/square、M5 为 40；HR 为 104/49，LR 为 76/31。但 contact 和 diffusion/poly 也变化：nominal poly contact 8 Ω、via contact 4.5 Ω，HR contact 15 Ω，LR contact=0；因此整条路径的变化不只是金属 sheet resistance 的百分比。[实际 extraction 方法与系数](../../evidence/joint-pex/extraction-method.json)记录源文件 hash、行定位和各次命令/日志。此处只确认 pinned open deck 的支持情况，不升级为制造方 signoff RC corner。

## 可复现与判定

入口是[重现说明](../../evidence/joint-pex/README.md)。先验证冻结共同 GDS 和全部 708 个 physical PDK inputs，再真实提取，最后按原始拓扑导出。public model 的 SHA 是下游唯一输入；as-run 文件名/hash 与 public gzip/hash 有单独映射。

独立 review 已核查 nominal MOS、ordered ports、45R/77C multiset、junction A/P、passivity、PWM R/C。复制实际模型后交换端口顺序、删除最大 dynamic C、加倍 buffer NMOS W 均被严格拒绝。[独立结果](../../evidence/research/v04-review.json)及[接口电气预设目标](../specifications/electrical-v0.4.md)给出各自证明范围；电气 transient 成功不改变理想 PG / 邻居截断的前提。

目前适合继续研究单像素电源、真实邻居网络、reference 与实测 LED 模型。4×4 阵列、通信和扫描架构应在这些假设被逐步闭合后再设计；这不是已经完成 full-chip PEX transient、substrate、IR/EM、pads/ESD、制造接受或硅片/光学验证。
