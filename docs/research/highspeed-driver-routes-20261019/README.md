# 高速 MicroLED Driver：电路、芯片与速率—能耗取舍

日期：2026-10-19。用途：实验性研发方法验证与教学。

入口：[中文交互研究报告](index.html)。含三条 MOS 电路路线、三张对应芯片功能分区、仪器表征电路、Blender 封装概念和解析预算。

## 成果与证据范围

| 文件 | 内容 | 证据阶段 |
| --- | --- | --- |
| `figures/route-a/b/c.svg` | 电压驱动、恒流转向 OOK、分段电流 DAC/PAM4 | 原创候选电路；无 W/L 与高速 SPICE |
| `figures/floorplan-a/b/c.svg` | 数据、前驱动、输出、参考、电源和封装接口分区 | 概念 Floorplan；非 GDS，面积/层数未定 |
| `figures/bench-linear.svg` | AWG/RF/Bias-T 表征平台 | 仪器原理图，不是实现的 ASIC |
| `package-concept.blend` | 硅 CMOS 与 III–V LED 的空间关系 | Blender 4.5.11 LTS 原创概念；非热/电磁/制造仿真 |
| `evidence-sources.json` | 8 条原始来源、工作条件、页码、缺口 | 全文、摘要、企业披露分级 |
| `calculations.json` / `numerical-notes.md` | 电容/静态/并行功耗、两极点与 Ldi/dt | 显式假设的解析预算；73 项公式自检 |
| `figures/circuit-metadata.json` | 16 只 MOS 的 D/G/S/B 与图形连接 | 教学图连接复核；不是 LVS |

本轮未新增高速晶体管仿真、DRC/LVS/PEX、光眼图、BER、硅片或光链路测量。当前 PWM 像素的历史验证不自动适用于高速方案。

## 本地阅读

在仓库根目录运行：

```sh
build/layout/venv/bin/python scripts/blender_animation/serve.py --port 8771
```

打开 `http://127.0.0.1:8771/highspeed-driver-routes-20261019/index.html`。支持原有动画页的 MP4 Range 请求。也可直接用浏览器打开本目录的 `index.html`；交互预算不依赖外网。

私人原图卡存于被忽略的 `build/highspeed-driver-routes-20261019/private-evidence/`，不复制到公开资料目录。必要时单独在回环地址提供：

```sh
python3 -m http.server 8772 --bind 127.0.0.1 --directory build/highspeed-driver-routes-20261019/private-evidence
```

本轮没有发布到个人博客或推送远程仓库。

## 复现

从仓库根目录运行，保留现有依赖版本：

```sh
build/layout/venv/bin/python scripts/highspeed_routes/circuits.py
python3 scripts/highspeed_routes/tradeoffs.py
python3 scripts/highspeed_routes/build_report.py
build/blender-demo/tools/Blender.app/Contents/MacOS/Blender --background --python scripts/highspeed_routes/package_concept.py
```

`circuits.py` 的 SVG 由标准库绘制，网页优先使用 PingFang SC。可选 PNG 预览使用 CairoSVG 2.8.2 / Cairo 和本机 Arial Unicode MS，以保证中文及数学符号都有字形；不会改变 SVG 字体或几何。在本机执行：

```sh
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib build/layout/venv/bin/python scripts/highspeed_routes/circuits.py --raster
```

其他机器可用 `--raster-font` 指定已有的完整 Unicode 字体；先检查字形再交付。Blender 使用已有字体 `build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf`，字体嵌入 `.blend`，许可在 `font-license.txt`。Blender 场景生成会受软件/渲染器版本影响；不以渲染文件字节一致代替语义检查。

验证记录在仓库 `evidence/highspeed-routes/`。其中公式检查、连接审阅和网页视觉检查各自说明范围，不合并为芯片设计通过。两个本地服务运行时，可执行 `python3 scripts/highspeed_routes/validate_report.py` 核查本地链接、原始来源哈希、SVG、场景来源和交付文件；浏览器交互记录另存于 `viewer-validation.json`。

## 研究建议

先在同一已标定 LED 和接收条件下完成单 lane NRZ；以电流转向为可观察基线，对比受限摆幅电压驱动。记录所有供电、PVT、端间应力、回灌和寄生。完成单 lane 布局与测量后，再决定 FFE、PAM4 或并行，避免用仪器最高速率搭配另一工作点的最低能耗。
