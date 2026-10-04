# 单像素 v0.4：实际输出级与共同版图寄生

日期：2026-10-05。本文件在新提取/仿真结果产生前固定目标。保持 v0.3 单像素共同 GDS、数字/模拟宏内部 geometry 和 3.3 V / 5 V 供电边界；不扩展阵列。

## 要解决的证据缺口

v0.3 使用官方六 MOS `buf_2` schematic SPICE 驱动模拟实际 RC，并单独加入跨宏 30 µm Metal3 区间。该标准单元 schematic 未包含其实际 diffusion A/P、单元内部金属 R/C、数字宏输出 routing 和邻近线耦合。v0.4 从冻结共同 GDS 提取实际 `output12/buf_2` 及有关线路，明确每个被截断的边界。

## 预设退出条件

| 检查 | 门槛与解释 |
| --- | --- |
| 输入身份 | 共同 GDS 与 v0.3 SHA一致；不修改宏 GDS/旧证据；保留完整 input/tool/PDK hashes |
| 实际实例 | 从 hierarchy、physical location 与实际 PWM/net12 connectivity 独立证明输出级为 `output12/buf_2`，不能挑选任意同型号cell |
| 器件核查 | 实际六 MOS 模型、W/L、body、diffusion AD/AS/PD/PS、并联/共享扩散解释可复核；严格 LVS检查模型/连接/W/L（原deck忽略A/P，故A/P另核查） |
| 寄生边界 | 优先取得完整共同 GDS RC；若以子电路 cutout/preserved hierarchy 导出，必须列明断开的电源、数字前级、周围输出与远端模拟区域，不能称全芯片 sign-off |
| RC 不重复 | 新模型明确是否含 cell internal RC、digital macro output routing、cross-macro span、analog input内部RC；下游仅各计一次 |
| 耦合处理 | 未仿真的邻近导体必须保留端口或给出明确静止/理想供电边界，记录原始cap并验证归一；不静默将未知node接地 |
| 真实deck角落 | 查询并实测 pinned Magic/PDK extraction styles 与所支持R/C参数；没有公开min/max extraction deck时只称所用deck的nominal parasitic提取，不借用MOS corner名称作为RC corner |
| 独立复算 | pin/body mapping、junction geometry、R/C counts/units、source-to-export graph或严格拓扑对应由独立检查复核；至少一项接错/遗漏负对照被拒绝 |
| 接口交付 | 有可运行的 extracted-stage SPICE、port合同、唯一冻结公共hash/说明；交接口研究用相同刺激比较schematic与actualPEX，电流/最低码/Liberty30–70%边沿门槛由接口研究沿用v0.3预设 |
| 资源 | 不长时间全数字数毫秒wave；原始失败留 `build/joint-pex`，公开紧凑成功证据。留足disk/RAM，仅执行工程上有意义的提取/检查 |

## 不随本轮升级的状态

实际 LED 动态/温漂、reference generator、pad/ESD/package、IR/EM、substrate impedance、制造接受、硅片与光学测量仍未建立。单独 output-stage 电路或部分 joint extraction 通过，不等于完整芯片多角落 PEX transient 或 tape-out readiness。
