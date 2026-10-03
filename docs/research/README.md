# 当前研究资料入口

更新：2026-10-04，单像素 v0.2。

先读[当前研究报告](research-report.md)，按整体架构、器件与负载、计算、版图和数字物理结果逐步理解。另有便于阅读的 [PDF](research-report.pdf) / [HTML](research-report.html)。它是当前设计的入口；旧教学 PPT 和 2026-10-03 检阅保留为历史快照。

| 内容 | 可检查的深入资料 |
| --- | --- |
| 研究指标与范围 | [v0.2 specification](../specifications/single-pixel-v0.2.md) |
| 实测 LED 静态模型 | [来源、拟合、单位计算和边界](measured-led.md) |
| Reference 与镜像管面积选择 | [误差预算、PDK Monte Carlo、实际 PEX 复验](reference-and-matching.md) |
| 模拟 physical implementation | [版图、DRC/LVS、PEX 和 macro views](../layout/README.md) |
| 数字逻辑与映射 | [Registered PWM 与 gate-level regression](../digital/README.md) |
| 数字布局布线与独立 DRC | [Physical implementation](../digital/physical.md) |
| 完整工程路线 | [阶段退出条件](../roadmap.md) |

记录规则：原始生成输出在 `build/`，紧凑结果与输入 hash 在 `evidence/`。同一条实测曲线、固定 corner 网格、随机模型抽样和动态假设各自有条件和分母。平均 branch current 是电气代理量，尚未测量真实光输出。

历史材料：[2026-10-03 检阅](../review/README.md)确认了旧 10/2 µm 基线的物理与计算问题；[教学 PPT](../teaching/open-microled-single-pixel-teaching-v2.pptx)用于最初架构学习。旧 manifest 锁定当时的输入和结论；当前源文件尺寸与 PWM 改动以 v0.2 新证据为准，不能把旧 hash 当作当前源文件的不变量。
