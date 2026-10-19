# GitHub 备份与另一台电脑接续开发

更新：2026-10-19。项目定位为实验性研发方法验证与教学。备份保存当前设计、研究资料和指定实验的证据链；它不使仿真结果升级为实测结果，也不表示已经完成芯片制造签核。

## 同步规则与存储分工

每个**已经验证的阶段完成后同步一次**：检查变更、更新报告、保存紧凑结果及来源哈希，然后推送 Git 提交与对应证据附件。采用阶段触发，不设置定时上传。正在运行、结果未检查的实验不作为新的已验证阶段发布。

| 位置 | 内容 | 接续开发时的用途 |
|---|---|---|
| Git 仓库 | 电路、RTL、生成与验证脚本、环境锁、报告、图片、最终 Blender 场景、紧凑证据与备份清单 | 克隆后可阅读研究结论、审阅设计和启动新开发 |
| GitHub Release 附件 | 清单列出的原始实验目录、大型数据及旧 Blender 备份 | 恢复既有实验，复算指定数据，审查历史场景 |
| 本地环境 | 完整 PDK、EDA 安装、Python 环境、Lima 虚拟机、应用与可重建缓存 | 按固定版本重新准备；不把整台电脑复制到 Git |

本阶段将超过 256 KiB 的稠密 CSV 和旧 `.blend1` 文件放入 Release 附件，按清单恢复到原项目相对路径。三个最终 `.blend` 场景总计约 48 MB，随 Git 保存，便于直接继续建模。报告引用 CSV 附件时，克隆后需要执行恢复；已有 HTML、图片和 MP4 不因此被当作原始波形或场景源码。

备份范围以 [`evidence/backups/research-20261019.json`](../evidence/backups/research-20261019.json) 的实际文件清单、长度和 SHA-256 为准。**这不是整个工作空间、全部历史 `build/`、虚拟机或全部 PDK 的备份。** 未列入清单的历史实验仍需保留在原机器，或另行完整归档。忽略列表中的大 CSV 若再次修改，也必须更新归档清单并发布新的阶段附件，不能仅检查 `git status`。上传成功也不自动删除本地副本；应先核对远端附件、恢复并校验，再依据当前开发依赖决定是否移走历史数据。

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
