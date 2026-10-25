# Fair-driver 2026-10-25 备份与恢复

本目录仅准备工具。完成实验、停止所有写入、提交公开源码后，才可执行 `freeze`；`pack`、上传、远端回读和恢复验证是后续独立步骤。工具没有删除实验原始数据或自动上传的功能。

## 实现计划与状态

**Goal:** 对本轮三个 build 目录做逐文件可核对的 Release 备份，并允许只恢复小分组重新运行 DC。

**Architecture:** `prepare.py` 清点并冻结显式文件清单，再调用已有 `release_bundle.py` 分卷和逐成员校验。`readback.py` 只读公共 Release，逐块计算 SHA-256，不保存大下载副本。

**Tech Stack:** Python 标准库、现有 `release_bundle.py`、Git/GitHub CLI；DC 恢复另需匹配的 Python/NumPy/ngspice。

**Spec:** 本轮已授权范围仅为下列三个目录；不得因功能失败排除证据，不跟随 symlink，原始数据保留。执行者是父任务；本工具准备阶段不打包、上传或提交。

- [x] `prepare.py`：只读清点、显式冻结、480 MiB 目标分卷与本地逐成员校验。
- [x] `readback.py`：流式回读、可恢复进度、读回前后核对远端身份。
- [x] 自检：范围/失败保留、symlink、bytecode、变更拒绝、分卷边界、进度原子写入、目录扫描错误；不创建归档。
- [ ] 所有 writers 停止、公开 source commit 确认后冻结并打包。
- [ ] 上传、远端回读、独立目录恢复与 DC 复跑。

Review focus：扫描错误不能静默漏备；selection 的 group 必须与 inventory 一致；上传索引必须绑定 manifest；进度文件不能跟随 symlink；回读过程中 tag/asset 变化必须阻止成功回执。

## 固定范围与分组

仅遍历普通文件：

```text
build/fair-driver-v1
build/fair-driver-v1-a-probe
build/fair-driver-v1-c-probe
```

失败、部分输出、日志、校准中间点、`matched-r1` 存储原型和完整 native B 对照均包括在内。只排除 `.pyc/.pyo`；所有 symlink 均逐项记录且不解引用。不包含全 PDK、VM、Python 环境、其他历史 build。目录扫描错误直接失败。

| 分组 | 内容 | 恢复用途 |
|---|---|---|
| `inputs` | `inputs/**`、`execution-sources/**`、manifest、stimulus | 冻结电路、模型子集、执行源码、刺激 |
| `results` | 其余普通文件，包括 case/result、原 deck、日志、校准等 | 恢复案例条件、历史数值及失败证据 |
| `waveforms` | `.dat/.dat.gz/.raw/.raw.gz/.vcd/.vcd.gz/.fst` | 原始波形复查；重新运行 DC 不需要下载 |

分组以文件路径/后缀决定，不根据通过/失败状态筛选。两个小组共同具备重新生成 DC deck 的必要输入；它们不是已经完成复跑的证明。原 deck 包含绝对路径，应保留原字节并在新 work 中生成新 deck。

每卷所含原文件总长度最多 480 MiB；单文件超过此值直接停止，不会自动切断或遗漏。压缩归档上限 512 MiB。最终范围预期小于 2 GiB，超出会停止等待范围审查。打包需要原文件大小的 1.02 倍加一卷余量，并保留 5 GiB 可用空间。不得通过删除原数据绕过门槛。

## 现在可执行的只读检查

在仓库根目录执行：

```sh
python3 -B scripts/backup/fair-driver-20261025/prepare.py self-test
python3 -B scripts/backup/fair-driver-20261025/readback.py --self-test
python3 -B scripts/backup/fair-driver-20261025/prepare.py scan
```

`scan` 仅打印瞬时范围和分卷预估，不写入冻结清单。自检只使用可丢弃的合成临时文件，不运行仿真、不创建归档、不联网。

## 停止写入之后：冻结与打包

先完成公开源文件审查和提交，由父任务提供完整 40 位 source commit。该提交须等于当前 HEAD；本轮 analog/scripts/evidence/report/backup 路径须干净且已提交。备份助手本身和通用 bundle 工具必须与该提交逐字节相同。

```sh
python3 -B scripts/backup/fair-driver-20261025/prepare.py freeze \
  --freeze-ack --source-commit <完整40位source_commit>
python3 -B scripts/backup/fair-driver-20261025/prepare.py pack --execute
```

状态写入 `build/github-sync-fair-driver-20261025/`。冻结记录每个原文件的 size、mtime、mode、group、SHA-256；哈希前后检查完整文件集。打包前后再次核对原文件，包括新增文件和内容变动。pack 使用 Python API 传入 `target_bytes=480*1024**2`，并独立验证每卷大小、全部成员哈希与所属组。既有清单和资产拒绝覆盖；失败留下的阶段产物须人工审查，脚本不会自动清空后重试。

输出为 `fair-driver-20261025-{scope,inventory,selection,local}.json`、归档 manifest `fair-driver-20261025.json`、`assets/*.tar.gz` 与 `upload-index.json`。实验 manifest 中的历史 source commit 不会被改成此次交付 commit；原执行源码哈希仍是实验来源依据。

## 上传与流式回读

仅在父任务已审阅最终清单并授权发布后操作。固定目标是公共仓库 `Kevin-Kaiyo/open-microled-driver-asic`、标签 `fair-driver-20261025`。父任务先推送精确源码/标签并创建指向该提交的 Release；本工具不创建、移动或覆盖标签，也不创建 Release。

以下上传段读取本地核验过的索引，按小清单、小分组、大波形顺序上传。没有 `--clobber`，同名资产冲突应停止审查。

