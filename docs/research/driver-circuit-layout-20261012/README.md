# 晶体管 电路与互连研究

2026-10-12。先读[14页报告](report.pdf)或[可编辑正文](report.md)，再按[来源索引](index.html)阅读公开论文。8篇研究论文与7条官方/数据来源按设计问题选择，不是穷尽文献综述。

本轮为文献/既有证据复核、器件原理图和独立教学计算，无新增EDA、silicon或optical结果。下一步设计保留单pixel，先完成reference、safe-off与PG边界，再比较单位管匹配布局及独立current-steering路径。现有signal PEX不能解释为完整PG。

计算输入见[calculations.json](calculations.json)，来源条件见[sources.json](sources.json)，本地输入hash见[provenance.json](provenance.json)，核查结果见validation.json。全部示意与计算图原创；未复制论文图或源PDF。

复现HTML、图与数据：`build/layout/venv/bin/python scripts/research/render_driver_circuit_layout.py`。打印PDF使用`scripts/research/print_driver_circuit_layout.cjs`，需指定Playwright module与Chrome path。后续修改正文/输入，应重跑渲染、数值核查和逐页视觉检查。

博客公开入口：[MicroLED驱动器的晶体管 电路与布线设计](https://kaiyo-blog.pages.dev/zh/blog/microled-driver-transistor-circuit-layout/)。部署确认以publication.json为准。
