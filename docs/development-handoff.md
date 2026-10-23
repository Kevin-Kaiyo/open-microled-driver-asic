# GitHub 备份与另一台电脑接续开发

更新：2026-10-23。项目定位为实验性研发方法验证与教学。备份保存当前设计、研究资料和指定实验的证据链；它不使仿真结果升级为实测结果，也不表示已经完成芯片制造签核。

## 当前阶段：慢热接收与快冷端电压修正（2026-10-23）

[新版中文研究报告](research/highspeed-nrz-pvt-20261023/index.html)、[真实新版 GDS 查看器](research/highspeed-nrz-pvt-20261023/layout-viewer.html)与[复现说明](research/highspeed-nrz-pvt-20261023/README.md)是当前入口。最终实际物理目录为 `build/highspeed-nrz-pvt-layout/final-r4`，仿真目录为 `build/highspeed-nrz-pvt/final-r4`。旧版模型与报告保留。

A 新增 48 × 1 µm、B 新增 58 × 1 µm 工艺输入电阻，并修改 DI 连线和衬底接地；B 的参考电阻改接已有固定 3.3 V 电源。相同 LED、输入码型和接收条件下，三组联合条件的最高离散通过点为 A 1 Gb/s、B 0.5 Gb/s。A 的 2 Gb/s 仍失败，快冷电压筛查余量约 9–11 mV，不能视为量产可靠性结论。

主表有 130 条记录（42 条只读基线引用、88 条本次正式运行的新仿真），另有 4 条寄生电容位置控制。整个探索与修复阶段新增 160 份波形，不应把 270 个引用/实际 case 目录当作 270 次新仿真。[阶段清单](../evidence/highspeed-nrz-pvt/phase-inventory.json)与[全部 186 份新旧唯一波形核验](../evidence/highspeed-nrz-pvt/phase-raw-validation.json)记录真实范围。

增量 Release：[`nrz-pvt-20261023`](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/nrz-pvt-20261023)。[逐文件清单](../evidence/backups/nrz-pvt-20261023.json)与[范围/排除项](../evidence/backups/nrz-pvt-20261023-scope.json)包含本轮仿真、候选失败、真实版图和诊断证据，以及公开依赖许可文本；不包含完整 PDK、工具、VM 或所有历史 build。原始日志中的本机路径属于环境溯源；跨机重新仿真应建立新 run，不能修改冻结输入来绕过身份核验。

先恢复上一阶段 `nrz-pex-20261020` 的基线原始结果与报告字体输入，再恢复本轮增量，保持相对路径。若要继续查看更早的 SCHEM 原始对照，还需下文 `research-20261019` 的 NRZ 组。

```sh
gh release download nrz-pvt-20261023 \
  --repo Kevin-Kaiyo/open-microled-driver-asic \
  --pattern 'nrz-pvt-20261023-*.tar.gz' \
  --dir build/github-download-nrz-pvt
python3 scripts/backup/release_bundle.py restore \
  --manifest evidence/backups/nrz-pvt-20261023.json \
  --asset-dir build/github-download-nrz-pvt --root .

build/layout/venv/bin/python scripts/highspeed_nrz_pvt_layout/validate_delivery.py
build/layout/venv/bin/python scripts/highspeed_nrz_pvt/validate.py \
  --work build/highspeed-nrz-pvt/final-r4
```

物理交付的独立校验器检查 123 个紧凑文件、实际 GDS 几何、四个开短路反例与 C 矩阵。这个回读检查不重新执行 DRC/LVS/PEX；完整重跑需按 `layout/pdk-lock.json` 及新增物理 README 准备匹配的环境。仅 Git 克隆可以阅读报告和查看紧凑版图，不能读取忽略的全部波形。

本轮源标签固定在 `136a1cc6e0659a28f2e9d37089e3252985e3c789`；后续备份回执进入主分支，标签保持不变。

