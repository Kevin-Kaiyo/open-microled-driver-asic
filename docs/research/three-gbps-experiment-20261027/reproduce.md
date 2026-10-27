# 复查、恢复与重新仿真

本轮证据对应原理图级电路与研究代理。恢复字节、复算已有结果、重新跑 ngspice、异机验证是不同层级；本轮未声明独立计算机已经复跑。

## 先读哪些文件

- `evidence/three-gbps-experiment-20261027/microled-summary.json`：9 个原条件瞬态、3 个零电容诊断、16 个 DC 检查。
- `microled-validation.json`：另有 3 个时间步减半瞬态；理想波形/滤波数值检查。
- `microled-training-feasibility.json`：48 个观察阶段的训练候选审计。
- `vcsel-driver-summary.json`：每个 case / analysis 的哈希、种子、五端口能量、接收、器件和模型域检查。
- `analog/models/vcsel_research_20261027/MODEL_CARD.md`：图读方法、误差、模型范围、去嵌和大信号限制。
- `circuit-figures.json`：13 MOS 的 D/G/S/B、模型、W/L 与 SVG 的逐器件绑定。
- `runtime.json`：本机 NumPy、Matplotlib、Markdown、Pillow、ngspice 版本。Python 环境不包含在 Git 中。

## Git 与 Release 分工

Git 保存新电路、模型来源/代码、仿真/分析脚本、报告和 compact evidence。全帧原始波形、网表、日志、运行输入快照及失败放在 `build/three-gbps-experiment-20261027/`，使用 Release 标签 `three-gbps-experiment-20261027` 备份。

Release 清单 `<tag>.json` 逐文件记录 SHA-256，并记录每个 tar.gz 的 SHA-256。`archive-local.json` 表示本地归档全部成员核验，`archive-remote.json` 表示下载流回读一致。只有看到对应成功回执，才能称那一步完成。

保留了全部新失败及修正记录。原始 Frontiers 完整网页和解析文本留在本地，因不需要再次分发整页而排除；源 URL / SHA 和选取的 CC BY 4.0 原图另有记录。Python 环境、完整 PDK、历史 build 和系统软件均不属于这次 Release。

恢复流程（在独立目录操作，不覆盖不同字节的旧数据）：

```sh
gh release download three-gbps-experiment-20261027 \
  --repo Kevin-Kaiyo/open-microled-driver-asic --dir /absolute/path/to/assets
python3 scripts/backup/release_bundle.py verify \
  --manifest /absolute/path/to/assets/three-gbps-experiment-20261027.json \
  --asset-dir /absolute/path/to/assets
python3 scripts/backup/release_bundle.py restore \
  --manifest /absolute/path/to/assets/three-gbps-experiment-20261027.json \
  --asset-dir /absolute/path/to/assets --root /absolute/path/to/checkout
```

首先用已提交回执核对 manifest SHA 和源码提交；不能仅信任下载目录内任意清单。命令参数以 `python3 scripts/backup/release_bundle.py --help` 为准。原 deck 保留历史绝对路径，所以异机应从冻结输入生成新 deck，不能修改原记录。

## MicroLED 复算与新运行

恢复本轮 `build/.../microled/run-r1/` 后，可重新分析已有原生波形：

```sh
build/layout/venv/bin/python scripts/three_gbps_experiment/microled_diagnosis.py --phase analyze
build/layout/venv/bin/python scripts/three_gbps_experiment/microled_validation.py --phase validate
```

这会重写派生汇总，建议在独立 checkout 中进行。`--phase run` 对已存在 case 读取历史结果，并不表示重新跑了仿真。若要新增实验，应另建 work 名称，复制原冻结 inputs / manifest / stimulus，使用 legacy engine 生成新 deck；不要删除旧 case 强制覆盖。首次初始化依赖旧 `build/fair-driver-v1/matched-r2`，恢复本轮已冻结目录可避免重新依赖旧实验初始化。

## VCSEL 新运行

`vcsel_driver_run.py` 拒绝覆盖同名 case。例：

```sh
build/layout/venv/bin/python scripts/three_gbps_experiment/vcsel_driver_run.py \
  --name independent-TT-3p2 --mode frame --pvt TT --rate 3.2 --seed 0x57AE
build/layout/venv/bin/python scripts/three_gbps_experiment/vcsel_driver_analyze.py \
  --case independent-TT-3p2 --label baseline
```

运行器需要 `.cache/pdk/gf180mcu/design.ngspice` 和 `sm141064.ngspice`；版本与 `analog/models/pdk-lock.json` 一致。本轮各 VCSEL case 的 `inputs/` 含这两个冻结文件，可在核对 SHA 后恢复到需要的位置。它们是公开模型子集，不是完整物理 PDK。参照模型源许可及 notice，保留原文件头与锁文件。另需 NumPy/ngspice。v3 使用 `vcsel_driver_analyze.py --case independent-TT-3p2 --label v3-diagnostic --receiver v3`；规则实现于 `vcsel_driver_receiver_v3.py`，对应 contract 与源快照保存在各 analysis 目录。

新种子仍是确定性 PRBS15，不能当成独立随机 BER 实验。不同 seed 可能只是同周期相移且窗口重叠；`vcsel-model/seed-overlap-audit.json` 记录了本轮重叠检查。

## 报告生成

```sh
build/layout/venv/bin/python scripts/three_gbps_experiment/diagrams.py
build/layout/venv/bin/python scripts/three_gbps_experiment/report.py
build/layout/venv/bin/python scripts/three_gbps_experiment/verify.py
```

报告生成器依赖完整 MicroLED 波形绘制眼图，仅读取 Git 中的 summary 不足以重画全部图。默认沿用既有 Noto CJK 字体路径；其他机器可以设置 `MICROLED_REPORT_FONT` 为本机具有许可的 CJK 字体文件。最终 HTML/PNG/SVG 已在 Git，可直接阅读，无需运行器或下载波形。
