# 复跑和跨机器恢复

## 读图、对账和复跑

| 任务 | 紧凑证据与输入 |
|---|---|
| 从四路冻结原理图重跑单帧 | [运行回执](../../../evidence/highspeed-workbench-20261110/replay-summary.json)记录四条 ngspice 命令、模型哈希、原生波形、端口能量及 RX 诊断。 |
| 新的前置驱动扫参 | [运行清单](../../../evidence/highspeed-workbench-20261110/predriver-manifest.json)固定两个模型文件、原始输出和脚本哈希。 |
| 重建物理工作台 | [工作台](physical/index.html)从仓库旧 GDS 回读，使用 [几何与工具来源](../../../evidence/highspeed-workbench-20261110/physical-sources.json)。查看现成 Blender 文件无需装 PDK。重新生成或检查需锁定的 GF180MCU D 技术文件、KLayout Python 库和 Blender 4.5.11。 |
| 重建报告 | Markdown、NumPy、Matplotlib。报告支持离线打开，论文链接需联网。 |

本机用 ngspice 47 KLU、Python 3.12、NumPy 2.5.3。不同求解器或平台可能产生末位差异，检查数值、指标和通过判定，保留新旧哈希。复跑不覆盖以前的案例，命令中的运行 ID 应每次更换。

```sh
# 从仓库根目录执行。python 为装有 NumPy、Matplotlib、Markdown 的项目环境。
for route in A B C VCSEL; do
  python scripts/highspeed_workbench_20261110/replay.py "$route" --run-id local-replay --portable
done
python scripts/highspeed_workbench_20261110/replay_summary.py --run-id local-replay
python scripts/highspeed_workbench_20261110/predriver.py --run-id local-buffer
python scripts/highspeed_workbench_20261110/predriver_phase.py \
  --run build/highspeed-workbench-20261110/predriver/local-buffer
python scripts/highspeed_workbench_20261110/render_report.py
```

汇总和报告脚本写入该阶段固定的证据、图表和 HTML 路径。建议在干净 checkout 或独立 worktree 执行整套重建，再对比 Git diff。原生波形与日志写入 `build/`。接收 CSV 仅是展示抽样，不能作为完整帧判决输入。

## 电气冻结输入

- A/B/C 的冻结输入、源快照与三个旧 TT 基准结果在本阶段 Release 的 `frozen-microled-metadata` 组。将 [锁定的 GF180MCU D](../../../layout/pdk-lock.json) 中 `libs.tech/ngspice/{design,sm141064}.ngspice` 复制到 `build/microled-dynamic-v1/electrical/run-r1/inputs/pdk/`，逐一校对 [预驱动运行清单](../../../evidence/highspeed-workbench-20261110/predriver-manifest.json) 的 SHA-256。预驱动用同一对文件，也支持 `--pdk` 指向同 SHA 拷贝。
- VCSEL 使用旧公开 Release 的 `vcsel-reference-microled-dynamics-20261029-s001-metadata-001.tar.gz`。使用 [旧清单](../../../evidence/vcsel-robustness-20261029/archive-manifest.json) 中该卷的条目生成子清单，将此卷恢复到原相对路径。按 [模型锁](../../../analog/models/pdk-lock.json) 和 `scripts/fetch_models.py` 恢复 `.cache/pdk/gf180mcu/` 的两个模型文件。[VCSEL 完整恢复说明](../vcsel-reference-microled-dynamics-20261029/reproduce.md)
- 历史 MicroLED 输入清单误锁一个机器相关 PYC。新归档排除该缓存，`--portable` 只允许在新工作副本忽略缺失的这一个记录，并写入回执。冻结 Python 源、模型和生成 deck 仍逐项核对 SHA-256。四路线汇总保留初次实际 dispatch 脚本哈希。模型子集用于电气实验，物理流程需完整 PDK。

## 本阶段原始数据备份

Git 保存源码、图、Blender 工程和紧凑回执。原始数据使用本阶段同名 GitHub Release，按该 Release 中的清单确认范围与上传状态。恢复时下载所需归档及 manifest，在仓库根目录执行 `scripts/backup/release_bundle.py` 的 `verify` 和 `restore`。可用 `--group` 选择数据组，详见 `--help`。恢复先校验 SHA-256，发现目标不同内容会拒绝覆盖。

```sh
python3 scripts/backup/release_bundle.py restore \
  --manifest release-assets/highspeed-workbench-20261110-archive-manifest.json \
  --asset-dir release-assets --group frozen-microled-metadata --root .
```

VCSEL 代表帧的原生数据复用前阶段已公开的 `vcsel-reference-microled-dynamics-20261029-s032-waveforms-001.tar.gz`。其中 `build/vcsel-robustness-20261029/frame-TT-r10/waveform.dat.gz` 解压后 SHA-256 与本轮 fresh 波形相同。gzip 外层哈希因封装时间不同而不同。完整历史矩阵、失败的中间重试、工具环境和 VM 继续保留在各原阶段。本轮无本地清理动作。

[当前阶段 Release](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/highspeed-workbench-20261110) · [VCSEL 归档 Release](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/vcsel-reference-microled-dynamics-20261029)

## 位错诊断与 VCSEL 十倍目标

本次增量归档的 tag 为 `highspeed-bit-errors-vcsel-x10-20261110`。清单按案例列出历史 10 fF 参考输入、B 的门极旁路、新 VCSEL 满帧与数值对照。先恢复上节的 200 fF 与冻结 metadata，再恢复增量归档，保持仓库相对目录。VCSEL 3.2 Gb/s 原始控制仍取旧公开归档的 s032；MOS 模型按原锁恢复。本轮脚本保留现有 raw 证据，重跑使用空的输出目录。

```sh
python scripts/highspeed_workbench_20261110/microled_errors.py
python scripts/highspeed_workbench_20261110/microled_errors_plot.py
python scripts/highspeed_workbench_20261110/vcsel_x10_run.py --net 32 --edge-ps 20 --steps 40
python scripts/highspeed_workbench_20261110/vcsel_x10_run.py --net 32 --edge-ps 20 --steps 80
python scripts/highspeed_workbench_20261110/vcsel_x10_run.py --net 32 --edge-ps 5 --steps 40
python scripts/highspeed_workbench_20261110/vcsel_x10_run.py --net 16 --edge-ps 20 --steps 40
python scripts/highspeed_workbench_20261110/vcsel_x10_gate_control.py
python scripts/highspeed_workbench_20261110/vcsel_x10_analyze.py baseline \
  net16-edge20-s40 net32-edge20-s40 net32-edge5-s40 net32-edge20-s80 net32-ideal-gates-edge5-s40
python scripts/highspeed_workbench_20261110/b_gate_bypass.py --run-id portable-bypass
python scripts/highspeed_workbench_20261110/render_report.py
```

[位错诊断报告](bit-errors.html) · [阶段增量备份](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/highspeed-bit-errors-vcsel-x10-20261110)
