# 复现本轮 A/B 电路实验

从仓库的本轮标签 `driver-ab-20261118` 恢复代码，使用 Python 3.12、NumPy 与 ngspice 47/KLU。在仓库根目录执行下列命令。历史研究包含两次重要交付，较新的 PVT 报告列出了对应的原生文件、模型身份和恢复命令。[上一轮恢复说明](../driver-pvt-20261117/reproduce.html)

### 固定输入与原始证据

先恢复上一阶段所列的 MicroLED 输入，包括 `driver-interface-20261115` 的 B-protected_v6r，以及 `driver-pvt-20261117` 的 A 输入和 B 单位镜。GF180 仿真模型使用前一阶段相同字节。下载本轮 Release 的原始归档分卷及清单，放入 `release-assets/`。复制或恢复操作前可先运行 verify。仓库保存报告、脚本与紧凑数字，Release 保存原生实验数据。[本轮归档](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/driver-ab-20261118)

```sh
python3.12 scripts/backup/release_bundle.py verify --manifest evidence/driver-ab-20261118/raw-backup-manifest.json --asset-dir release-assets
python3.12 scripts/backup/release_bundle.py restore --manifest evidence/driver-ab-20261118/raw-backup-manifest.json --asset-dir release-assets --root .
python3.12 scripts/driver_ab_20261118/backup.py restore-inputs --model-dir /path/to/matching/MicroLED-PDK
```

原模型依赖文件和目录链接由脚本按 SHA-256 或相对路径重建。原有目标路径若有不同数据会中止。独立重算宜用单独工作区。恢复的数据可以直接核对；需要再次运行已有缓存的病例时，在新的工作区仅恢复其输入及父阶段依赖，保留参考输出供比较。

### 电路与接收评分

每个病例目录保留实际 SPICE 网表、输入码型、原生波形和执行日志。短窗检查命令边沿，完整帧按尺量接收幅度和采样时间两项余量。图中标明相对时间零点。所有能耗均覆盖网表内的七个独立源，A 的外部测量和数字校准功耗需要单独预算。

[返回图文报告](index.html)

### 复跑 A 与 B

A 的逐工况实际检测压降、量化读数、搜索路径和最终修调码可以从每个工况的证据追溯。留出工况的电压按实际网表与顶层 pvt 元组核对，沿用模板中的 rails_V 只描述来源。测流校准用外部算法和无源网络，附录列出模拟边界。[A 的执行顺序与误差说明](../../../evidence/driver-ab-20261118/a/methods.md) · [校准搜索独立审核](../../../evidence/driver-ab-20261118/a/calibration-audit.json)

B 先复跑 44 MOS 保护基线，再依次运行保护阻值、4/2 µm 合并版和最终 6/3 µm 版本。先生成 `merged220c10` 的九角 DC 与成对保护窗口及三个完整协议，之后从同名父网表生成 6/3 µm 版本。下列以慢热低压整段故障为例，需已恢复父输入与历史模型。如果从缓存重算，先在独立工作区生成同名输入。

```sh
python3.12 scripts/driver_ab_20261118/b/run.py merged220c10 --grid ss_hot_low --mode full
python3.12 scripts/driver_ab_20261118/b_final.py full ss_hot_low --variant unit6-r260-n4ff36
python3.12 scripts/driver_ab_20261118/b_final.py full ss_hot_low --variant unit6-r260-n4ff36 --steps 80
python3.12 scripts/driver_ab_20261118/b_final.py dc all --variant unit6-r260-n4ff36
python3.12 scripts/driver_ab_20261118/b_grid.py unit6-n4ff36 build/driver-ab-20261118/b_final/unit6-r260-n4ff36 --final-grid
```

每份故障网表的 DISABLE 在 0.64 µs 断言、1.28 µs 释放，到 5.12 µs 结束。采样算法在故障前训练，此后还需通过单侧 0.37 UI、7.5 µAeq 的持续余量检验。普通首帧长度为 2.56 µs。对数据修正过程中保留的不同拓扑，可查看原实验与独立计分的配对表。[B 支线结果](../../../evidence/driver-ab-20261118/b/full-frames.md) · [全帧复算说明](../../../evidence/driver-ab-20261118/b_review/README.md) · [最终电路所有端口与接收指标](../../../evidence/driver-ab-20261118/matched-frames.json)

### 检查模型与能耗

```sh
python3.12 scripts/driver_ab_20261118/verify.py --deep --final
python3.12 scripts/driver_ab_20261118/b_review/check_stage.py
python3.12 scripts/driver_ab_20261118/review_unit6.py
python3.12 scripts/driver_ab_20261118/metrics.py
python3.12 scripts/driver_ab_20261118/storage_ledger.py
```

独立评分直接读取原生时间点，以两个并联一阶滤波器的加权差重建等效级联响应。数字正确与全部余量合格分别核对。36 fF 前馈版本有一项继承自 31.275 fF 模板的电容首末储能诊断字段，随附修正表依实际网表电容和端点压差重新计算。七个源端口的积分独立读取实际 SPICE 电压、电流。[首末储能修正明细](../../../evidence/driver-ab-20261118/storage-ledger.json)

网页源文档为本目录的 README.md，使用 `scripts/driver_ab_20261118/render.py` 与 `print.mjs` 生成网页和 PDF，图表使用报告目录 assets 下的本地文件。

本轮审核了 484 个带病例清单的求解，包括 329 个直流、129 个短窗和 26 个完整帧或完整双帧病例，另核对 1494 个直流扫描点的网表、模型和原始电流。重复标定、单因素对照和失败结果均包含在内。最终 B 慢热工况用每 UI 40 与 80 个最大步长分段重算，第二帧时间余量差约 0.002 ps。全阶段原始文件分为 55 卷、9956 个归档成员，可依清单逐文件恢复。[完整性审核](../../../evidence/driver-ab-20261118/validation.json) · [最终慢热细步长独立评分](../../../evidence/driver-ab-20261118/b_final/unit6-r260-n4ff36-ss_hot_low-full-s80.json) · [原始归档清单](../../../evidence/driver-ab-20261118/raw-backup-manifest.json)
