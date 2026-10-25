# 阶段复盘：显示PWM与高速光通信

日期：2026-10-25。入口：[HTML](index.html) / [完整Markdown](report-complete.md)。

这是对现有电路、RTL、实际版图/PEX和公开原始资料的复核；本轮没有新增电路、SPICE、物理实现或光学测量。报告回答性能、器件材料、阵列、QSPI、成本、量产边界和下一路线选择。

- 显示约100 µA幅值；1 MHz时隙/3.90625 kHz PWM；0.1–7 mA可编程幅值及Fmax未完成。
- 高速B最新固定0.5 Gb/s；完整端口正向能量名义2.688 pJ/gross bit，外部基准IC/Rx等仍有预算边界。A/B/C成熟度分开，不把历史名义最快点升级为当前规格。
- 共享参考与16路带宽/能耗仅为明示假设的算术场景；源证据、失败和未知都保留。

在原项目Python环境中重建与验证：

```sh
build/layout/venv/bin/python -B scripts/architecture_review_20261025.py
build/layout/venv/bin/python -B scripts/architecture_review_20261025_validate.py
```

Python依赖为Markdown和Matplotlib；`report.md`是含数据表占位符的文字源，`report-complete.md`是填入审查表的完整输出。脚本不调用ngspice或物理工具。既有原始波形、完整PDK和工具另按[交接说明](../../development-handoff.md)准备；本轮新报告/图/计算和公开来源台账均是小文件，随Git保存。

外部论文原始PDF和图页仅留本机私人研究目录`build/architecture-review-20261025/private-evidence/`及之前的来源目录，不随公共Git重分发。公共报告使用本项目原创图、事实转述、条件和原文链接。当前企业声明、测量、设计估算及本项目仿真分别标识。

独立复盘已重积分既有A/B六个原始波形，不是新增SPICE。报告验证器会核对已恢复的build来源；未恢复的来源会明确列为未检查。复现原波形复核需先按对应旧阶段Release恢复，普通Git克隆只包含公开小证据与报告。
