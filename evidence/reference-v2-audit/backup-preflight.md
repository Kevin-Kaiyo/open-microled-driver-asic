# Reference v2 备份交付只读预审

审查日期：2026-10-24。审查目录：`build/github-sync-reference-v2-20261024/`。

本次只读取助手、当前文件清单和冻结输入，未执行 selection、pack、upload、readback、恢复、仿真或清理。唯一新增文件为本报告。下面的命令是父级完成全部报告/证据冻结之后的执行说明，不是已完成记录。

## 结论与冻结前条件

1. 当前范围覆盖本轮 NRZ/PWM 的候选、失败、执行源、输入、原始波形和新物理/独立审计目录。两路选定 DC 的冻结输入哈希全部一致，且进入小输入包；没有发现选定电路或提取网络遗漏。
2. `upload.py` 与顺序 `readback.py` 有明确的远端仓库、tag→commit、大小和 SHA 验证。恢复器逐成员验证并拒绝覆盖不同内容。建议本轮直接使用顺序回读入口；`readback_parallel.py` 不能独立首跑。
3. 此时 HEAD 仍为基线 `112ba95969ac6a2141c305324ea694e7b96c0765`，本轮公共文件尚未提交。必须先等所有写入者结束，再提交预期公共文件、确定新 commit，才执行 `prepare_selection.py`。该助手只检查 commit 存在，不替父级检查“新源已经全部提交”。

审查时 `evidence/pwm-reference-v2/20261024/validation.json` 尚不存在，虽然 PWM README 引用了它。这属于冻结前待完成输出；不能据当前清单称全部交付已经冻结。父级应在最终验证/报告生成完成后重新取得正式 inventory。本文数字是只读预审快照。

## 当前范围、大小和排除项

`backup_common.py` 仅遍历以下四个新目录，并额外包含报告字体及其许可证：

| 分组 | 文件数 | 字节数 |
|---|---:|---:|
| nrz-inputs | 305 | 19,502,939 |
| nrz-metadata | 1,798 | 27,054,921 |
| nrz-waveforms | 388 | 3,816,124,086 |
| pwm-inputs | 94 | 3,435,615 |
| pwm-metadata | 1,387 | 21,541,120 |
| pwm-waveforms | 458 | 1,049,234,508 |
| physical-evidence | 1,148 | 44,091,625 |
| audit-metadata | 11 | 303,748 |
| audit-waveforms | 8 | 180,688 |
| report-support | 2 | 16,441,665 |
| 合计 | 5,599 | 4,997,910,915 |

四个根目录为 `build/nrz-reference-v2/`、`build/pwm-reference-v2/`、`build/reference-v2-layout/` 和 `build/reference-v2-audit/`。字体为 `build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf`，同时保留 `LICENSE.txt`。

当前排除 576 个符号链接和 7 个 Python bytecode 目录。576 个链接的目标均存在、均为仓库内路径、均已独立选入本轮 regular files；没有目标未覆盖或仓库外链接。恢复时要重建为相对链接，不能照搬旧绝对路径。

最大单文件为 NRZ 最紧数值配置的 `waveform.dat.gz`，489,002,113 B，约 466.35 MiB，低于 480 MiB 单文件/分包目标。助手另检查最终归档不得超过 512 MiB。当前 pack 的保守可用空间门槛是 7,732,244,584 B，审查时可用 10,292,731,904 B；实际运行前仍须重新检查。这个门槛包括完整归档副本和 2 GiB 预留，不代表已经预分配空间。

六个核心小组（NRZ/PWM inputs、metadata、physical-evidence、report-support）共 4,734 个文件、132,067,885 B 未压缩数据。可以不下载两路大 waveform 分组而完成 DC smoke 和物理证据回读。若同时保留本轮独立小型 AC 审计原件，再取 `audit-metadata`、`audit-waveforms`，只增加 484,436 B。

未纳入本轮 Release 的环境依赖：完整 PDK、规则 deck 安装、Magic/Netgen/KLayout/ngspice/Icarus 工具、VM、Python 环境。旧阶段大波形和完整旧物理目录由 `driver-robustness-20261024` Release 保留。本轮 scope 已写明这一依赖。历史失败没有因分组或排除而被删去。

## 公共 Git 文件与电路完整性

审查时新增非忽略 regular files 共 1,608 个、91,730,551 B。没有大于 10 MiB 的文件，也没有原始大波形误入 Git。最大的两个文件为：

- `evidence/reference-v2-layout/visuals/nrz-switched-keeper-joint-r1.svg`：5,460,990 B。
- `evidence/reference-v2-layout/visuals/nrz-joint-r1c.svg`：5,430,260 B。

