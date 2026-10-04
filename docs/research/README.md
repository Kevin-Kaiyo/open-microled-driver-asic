# 当前研究资料入口

更新：2026-10-05，单像素 v0.4。

先读[28页分层研究报告](research-report.md)，按“总览 → 初学者基础 → 工程验证 → 技术、价值与市场”逐步深入。另有便于阅读的 [PDF](research-report.pdf) / [HTML](research-report.html)。入门读者先理解电流、PWM和MOS；工程读者再核查模型、units、测量分母、失败与寄生；方向判断见[技术—价值—市场](technical-value-market.md)。旧教学 PPT 和检阅保留为历史快照。

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
| 技术、价值与市场方向 | [官方benchmark、4×4预算、用户假设、Go／No-go与报价边界](technical-value-market.md) |
| 完整工程路线 | [阶段退出条件](../roadmap.md) |

记录规则：原始生成输出在 `build/`，紧凑结果与输入 hash 在 `evidence/`。同一条实测曲线、固定 corner 网格、随机模型抽样和动态假设各自有条件和分母。平均 branch current 是电气代理量，尚未测量真实光输出。

v0.4联合signal模型整体替换旧buf／analogRC／SPEF／link路径，包含真实输出级结几何并从实际M3右端接入；PG／body电阻和PG-only电容仍投影到理想rails。语义复现依据端口、数值、重数和拓扑，而不是Magic输出的记录排序字节。启动能量属于声明的selected十二MOS模型加外部假设，不能称全芯片PG或系统功耗；所有4×4、成本和市场需求均未实现或未验证。

历史材料：[2026-10-03 检阅](../review/README.md)记录旧10/2µm问题；[教学PPT](../teaching/open-microled-single-pixel-teaching-v2.pptx)用于初始架构；[v0.2报告](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/tree/7ad33e16cfc26a8e785061ef1713156d36d97259/docs/research)保留独立macro；[v0.3报告](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/tree/f4d478707f055cf1015267e14a2a56e28c3e9991/docs/research)保留共同物理top及分块接口。旧manifest锁定当时输入，不能当当前source inventory；v0.4保留所有旧证据，新增联合signal PEX与电气边界研究。
