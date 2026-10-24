## 如何复核与接续开发

本报告对应新目录，不覆盖旧阶段。阅读入口分三层：先看本页的电路与决策，再看表格及图旁的 JSON/CSV，最后恢复原始网表、求解器日志与全端子波形。Markdown、SVG、网表和 Python 脚本均开放；原始失败同样保存。

| 内容 | 入口 | 能证明什么 |
|---|---|---|
| 12 MOS 参考与保护的源连接 | `analog/nrz_reference_v2/vi_reference_switched_keeper.spice` | 每只 D/G/S/B、型号与 W/L |
| 实际 21 MOS 顶层 | [物理摘要](../../../evidence/reference-v2-layout/nrz-switched-keeper-summary.json) | 生成 GDS、DRC/LVS、提取身份及负控 |
| 电气矩阵与冻结范围 | [最终范围声明](../../../evidence/nrz-reference-v2/final-scope-amendment.json) | 条件、判据、负载及未覆盖项 |
| 条件 keeper 与精密 RSET 修订 | [修订声明](../../../evidence/nrz-reference-v2/final-scope-amendment-conditional-keeper.json) | 为什么改变电路与 BOM，保留原失败 |
| 独立复核 | [最终审查记录](../../../evidence/reference-v2-audit/review-final.md) | 来源身份、数值复算及发现的问题 |
| 原始仿真 | `build/nrz-reference-v2/selected-final-r2/` | 实际执行的 deck、输入、日志、全波形与分析 |
| 布局重建与跨目录依赖 | [物理恢复说明](../../../evidence/reference-v2-layout/RESTORE.md) | PDK、Magic、Netgen、KLayout、Lima 及最小流程 |

恢复 Release 中的新阶段输入后，可在同一仓库的新空目录复跑一个 DC 点，不复制旧求解结果：

```sh
build/layout/venv/bin/python scripts/nrz_reference_v2/reproduce.py \
  --source-work build/nrz-reference-v2/selected-final-r2 \
  --out build/nrz-reference-v2/my-reproduction-check --smoke-dc
```

脚本拒绝覆盖已有目录，核对冻结输入与实际运行源，再调用 ngspice。当前已做过同机不同目录的最小 DC 重跑；它不等于另一操作系统安装成功，也不等于重跑全部 138 个电气案例与 7 个 AC 条件。具体备份范围与恢复回执见[跨机交接说明](../../development-handoff.md)。

### 下一步怎样选实验

第一步应做真实的 reference-ready / undervoltage 监督和 fail-safe 启动互锁，覆盖 anchor 不到、掉电顺序、DISABLE 驱动丢失，并保持现有过压失败作为负控制。第二步把外部基准的实际启动、噪声和 Iq 加入模型，补分压器误差与 RSET 的最坏联合角、局部失配及更长码序列。第三步才适合研究多通道供电共享或更高数据速率。

高速补偿引脚、板级供电阻抗与真实封装还需测量或场解；当前缺少 pad/ESD、EM/IR、三维衬底及热验证。A 电压驱动路线在本轮未改动、未重新扫描，不能用 B 的新完整能耗与 A 的旧理想供电数据宣布最终技术路线胜负。
