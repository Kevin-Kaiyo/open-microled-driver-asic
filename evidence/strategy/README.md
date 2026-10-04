# 技术价值与方向证据

日期：2026-10-05。当前结论见 [technical-value-market.md](../../docs/research/technical-value-market.md)。

- `sources.json`：12条公开第一手来源，记录版本、访问状态、locator、条件和图片reuse边界。
- `claim-ledger.json`：18条claim，分开厂商规格、论文摘要实验、项目原始证据、独立计算和方向假设。
- `budget.json` / `budget.csv`：area/reference-power/storage/bandwidth场景，全部array结果均未实现；输入hash来自冻结v0.3证据。
- `validation.json`：独立Fraction复算及source/claim关联检查。

复算入口：`.venv/bin/python scripts/strategy/budget.py`。无需新模型或商业工具，不修改任何已完成电气结果。

没有客户访谈、订单、报价、收入或市场增长预测。没有商业产品图片/PDF页面重发布；必要事实与出处邻近引用。JBD直接page访问403，保留官方公开索引中的company claim及此限制；VLC只使用可读摘要，不补造bias/BER/距离条件。

Google原PDK仓库archived/alpha的current状态不否定锁定模型计算，也不建立provider接受资格。Tiny Tapeout SKY130 analog限制或价格不能转用GF180工程。公开route只能作为下一阶段匹配入口。