另外三个超过 1 MiB 的文件为 `vi-power-comparison.svg`（3,628,029 B）、`N-layout.svg`（3,249,484 B）、`N-geometry.json`（1,263,956 B）。这些是公开 PDK 独立实现的版图图形/几何证据，体积适合当前单次里程碑；SVG 冗长会增加后续 Git 历史体积，但本次没有必要重写已冻结证据。新增公共体积主要来自 physical evidence 约 52.56 MB 和 PWM 紧凑 JSON/CSV 约 29.90 MB。

已核实以下网络真实存在：

| 网络 | SHA-256 | 位置与边界 |
|---|---|---|
| 最终 NRZ 21MOS+RIN fullRC | `925b0e98ede116b7d3dc0c0f326aa1704fd08b84dd8cabe39cf03ae4ac4f3d6a` | build 和 `evidence/reference-v2-layout/nrz-switched-keeper-joint-r1/J/full-rc/nrz_reference_integrated_rc.spice` 字节一致，均 33,331 B |
| 最终 PWM 沿用的 39MOS fullRC | `d6ebc340c5f2096c43e1358b851d68590fefddbf47b5cc6e746ffc3c12851424` | `build/pwm-reference-v2/20261024/inputs/dut.spice`，22,338 B，进入 pwm-inputs |

NRZ 最终 compact 物理目录含 125 个文件、6,869,530 B，包括真实 GDS、fullRC、geometry-only、电路源、原始/修正提取、DRC/LVS 报告及负控。它不是仅有摘要哈希。`analog/nrz_reference_v2/selected_integrated_geometry.spice` 是实际几何电路副本，不能把它当作 fullRC。

本次只读重新计算了 NRZ 最终 manifest 的 30 项输入 SHA，以及 PWM `c15_dc` manifest 的 22 项输入加 1 项执行 runner SHA；全部匹配，全部在小组范围内。PWM 完整旧 GDS/物理审计没有被重新宣称为本轮新物理结果；本轮输入包中的 `dut.spice` 已足够重跑选定电气案例，重新审查旧物理来源仍需既有 Git/上一轮 Release。

## 助手逻辑与待保留的审计材料

- `prepare_selection.py` 用独占创建防止覆盖旧 selection，记录 size/mtime/mode/group/SHA，再次比较清单和排除项。
- `pack.py` 在打包前复核所有输入 SHA，调用公共 `scripts/backup/release_bundle.py`，逐 tar 成员验证，再检查文件清单稳定性。pack 中途失败时，已完成的 archive 会留下且后续重跑拒绝覆盖；应调查后使用另一个明确的 staging，不能随手删除原始证据。
- `upload.py` 不使用 clobber。同名已有资产会先实际下载流式 SHA 验证，只有一致才作为续传成功。
- `readback.py --execute --resume` 仅在远端 asset ID、size、state、expected SHA 和可用 digest 均一致时复用旧收据。无 `--resume` 是完整重新流式回读。每次 4 MiB 分块，不落地大下载副本。
- `release_bundle.py restore` 先验证全部所选 archive 和成员，再预检全部目标。不同内容文件、symlink 路径、路径逃逸、重复/非 regular tar 成员均拒绝；相同文件可跳过。它不重写归档中旧绝对路径。
- `restore_symlinks.py` 默认预览。它预检 scope 中全部链接目标，没有 `--group` 过滤；若只恢复少量单 case，就不要执行全 scope 链接重建。按本文六个小组恢复时，当前 576 个目标齐全。独立 reproducer 本身会重新建立新运行目录，不依赖旧 case 链接。
- `readback_parallel.py` 除进度文件外还要求 `readback-parallel-control.json`、`readback-transition.json` 和其串行进度快照；当前没有生成 transition 的配套入口。因此本文只给可独立工作的顺序命令，避免把并行 resume 当首跑。

**需要父级另行保存的审计材料：** `build/` 被 Git 忽略，当前 Release 上传列表只包含两份恢复助手 `restore_symlinks.py`、`backup_common.py`，不包括 prepare/pack/upload/readback/test 脚本、`upload-index.json`、最终 remote receipt 或恢复验证回执。这不妨碍已验证小包的电气恢复，但会使“如何执行备份和验证”的本轮实现与证据依赖本机 staging。建议交付时把这些小型助手、精确 SHA、upload-index、remote/recovery receipts 保存在公开 compact backup evidence（或作为额外 Release assets），不要只留在未来可能清理的 staging。本审查未擅自修改上传集合。

本次只对 8 个助手做了 AST 解析，全部成功。未运行会创建临时文件的 `test_tools.py`，也未执行网络测试。现有 `test_tools.py` 覆盖分组/排除、输入漂移、流式 SHA 与链接预检冲突；不覆盖真实 GitHub 和本轮完整恢复，这些仍需下列正式步骤。

