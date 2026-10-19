# 参考源、独立保护与驱动架构研究

实验始于2026-10-13，报告更新至2026-10-14。入口：[19页PDF](report.pdf)、[HTML](report.html)、[可编辑研究稿](report.md)、[详细架构教学](architecture-notes.md)。

本次新增晶体管／RTL实验，原v0.4版图和模型保持对照。新模块没有新增layout/DRC/LVS/PEX；没有silicon或光学测量。报告从IREF、电流镜、DC工作点逐步讲到0.1～7 mA、均匀性、PWM、buffer及高速OOK／DAC。

## 本次工程结论

- Beta multiplier可启动，但135个PVT／电阻组合中126个未达±5%。失败保留，不选作精密主参考。
- 外部VSET0.5 V、RSET5 kΩ各±0.1%的**声明边界**下，实际10MOS反馈候选180点参考电流98.942～99.520 µA；这些外部条件不是已选定元件保证值。
- 新10MOS保护gate＋2MOS/100 kΩ LED钳位，在原core场景的fault合同通过，最慢302.223 ns至1 nA以下。恢复寄存器只有RTL证据。
- Servo联测的原正常／故障合同通过；整体`passed=false`，额外全启动branch峰守卫与微小启动电荷收敛未通过。
- 0.1～7 mA目前是几何增益／余量／charge的可行性实验，未完成电流DAC。公开静态LED在7 mA的VF约5.136 V；合成负载下扩大输出但保留原gate驱动，最低码误差约−15.16%。
- 追加同10 ns边沿、相同硬件负载、只禁用clamp控制动作的A/B，禁用2.762 µs、启用203.819 ns；两种步长得到同一判断。

## 数据与原理图

| 入口 | 用途 |
| --- | --- |
| [reference候选索引](../../../evidence/reference/summary.json) | 两套源、startup、外部VSET、端压与结面积敏感性 |
| [reference电路说明](../../../analog/reference/README.md) | 实际网表、物理依赖、损耗、失败及复现 |
| [保护实验](../../../evidence/safety/README.md) | 阈值、逻辑、正常／停钟／恢复、负对照、startup失败 |
| [电流范围](../../../evidence/current-range/summary.json) | 143DC、16PWM、4独立LED校准；理想bias机制对照 |
| [匹配条件clamp A/B](../../../evidence/safety-clamp-ab/summary.json) | 4次匹配10 ns的晶体管控制实验 |
| [来源与独立计算](sources.json) | 原论文、PDK、数据域、条件、图的连接核查 |
| [报告证据清单](evidence-ledger.json) | 本次及既有输入hash、分类与关键数值 |
| [报告验收](validation.json) | 原始数据／计算／链接／19页渲染的独立复核 |

## 复现顺序

需要本项目既有锁定GF180MCU D PDK、ngspice47、Icarus、`uv`环境。所有重跑在独立build目录保留raw与失败；证据审核不把failed实验改成passed。

```sh
uv run python scripts/reference/reproduce.py
uv run python scripts/current_range/run.py
uv run python scripts/current_range/validate.py
uv run python scripts/safety/run.py --suite core --reference-path analog/reference/beta_multiplier.spice --publish-evidence
uv run python scripts/safety/validate.py evidence/safety/summary.json --output evidence/safety/validation.json
uv run python scripts/research/check_clamp_ab.py
```

Servo保护suite保留附加启动失败，按[保护说明](../../../evidence/safety/README.md)执行、审计与导出新raw，不要求它返回全通过。

报告生成需要既有`build/layout/venv`中的markdown/matplotlib，PDF由Playwright＋Chrome输出，Poppler与pypdf验收：

```sh
build/layout/venv/bin/python scripts/research/reference_architecture_figures.py
uv run python scripts/research/highspeed_architecture_figures.py
build/layout/venv/bin/python scripts/research/prepare_safety_report.py
build/layout/venv/bin/python scripts/research/prepare_reference_safety_report.py
build/layout/venv/bin/python scripts/research/render_reference_safety.py
node scripts/research/print_reference_safety.cjs
```

本机bundled Playwright路径由`REPORT_PLAYWRIGHT_MODULE`指定，Chrome由`REPORT_CHROME_PATH`指定。PDF打印脚本先检查所有图加载、水平溢出及单页高度；每次最终PDF还需逐页渲染审阅，再运行`validate_reference_safety_report.py --pdf-pages-reviewed 19`。验证脚本从raw计算并生成evidence-ledger，不需要再次运行EDA。

## 后续进入条件

先闭环reference/fault的启动、真实外部元件、随机失配、补偿、实际layout／PG与LED测量。随后才定义物理4×4或高速单通道。当前新电路没有建立制造接受、全供电、真实LED允许工作区或光学均匀性保证。
