# 输入接口、连续运行与独立关断：复现与恢复

本阶段从 `d47c7f16f39a3be538f971a79d5a9626c232e3ad` 开始，沿用[2026-11-11第二版](../driver-methods-20261111/reproduce.html)的候选和固定负载/接收条件。新证据在独立的 `driver-interface-20261115` 目录；历史网表、模型和失败结果不覆盖。

## 先看公开证据

- [MicroLED连续与保护结果](../../../evidence/driver-interface-20261115/micro-summary.json)
- [MicroLED预声明协议](../../../evidence/driver-interface-20261115/micro-protocol.json)
- [VCSEL输入接口结果](../../../evidence/driver-interface-20261115/vcsel-interface-summary.json)
- [预声明的VCSEL留出窗口](../../../evidence/driver-interface-20261115/vcsel-interface-protocol.json)
- [独立完整性审查](../../../evidence/driver-interface-20261115/scientific-validation.json)
- [原始波形归档清单](../../../evidence/driver-interface-20261115/raw-backup-manifest.json)
- [物理解释与一手资料范围](methods-notes.html)

原理图求解完成、数据完整性通过、功能门槛通过、物理版图通过、硅片/光学测量是不同状态。保留的失败case不是成功候选。零观察错也不能替代幅度与时序余量。

## 恢复大型数据

先按前阶段说明恢复锁定模型和依赖，包括 `driver-methods-20261111`、`driver-improvement-20261111`、`blue-emitter-speed-review-20261110` 及其列出的旧输入。保留仓库相对路径。

再从[本阶段Release](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/driver-interface-20261115)下载分卷与archive manifest：

```sh
python3 scripts/backup/release_bundle.py verify \
  --manifest evidence/driver-interface-20261115/raw-backup-manifest.json \
  --asset-dir release-assets
python3 scripts/backup/release_bundle.py restore \
  --manifest evidence/driver-interface-20261115/raw-backup-manifest.json \
  --asset-dir release-assets --root .
```

分卷可以在文件边界拆开同一个案例，完整恢复需下载全部分卷。恢复器逐卷、逐成员检查SHA-256，拒绝覆盖内容不同的文件。普通Git clone不包含被忽略的build波形、PDK、虚拟机和环境。

## 仿真入口与运行规则

科学环境为Python 3.12、NumPy 2.5.3、ngspice 47 KLU；本机Python入口为 `build/layout/venv/bin/python`。最多两路ngspice同时运行。所有新case保留testbench、输入与执行源码快照、日志、原生波形身份和结果。

以下是对应命令形式；最终完整矩阵以报告和冻结selection/summary为准，不应把未执行的参数组合当作已验证：

```sh
python scripts/driver_interface_20261115/vcsel/run.py --candidate single-phy4 --rates 6.4 8.8
python scripts/driver_interface_20261115/vcsel/run.py --candidate single-phy12 --rates 6.4 8.8
python scripts/driver_interface_20261115/vcsel/run.py --candidate single-phy4-r25k --rates 6.4 8.8
python scripts/driver_interface_20261115/vcsel/run.py --candidate double-phy4 --rates 6.4

python scripts/driver_interface_20261115/micro/run.py A baseline --frames 4
python scripts/driver_interface_20261115/micro/run.py B baseline --frames 4
python scripts/driver_interface_20261115/micro/run.py A protected_v3r --dc
python scripts/driver_interface_20261115/micro/run.py B protected_v6r --dc
python scripts/driver_interface_20261115/micro/run.py A protected_v3r --frames 4
python scripts/driver_interface_20261115/micro/run.py B protected_v6r --frames 4
python scripts/driver_interface_20261115/micro/run.py A protected_v3r --kind fault --frames 2
python scripts/driver_interface_20261115/micro/run.py B protected_v6r --kind fault --frames 2
python scripts/driver_interface_20261115/micro/run.py A protected_v3r --kind fault --frames 2 --steps 80
python scripts/driver_interface_20261115/micro/run.py B protected_v6r --kind fault --frames 2 --steps 80
# 候选selection冻结记录存在、匹配输入身份后才能运行留出
python scripts/driver_interface_20261115/micro/run.py A protected_v3r --kind fault --frames 2 --holdout
python scripts/driver_interface_20261115/micro/run.py B protected_v6r --kind fault --frames 2 --holdout
```

已存在且身份一致的case会复用；这不是重新求解。若需要独立复跑，应在新的checkout/输出环境恢复旧基线，使本阶段输出目录为空。不能删掉旧失败后在同名case里覆盖为成功。

连续实验在同一次瞬态内重复实际PRBS帧，不重置电容；光学/RX对完整电流只滤波一次，再切帧。既报告逐帧训练，也报告首帧固定采样相位。重复4736位不等于完整PRBS15周期，更不代表热稳态。

保护关断时数据持续翻转。20 ns内导电电流低于0.1 µA是研究筛查目标；低电流处是既有I–V参考范围以外的延拓，不能解释成实测漏光或安全资格。恢复必须按同一接收门槛检查，不能只看电流均值。

## 如何读取失败与修正

所有summary rows均在最终审查矩阵中，包括模型尺寸失败、数值截断、应力失败和一帧机制诊断。B-v2的三条记录另有`reanalysis.json`：原始网表、原始结果和SHA保留，按实际接地的XDIS/XKEEP栅极重新计算应力。需要真实有效应力时读取`corrected_effective_result`，不能继续用旧元数据解释结论。

A最初两条W300模型失败案例还有执行快照文件名碰撞：两个不同来源的helper都曾写入`execution-sources/analyze.py`。现追加`restored-dynamic-analyze.py`和`provenance-correction.json`，恢复字节的SHA严格匹配原manifest声明；原manifest、结果、网表和日志均保留。该修复恢复的是来源可读性，不赋予失败案例电路性能结论。

A-v3的两次截断以及B-v6的截断不是完整通信测试，即使ngspice退出码为0也不算成功。运行器同时检查停止时刻、日志和全部源生数据。B-v5仅一帧诊断，不能继承最终保护候选的完整恢复资格。

A-v3r与B-v6r采用100 Ω保护命令源；只有B包含READY RC、DATA门控和输入PDK阻尼。这些都是实际电路修改，需要在真实接口与新版图中兑现。本阶段没有修改历史物理签核。

## 审查与报告重建

```sh
python scripts/driver_interface_20261115/validate_stage.py --final
python scripts/driver_interface_20261115/report.py
python scripts/driver_interface_20261115/validate_report.py
```

`--final`只用于最终实验矩阵与输入冻结后。普通中间审查保持partial，不把当前已发现文件数误认为任务完成。科学审查包含原生数据能量、端压、接收、波形/源码身份和数据标签；报告检查包含图文绑定、页面和本地链接。

PDF使用ReportLab 4.4.9、pypdf 6.10.0、pdfplumber 0.11.9与Markdown 3.9；本机报告环境为 `build/blue-emitter-speed-review-20261110/report-venv/bin/python`。HTML优先PingFang SC，PDF采用可嵌入Heiti SC TrueType和Arial符号回退。输出每页都须渲染检查。

## 备份边界

公开源码、紧凑证据和报告提交Git；本轮原生波形、执行快照、输入和失败日志备份为Release资产。PDK字节、虚拟环境、VM、论文原件、已有历史Release波形、报告临时渲染和无关工作不重复上传。PDK排除项仍记录身份，模型子集不能替代完整物理PDK。

最终备份收据在 `evidence/driver-interface-20261115/delivery.json`。只有实际下载回读、归档与全部成员SHA验证完成，才称远端备份完成。本阶段保留本地原始证据，不做清理。
