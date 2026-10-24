## 如何复核与继续开发

原始数据位于 `build/pwm-reference-v2/20261024/`，公开紧凑证据位于 `evidence/pwm-reference-v2/20261024/`。每个 case 保留实际网表、求解器日志、压缩全波形、执行脚本和不可变输入清单；报告 CSV 是用于阅读的采样，不代替完整波形的峰值或电荷计算。

| 内容 | 入口 | 作用 |
|---|---|---|
| 最终元件与连接 | [final-network.json](../../../analog/pwm_reference_v2/final-network.json) | PCB、封装、实际 PEX 与外部控制边界 |
| 仿真和分析实现 | `scripts/pwm_reference_v2/{run,loop,validate,report}.py` | 同条件实验、数值网格及指标定义 |
| 实际参考源原理连接 | `analog/reference/vset_servo.spice` | 参考电压、误差放大与电流镜 |
| 原实际版图 | [r5 版图与验证](../single-pixel-closure-20261015/README.md) | 39 MOS 宏的历史物理范围；本轮没有改动芯片图形 |
| 旧输入身份问题 | [恢复审计](../../../evidence/pwm-reference-v2/20261024/manifest-recovery-audit.json) | 早期清单关联异常单独保留，不混入最终验收 |
| 独立最终审查 | [审查记录](../../../evidence/reference-v2-audit/review-final.md) | 输入、图文及电气结果核对 |

恢复新阶段 Release 的输入与指定 case 后，用 `scripts/pwm_reference_v2/reproduce.py --case CASE_ID --source build/pwm-reference-v2/20261024 --destination build/pwm-reference-v2/my-reproduction-check` 复跑。`CASE_ID` 应选本报告最终清单里的 DC 或瞬态点；脚本拒绝覆盖目录、核对执行源与清单，必要时重编译 RTL，然后按新根目录迁移 `.include` 路径。它不依赖旧机器的绝对路径。

早期可变输入清单曾造成两项执行源关联异常：`startup_diagnostic_strict_r10_gear1_fullmesh` 和 `pcb150_board100n_ac`。原 deck/log/raw 并未丢失，但这两项不作为最终被接受的证据；后续清单按内容哈希不可变保存。复现脚本会拒绝不匹配的 case，而不是自动修饰来源。备份与恢复范围见[跨机交接说明](../../development-handoff.md)。

### 下一步应解决什么

本轮受控启动依赖外部 FAULT/PERMIT 时序和有限 GPIO 输出阻抗。下一步应把参考就绪检测、欠压锁定与故障释放做成可验证的实际电路，并覆盖控制电源缺失的顺序；同时对外部 0.5 V 基准补真实启动、噪声和输出阻抗。

外部补偿电容需要 N2 引脚，其 pad/ESD 电容、封装互感及板级回流尚未由实物提取。已有 1 Ω / 5 nH 是应力假设，不能自动作为产品封装。建议先用板级电路和可测 LED 负载验证这些边界，再决定将补偿电容和基准集成到芯片，随后才扩展阵列规模。
