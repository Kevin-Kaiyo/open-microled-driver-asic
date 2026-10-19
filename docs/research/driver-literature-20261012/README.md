# MicroLED driver材料、工艺与论文研究 · 2026-10-12

[10页报告](report.md) / [PDF](report.pdf) / [HTML](report.html) / [可搜索索引](index.html) / [文字索引](papers-index.md) / [结构化来源](sources.json) / [provenance](provenance.json) / [验收](validation.json)

回答MicroLED驱动MOS材料与主流技术、显示与高速通信driver的差别，并为逐篇学习建立可检索资料。按问题选取21篇研究论文，13篇已核查关键全文段、8篇仅核查摘要；另有1篇综述与官方来源，共35条。不意味着用户已读完，也不意味着全面系统综述、市场调查或跨论文排名。

材料（Si、GaN、oxide等）、器件（MOS、TFT、HBT/HEMT）、工艺（CMOS、BCD、SOI）、架构（mirror/PWM/current-steering）和异质集成分别说明。µPLS/EVIYOS只回应本轮公开材料身份疑问，保留未公开的工艺信息，项目仍定位实验性研发方法验证，不复制商业协议和内部设计。

报告按入门 → 器件/工艺 → 原型与数据 → 研究决策展开；索引每条记录原定位、访问核查、条件/分母、支持/不支持、资料版本疑点。关键全文与摘要分级，实测、post-layout仿真、设计目标、厂商声明和计算互不替代。旧工程证据与报告保留，本轮无EDA/model/RTL变更。

数据摘录保留事实、单位和条件；未复制源PDF或论文图。作者稿入口是否可匿名获取取决于当前站点状态，记录过获取失败的条目未升级为全文核查。来源版权仍由原网站说明，未来复用图表需另核查许可。

可搜索HTML为离线文件，不发送输入到外部服务；关键词、技术组、来源类别和全文核查状态可组合筛选。JSON用于后续追加条目/检索；新来源先校验doi/title/年份和关键实验配置，不能只摘取摘要最大数值。

既有环境中的重建入口（只生成文档，无EDA）：

```sh
build/layout/venv/bin/python scripts/research/render_driver_literature.py
REPORT_PLAYWRIGHT_MODULE=/Users/kimmy/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright \
REPORT_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
/Users/kimmy/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node scripts/research/print_driver_literature.cjs
```

初次render由build中的分工metadata冻结为sources.json；后续机器没有该build输入时，脚本自动读取冻结sources.json。新研究另建判断日期。现有provenance保存输入hash，HTML/PDF更新后必须重新检索验收、逐页检查，再更新validation.json。
