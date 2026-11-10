# 电路改进：复现、验收与原始证据

本阶段在冻结的 MicroLED A/B 与 VCSEL 基线之上做逐项电路改进。每个候选、直流拟合点和速率都有自己的目录、网表、执行源码快照、日志、原生波形 SHA-256 和结果。失败的接收筛查保留在结果中；它与求解失败不是一回事。早期 `engine.py` 保留原样，后来运行器的输入检查由 `engine_checked.py` 承担，不能通过覆盖旧快照改变历史证据。

## 结果入口

- [A/B 全部完成案例与 DC 校准](../../../evidence/ab-improvement-20261111/summary.json)
- [最终候选与边界](../../../evidence/ab-improvement-20261111/selection.json)
- [A 改进对照](../../../evidence/ab-improvement-20261111/a-improvement-summary.json)、[B 边沿诊断](../../../evidence/ab-improvement-20261111/b-diagnostics.json)、[VCSEL 因果对照](../../../evidence/ab-improvement-20261111/vcsel-causal-comparison.json)
- [完整科学验收](../../../evidence/ab-improvement-20261111/scientific-validation.json)、[报告文件验收](../../../evidence/ab-improvement-20261111/validation.json)
- [预先锁定的第二帧协议](../../../evidence/ab-improvement-20261111/holdout-protocol.json)、[A 结果](../../../evidence/ab-improvement-20261111/a-holdout.json)、[B 结果](../../../evidence/ab-improvement-20261111/b-holdout.json)、[VCSEL 结果](../../../evidence/ab-improvement-20261111/vcsel-holdout.json)

所有通过点只适用于本轮 TT、已建立偏置、无外加噪声的数据帧。MicroLED 的 200 fF、200 ps 光学极点和 VCSEL 的 150 fF 等动态参数没有被本轮校准为真实器件参数。源端正向、返回和净能量分别记录；分母是 4096 个尝试载荷位，未通过点不能作为可靠有效载荷能效。启动、关断、随机 BER、长时间稳态和完整 PVT 不在这次通过结论内。

## 恢复输入

先按[上一阶段恢复说明](../blue-emitter-speed-review-20261110/reproduce.html)恢复 `blue-emitter-speed-review-20261110` 的基线输入、历史锚点和必要 metadata。本阶段仍引用这些既有文件，不重复归档同一套历史波形。两个 GF180 模型文件必须依锁定 SHA-256 恢复；PDK、VM 和 Python 环境没有放入公开原始波形归档。

随后下载本阶段 Release 的全部 assets，保留仓库相对路径：

```sh
python3 scripts/backup/release_bundle.py verify \
  --manifest release-assets/driver-improvement-20261111-archive-manifest.json \
  --asset-dir release-assets
python3 scripts/backup/release_bundle.py restore \
  --manifest release-assets/driver-improvement-20261111-archive-manifest.json \
  --asset-dir release-assets --root .
```

恢复会核对 archive 和每个成员文件 SHA，不覆盖已有不同内容。若只要审阅报告，无需恢复大波形。重新分析需要完整案例与上述历史输入；重新求解则在独立 checkout 中保留历史输入、让本阶段候选目录为空。运行器见到完整已有结果时会验证并返回它，不能把这种重用称为新求解。

## 重新求解示例

基准环境是 Python 3.12、NumPy 2.5.3、ngspice 47 KLU。`python` 应指向对应环境。本机科学图环境为 `build/layout/venv/`。下列是最终候选的核心复现入口；完整试验矩阵以结果 JSON 为准。

```sh
# A：重新拟合两条真实输出轨，保留所有二分迭代，再冻结参数扫速。
python scripts/ab_improvement_20261111/a_calibrate.py \
  a-rin1wide-core03 --rates 1.2 1.6 1.8 2.0 3.2

# B：初始参数不变；显式集中 CFF 不是 PDK MIM/PEX。
PYTHONPATH=scripts/ab_improvement_20261111 python - <<'PY'
from b_candidates import candidate
from engine_checked import init_candidate, run_case
c = candidate('B_wide_ff31p275')
w = init_candidate(c['name'], c['route'], c['route_text'],
                   c['parameters'], c['notes'])
for level in [0, 1]:
    run_case(w, level=level)
for rate in [0.8, 1.2, 1.6, 2.0, 2.4, 3.2]:
    run_case(w, rate=rate)
PY

python scripts/ab_improvement_20261111/vcsel_improve.py \
  --candidate vc-atten50-steer20 --rates 4.8 6.4 7.2 8.0
python scripts/ab_improvement_20261111/vcsel_improve.py \
  --candidate vc-atten50-steer20 --rates 6.4 --steps 80
```

半步长对照使用 `run_case(w, rate=..., steps=80)`。A 的 1.6/1.8 和 B 的 2.0/2.4 Gb/s 都检查。第二帧在最终电路冻结后运行：

```sh
python scripts/ab_improvement_20261111/holdout.py a-rin1wide-core03-matched --rate 1.6
python scripts/ab_improvement_20261111/holdout.py B_wide_ff31p275 --rate 2.0
python scripts/ab_improvement_20261111/vcsel_holdout.py
python scripts/ab_improvement_20261111/summarize.py
python scripts/ab_improvement_20261111/validate_stage.py --final
```

验收包括实际 PWL 的位数、速率与边沿、模型与执行源码哈希、正向能量范围、DC 匹配、接收和应力筛查、半步长及第二帧。另一种子是在已知开发序列之后选择的 PRBS15 非重叠窗口，不是新独立器件，更不是统计 BER 证据。

## 重建图表和报告

```sh
python scripts/ab_improvement_20261111/figures.py
python scripts/ab_improvement_20261111/plot.py
python scripts/ab_improvement_20261111/a_waveforms.py
python scripts/ab_improvement_20261111/b_figures.py
python scripts/ab_improvement_20261111/vcsel_plots.py
python scripts/ab_improvement_20261111/report.py
python scripts/ab_improvement_20261111/validate_report.py
```

科学图使用 Matplotlib、Pillow 和 CairoSVG；报告使用 ReportLab 4.4.9、pypdf 6.10.0、pdfplumber 0.11.9、Markdown 3.9。本机报告环境复用 `build/blue-emitter-speed-review-20261110/report-venv/`。HTML 优先 PingFang SC；PDF 使用可嵌入 Heiti SC TrueType 与 Arial，因为 ReportLab 不支持系统 PingFang 的 CFF 字体。跨平台应替换为有许可的 CJK 可嵌入字体。

本轮图是独立绘制的连接图和原生仿真数据图，未新增完整物理版图、DRC/LVS/PEX 或可流片 GDS。原有物理结果只对应其历史网表，不能自动覆盖这次改版。

## 备份范围

Git 保存公开源码、报告、图表和紧凑证据；[本阶段 Release](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/driver-improvement-20261111)保存完成求解的原始波形、冻结输入、源码快照与日志，包括接收未通过的案例和 DC 拟合中间点。发布后按 [archive 清单](../../../evidence/ab-improvement-20261111/archive-manifest.json)验证远端下载的 archive 及每个成员。最终交付状态在独立 `delivery.json` 中记录。

未完成或求解失败的本地日志、PDK、环境、无关工作区内容不纳入这次 Release，也不删除。此前未完成的 `microled-dynamic-validation-20261108` 全矩阵 draft 不属于本次补齐范围。Git push 不等于忽略目录的备份；本阶段不清除任何本地原始证据。