- [本地归档核验](../evidence/backups/nrz-pvt-20261023-local.json)：17 个归档、2,400 个普通文件；原文件 7,182,890,437 字节，归档 7,142,581,572 字节。全部归档与逐成员 SHA-256/长度通过。
- [GitHub 回读](../evidence/backups/nrz-pvt-20261023-remote.json)：17 个归档及 4 份首批清单已全部流式回读，长度和 SHA-256 一致；3 份补充回执另见[补充回读记录](../evidence/backups/nrz-pvt-20261023-receipt-readback.json)。
- [独立恢复](../evidence/backups/nrz-pvt-20261023-recovery.json)：从 GitHub 新检出源标签，恢复 933 个物理过程文件；4 份相同的许可/NOTICE 原样跳过。核对 206 个源文件/精简证据及 123 个物理交付文件，通过实际 GDS 几何、负例和电容矩阵复核。
- 恢复检查使用同一台 macOS ARM 主机的独立目录，没有重跑 SPICE、DRC/LVS/PEX，也没有在该目录恢复与复算全部波形。全量归档字节和限定恢复执行范围分别记录。
- 再次核对全部 2,400 个原件哈希后，仅移除已核验的归档和独立检出副本，共 7,435,655,820 逻辑字节，见[清理回执](../evidence/backups/nrz-pvt-20261023-cleanup.json)。活动实验原件、失败证据、完整 PDK、VM 和工具均保留；APFS 可用空间约 12 GiB，不能将逻辑删除量当作等量的实际释放空间。

## 前一阶段：单通道 NRZ 版图与寄生比较

[研究报告](research/highspeed-nrz-pex-20261020/index.html)、[分层版图](research/highspeed-nrz-pex-20261020/layout-viewer.html)和[复现说明](research/highspeed-nrz-pex-20261020/README.md)为上一阶段入口。正式运行是 `build/highspeed-nrz-pex/run-0m3zyewc`；物理几何在 `r3` 冻结，修正电容模型在 `build/highspeed-nrz-layout/r4`。本阶段完成预声明的实验及独立核验，仍保留 PVT 失败和模型边界，未完成产品验证。

新增 Release 为 [`nrz-pex-20261020`](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/nrz-pex-20261020)，[归档清单](../evidence/backups/nrz-pex-20261020.json)和[范围/排除项](../evidence/backups/nrz-pex-20261020-scope.json)记录全部普通文件。包含新增仿真、物理过程、失败诊断和报告字体输入；不重复归档上一阶段只读引用的 SCHEM 波形，不包含完整 PDK、工具或虚拟机。

在新的检出目录中，先按本文后续步骤恢复 `research-20261019` 的 `nrz-evidence` 组，再恢复本轮增量：

```sh
gh release download nrz-pex-20261020 \
  --repo Kevin-Kaiyo/open-microled-driver-asic \
  --pattern 'nrz-pex-20261020-*.tar.gz' \
  --dir build/github-download-nrz-pex
python3 scripts/backup/release_bundle.py restore \
  --manifest evidence/backups/nrz-pex-20261020.json \
  --asset-dir build/github-download-nrz-pex --root .
```

恢复路径不能扁平化。正式仿真有 279 条分析记录，包含 74 条 SCHEM 基线及 GEOM/SNAP 控制复用；它不等于 279 次新仿真。`finalization.json` 固定最终哈希，`final-raw-inventory.json` 记录逐条波形核验，`integration-method-audit.json` 解释理想 DATA 取能/回灌的方法敏感性。重复分析先在独立目录进行，保留归档结果。

准备匹配的 Python/NumPy 环境后，可运行 `scripts/highspeed_nrz_pex/validate.py --work build/highspeed-nrz-pex/run-0m3zyewc` 和 `scripts/highspeed_nrz_layout/validate_delivery.py`。实际重跑物理流程还需固定完整 PDK、Magic、Netgen、KLayout 与独立 DRC 容器，安装入口见后文。此阶段的归档与恢复回执会分别记录文件完整性和实际执行的检查，不把恢复成功当作再次完成全部 EDA。

本轮源码标签固定在 `409c56a9da6c0d42f805cd87c6e0f79e96b03cba`；归档校验及恢复回执随后进入主分支，标签保持不变。

