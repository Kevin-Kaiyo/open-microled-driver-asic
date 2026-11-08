# 动态负载验证：原始证据备份与跨机器恢复

本说明对应阶段 tag `microled-dynamic-validation-20261108`。源码、来源 CSV、模型卡、报告及 compact evidence 随 Git tag 保存；被忽略的原始仿真/分析输出需另存 Release assets。仅有 Git push 不能恢复这些原始输出。

`scripts/microled_dynamic_v1/archive.py` 负责明确选择、冻结检查及调用现有 `scripts/backup/release_bundle.py` 的 pack / verify / restore。它不上传、不操作 Git、不删除原始文件。**helper 或本说明的存在不表示本轮已打包、上传、远端回读或在另一台机器重跑。** 这些状态应分别由实际 receipt 证明。

## 保存范围与排除项

| 范围 | 保存内容 | 边界 |
|---|---|---|
| `build/microled-dynamic-v1/electrical/` | 全部常规文件：frozen inputs、source snapshots、manifest、plan、stimulus、case/deck/result/log、原生 waveform 压缩件及重跑证据 | r1 manifest 误锁的 `inputs/__pycache__/receiver.cpython-312.pyc` 原字节照存，以保持身份；后续 runner 禁止写入新 bytecode，重跑依赖已保存的源码，它不是新电脑所需运行环境 |
| `build/microled-dynamic-v1/receiver/` | 每次分析、眼图 NPZ、fixture、数值验证与失败日志、旧源码/证据快照 | 排除 `cache/`、`states/`、`state-cache/`、Python 环境及 bytecode；大型滤波状态由已恢复的原生 conduction trace 与对应源码重新生成 |
| `build/microled-dynamic-v1/calibration/` | 全部拟合试验、多起点、失败、留出与 fit logs | 排除整个 `venv/`、其他 Python 环境及 bytecode |
| `build/microled-dynamic-v1/report/` | render logs、JSON / TXT 元数据 | 已进 Git 的报告及可再生渲染不重复纳入 raw bundle |

历史 `build/`、私有论文 PDF/HTML/截图、完整 PDK/VM、整个 Python 环境和新 receiver 状态缓存不在此 raw selection。任何排除项都只是不打包，原文件保留。`scope.json` 记录实际选择和排除路径，`files-sha256.json` 记录每个原始文件的 SHA-256、大小和权限；归档 manifest 另有每卷及卷内每文件 SHA-256。

## 冻结、准备与本地归档

在所有实验/分析/报告写入进程停止且父任务确认冻结后执行。默认检查要求：49 个计划电气 case 均已有 attempted result；33 个 transient 均成功；最终 RX 对全部 33 case 各覆盖 τ=0/25/75/200 ps；33 个旧 200 ps 接收回归均通过，且无缺失或 RX analysis failure。文件集合、日志 stat、逐文件 SHA 和源证据身份须保持稳定；`lsof` 写句柄检查默认启用。

从仓库根目录运行。将 `<reviewed-source-commit>` 换成此次 tag 对应的完整 40 字符 commit。helper 不读取或更改 Git 身份，因此 caller 必须先核对该值。`--output` 必须是新目录，且位于被选择的 raw stage 之外。

```bash
python3 scripts/microled_dynamic_v1/archive.py prepare \
  --source-commit <reviewed-source-commit> \
  --output build/github-sync-microled-dynamic-validation-20261108
```

先检查输出目录中的 `readiness.json`、`selection.json`、`scope.json`、`provenance.json` 和 `files-sha256.json`。`prepare` 只做检查、选择与 per-file hashes，不打包。它会将仓库 root 先作 `Path.resolve()`，因此当前 Mac 的可见路径与实际 DevSSD 路径不会传入归档 API 造成 symlink-root 错误；成员路径始终相对仓库。

父任务已确认冻结后，显式传入该状态：

```bash
python3 scripts/microled_dynamic_v1/archive.py pack \
  --prepared build/github-sync-microled-dynamic-validation-20261108 \
  --freeze-confirmed
```

每卷目标为 **512 MiB 原始输入大小**，并非硬性的压缩后卷大小。单个文件不跨卷；底层工具拒绝大于 1.8 GiB 的单文件。卷数、大小以实际 manifest 为准。pack 前重新核对文件集合和所有 SHA，pack 时由底层工具逐文件检查流内容，完成后本地 verify 每卷及每个 tar member。现有输出不覆盖，原始文件不删除。

再次独立检查本地包：

```bash
python3 scripts/microled_dynamic_v1/archive.py verify \
  --manifest build/github-sync-microled-dynamic-validation-20261108/microled-dynamic-validation-20261108.json \
  --asset-dir build/github-sync-microled-dynamic-validation-20261108/assets
```

`archive-local.json` 只证明本地包/member 验证。父任务应另将所有 asset、归档 manifest 和准备阶段的五个 JSON sidecars 上传到对应 Release；再核对 tag→commit，下载回读所有上传字节，逐卷 SHA 并 verify members，才可记录远端完成。此 helper 不包含上传或远端回读动作，也不允许据本地 receipt 宣称备份已完成。任何将来的本地移除仍需单独决策，本流程不移除原始数据。

