# MicroLED驱动ASIC产品开发框架 · 2026-10-14

主入口：[28页研究报告 PDF](report.pdf)／[带目录 HTML](report.html)／[可编辑正文](report.md)。先从架构、数字逻辑、buffer、像素与参考源读起，再进入LED模型、保护、版图、工艺、高速通信、验证和制造交付。

本轮是当前成果的系统整理、实际GDS可视化和明确假设的高速教学计算；没有重新运行晶体管或物理签核批次。启动功能合同通过，严格极小Q+相对收敛仍失败，原始整体 `passed=false` 保留。新参考、隔离、保护和恢复逻辑没有合入旧GDS。

## 先看图

- [实际二维／三维分层浏览器](layout/viewer.html)：离线可用，切换联合top／单像素，开关层、缩放、平移、旋转。
- [旧联合top](layout/integrated-2d.svg)、[六MOS像素局部](layout/pixel-2d.svg)、[相对层高投影](layout/pixel-3d-projection.png)。X/Y来自真实GDS；Z是相对层序，无物理厚度或场求解。
- [高速眼图对照](figures/highspeed-eye.svg)、[带宽敏感性](figures/highspeed-bandwidth.svg)：合成线性两极点，不是GF180仿真、真实光学或BER。

## 从框架到可执行工作

- [当前架构审查](current-architecture-audit.md)与[current-evidence.json](current-evidence.json)：模块、实际信号顺序、证据等级、输入hash。
- [验证计划](verification-plan.json)：G0–G12和高速H1，逐项列输入、输出、状态及缺口。
- [流片交付包模板](tapeout-package-template.json)：明确 `ready_for_submission=false`，待填字段保持null；不可作为实际制造包。
- [高速深入章节](highspeed-chapter.md)与[5项主来源](highspeed-sources.json)：数据链、电路、工艺／封装差异、论文条件和原始资料位置。
- [版图深入说明](layout-chapter.md)与[几何manifest](layout/manifest.json)：实际层映射、GDS hash、bbox、图形统计与边界。

## 复现

保留旧工程文件。脚本使用已配置的Python／KLayout环境及Chrome打印；没有下载新PDK或改变原始GDS。

```sh
build/layout/venv/bin/python scripts/research/framework_figures.py
build/layout/venv/bin/python scripts/research/framework_layout.py
build/layout/venv/bin/python scripts/research/product_framework_highspeed.py
build/layout/venv/bin/python scripts/research/build_framework_report.py
REPORT_PLAYWRIGHT_MODULE=/path/to/playwright node scripts/research/print_framework_report.cjs
```

`framework_layout.py`生成SVG和浏览器；PNG及浏览器检查由 `layout/browser-check.cjs`在配置好的Playwright／Chrome环境生成。最终PDF需Poppler逐页渲染并人工视觉检查，再运行 `scripts/research/validate_framework_report.py --pdf-pages-reviewed 28`。校验器需要pypdf；报告和几何校验通过不改变电路实验状态。

原始图、论文页面和临时波形在 `build/product-framework-20261014/`。引用数据与本轮输出身份在[evidence-ledger.json](evidence-ledger.json)及[validation.json](validation.json)。尚未对外发布、提交晶圆厂或订购制造。