- [本地归档校验](../evidence/backups/nrz-pex-20261020-local.json)：15 个归档、3,000 个普通文件；原始 6,270,372,528 字节，归档 6,227,394,952 字节，归档及每个成员的 SHA-256 和大小均通过。
- [GitHub 回读核验](../evidence/backups/nrz-pex-20261020-remote.json)：15 个归档和 4 份清单全部从公开 Release URL 流式下载，长度及 SHA-256 均一致。此前本地逐成员验证的归档与远端字节相同。
- [独立恢复检查](../evidence/backups/nrz-pex-20261020-recovery.json)：从 GitHub 新检出上述提交，恢复 `nrz-physical-evidence` 和 `report-font-inputs` 两组共 483 个文件；重新核验 74 个精简物理交付文件、GDS/网表身份及电容矩阵，跟踪文件保持干净。
- 恢复检查发生在同一台 macOS ARM 主机的独立目录，没有重新恢复全部 6 GB 仿真数据、重跑 SPICE/DRC/LVS、重新分析所有波形或验证 Windows/Linux。全量归档的逐成员字节完整性由第一项验证，实际恢复范围由第二项验证，两者分别记录。
- [本次暂存副本清理](../evidence/backups/nrz-pex-20261020-cleanup.json)：远端回读通过后，再次计算全部 3,000 个保留原文件的 SHA-256；仅删除新生成的归档副本、独立恢复副本和临时检出目录，共 6,545,106,365 逻辑字节。活动原始数据、失败证据、PDK、虚拟机和工具均保留；APFS 实际可用空间变化不等同于逻辑字节数。

## 同步规则与存储分工

每个**已经验证的阶段完成后同步一次**：检查变更、更新报告、保存紧凑结果及来源哈希，然后推送 Git 提交与对应证据附件。采用阶段触发，不设置定时上传。正在运行、结果未检查的实验不作为新的已验证阶段发布。

| 位置 | 内容 | 接续开发时的用途 |
|---|---|---|
| Git 仓库 | 电路、RTL、生成与验证脚本、环境锁、报告、图片、最终 Blender 场景、紧凑证据与备份清单 | 克隆后可阅读研究结论、审阅设计和启动新开发 |
| GitHub Release 附件 | 清单列出的原始实验目录、大型数据及旧 Blender 备份 | 恢复既有实验，复算指定数据，审查历史场景 |
| 本地环境 | 完整 PDK、EDA 安装、Python 环境、Lima 虚拟机、应用与可重建缓存 | 按固定版本重新准备；不把整台电脑复制到 Git |

本阶段将超过 256 KiB 的稠密 CSV 和旧 `.blend1` 文件放入 Release 附件，按清单恢复到原项目相对路径。三个最终 `.blend` 场景总计约 48 MB，随 Git 保存，便于直接继续建模。报告引用 CSV 附件时，克隆后需要执行恢复；已有 HTML、图片和 MP4 不因此被当作原始波形或场景源码。

备份范围以 [`evidence/backups/research-20261019.json`](../evidence/backups/research-20261019.json) 的实际文件清单、长度和 SHA-256 为准。**这不是整个工作空间、全部历史 `build/`、虚拟机或全部 PDK 的备份。** 未列入清单的历史实验仍需保留在原机器，或另行完整归档。忽略列表中的大 CSV 若再次修改，也必须更新归档清单并发布新的阶段附件，不能仅检查 `git status`。上传成功也不自动删除本地副本；应先核对远端附件、恢复并校验，再依据当前开发依赖决定是否移走历史数据。

## 本阶段实际恢复检查

研究快照：[research-20261019](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/research-20261019)，源提交 `ee9cd265d7f3221b428d60cb5283a952e4ef0993`。后续验证回执另加在主分支和 Release 附件，保持该标签不变。

- [本地归档校验](../evidence/backups/research-20261019-local.json)：31 个归档、3,784 个普通文件；原始 12,299,538,316 字节，归档 6,274,853,490 字节；归档及逐文件 SHA-256 均通过。恢复工具 12 项测试通过。
- [GitHub 回读核验](../evidence/backups/research-20261019-remote.json)：31 个归档全部上传后重新下载，长度和 SHA-256 与本地已逐文件校验的归档一致。恢复测试使用这些本地归档；远端文件与其字节等价由该回执单独记录。
- [恢复与复算记录](../evidence/backups/research-20261019-recovery.json)：从 GitHub 新检出该提交，在另一个目录恢复 NRZ 与建模输入共 1,419 个文件；15 项算法自检和 472 项交付一致性检查通过。
- 重新分析正式 NRZ 批次的 36 组 DC 和 60 组瞬态；完整 `analysis.json` 与汇总 `summary.json` 均与归档逐字节一致，Git 跟踪文件没有因复算产生变化。该检查未重新运行 ngspice。
- 首次验证脚本把虚拟环境 Python 的符号链接解析成裸解释器，导致 NumPy 导入失败；改为调用虚拟环境原路径后通过。修正仅涉及临时验证脚本，未改动电路或分析方法。

