# 2026-10-08 研究说明与事实审查

先读[研究说明](report.md)，或独立阅读的[PDF](report.pdf)／[HTML](report.html)；再按问题查[技术疑点清单](questions.md)。

本说明重写论证顺序，从单像素研究问题与实际结论出发，解释偏置、电路选择、模型来源和单位、软件配置、RTL→PWL→transistor路径、真实RC提取边界、结果图、已发生的失败／修正，以及建议但未执行的下一验证。

审查基线为`781ceb266eb1f1dc16780d806cdcd0d5005716ae`。初始git clean；[snapshot-inputs.json](snapshot-inputs.json)保存649个tracked文件的SHA-256。本轮读取既有代码／结果，不改模型、电路或实现代码，不运行EDA实验、不安装工具、不推送GitHub、不改memory。新增图只读取原数值／保存波形；[deliverable-manifest.json](deliverable-manifest.json)记录源文件、派生方式及输入／输出hash。[audit-validation.json](audit-validation.json)记录完成时的原输入比对、链接及版面检查。

阅读时区分：4×4是16个logical positions，电气／物理仍单像素；measured-led是静态表，dynamic probes的电容为假设；joint PEX是真实selected signal网络，PG/body和34邻居边界仍理想化；ns电气阈值不证明真实高速光学调制。boundary数值完成保留了10kΩ供电假设下的工程失败。

旧研究报告、模型卡与运行输出均保留。数据发布日期的原卡错误在新报告中标注；它不触发本轮模型修改。未来如要验证因果或扩展范围，应先声明新run必要性与范围，再写独立build目录，完成DC calibration与coupled regression。
