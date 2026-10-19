# 单通道 NRZ 晶体管比较

打开 [HTML 研究报告](index.html)。本目录是高速路线概念研究后的独立晶体管验证阶段；保留早期 PWM 单像素版图，不以本报告覆盖其证据。

## 实验边界

- A：两级 CMOS 前驱动与受限输出摆幅电压驱动，实际 6 MOS。
- B：电阻偏置电流镜、常开基线、电流转向和 dummy 支路，实际 9 MOS。
- 两版使用同一公开 GF180 3.3 V 模型，同一测得静态 LED I–V、200 fF / 1 Ω / 0.5 nH 动态假设、同一数据序列和无噪声接收代理。
- TT / 27 °C 先校准 25 / 100 µA；其余条件保持电路参数，不再重新校准。
- 本报告不建立物理 BER、实测光带宽、最大实际速率或流片准备完成的证据。

## 可复现入口

先按仓库现有物理环境安装匹配的完整 GF180 PDK；`layout/pdk-lock.json` 的两个 ngspice 模型文件必须与 `build/layout/pdk/gf180mcuD/libs.tech/ngspice` 一致。模型锁哈希不匹配会停止运行。需要 ngspice 47、Python 3.12、NumPy 2.x、Matplotlib，已用 `build/layout/venv/bin/python` 执行。

```sh
build/layout/venv/bin/python scripts/highspeed_nrz/metrics.py
build/layout/venv/bin/python scripts/highspeed_nrz/run.py --stage all --workers 2
```

运行会创建新的 `build/highspeed-nrz/run-*`，打印 WORK 路径，不覆盖历史数据。将该路径填入以下命令：

```sh
build/layout/venv/bin/python scripts/highspeed_nrz/analyze.py --work build/highspeed-nrz/run-0xqxvspp
build/layout/venv/bin/python scripts/highspeed_nrz/receiver_sensitivity.py --work build/highspeed-nrz/run-0xqxvspp
build/layout/venv/bin/python scripts/highspeed_nrz/report.py --work build/highspeed-nrz/run-0xqxvspp
build/layout/venv/bin/python scripts/highspeed_nrz/validate_delivery.py
```

报告生成器读取 `evidence/highspeed-nrz/summary.json`；该摘要应对应指定的 work。中文图形使用 `build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf`，重新搭建环境需准备公开的 Noto Sans CJK SC 字体。已有实验的续跑必须使用与冻结脚本相同的 runner，否则应新建 run。所有 `build/` 文件均是本地生成数据，不随 Git 自动发布。

## 来源与原始数据

- 实验输入、PDK 模型哈希、Python / NumPy / ngspice 版本：正式批次 `manifest.json`、`ngspice-version.log`。
- 每个 case：`testbench.spice`、`case.json`、`ngspice.log`、`waveform.dat.gz`、`result.json`。
- 后处理脚本冻结在正式批次的 `analysis-sources/`；交付文件哈希见 `evidence/highspeed-nrz/delivery-manifest.json`。
- 后处理：`analysis.json` 保留所有逐 MOS 应力、接收抽样规则、逐源能量、首尾显式储能和原始来源哈希。
- [全部实验摘要 JSON](summary.json)、[CSV](summary.csv)、[测量约定](measurement-contract.md)。
- [解析机理核对](mechanism-notes.md)：CSV 分段、电荷、动态电阻和理想电流阶跃子模型。
- [数值失败诊断](numerical-notes.md)：失败日志、数值设置变化、与成功严格解及细步长结果的比较。
- `evidence/highspeed-nrz/` 是紧凑证据的仓库入口；该报告目录复制的摘要仅便于浏览下载。

动态图和电路图均为本项目独立生成。静态 LED 数据引用 Lin et al. 2026，Zenodo 数据集 CC-BY 4.0；原始文件、许可与定位见 `analog/models/measured-led/source-lock.json`。

## 空间预算

建议开始大批次前留出至少 6 GiB，并使用 1–2 个并行 worker。压缩时原始波形与压缩副本会短暂共存；高压/低温角落可能产生大量自适应时间点。历史冗余波形的优化记录见 `evidence/highspeed-nrz/storage-summary.json`，不应删除整个 build 目录。
