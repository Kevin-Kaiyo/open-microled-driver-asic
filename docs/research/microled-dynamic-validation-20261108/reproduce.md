# 复现与交付范围

本轮在 macOS ARM、ngspice47 的冻结公开 GF180 模型子集上运行。`build/` 当前位于本机 DevSSD，但证据和源代码使用仓库相对路径；新电脑应恢复对应源码与输入包，不要求相同磁盘名。

## 分层重跑

1. **公开幅频拟合**：使用 `analog/models/microled_dynamic_v1/model-card.json` 记录的 Python/numpy/scipy 版本，运行 `scripts/microled_dynamic_v1/fit.py`。本机独立解释器为 `build/microled-dynamic-v1/calibration/venv/bin/python`。它只产生整链条件化数学拟合；`usable_transient_family=false` 不得改为器件资格。
2. **电气仿真**：运行 `scripts/microled_dynamic_v1/run.py --help`，按 `backup.md` 恢复输入并在新的输出目录执行 `--phase reproduce --case DC-TT-A-C200fF-L1`。完整矩阵通过 `--phase run` 运行；不覆盖既有case。ngspice与回归解释器分别需可用；数值分析使用Python≥3.11和numpy。
3. **接收分析**：`build/layout/venv/bin/python scripts/microled_dynamic_v1/analyze.py` 从新阶段的 electrical-registry 读取原生导电电流，保留原 v2 训练规则，生成四种光响应假设、分层与理想波形控制。缓存是可再生派生物，不能替代原生波形。
4. **报告**：准备 numpy、matplotlib、Markdown、CairoSVG 及中文字体。macOS 本机 Cairo1.18.4 动态库需要可发现；本机命令如下。

```sh
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  build/layout/venv/bin/python scripts/microled_dynamic_v1/report.py
build/layout/venv/bin/python scripts/microled_dynamic_v1/validate.py --raw-readback
```

`--partial` 仅用于运行中的内部报告检查，最终验收应省略。最终coverage独立核对49个计划case（33个瞬态、16个DC），每个成功瞬态的四种光响应，以及失败/缺失项；不只相信一个完成状态字段。

## 模型和接收条件

- 原 I–V、A/B/C 网表、原校准参数、包封1Ω/0.5nH、输入20ps边沿、七个取能端口保持各自冻结身份。
- 原 v2 receiver 的带宽1GHz、阈值、7.5µAeq/100ps门槛和训练选择规则不变。每个波形仍独立使用训练段选择delay，验证段不参与选择。
- 200fF/200ps旧假设先重跑并与历史原生结果核对。新C/τ敏感性不是实测参数，也没有把拟合整链S21串进电气/RX后面。
- `electrical-input-audit.json`说明r1输入身份误包含一个自动生成PYC缓存：没有被SPICE消费，原记录未改。清洁恢复控制以显式语义输入完成，原r1身份和过程仍保留。

## 来源、失败与备份

公开代码/模型卡/报告/compact evidence在Git。原始SPICE波形、deck、逐case日志和拟合/接收验证详细产物按[backup.md](backup.md)中的阶段Release恢复。Python环境、完整PDK、历史阶段全部数据、私有论文原件以及可再生receiver state cache不在本次原始证据增量范围。保留原始失败和独立复核日志，不能用最后一次成功抹掉中间过程。

本轮无新GDS/DRC/LVS/PEX、无实物LED或PD/TIA测试、无统计BER资格。报告的pJ/bit为完整实验帧的源端取能/尝试净位，不包括完整光互连能耗。