## 准确 pack / upload / readback 命令

以下命令在源仓库根目录执行。先由父级完成公共文件审查、提交及 source commit 推送；`refv2_commit` 必须是本轮新提交，不能仍为上述基线。先审阅 `git status --short`，确认预期公共文件未遗留为 untracked。执行前所有四个 build 根目录写入者必须停止。

```sh
refv2_python=/Users/kimmy/Projects/open-microled-driver-asic/build/layout/venv/bin/python
refv2_stage=build/github-sync-reference-v2-20261024
refv2_tag=reference-v2-20261024
refv2_repo=Kevin-Kaiyo/open-microled-driver-asic
refv2_commit=$(git rev-parse HEAD)
test "$refv2_commit" != 112ba95969ac6a2141c305324ea694e7b96c0765
git status --short

"$refv2_python" -B "$refv2_stage/test_tools.py"
"$refv2_python" -B "$refv2_stage/prepare_selection.py" \
  --freeze-ack --source-commit "$refv2_commit"
"$refv2_python" -B "$refv2_stage/pack.py" --execute
```

pack 成功后读取 `reference-v2-20261024-local.json`，必须有 `all_archive_and_member_hashes_verified: true`。此时才建立/使用指向同一 commit 的远端 tag 和 Release；不要移动旧 tag，不要用覆盖开关。若父级已创建正确 tag/Release，跳过创建：

```sh
git tag -a "$refv2_tag" "$refv2_commit" -m 'Reference v2 frozen research evidence'
git push origin "refs/tags/$refv2_tag"
gh release create "$refv2_tag" --repo "$refv2_repo" --verify-tag \
  --title 'Reference v2 research evidence 2026-10-24' \
  --notes 'Frozen NRZ/PWM reference experiments, retained failures, actual layout evidence, and SHA-256 restoration manifest. Experimental R&D evidence; not silicon or reliability qualification.'

"$refv2_python" -B "$refv2_stage/upload.py" --execute
"$refv2_python" -B "$refv2_stage/readback.py" --execute
```

只有顺序 readback 曾中断时使用：

```sh
"$refv2_python" -B "$refv2_stage/readback.py" --execute --resume
```

最终检查 `reference-v2-20261024-remote.json` 的 commit、manifest SHA 和 `all_expected_assets_verified: true`。保留整个 receipt，不能只保留一行“上传成功”。

## 从 GitHub 下载小包并恢复验证

下面在同机新目录验证；不重跑全矩阵/EDA，不修改源工作区。选择一个尚不存在的新目录。另一台机器需自行安装匹配的 Python/NumPy、ngspice、Icarus/vvp 和 KLayout Python 包，不能依赖这里的原机器 venv 绝对路径。

```sh
refv2_recovery=/Users/kimmy/Projects/open-microled-driver-asic/build/github-recovery-reference-v2-20261024
test ! -e "$refv2_recovery"
mkdir -p "$refv2_recovery/downloads" "$refv2_recovery/check-evidence"
git clone --branch "$refv2_tag" --single-branch \
  https://github.com/Kevin-Kaiyo/open-microled-driver-asic.git \
  "$refv2_recovery/repository"
test "$(git -C "$refv2_recovery/repository" rev-parse HEAD)" = "$refv2_commit"

gh release download "$refv2_tag" --repo "$refv2_repo" \
  --dir "$refv2_recovery/downloads" \
  --pattern "$refv2_tag.json" --pattern "$refv2_tag-scope.json" \
  --pattern 'restore_symlinks.py' --pattern 'backup_common.py' \
  --pattern "$refv2_tag-nrz-inputs-*.tar.gz" \
  --pattern "$refv2_tag-nrz-metadata-*.tar.gz" \
  --pattern "$refv2_tag-pwm-inputs-*.tar.gz" \
  --pattern "$refv2_tag-pwm-metadata-*.tar.gz" \
  --pattern "$refv2_tag-physical-evidence-*.tar.gz" \
  --pattern "$refv2_tag-report-support-*.tar.gz"
```

在运行下载的恢复助手之前，将 manifest、scope、两份 helper 的 SHA 与已核实、独立保留的 `upload-index.json`/remote receipt 比较。不要只用同一下载包自身提供的未核实 SHA 作为来源身份。archive 和逐文件 SHA 由公共恢复器进一步检查：

