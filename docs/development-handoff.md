# GitHub 备份与另一台电脑接续开发

更新：2026-10-27。项目定位为实验性研发方法验证与教学。备份保存当前设计、研究资料和指定实验的证据链；它不使仿真结果升级为实测结果，也不表示已经完成芯片制造签核。

## 新增阶段：净3.2 Gb/s瓶颈与VCSEL晶体管研究（2026-10-27）

阅读[新报告](research/three-gbps-experiment-20261027/index.html)与[恢复/复现说明](research/three-gbps-experiment-20261027/reproduce.md)。本轮MicroLED保留原负载与门槛做35次SPICE诊断；VCSEL建立13MOS真实电阻参考/偏置/转向电路和公开图读约束代理，运行8个完整帧、14个成功DC点、21组接收分析。原v2结果不覆盖；新v3训练规则先冻结，再以不重叠PRBS窗口确认TT条件性结果。SS/FF仍失败，尚非实际光链路、BER或物理实现资格。

新原始范围为 `build/three-gbps-experiment-20261027/`；源与compact evidence在Git。Release标签为 `three-gbps-experiment-20261027`，归档、远端读回和排除范围以本轮 `evidence/three-gbps-experiment-20261027/archive-*.json` 验收回执为准。历史实验、完整PDK、运行环境不包含在本轮范围，不复用或移动旧标签。

## 目标与研究增补：单通道 >3 Gb/s 与 VCSEL（2026-10-27）

[本轮报告](research/three-gbps-vcsel-20261027/index.html)及[证据台账](../evidence/three-gbps-vcsel-20261027/source-ledger.json)区分用户确认的单通道净率目标与建议评估点3.2 Gb/s。只读核对旧1/2 Gb/s结果，计算帧效率、UI及旧代理响应；新增VCSEL教学电路与公开一手资料索引。没有新增晶体管、VCSEL、3 Gb/s瞬态或物理验证，未预选拓扑或更换PDK。

本阶段源码、报告、许可明确的Frontiers Fig.8和紧凑计算可随Git恢复；重建脚本需要已有项目Python绘图库、Markdown及report-font。未明确公开复用许可的原PDF/页面及本地证据卡保留在忽略目录`build/three-gbps-vcsel-20261027/`，未包含在Git或旧Release中，仍可从台账URL重新取得。本轮没有产生大型新SPICE原始波形，不另复用或移动旧fair-driver归档标签。

## 新增阶段：高速A/B/C配对原理级研究（2026-10-26）

先读[研究报告](research/fair-driver-comparison-20261025/index.html)和[同条件数据](../evidence/fair-driver-v1/summary.json)。显示PWM和既有版图保持其历史证据；这轮A20/B21/C49 MOS均是新的SCHEM候选，不能继承此前B的GDS/PEX资格。相同Lin静态负载和假设200fF下，实际参考/辅助轨与译码都计入七端口能量；未包含上游电源IC内部损耗或实体RX。

- 主体：`build/fair-driver-v1/matched-r2`；单因素：`controls-r1`；C内部节点：`c-transition-probe/run-03`。原输入、失败、超时与存储原型均保留。
- 最终接收：`build/fair-driver-v1/rx-equal-latency-v2-final-r1`。对相同原生LED波形，以共同0–8ns、5ps和448训练评分＋64bit保护重新分析；旧symbol窗口v1与执行身份较弱的v2预跑目录保留，但不进入最终表。
- 原始输入、模型子集、源哈希与实际执行代码由新的[备份/恢复工具](../scripts/backup/fair-driver-20261025/README.md)打包；仅恢复inputs＋results即可在新目录重新生成DC deck。完整物理PDK、VM和Python环境仍须另装。报告绘图字体与许可置于`build/fair-driver-v1/report-font`。
- [旧成功波形按需恢复记录](../evidence/backups/fair-driver-20261025-old-waveforms-offload.json)：54个已完成备份与读回核验的历史成功波形转为GitHub Release按需恢复，释放4.016GiB。当前阶段输入/原生波形、全部失败、旧模型与版图不在此删除范围。原case目录保留`REMOTE-WAVEFORM.json`，按其指定archive/成员/SHA恢复；旧归档验收回执是当时快照，不表示清理后本地仍含全部旧波形。

本轮[Release：fair-driver-20261025](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/fair-driver-20261025)已完成验收。标签固定源码提交`d203aa748de36c96a4d51605bc5acaae94b0b759`，源树`e90af1adeec19fb3b79c7c5616d94e4cbe4d66ab`，不随验收回执提交移动。

