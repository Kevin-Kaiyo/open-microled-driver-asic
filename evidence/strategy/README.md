# 历史来源记录与独立预算

本目录的JSON／CSV为2026-10-05运行与审查快照。2026-10-06起，项目定位统一为**实验性研发方法验证与教学**，当前说明见[实验方法与研究价值](../../docs/research/technical-value-market.md)。

- `sources.json`与`claim-ledger.json`保存历史阅读范围、出处、条件和当时的claim分类，仅供追溯原审查输入。
- `validation.json`记录当时57项检查及原始artifact hashes；文档后续修订不改写该历史结果。
- `budget.json`／`budget.csv`为面积、reference功耗、storage与bandwidth的独立预算；array项全部是未实现场景。
- 原始电路、科学数据与模型notice保留各自出处和许可。历史来源清单不定义当前研究目标。

预算复算入口：`.venv/bin/python scripts/strategy/budget.py`。该脚本只重新计算声明条件下的场景，不执行新电路或实物实验。

文档修订的历史／当前身份映射见[修订记录](../methodology/document-revisions.json)；旧文档可从记录中的Git commit追溯，当前文件由新的artifact索引核查。