这些检查发生在**同一台 macOS ARM 主机的独立检出目录**，没有验证 Windows／Linux 安装，也没有重跑单像素全部物理流程。它们证明指定文件可恢复且现有 NRZ 数据可复算，不构成硅片或光链路验证。

## 获取资料与恢复指定证据

需要 Git、GitHub CLI（`gh`）和 Python 3。以下命令在项目目录执行；Windows 可在 WSL2 终端执行同样的下载与恢复操作。Release 标签表示一个研究快照，开发时应另外检查当前分支是否已有更新。

```sh
git clone https://github.com/Kevin-Kaiyo/open-microled-driver-asic.git
cd open-microled-driver-asic
git checkout research-20261019

gh release download research-20261019 \
  --repo Kevin-Kaiyo/open-microled-driver-asic \
  --dir build/github-download

python3 scripts/backup/release_bundle.py restore \
  --manifest evidence/backups/research-20261019.json \
  --asset-dir build/github-download \
  --root .
```

部分历史目录包含指向 PDK 或冻结模型的符号链接；本次仅归档普通文件，排除项与原目标记录在 [范围清单](../evidence/backups/research-20261019-scope.json)。这些链接不影响已保存波形的阅读；重跑相关网表前需按锁准备模型，并由生成器建立新运行目录。

恢复后检查工具的文件长度及哈希核验结果。遇到已有文件冲突、缺失附件、哈希不一致或未知路径时，先调查原因，保留两侧文件；不要通过覆盖原文件或修改清单来消除错误。需要修改时，从已恢复的提交创建开发分支，例如 `git switch -c codex/next-driver-study`。

附件按实验组组织；只检查 NRZ 原始证据时，可按下列命令下载、恢复对应组，避免解压其他研究数据：

```sh
gh release download research-20261019 \
  --repo Kevin-Kaiyo/open-microled-driver-asic \
  --pattern 'research-20261019-nrz-evidence-*.tar.gz' \
  --dir build/github-download
python3 scripts/backup/release_bundle.py restore \
  --manifest evidence/backups/research-20261019.json \
  --asset-dir build/github-download --root . --group nrz-evidence
```

重绘中文图时还需下载、恢复 `blender-support` 组。分组选择参数及最终选项以 `python3 scripts/backup/release_bundle.py restore --help` 为准。

**资料恢复与实验复现是两项不同检查。** 哈希一致证明恢复的是归档字节；实验复现还需要相应工具版本、PDK、输入、完整日志和结果核对。重新仿真应创建新 run，与已归档实验并列保存。

## 当前指定的原始证据范围

下表是本轮归档的依赖依据，字节数为打包前原文件总量，压缩附件会更小。清单生成后以其实际覆盖范围为准。

| 路径 | 原文件字节数 | 必要性 |
|---|---:|---|
| `build/highspeed-nrz/` | 4,613,012,268 | 当前正式 96 组实验、数值诊断、两周期窗口检查、原型及本轮保留的失败记录；正式批次为 `run-0xqxvspp` |
| `build/layout-v3/` | 108,139,821 | r5 模拟宏、共同顶层、DRC/LVS/PEX 与修订失败过程 |
| `build/analog-v3/pex-r5-final-bleed10M-4ii_gn5t/` | 1,236,063,735 | 最终正常 PWM、故障保护及选定原始结果 |
| `build/analog-v3/pex-r5-bleed10M-startup-grid-dp8634q4/` | 2,740,862,525 | 最终报告选用的启动过程原始波形 |
| `build/analog-v3/pvt-pex-r5-bleed10M-xfzzdbuf/` | 903,181 | 当前工艺、电压、温度扫描 |
| `build/analog-v3/pex-r5-bleed10M-fftrial-x718575b/` | 31,218,631 | 启动数值探针引用的原始测试网表和失败背景 |
| `build/control-v3/sdf-r5-bleed10-zysigvwi/` | 62,978,521 | 当前数字时序到模拟电路的联动证据 |
| `build/control-v3/physical/final/` | 4,781,698 | 共同版图使用的实际数字 GDS、LEF、PNL 与时序输出 |
| `build/control-v3/inputs/` | 4,650 | 数字实现的冻结配置与 RTL |
| `build/startup-v3/numerical/` | 2,718,913,314 | 启动收敛研究的数值控制与失败记录；此处只计所选普通文件，不计环境符号链接 |
| `build/closure-v3/` | 3,251,704 | 报告渲染检查及验证器使用的 `layout-check.json` |

