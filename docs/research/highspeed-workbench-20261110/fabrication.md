# 单通道高速发射测试芯片的制造交付路线

本轮把 GF180MCU D 作为可复跑的教学平台，保留 MicroLED 与 VCSEL 接入的两种负载边界。首个测试芯片可用外接发光器件，先完成电气探针测试，再接装配后的光路。驱动芯片是硅 CMOS，发光器件的外延、器件制程与光学装配是独立交付项。当前没有锁定流片服务、封装供应商、裸片尺寸、层选项或样品订单。[GF180MCU 互连与器件选项](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_02.html)

## 按什么顺序做

| 阶段 | 交付物与验收问题 | 本项目证据 |
|---|---|---|
| 1. 接口和负载冻结 | 定义净率、码型、UI、峰值/平均电流、供电和温度，给出发射/接收参考面、BER 条件以及总能量边界。量测芯片接收端共模、差分摆幅、时钟和封装。 | 目前有历史 3.2 Gb/s 净率算例，尚待选实际发光样品与输入 PHY。 |
| 2. 原理图与前仿真 | 冻结晶体管网表、器件模型与角。验证偏置、调制、关断、上电、可靠性、功耗、环路稳定性和码型眼图。数字输入逻辑另做 RTL 功能仿真、约束与时序。 | 有 A/B/C 与 r10 代表帧以及本轮独立前置驱动扫参；需做实际输入接收前端和负载验证。 |
| 3. 单通道版图 | 先放输出开关和最近的 PAD/回流，后放前置驱动与独立参考。按尺寸规划匹配指、guard ring、well taps、地线、旁路与电源岛。用真实接收端/发光端口和 bump 或 bondwire 参考面。 | 旧 A/B 核心有 GDS/DRC/LVS/PEX，现有完整候选要重建。 |
| 4. 寄生与封装联合验证 | 跑 DRC、LVS、PEX、ERC，回灌 PVT、失配、EM/IR、关键体结和端间应力。把 extracted RC 与封装 S 参数接在同一参考面，防止重复计入 PAD 或 bump。重跑终端、眼图、供电扰动、失锁与关断。 | 新全通道布局与接收链尚无此级证据。 |
| 5. 芯片顶层和签核 | 整合 PAD/ESD、seal ring、density/fill、scribe 配置、antenna、latch-up、test access。供电和关断要可测。用服务商认可的 PDK 和 rule deck 重新检查，与芯片顶层 stream-out 一致。 | 尚待代工入口与规则确认。 |
| 6. 提交与样品制造 | 按服务商要求验收顶层、层映射、尺寸、版本、授权、waiver、清单和哈希。确认费用、交期、die 数、已知良品定义、切割、封装与测试边界。 | 当前为交付规划。 |
| 7. 回片、封装及光电台架 | 裸片先测漏电、I–V、静态偏置、端口阻抗和启动保护，再测数据眼图与 BER。量测光器件 L–I–V、S11/S21、温漂，并按同一收光、通道和 RX 边界比较整链。 | 待有样品和台架。 |

[GF180MCU 设计数据清单](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_06.html) · [规则覆盖边界](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_16.html) · [已有完整制造教学章节](../startup-tapeout-20261014/fabrication-chapter.md)

## 到底发给谁什么文件

| 接收方 | 建议在准备区保留的文件 | 确认事项 |
|---|---|---|
| 晶圆厂 / MPW 服务 | `layout/final_top.gds`、`release-manifest.json`、`signoff/`、层映射和顶层边界报告。OASIS 只在对方明确接受时使用。 | 由对方确认 GDSII/OASIS、命名、DBU、顶层、工艺层选项、必要标记、签核 deck、填写表、waiver 和提交机制。另确认哪些报告由对方生成。 |
| 内部 ASIC 复核 | 版本化 schematic、最终网表、extractor 配置、PEX/SPICE/SPEF、数字宏相关 LEF/Liberty、STA 约束、眼图及可靠性报告。 | 若对方或合同要求，再共享必要工程视图。GDS 的 SHA-256 必须与 DRC/LVS/PEX 报告对应。 |
| 切割 / 封装 / 贴装方 | `assembly/die-drawing.pdf`、`pad-map.csv`、`bond-map.pdf`、`pinout.csv`、封装截面与装配材料、裸片坐标和朝向。 | 明确 pad 尺寸、bump pitch、键合线长度、回流位置、die 厚度、公差、保护区、热路径、光轴与耦合公差。 |
| 探针和成测团队 | `test/wafer-test.md`、`test/packaged-test.md`、`test/limits.csv`、安全偏置和供电顺序、图样和板图。 | 预先分配电流监控、PRBS 注入/测试模式、可独立关断、反射去嵌、温度测点与光学对准。 |
| 光器件供应和光学台架 | 发光器件数据手册或自测数据、光耦合夹具图、可测端口与眼图、误码和接收功率口径。 | 对 VCSEL 明确安全上电和电流限制；确认发射波长、耦合、探测器带宽和光功率校准。 |

[现有流片包空模板](../product-framework-20261014/tapeout-package-template.json)。模板保留空的最终芯片、工艺、规则、签核和制造接受字段。二维图与 Blender 模型可做设计评审与教学，制版交付使用经服务方验收的最终 stream-out 文件及检查报告。

## 工具、材料和面积

本地路线可用 ngspice 复跑晶体管网表，用 KLayout 查看 GDS，使用完整 PDK 及对应规则流检查 DRC/LVS/PEX。成熟节点的开源工具适于做可验证的电路/版图实验；生产服务是否接受这些 deck 和报告要逐项确认。光器件有各自的半导体材料体系，GaN 系 MicroLED 与典型 850 nm GaAs 系 VCSEL 均可作为外接器件。硅 CMOS 选型首先取决于 pad/ESD、晶体管耐压、速度、功耗、信号和供电寄生、可制造性以及可测性，器件分别制造时两者不要求同一材料体系。[GF180MCU 工艺选项](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_02.html)

对已完成层次化 GDS，先用最外包围盒计算 `A = (xmax − xmin) × (ymax − ymin)`，保留 DBU 到 µm 的换算。宏 bbox 只反映宏空间。首片面积还取决于 PAD pitch、周边开窗、seal/scribe、去耦和电源网、测试电路、封装、光器件放置及最小 MPW slot。光源模块体积、芯片硅面积和 pad-ring 限制分别计量。对于多通道，实际版图参数还受共用偏置及隔离、供电回路、温升、串扰和耦合装配良率约束，不能按 MOS 数线性估面积。