## 新电脑恢复 raw files

1. 获取同 tag 的源码 checkout；确认其 commit 与 `provenance.json`、Release tag 一致。下载 manifest 及其列出的全部 `.tar.gz` assets，放在一个独立目录（下例为 `release-assets/`）。同时保留 scope / provenance / per-file sidecars。
2. 在 tag checkout 根目录运行下面命令。`restore` 首先验证每卷及每个 member，再预检全部目标；同内容文件跳过，已有不同内容文件使整个预检失败，避免覆盖本地工作。

```bash
python3 scripts/microled_dynamic_v1/archive.py verify \
  --manifest release-assets/microled-dynamic-validation-20261108.json \
  --asset-dir release-assets

python3 scripts/microled_dynamic_v1/archive.py restore \
  --manifest release-assets/microled-dynamic-validation-20261108.json \
  --asset-dir release-assets \
  --destination .
```

也可用 `--group metadata` 先恢复 inputs / case metadata / 分析/眼图；`--group waveforms` 再恢复原生 waveform。完整 raw 备份需两组都具备。完整恢复保持 `build/microled-dynamic-v1/electrical/run-r1/` 及其相对目录，不需要当前 Mac 的绝对路径，也不需要先恢复历史 `matched-r2` 或旧 MicroLED build。

Python 环境需重新安装。helper 及底层打包工具只用 Python 标准库；电气重跑另需可用的 `ngspice` 与 NumPy。原运行版本以 frozen manifest / provenance 和报告实际 receipt 为准（本轮主电气环境为 Python 3.12.13、NumPy 2.5.3、ngspice 47 KLU）；拟合独立环境的依赖见 `analog/models/microled_dynamic_v1/requirements.txt`。r1 的 bytecode 仅作为历史身份保存，不作为跨版本依赖使用。

## DC smoke：验证恢复后的可运行路径

在新电脑建好独立 Python / NumPy 环境、确认 `ngspice --version` 后，从 tag checkout 根目录执行。`--work` 必须为不存在的新路径，且在 `build/microled-dynamic-v1/electrical/` 下：

```bash
python scripts/microled_dynamic_v1/run.py --phase reproduce \
  --case DC-TT-A-C10fF-L0 \
  --work build/microled-dynamic-v1/electrical/restore-dc-smoke
```

该命令复制已恢复 r1 的 frozen inputs / execution-sources / manifest / plan / stimulus，不走依赖历史 build 的初始化路径。检查新目录中的 `reproduction.json` 和 `cases/DC-TT-A-C10fF-L0/result.json`：至少核对 `simulation_ok`、`metrics.i_led_A`、`metrics.current_error_percent`、端压筛查及 ngspice log。跨工具版本/平台原生 waveform 的 SHA 可能不同；SHA 不同本身不等于电路失败，应保留版本与数值差异。DC smoke 证明恢复路径和静态求解，不证明完整 49-case、瞬态眼图或真实光学链路。

receiver filter states 没有存入归档；需要时按 tag 的接收分析命令从已恢复 native traces 重新生成。该重算是独立验证步骤，不把缺失缓存当成丢失电气原始证据。

## 重建接收缓存：先保留归档摘要

恢复检查发现，tag 中的 `analyze.py` 会在逐 case 摘要指纹匹配时直接复用摘要；这一步不会补建被排除的 state cache。随后半步长比较需要读取这些缓存。因此，**在新的恢复 checkout 中完整恢复 metadata 和 waveforms 后**，首次全 RX 重算前先把归档的 `receiver/cases/` 无损另存。不要在现有研究工作树中照搬这一操作。

```bash
python - <<'PY'
from pathlib import Path
cases = Path('build/microled-dynamic-v1/receiver/cases')
saved = cases.with_name('cases-from-release-reference')
if saved.exists():
    raise SystemExit('Reference directory already exists; inspect it before proceeding.')
if cases.exists():
    cases.rename(saved)
PY
python scripts/microled_dynamic_v1/analyze.py
```

新运行会从原生波形建立独立缓存和 case 摘要；原归档摘要保留在 `cases-from-release-reference/`，可核对新旧接收指标。请保留重算的版本、日志和差异，不用它覆盖已发布阶段的科学证据。`--only TT-A-C200fF-S40` 可作单 case 重建检查，但不能证明 33 个瞬态或完整半步长矩阵已重算。实际恢复覆盖范围以 `archive-restore.json` 为准。

这一恢复步骤作为本阶段 Release 的 `restore-addendum.md` 同时保存；Release 固定源码仍为原已验证的 source commit，主分支的交付回执另行记录补充说明。

## helper 自测

```bash
python3 scripts/microled_dynamic_v1/archive.py self-test
```

自测仅创建系统临时目录内的小 fixture，覆盖 explicit selection、原样锁定 bytecode、排除 env/cache、活跃写句柄、未确认冻结、源变化、pack/member verify、冲突拒绝、重复恢复及损坏归档拒绝。它不读取/打包实际运行中的 raw outputs，不上传、不操作 Git。