```sh
python3 -B - <<'PY'
import importlib.util, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode = True
path = Path('scripts/backup/fair-driver-20261025/prepare.py').resolve()
spec = importlib.util.spec_from_file_location('fair_backup', path)
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
index = p.expected_uploads()
for item in index['files']:
    subprocess.run(['gh', 'release', 'upload', index['tag'],
                    str(p.stage_dir() / item['local_path']), '--repo', index['repository']], check=True)
PY
python3 -B scripts/backup/fair-driver-20261025/readback.py --execute
```

中断后可使用 `--execute --resume`。只有相同 tag/source commit、upload-index SHA、asset ID、updated_at、size、SHA 的已验证项可以复用；其余重新流读。每次至多保留一个 4 MiB 数据块及 HTTP 缓冲，不在磁盘保存归档下载副本。结束时再查 tag、Release 和每项资产身份。`*-remote.json` 表示远端字节与本地已逐成员验证的归档一致，**不表示异机恢复或 DC 复跑已完成**。

没有自动清理入口。原 raw、失败、模型、工作目录和归档均保留。远端回读通过也不会触发删除。

## 小分组恢复与 DC smoke

在独立检出目录使用记录的 source commit，并先检查 manifest 的 SHA 与交付回执一致。manifest 的 SHA 必须来自可信的交付回执；只验证归档与一个任意 manifest 一致不能证明来源。

只下载 manifest、scope 与两个小分组；不下载 waveforms：

```sh
gh release download fair-driver-20261025 \
  --repo Kevin-Kaiyo/open-microled-driver-asic --dir recovery-downloads \
  --pattern fair-driver-20261025.json \
  --pattern fair-driver-20261025-scope.json \
  --pattern 'fair-driver-20261025-inputs-*.tar.gz' \
  --pattern 'fair-driver-20261025-results-*.tar.gz'
python3 -B scripts/backup/release_bundle.py restore \
  --manifest recovery-downloads/fair-driver-20261025.json \
  --asset-dir recovery-downloads --root . --group inputs --group results
```

`restore` 先验证每卷及成员，再检查全部目标路径。同内容文件跳过；内容不同则拒绝覆盖。保持下载归档静止，避免校验后再读取时被另一进程改动。中断可能留下已恢复文件，须保留回执并核查后重试；没有事务回滚或自动清理。

安装匹配运行时和 ngspice 后，下面使用实际冻结 runner，仅重定位其路径常量；电路、模型、判据保持原字节。运行位置必须是新检出的仓库根目录。`recovery-dc-r1` 必须不存在，原恢复证据不修改。

```sh
python3 -B - <<'PY'
from pathlib import Path
import hashlib, importlib.util, json, math, shutil, subprocess
root = Path.cwd().resolve()
scope = json.loads((root / 'recovery-downloads/fair-driver-20261025-scope.json').read_text())
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == scope['source_commit']
source = root / 'build/fair-driver-v1/matched-r2'
original = json.loads((source / 'cases/DC-TT-B-L0/result.json').read_text())
runner_path = source / 'execution-sources' / ('run-' + original['runner_sha256'] + '.py')
assert hashlib.sha256(runner_path.read_bytes()).hexdigest() == original['runner_sha256']
work = root / 'build/fair-driver-v1/recovery-dc-r1'
assert not work.exists(), 'Refuse overwrite of an earlier recovery'
shutil.copytree(source / 'inputs', work / 'inputs')
for name in ('manifest.json', 'stimulus.json'):
    shutil.copy2(source / name, work / name)
spec = importlib.util.spec_from_file_location('frozen_fair_runner', runner_path)
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
runner.ROOT = root
runner.BUILD = root / 'build/fair-driver-v1'
runner.MODELS = source / 'inputs'  # No init/model copying is used; all inputs already restored.
case = dict(original['case'], name='DC-TT-B-L0-recovery')
fresh = runner.run(work, case)
assert fresh['simulation_ok'] and 'metrics' in fresh, 'Retain failing logs; DC not reproduced'
delta = fresh['metrics']['i_led_A'] - original['metrics']['i_led_A']
powers = {k: fresh['metrics']['energy'][k]['DC_power_W'] - v['DC_power_W']
          for k, v in original['metrics']['energy'].items()}
passed = abs(delta) <= 1e-12 and all(abs(x) <= 1e-10 for x in powers.values())
receipt = {'source_commit': scope['source_commit'], 'runner_sha256': original['runner_sha256'],
           'path_relocation_only': ['ROOT', 'BUILD', 'MODELS'], 'case': case,
           'current_difference_A': delta, 'port_power_differences_W': powers,
           'original_current_A': original['metrics']['i_led_A'],
           'fresh_current_A': fresh['metrics']['i_led_A'], 'reproduction_passed': passed,
           'boundary': 'One TT B low-level DC only; no waveform download, NRZ rerun or physical EDA.'}
(work / 'recovery-check.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
assert passed, 'Numerical difference exceeds predeclared DC recovery tolerance'
PY
```

以上是恢复操作示例；本批次实际执行脚本、下载SHA、恢复文件数、命令/退出码、fresh DC result/log与比较回执见下方验收链接。恢复成功与原电路功能是否合格分别报告。

## 本批次已完成验收

见[交接与验收回执](../../../docs/development-handoff.md)。源码标签保持`d203aa748de36c96a4d51605bc5acaae94b0b759`，验收回执另提交到main。原始3树保留；父任务在完整远端读回与新检出单DC通过后，手动移除了7个暂存tar重复副本。工具仍无自动清理行为。需要本地归档的入口应先按清单从Release重新下载并核SHA。
