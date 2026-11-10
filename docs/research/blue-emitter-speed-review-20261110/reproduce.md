# 数据、复现与阶段备份

本轮研究包含公开蓝光器件资料、现有完整晶体管电路的真实扫速、负载电容对照与成果审计。所有新速率以新的 PWL 位周期运行 ngspice；没有把旧波形的时间轴缩放后当作新电路结果。历史锚点的网表与原生波形由 SHA-256 绑定。

## 结果入口

- [完整逐点结果](../../../evidence/blue-emitter-speed-review-20261110/speed-sweep-all.json)包含速率、错误位、幅度／时间、源端能量、应力和模型域。
- [公开文献来源台账](../../../evidence/blue-emitter-speed-review-20261110/sources.json)区分厂商规格、样机、研究测量、图读值与独立计算。
- [PDF／网页检查](../../../evidence/blue-emitter-speed-review-20261110/validation.json)和[文件身份](../../../evidence/blue-emitter-speed-review-20261110/report-manifest.json)用于核对报告与数据。
- [原阶段恢复说明](../highspeed-workbench-20261110/reproduce.html)保留电气模型、冻结输入与工具条件。

比较使用 TT 已建立 DC 偏置的数据帧，20 ps 激励边沿。显示参考源的启动验证属于另一组实验。4,096 位验证段前有独立训练段，采样延迟只从训练数据确定。新的归一化时间门槛为 0.37 线路 bit UI；旧报告的绝对 100 ps 另存为参考。MicroLED 的 0～8 bit UI 新训练窗与旧绝对延迟窗不同，原生波形不变也可能使少数错误计数变化。

综合筛查需要训练／验证零错、幅度至少 7.5 µAeq、单侧时间至少 0.37 bit UI、MOS 端间电压筛查通过、体结正偏不超过项目 0.3 V 研究线，以及电流在原静态模型范围内。动态发光参数仍未完成物理校准；这些门槛不等于代工可靠性规则、实测 BER 或产品保证。

## 重新运行仿真

建议在独立 checkout 中恢复历史输入，使用空的本阶段 `build/blue-emitter-speed-review-20261110/`。恢复本阶段归档后可以重做分析；要重新求解，应另建 checkout，保留归档原生证据，避免把返回已有成功结果当作新求解。

电气环境使用项目 Python 3.12、NumPy 2.5.3、ngspice 47 KLU。完整 PDK 与工具环境不打包。MicroLED 原始 `run-r1/inputs/`、执行源快照和帧文件按原阶段说明恢复；PDK 两个文件按锁定哈希恢复到其 `inputs/pdk/`。VCSEL 需要 `frame-TT-r10/` 的冻结 metadata，以及 `.cache/pdk/gf180mcu/` 中锁定的两个模型文件。

```sh
# 仓库根目录，python 指向上述研究环境。
python scripts/blue_emitter_speed_20261110/sweep.py microled --rates 0.4 0.8 1.6
python scripts/blue_emitter_speed_20261110/sweep.py microled --routes C --rates 0.2
python scripts/blue_emitter_speed_20261110/sweep.py microled --routes B --rates 0.4 --cap-fF 800
python scripts/blue_emitter_speed_20261110/sweep.py vcsel --rates 6.4 12.8

# 半步长案例和实际执行矩阵以 speed-sweep-all.json 为准。
python scripts/blue_emitter_speed_20261110/analyze.py
```

分析还需要历史 MicroLED 净 3.2 Gb/s 的 A/B/C、B 的 0/10/50/800 fF 原生案例，及 VCSEL 原 3.2、16、32 Gb/s 案例。它们保留原相对路径，不将镜像快照和原件混为同一哈希。本轮 Release 清单纳入本报告实际使用的选定历史锚点及必要冻结 metadata；MOS 模型仍按锁恢复。

核查时，旧 `microled-dynamic-validation-20261108` 全矩阵 Release 仍为 draft，已有 9 个 assets，不能当作完整公开备份。本轮只闭合本报告选定输入与结果的恢复范围，不宣称旧全矩阵已补齐；其本地原件继续保留。

本轮 0.1 Gb/s 的预排队列取消，以已通过的 0.4 Gb/s 作为 A/B 低速点，仅为 C 追加 0.2 Gb/s。取消与未完成求解的本地日志保留，不计为通信失败，不进入已完成结果表。

## 重建报告

科学图表使用 NumPy、Matplotlib、Pillow 与 CairoSVG。PDF 使用 ReportLab、pypdf、pdfplumber；HTML 使用 Markdown 3.9。字体按项目规则优先 PingFang SC，PDF 因 ReportLab 对系统 PingFang CFF 的限制嵌入 Heiti SC TrueType 和 Arial。跨平台需替换为有许可、支持 CJK 的可嵌入字体。

```sh
python scripts/blue_emitter_speed_20261110/figures.py
python scripts/blue_emitter_speed_20261110/plot.py
python scripts/blue_emitter_speed_20261110/waveform_plot.py
python scripts/blue_emitter_speed_20261110/report.py
python scripts/blue_emitter_speed_20261110/validate_report.py
```

本机科学图环境为 `build/layout/venv/`。报告环境为 `build/blue-emitter-speed-review-20261110/report-venv/`，复用桌面工具的 ReportLab／PDF 依赖，只额外安装 Markdown 3.9。这些环境不是研究输入，未放入 Git 或 Release。

## Git 与原始波形

源码、图表、报告与紧凑证据进入 Git。大波形按 `blue-emitter-speed-review-20261110` 阶段 Release 的清单恢复，必须保留原仓库相对路径。

```sh
python3 scripts/backup/release_bundle.py verify \
  --manifest release-assets/blue-emitter-speed-review-20261110-archive-manifest.json \
  --asset-dir release-assets
python3 scripts/backup/release_bundle.py restore \
  --manifest release-assets/blue-emitter-speed-review-20261110-archive-manifest.json \
  --asset-dir release-assets --root .
```

恢复先校验归档与每个成员 SHA，目标已有不同内容会拒绝覆盖。Git push 只备份 Git 中的文件，不能替代 `build/` 原生波形归档。远端备份状态见[交付核验](../../../evidence/blue-emitter-speed-review-20261110/delivery.json)。本轮不删除任何本地原始输入、失败记录、PDK 或 VM。

公开归档排除 Python 环境、PYC、PDK 副本、重复中间波形和文献原始 PDF／截图。原文图像公开转载许可未核实，已下载的原件与中文解释保存在本地 `build/blue-emitter-speed-review-20261110/literature/index.html`；公开报告使用独立图示、事实表与明确出处。

[本阶段 Release](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/blue-emitter-speed-review-20261110) · [历史 MicroLED 动态实验](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/microled-dynamic-validation-20261108) · [此前位错／VCSEL 增量](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/highspeed-bit-errors-vcsel-x10-20261110)