`scripts/closure_v3/validate.py` 会直接读取所选启动批次的 `waveform.dat`、冻结网表、日志与来源文件。仅恢复 `evidence/analog-v3/final/summary.json` 不足以重新执行该检查。物理来源校验还需要按锁重新安装完整 PDK；上表没有打包整个 PDK。

NRZ 的 `waveform.dat.gz` 已是无损压缩原始波形。分析器同时检查压缩文件与解压内容的 SHA-256、行数、有限值、严格递增时间和完整终点。恢复时保持文件名与内容，不把 `.gz` 更名为 `.dat`。其他历史验证器直接读取未压缩 `.dat`，Release 的外层压缩应在恢复时还原其原名与字节，不能自行改变引用格式。

## 重新准备仿真环境

先阅读[环境说明](environment.md)、[模拟版图环境](layout/README.md)、[数字物理实现说明](digital/physical.md)和[NRZ 复现入口](research/highspeed-nrz-20261019/README.md)。当前实际验证主机为 macOS ARM；跨平台安装成功不等于结果已经验证。

macOS ARM 的基本入口：

```sh
HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 \
  brew install ngspice icarus-verilog uv
uv python install 3.12.13
export UV_PYTHON=3.12.13
uv sync --locked
make setup
make test

# 需要完整 GF180 PDK、Magic、Netgen 和 KLayout Python 时：
bash scripts/layout/bootstrap_macos.sh
```

`uv.lock` 与 `scripts/layout/requirements.lock.txt` 固定 Python 依赖。`layout/pdk-lock.json` 固定当前完整 PDK build 和原生工具源码版本；`scripts/physical/pdk-lock.json` 记录物理输入文件哈希。`analog/models/pdk-lock.json` 只是模拟模型子集，不能替代完整物理 PDK。

Homebrew 安装命令可能取得比历史实验更新的二进制。当前 NRZ 验证使用 ngspice 47；保存实际 `ngspice --version`、Python、NumPy、EDA 工具版本，确认模型哈希，再运行数值控制和比较。不要仅凭软件名称相同就称为复现。

恢复原始 NRZ 证据后可先执行：

```sh
build/layout/venv/bin/python scripts/highspeed_nrz/metrics.py
build/layout/venv/bin/python scripts/highspeed_nrz/validate_delivery.py
```

需要复算波形时，使用 `analyze.py --work build/highspeed-nrz/run-0xqxvspp`；先保存归档结果，避免覆盖而失去原结果对照。需要新实验时，运行 `run.py --stage all --workers 2` 创建新的 `run-*`。仿真批次至少留出 6 GiB 临时空间；原始数据完整恢复所需空间另按清单总量计算。

## macOS、Windows 与 Linux 的差异

| 场景 | 当前可做的事 | 仍需处理的条件 |
|---|---|---|
| 任意平台阅读 | Git 克隆后阅读 HTML、图片、研究报告；恢复附件后检查数据和 Blender 场景 | 本地文件链接、字体及浏览器差异可能影响排版 |
| macOS ARM 仿真与版图 | 使用已有 bootstrap、锁定模型及现有原生流程 | Xcode SDK、Homebrew 二进制与版本仍需检查 |
| Windows | 可在 WSL2 内准备 Python、ngspice、RTL 工具；Blender 场景可由对应平台 Blender 打开 | 尚未验证完整 ASIC 流程；不能直接运行 macOS `.app`、Homebrew 路径或 VZ 虚拟机 |
| Linux / x86 主机 | 可另建原生或容器环境并按输入锁核对 | 当前 Lima 配置是 ARM/macOS 专用；容器镜像的目标架构和实际工具版本必须另行验证 |

