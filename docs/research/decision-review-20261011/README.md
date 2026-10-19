# 从事实到研究决策 · 2026-10-11

[9页报告](report.md) / [PDF](report.pdf) / [HTML](report.html) / [证据清单](evidence-ledger.json) / [验收记录](validation.json)

本轮跟进研究表述与方向：问题 → 方法与依据 → 条件/数据 → 解释与边界 → 下一实验/决定。保留原稿和工程记录，没有新EDA、电路、模型、RTL、提取或实物测量结果。工程基线为`781ceb266eb1f1dc16780d806cdcd0d5005716ae`。

入门读者看第1–2页；工程读者读第3–6页；研究投入决策读第7–8页；第9页和JSON清单追溯出处。A/B/C都是未执行方案；1 µs fault只是候选设计目标，具体电流、尾电荷与恢复合同需在新run前冻结。

图表来自本库冻结摘要：四个既有DC点、三种假设C的未测域signed charge比值，原样重绘，不产生新仿真结果。静态表数据来自Lin等的CC-BY-4.0公开资料，来源、条件与许可见原source-lock及本报告。导出的PDF对既有tracked来源使用工程基线commit链接；新稿链接保留本地相对路径，不暗示已经发布。

重建仅渲染文档（需已有Markdown/Matplotlib与Playwright/Chrome；不安装依赖、不运行EDA）：

```sh
build/layout/venv/bin/python scripts/research/render_decision_review.py
REPORT_PLAYWRIGHT_MODULE=/Users/kimmy/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright \
REPORT_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
/Users/kimmy/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node scripts/research/print_decision_review.cjs
# 使用带pypdf的既有Python环境；只有实际看完9页后才能填写9
/Users/kimmy/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
scripts/research/validate_decision_review.py --pdf-pages-reviewed 9
```

当前机器路径仅为本地渲染命令示例；其他机器可指定自身的module与Chrome路径。日期化脚本要求原工程HEAD，后续工程输入发生变化应创建新的日期化研究，不覆盖本报告。原摘要/source hash、派生公式、图来源均可检查；PDF需重新逐页检查后更新验收记录。
