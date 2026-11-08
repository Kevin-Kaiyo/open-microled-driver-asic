# 报告生成与核查

编制日期2026-11-09，工程证据截止2026-11-08。目录日期沿用任务开始日。本报告为既有项目资料的审查与综合，不执行新的RTL、SPICE、DRC/LVS/PEX或实物实验。

- 正文结构：`scripts/project_progress_20261108/content.py`。
- 生成器：`scripts/project_progress_20261108/build.py`。同一内容结构输出HTML、Markdown、PDF与内容JSON。
- 验证器：`scripts/project_progress_20261108/validate.py`。
- 三组审计和source/figure SHA：`evidence/project-progress-review-20261108/`。
- 原实验/研究资料按其各自日期和版本保留，本文不会改变原数据。

```sh
python scripts/project_progress_20261108/build.py
python scripts/project_progress_20261108/validate.py
pdftoppm -r 110 -png \
  docs/research/project-progress-review-20261108/project-progress-report.pdf \
  build/project-progress-review-20261108/pdf-pages/page
```

生成PDF的本机解释器为Codex bundled Python 3.12，reportlab4.4.9、Pillow13.0.0；核查另用pypdf6.10.0、pdfplumber0.11.9和Poppler。SVG/科学图表渲染复用项目`build/layout/venv/bin/python`中的CairoSVG2.8.2、Matplotlib3.11.2及NumPy2.5.3。Cairo动态库发现通过进程环境设置，不改变系统配置。

生成器当前使用macOS字体路径：PDF嵌入Heiti SC与Arial；HTML优先PingFang SC。系统PingFang为CFF轮廓，不直接用于ReportLab TTFont。其他操作系统需替换为许可允许嵌入的CJK字体并复核版面；已经生成的PDF阅读不依赖本机字体。字体文件没有单独复制进仓库。

HTML图像以data URI嵌入，可离线阅读；原图与来源链接仍指向对应仓库文件。PDF来源链接指向审计基线commit（新增审计文件使用当前仓库入口）。来源内部精度/版本以sources.json和三份逐claim审计为准，不将本轮文件审查升级为重跑全部实验。

本轮新增的报告、生成器和精简证据随Git提交；原始EDA输出及上一轮大型波形仍在各自build/和Release范围内。此前raw传输已因HTTP408停止，远端未验收。报告交付与原始备份状态分开记录，不删除本地原数据。
