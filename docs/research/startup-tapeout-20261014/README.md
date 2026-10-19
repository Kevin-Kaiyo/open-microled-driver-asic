# 单像素启动修复与ASIC流片路线 · 2026-10-14

这一轮继续完善参考电流源和独立保护，并补充设计、版图与流片教学。旧19页研究报告及旧失败证据保留；新增模块没有新版layout/DRC/LVS/PEX，也没有制造接受、silicon或光学测量。

入口：[PDF](report.pdf)、[HTML](report.html)、[可编辑研究报告](report.md)、[完整制造教学](fabrication-chapter.md)。

## 证据入口

- [制造主来源与计算](fabrication-sources.json)：工艺材料、金属层、PDK版本、交付与回片测试。
- [旧版GDS面积重新读取](area-baseline.json)：三个宏／共同顶层外框，与最终die区分。
- [独立数值／端压／RTL审计](../../../evidence/startup-v2/peer-audit.json)：可重跑脚本检查来源、计算和失败分类，不升级制造或光学证据。
- [新启动实验](../../../evidence/startup-v2/summary.json)：失败对照、候选修改、正常／fault／恢复和数值守卫分别报告。
- [报告证据清单](evidence-ledger.json)与[报告验收](validation.json)：输入／输出hash、计算、链接和逐页视觉审阅。
- [原参考／保护报告](../reference-safety-20261013/README.md)：IREF→电流镜→DC、0.1–7mA、PWM、均匀性与高速通信架构。

## 工作边界

本轮启动以有效logic／LED电源和外部fault为前提，只让reference rail单独启动。没有把它写成片上POR或全供电启动保证。电流来自电气仿真；极小方向电荷的严格相对收敛结果与峰值守卫分开保留。

材料／制造章节以公开官方文档与本地锁定文件为据。金属五层不是所有工艺层数；厂商接受版本、rule deck、slot、pad／ESD、封装与测试需具体确认，当前没有对外提交或采购。

## 报告复现

完成新启动实验后，按其目录说明重跑／审计。报告生成采用既有Markdown／matplotlib环境、Playwright＋Chrome及Poppler：

```sh
build/layout/venv/bin/python scripts/research/startup_tapeout_figures.py
build/layout/venv/bin/python scripts/research/prepare_startup_tapeout_report.py
build/layout/venv/bin/python scripts/research/render_startup_tapeout.py
node scripts/research/print_startup_tapeout.cjs
```

本机Playwright模块由REPORT_PLAYWRIGHT_MODULE指定，Chrome由REPORT_CHROME_PATH指定。最终PDF需逐页渲染、检查，再运行validate_startup_tapeout_report.py。验收脚本验证数据与报告一致，不将实验失败改为通过。