- [归档manifest](../evidence/backups/fair-driver-20261025.json)、[范围](../evidence/backups/fair-driver-20261025-scope.json)、[本地逐成员验收](../evidence/backups/fair-driver-20261025-local.json)与[远端读回](../evidence/backups/fair-driver-20261025-remote.json)：1,413个原文件、2,085,144,228字节；7卷1,965,567,453字节。12个预定归档/清单资产全部流式SHA-256读回一致，未落额外全下载副本。manifest SHA为`3a9af00442308fe7c01034d64c834e65456803968e47ecc4b4b44e725393f7b2`。
- [新检出恢复与DC回执](../evidence/backups/fair-driver-20261025-recovery/check.json)：从公开标签作depth1新检出，仅下载inputs＋results约30.1MB，恢复1,184文件并逐个核SHA；新work的B TT L0为25.000668784µA，与原值相差0 A，七端口DC功率差均0 W。17条命令全部成功；[运行脚本/日志/小证据](../evidence/backups/fair-driver-20261025-recovery/)保留。使用同一Mac与既有Python/ngspice，只证明单点路径恢复；不是异机/新OS、NRZ全矩阵、光学或物理EDA验证。恢复应先检出上述标签/源提交，而非任意较新的main。
- [暂存副本整理](../evidence/backups/fair-driver-20261025-staging-cleanup.json)：完成远端读回和DC恢复后，再次对原范围1,413文件作完整内容SHA核对；只移除7个可重新下载的暂存tar副本，释放1,965,567,453字节。全部本轮原输入/波形/失败与恢复检出保留。备份工具本身不自动清理；若要再次运行要求本地assets的校验入口，先从Release下载指定同名归档并核SHA。

当前主分支会比源码标签多一个验收回执提交；tag、源模型与归档都不改写。

## 前一阶段：PWM 参考启动与高速 B 真实参考（2026-10-24）

分别阅读[显示 PWM 报告](research/pwm-reference-startup-20261024/index.html)和[高速 B 报告](research/nrz-b-reference-power-20261024/index.html)。这轮保持各自 LED、PWM/NRZ 时序及接收条件；失败与负控制一并保存。

PWM 复用原 r5 39 MOS / 345 R / 288 C，修改片外补偿与 100 Ω / 15 nF 滤波。新输入包已经保存原完整 RC；旧 GDS/物理工具重跑仍依赖此前阶段。高速最终是 21 MOS + RIN 的实际联通版图，正式 RC 为 `925b0e98ede116b7d3dc0c0f326aa1704fd08b84dd8cabe39cf03ae4ac4f3d6a`；芯片面积只指实验宏，不含 pad/ESD 与片外元件。

- 新实验树：`build/pwm-reference-v2/20261024/`、`build/nrz-reference-v2/`、`build/reference-v2-layout/`、`build/reference-v2-audit/`。完整 PDK、VM、Python 环境和所有历史实验不自动包含在增量中。
- 可移植入口：`scripts/pwm_reference_v2/reproduce.py` 和 `scripts/nrz_reference_v2/reproduce.py`。它们核对输入身份并在新目录生成新 deck，不能直接运行带旧机器路径的冻结 deck。
- 物理重跑环境与顺序见[物理恢复说明](../evidence/reference-v2-layout/RESTORE.md)。报告重建依赖中英文字体；字体与许可随该阶段 report-support 分组提供。
- 高速仍依赖外部精密基准和 DISABLE 时序；提前释放存在端压失败，残余电源重启存在约 0.747 V 体结正向偏置，不能当作生产就绪设计。

本轮增量 Release：[reference-v2-20261024](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/reference-v2-20261024)，源标签固定在 `29266d9758894e87bc08a77a3ddf4f86f7b502e1`，源树 `67aae915d64a76c5a20e963c464f010e70fc83c0`。备份验收回执另入主分支，标签不移动。

- [清单](../evidence/backups/reference-v2-20261024.json)与[范围/排除项](../evidence/backups/reference-v2-20261024-scope.json)：22 个归档、5,760 个普通文件；原始 5,060,468,194 字节、归档 4,933,879,962 字节。576 个内部链接单独记录；完整 PDK、VM、Python 环境和其它历史实验不在本次增量内。
- [本地逐成员核验](../evidence/backups/reference-v2-20261024-local.json)与[全部远端回读](../evidence/backups/reference-v2-20261024-remote.json)：22 个归档、5 份 JSON 与2个恢复助手，共29个资产的长度和 SHA-256 均一致。清单 SHA 为 `ff5dc9f3946b7ccdd95619ea50e7ea388ba882b9b5e43203545e59da2dd2c132`。
- [新目录恢复回执](../evidence/backups/reference-v2-20261024-recovery.json)与[紧凑复跑日志](../evidence/backups/reference-v2-20261024-recovery/README.md)：从 GitHub 新检出源提交，下载六个小分组，实际恢复4,801文件、576相对链接。NRZ/PWM两个DC点分别 **100.395162236404 / 99.733511411711 µA**，与归档原结果均差0 A；PWM重新编译RTL。实际联通版图及12 MOS模块分别123/114文件的既有物理证据回读通过。
- 验证发生在同一 macOS ARM 主机的不同目录，复用已有Python/ngspice/Icarus；没有在全新电脑安装工具、恢复全部大波形、重跑全矩阵或DRC/LVS/PEX，也没有其他操作系统结论。
- 首次DC因可用空间不足5 GiB在仿真前被阻止，失败日志保留。全部远端回读与小文件恢复再核验后，仅清理22个已验证的压缩暂存副本，随后用retry1新目录复跑通过。[清理回执](../evidence/backups/reference-v2-20261024-cleanup.json)准确记录当时为`files_restored_DC_pending`；最终DC成功见恢复回执。原始活动输入/波形/失败、PDK、恢复检出与下载副本均保留。删除约4.93 GB逻辑暂存字节，APFS实际可用空间另记，二者不等同。