已知不可直接移植的位置：

- `scripts/physical/lima.yaml` 固定 `vz`、`aarch64` 和旧主机的项目挂载路径。新机器应生成符合实际路径和架构的新配置，并保留变更记录。不要复制正在运行的 Lima 磁盘作为可移植工具环境。
- 历史生成的 SPICE 网表含 `/Users/kimmy/Projects/open-microled-driver-asic/...` 绝对 `.include` / `.lib` 路径。恢复字节后仍可审查、分析已有波形；在别的目录直接重跑该历史网表会找不到输入。应由当前生成器创建新 run，或在独立副本中重定位路径、记录变更，保留归档原件。
- NRZ 结果通常保存项目相对路径，分析器以仓库根目录定位；因此必须按清单恢复原相对目录结构。不能把所有波形扁平放到一个文件夹。
- Blender / PDF 脚本有 `/opt/homebrew/bin/ffmpeg`、macOS 字体、Chrome 以及个人 Playwright 安装路径。其他平台需配置工具位置，并重新检查输出图像、字体和媒体完整性。
- `highspeed_nrz/report.py` 使用 `build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf`；重新生成中文图之前必须恢复该字体和许可证。

## Blender 接续与可重建文件

最终 `.blend`、MP4 和报告图片随 Git 保存，历史 `.blend1` 从 Release 恢复；字幕、映射和证据记录按 Git 或附件清单定位。以下 `build/` 文件体积小，却是当前生成链的明确输入：

| 路径 | 原文件字节数 |
|---|---:|
| `build/blender-demo/geometry-3d.json` | 4,853,697 |
| `build/blender-demo/stack-audit.json` | 7,609 |
| `build/blender-demo/audit-manifest.json` | 831 |
| `build/blender-pwm-animation/mapping.json` | 74,571 |
| `build/blender-pwm-animation/mapping-notes.md` | 1,775 |
| `build/blender-pwm-animation/fonts/` | 16,441,665 |

媒体过程可另保留 `chapters.ffmeta`、`render.log`、`decode.log` 和 `encode.log`。Blender 应用安装、下载的 DMG、完整逐帧 PNG 缓存没有作为本阶段跨机归档的必要内容。版本与原 Mac ARM 下载 SHA 记录在 `evidence/blender-demo/verified.json`；其他平台应使用相应构建并另记版本与校验。

已恢复的 `.blend` 可直接打开。需要从 GDS 重新生成几何时，先安装匹配 PDK 和 KLayout Python，再按顺序执行：

```sh
build/layout/venv/bin/python scripts/blender_demo/prepare_geometry.py
build/layout/venv/bin/python scripts/blender_animation/prepare_mapping.py --help
```

`prepare_mapping.py` 默认保护已有映射，应选择新的输出目录进行比较。之后才执行 Blender 场景构建、验证和渲染。`finalize.py` 需要完整逐帧 PNG，因此未恢复渲染缓存时，不能把它当作可直接执行的轻量校验；可先检查已交付 MP4 / `.blend` 的哈希，再按需重渲染。

Blender 图像使用真实 GDS 的 XY 几何和公开技术文件的名义层高作教学表达；层间展开与 Z 放大不是制造结构仿真，不能提供新的电路、光学或工艺签核结论。

## 每个阶段完成后的最小检查

1. 记录实际完成范围、失败项、输入模型、工具版本及对应结果；先运行该阶段的验证入口。
2. 审阅新增文件，保持公开来源、许可证和项目保密边界；确认没有凭据或机器私有数据进入提交。
3. 代码、报告与紧凑证据入 Git；大数据按相对路径、长度、哈希生成附件清单，保留与提交/阶段的关联。
4. 推送并核验远端提交，上传附件并回读校验。至少做一次独立恢复检查，记录哪些验证实际执行、哪些只检查了文件完整性。
5. 更新此接续说明中的入口与实际覆盖范围。清理本地旧数据前，确认归档覆盖、恢复结果和当前实验依赖。

下一台电脑应能明确判断：已经取回哪些文件、可直接阅读哪些结果、还需准备什么环境、哪些检查尚未执行。这个判断依据实际清单与检查记录，不依据“已经上传”一句话。