```sh
cd "$refv2_recovery/repository"
"$refv2_python" -B scripts/backup/release_bundle.py restore \
  --manifest "$refv2_recovery/downloads/$refv2_tag.json" \
  --asset-dir "$refv2_recovery/downloads" --root "$PWD" \
  --group nrz-inputs --group nrz-metadata \
  --group pwm-inputs --group pwm-metadata \
  --group physical-evidence --group report-support

"$refv2_python" -B "$refv2_recovery/downloads/restore_symlinks.py" \
  --root "$PWD" --scope "$refv2_recovery/downloads/$refv2_tag-scope.json"
"$refv2_python" -B "$refv2_recovery/downloads/restore_symlinks.py" \
  --root "$PWD" --scope "$refv2_recovery/downloads/$refv2_tag-scope.json" --execute
```

`restore` 本身包含 archive+member verify，无需为相同已下载小包重复一次 verify。首次恢复计数应等于最终 manifest 六组文件计数；本文快照为 4,734。若只想先验证下载、不写恢复目录，可把 `restore` 换成 `verify` 并去掉 `--root`。

运行两个新 DC 与新 NRZ 物理证据回读：

```sh
mkdir -p build/recovery-checks
"$refv2_python" -B scripts/nrz_reference_v2/reproduce.py \
  --source-work build/nrz-reference-v2/selected-final-r2 \
  --out build/nrz-reference-v2/github-recovery-smoke-dc --smoke-dc
"$refv2_python" -B scripts/pwm_reference_v2/reproduce.py \
  --source build/pwm-reference-v2/20261024 --case c15_dc \
  --destination build/pwm-reference-v2/github-recovery-c15-dc
"$refv2_python" -B scripts/reference_v2_layout/validate.py \
  --run build/reference-v2-layout/nrz-switched-keeper-joint-r1 \
  --out build/recovery-checks/nrz-selected-physical-validation.json
```

如需要再核实其独立 12MOS 模块，同一小包已经包含对应证据：

```sh
"$refv2_python" -B scripts/reference_v2_layout/validate.py \
  --run build/reference-v2-layout/vi-switched-keeper-pg-r1b \
  --out build/recovery-checks/nrz-module-physical-validation.json
```

这里两条 physical validation 均是现有证据回读：逐个 SHA、LVS/DRC 报告、实际 GDS 几何与负控检查；**不运行新 Magic/Netgen/KLayout DRC/PEX**。本轮 PWM 没有新片内版图，不应把这两条 NRZ 回读写成“两路新 EDA 通过”。若验证旧 PWM 39MOS 物理来源，须按上一轮 Release 的恢复说明恢复它自己的原目录并使用其对应验证入口。

NRZ `reproduction-check.json` 必须记录 `reproduction_passed: true` 和 `current_difference_A`；PWM `reproduction.json` 必须记录 `current_delta_from_original_a`、`dc_error_pct`、工具版本及原/新输入/deck/raw SHA。PWM reproducer 对 DC 只断言电流在 ±5%，**不会自行把原/新电流差判为合格**；恢复报告须独立核对数值差，不能只看退出码或 `raw_byte_identity_to_original`。同机建议以 |差值| < 1e-12 A 核对两路；跨工具版本必须明确容差和实际差值。

将两路 reproduction receipt、case result/analysis（有则保存）、ngspice/RTL 编译日志、physical validation JSON、下载哈希、source commit、restore counts、每条命令/退出码保存在外层 `check-evidence/` 与 `recovery.json`。这些应在临时 checkout 之外另行保留后才构成可交付恢复证据。本说明没有授权或执行任何清理。

## 本次读到的助手 SHA-256

| 文件 | SHA-256 |
|---|---|
| backup_common.py | `01994295731ffdd0469c49ed415a57fd516417835060f1ac16ce2f25b90b34c0` |
| prepare_selection.py | `3eea28c83dc5e82367e6af5361e9e8f33aaa6543ffda537c7c519e591d5f57eb` |
| pack.py | `66227358774d9796857b3c91ac8ed3dd9bf1f497b94c26ccc32517b3682406d2` |
| upload.py | `ea3c35b268bf350d80659e7166ae3e5cbc00dddd381c4da8f817016d8370526f` |
| readback.py | `bfa6d2912302045e7d9303fe4a62c00d19f57f032cffe45de071fdca118687eb` |
| readback_parallel.py | `9c841d44d0ede0957cd437e6fc86d375dcc8257801b1fbf6d41b59ff9d4c95d6` |
| restore_symlinks.py | `c90ec6127b5dd31c90d8bc686c20dd4f43a3d0dc4f610153d359ca530d97428a` |
| test_tools.py | `ab12b61a66aa82707699c91e16cb1184ed83d7c005708ac29d6e198f6b0c24e9` |

之后若父级修订备份集合或助手，应记录新 SHA 和理由，不将本表冒充修订后的执行身份。
