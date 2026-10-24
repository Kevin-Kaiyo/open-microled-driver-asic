# 高速 B：真实参考、供电与启动保护

[完整 HTML 研究报告](index.html) / [完整 Markdown](report-complete.md) / [报告输入和图表 SHA-256](report-provenance.json)。

阅读顺序：本轮结论 → 电路与器件连接 → 修改前后波形/数值 → 实际版图 → 复现与未闭合问题。报告的每项通过均限于声明的负载、激励与接收条件；失败、负控制和数值异常保留，不等于产品认证或流片签核。

- [最终电气摘要](../../../evidence/nrz-reference-v2/selected-final-r2-summary-verified.json)
- [更详细的电气实验记录](electrical-notes.md)
- [可复现操作与边界](reproduce.md)
- [独立审计](../../../evidence/reference-v2-audit/review-final.md)
- [GitHub 备份与另一台电脑接续](../../development-handoff.md)

## 报告重建

仓库根目录运行（Python 需要 numpy、matplotlib、markdown；报告字体按 Release 恢复）：

```sh
build/layout/venv/bin/python scripts/reference_v2_report/summarize_nrz.py
build/layout/venv/bin/python scripts/reference_v2_report/build_report.py nrz
build/layout/venv/bin/python scripts/nrz_reference_v2/reproduce.py --help
```

重建报告不等于重跑模拟。原理图 SVG、公开模型、网表和生成脚本保存在仓库；原始日志和波形按带逐文件哈希的 Release 范围恢复。旧 deck 是冻结证据，不能改写其中路径来伪装同一次运行；跨目录入口会生成新 deck 并保留原输入身份。