仅复跑小输入，不需要下载全部大型波形。准备 README 所列依赖，在该源标签的项目根目录执行：

```sh
gh release download reference-v2-20261024 \
  --repo Kevin-Kaiyo/open-microled-driver-asic \
  --pattern 'reference-v2-20261024.json' \
  --pattern 'reference-v2-20261024-scope.json' \
  --pattern 'restore_symlinks.py' --pattern 'backup_common.py' \
  --pattern '*-inputs-*.tar.gz' --pattern '*-metadata-*.tar.gz' \
  --pattern '*-physical-evidence-*.tar.gz' --pattern '*-report-support-*.tar.gz' \
  --dir build/github-download-reference-v2
python3 scripts/backup/release_bundle.py restore \
  --manifest build/github-download-reference-v2/reference-v2-20261024.json \
  --asset-dir build/github-download-reference-v2 --root . \
  --group nrz-inputs --group nrz-metadata \
  --group pwm-inputs --group pwm-metadata \
  --group physical-evidence --group report-support
python3 build/github-download-reference-v2/restore_symlinks.py \
  --root . --scope build/github-download-reference-v2/reference-v2-20261024-scope.json --execute

build/layout/venv/bin/python scripts/nrz_reference_v2/reproduce.py \
  --source-work build/nrz-reference-v2/selected-final-r2 \
  --out build/nrz-reference-v2/new-machine-smoke --smoke-dc
build/layout/venv/bin/python scripts/pwm_reference_v2/reproduce.py \
  --source build/pwm-reference-v2/20261024 --case c15_dc \
  --destination build/pwm-reference-v2/new-machine-smoke
```

解释器路径是项目约定，需要先安装；新输出目录必须不存在。所有restore拒绝覆盖不同字节，复跑入口重新生成新路径，不直接运行含旧绝对路径的冻结deck。上述通配符还会下载很小的audit-metadata归档，但restore只选六组。全波形复算另下载相应waveforms组；完整物理重跑按物理恢复说明准备固定完整PDK及工具。下列旧Release保持不可变。

## 历史阶段：显示PWM与高速NRZ的扰动验证（2026-10-24）

[中文研究报告](research/driver-robustness-20261024/index.html)与[该阶段复现说明](research/driver-robustness-20261024/README.md)为历史入口。两种应用保留不同的冻结负载和判据，不能混用电流精度与高速RX结果。

- 高速旧核心的9–11mV余量已被本轮+50mV与供电/回地封装R/L反例否定。最终真实物理选择是 `build/highspeed-nrz-robustness-layout/hv-A8-r3/A` 和 `hv-r2/B`；电气矩阵在 `build/highspeed-nrz-robustness/selected-a8-b58-r4`。A在固定辅助电源下0.4Gb/s离散点通过，但辅助电源扰动仍失败；不能称整个速率包络已闭合。
- PWM仍用r5实际39MOS/345R/288C和原合成LED，原始输入/实验在 `build/pwm-robustness/20261024`。PCB侧100Ω/100nF滤波是外部网络修订，没有虚构新版芯片版图；恢复时间与启动的跨数值设置一致性仍待解决。
- 本轮小输入恢复入口不再依赖旧历史raw目录：NRZ `scripts/highspeed_nrz_robustness/reproduce.py`，PWM `scripts/pwm_robustness/reproduce.py`。两者按新机器路径生成新的deck，原冻结证据保持字节不变。完整物理重跑仍需固定full PDK及工具。

本轮增量 Release：[`driver-robustness-20261024`](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/driver-robustness-20261024)，源标签固定在 `9d84753bae099e497a813f9097b1ce6eeb2f2df7`。后续回执进入主分支，标签不移动。实验工作完成不表示所有电路条件通过，失败与未收敛记录一并保存。

- [逐文件清单](../evidence/backups/driver-robustness-20261024.json)与[范围/排除项](../evidence/backups/driver-robustness-20261024-scope.json)：25 个归档、2,302 个普通文件；原文件 8,446,706,417 字节，归档 8,307,456,214 字节。294 个符号链接单独记录目标，未跟随复制；完整 PDK、工具、VM、Python 环境及其它历史 build 不在本轮增量内。
- [本地逐成员核验](../evidence/backups/driver-robustness-20261024-local.json)与[GitHub 流式回读](../evidence/backups/driver-robustness-20261024-remote.json)：25 个归档及 7 份清单/恢复助手共 32 个资产的长度和 SHA-256 一致。远端归档字节与已逐成员验证的本地归档相同。
- [新目录恢复回执](../evidence/backups/driver-robustness-20261024-recovery.json)与[保留的复跑日志](../evidence/backups/driver-robustness-20261024-recovery/README.md)：从 GitHub 新检出源标签，实际下载六个小分组，恢复 2,057 个文件；NRZ/PWM 的一个 DC 点分别重跑为 108.566138350767 / 99.733511476514 µA，与归档原结果均差 0 A。实际 GDS/物理证据回读分别覆盖 105 与 205 文件并通过。一次仅发生在回执整理中的脚本类型错误已修正并保留记录，电路仿真与物理回读均退出 0。
- 这次恢复使用同一台 macOS ARM 主机的不同目录，复用已有 Python/ngspice/iverilog。没有在全新电脑安装工具，没有重跑全部瞬态矩阵或 DRC/LVS/PEX，也没有恢复全部大波形。NRZ 仅把新分析摘要的输出目录在进程内重定向到恢复工作区；电路、输入与判据未改。
- [暂存清理回执](../evidence/backups/driver-robustness-20261024-cleanup.json)记录再次核对所有活动原件后，仅清理本次归档副本、下载副本与临时检出目录。活动实验、失败证据、完整 PDK、VM、工具和紧凑恢复日志全部保留。逻辑删除字节数不等于 APFS 实际空间增量。

仅复跑新的 DC/瞬态，不需要先下载约 8 GB 大波形。先检出本轮源标签，再准备 README 所列 Python、ngspice 和 Icarus Verilog 依赖：

```sh
gh release download driver-robustness-20261024 \
  --repo Kevin-Kaiyo/open-microled-driver-asic \
  --pattern 'driver-robustness-20261024.json' \
  --pattern '*-inputs-*.tar.gz' --pattern '*-metadata-*.tar.gz' \
  --pattern '*-physical-evidence-*.tar.gz' --pattern '*-report-support-*.tar.gz' \
  --dir build/github-download-driver-robustness
python3 scripts/backup/release_bundle.py restore \
  --manifest build/github-download-driver-robustness/driver-robustness-20261024.json \
  --asset-dir build/github-download-driver-robustness --root . \
  --group nrz-inputs --group nrz-metadata \
  --group pwm-inputs --group pwm-metadata \
  --group physical-evidence --group report-support

build/layout/venv/bin/python scripts/highspeed_nrz_robustness/reproduce.py \
  --source-work build/highspeed-nrz-robustness/selected-a8-b58-r4 \
  --work build/highspeed-nrz-robustness/new-machine-smoke --smoke-dc
.venv/bin/python scripts/pwm_robustness/reproduce.py \
  --work build/pwm-robustness/new-machine-smoke
```

解释器路径是本项目环境约定，需在新机器安装相同依赖；Git 克隆不会生成这些环境。`restore` 会先核对归档及每个成员，拒绝覆盖不同的已有文件。小输入入口按新根目录生成绝对引用，不执行旧 deck 中的旧机器路径。若要复算已归档的全部波形，另下载 `nrz-waveforms` / `pwm-waveforms` 分组后按同样方式恢复。

恢复原案例中的符号链接时，先下载 Release 的 `restore_symlinks.py`、`backup_common.py` 和 scope JSON 到同一目录，用 `python3 restore_symlinks.py --root <checkout> --scope <scope.json>` 先预览，再加 `--execute` 执行；当前小输入复跑入口不依赖恢复这些旧链接。旧基线波形和完整物理重跑环境仍按相应历史 Release 与 PDK 锁文件准备。

## 历史阶段：慢热接收与快冷端电压修正（2026-10-23）

[新版中文研究报告](research/highspeed-nrz-pvt-20261023/index.html)、[真实新版 GDS 查看器](research/highspeed-nrz-pvt-20261023/layout-viewer.html)与[复现说明](research/highspeed-nrz-pvt-20261023/README.md)是该历史阶段入口。最终实际物理目录为 `build/highspeed-nrz-pvt-layout/final-r4`，仿真目录为 `build/highspeed-nrz-pvt/final-r4`。旧版模型与报告保留。

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
