# 第二版：实验复现与跨电脑恢复

本阶段是 `driver-improvement-20261111` 冻结基线之上的独立增量。新网表、执行快照和原生波形保存在 `build/driver-methods-20261111/`；公开结果、图与SHA在 `evidence/driver-methods-20261111/`。不是覆盖前一阶段结果后重新解释。

## 先审阅，再决定是否恢复大文件

- [MicroLED结果与源SHA](../../../evidence/driver-methods-20261111/micro-summary.json)、[最终工作点](../../../evidence/driver-methods-20261111/micro-selection.json)、[因果说明](../../../evidence/driver-methods-20261111/micro-mechanisms.md)
- [VCSEL全部结果](../../../evidence/driver-methods-20261111/vcsel-methods.json)、[同速比较](../../../evidence/driver-methods-20261111/vcsel-comparison.json)、[最终工作点](../../../evidence/driver-methods-20261111/vcsel-selection.json)、[方法说明](../../../evidence/driver-methods-20261111/vcsel-methods-notes.md)
- [32格条件性敏感性](../../../evidence/driver-methods-20261111/link-sensitivity.json)、[独立科学审查](../../../evidence/driver-methods-20261111/scientific-validation.json)
- [产品与流片门槛](../../../evidence/driver-methods-20261111/tapeout-readiness.json)、[公开一手来源](../../../evidence/driver-methods-20261111/product-sources.json)

20个新MicroLED案例和22个新VCSEL案例都是完成求解的证据，包含接收/模型范围未通过的失败结果；“完整性检查通过”不表示每个电路都达到功能门槛。光学/RX的32格属于冻结电流波形后处理，不是另外32个SPICE求解。

## 恢复原始输入与波形

先恢复[第一版输入](../driver-improvement-20261111/reproduce.html)及其列出的历史依赖。科学脚本读取前版候选的冻结输入与动态模型，保留项目相对路径。GF180模型/完整物理PDK、虚拟机与Python环境不在波形归档中；按锁定版本和哈希另行恢复，不能把模型子集当完整物理PDK。

下载[本阶段Release](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/driver-methods-20261111)的所有分卷与archive manifest，再执行：

```sh
python3 scripts/backup/release_bundle.py verify \
  --manifest evidence/driver-methods-20261111/raw-backup-manifest.json \
  --asset-dir release-assets
python3 scripts/backup/release_bundle.py restore \
  --manifest evidence/driver-methods-20261111/raw-backup-manifest.json \
  --asset-dir release-assets --root .
```

恢复器验证archive与每个成员的SHA，并拒绝覆盖不同内容。只阅读报告无需下载大波形。重新求解应在独立checkout中保留历史输入，使本阶段候选目录为空；对已经存在且身份一致的案例，运行器会复用，不能把复用称为新仿真。

## 仿真入口

基准环境：Python3.12、NumPy2.5.3、ngspice47 KLU。以下 `python` 指对应科学环境；本机为 `build/layout/venv/bin/python`。最多两路ngspice并发。

```sh
python scripts/driver_methods_20261111/micro_run.py A_rcff31p275 --rates 1.6 2.0 2.4
python scripts/driver_methods_20261111/micro_run.py B_vin3p3_dummy27p6k --rates 1.6 1.8 2.0 2.4
python scripts/driver_methods_20261111/micro_run.py B_vin3p3_dummy50k_control --rates 1.6
python scripts/driver_methods_20261111/micro_run.py A_rcff31p275 --skip-dc --rates 2.0 --steps 80
python scripts/driver_methods_20261111/micro_run.py B_vin3p3_dummy27p6k --skip-dc --rates 1.8 --steps 80
python scripts/driver_methods_20261111/micro_verify_selected.py

python scripts/driver_methods_20261111/vcsel/run.py --candidate vc-ff20 --rates 6.4 7.2
python scripts/driver_methods_20261111/vcsel/run.py --candidate vc-dr65 --rates 6.4 7.2
python scripts/driver_methods_20261111/vcsel/run.py --candidate vc-single --rates 7.2
python scripts/driver_methods_20261111/vcsel/run.py --candidate vc-single-r100 --rates 7.2
python scripts/driver_methods_20261111/vcsel/run.py --candidate vc-single-r150 --rates 6.4 7.2 8.0 8.8
python scripts/driver_methods_20261111/vcsel/run.py --candidate vc-single-r150 --rates 8.8 --steps 80
python scripts/driver_methods_20261111/vcsel/run.py --candidate vc-single-r150 --rates 8.8 --holdout
```

固定参数后才运行预声明的0x4c2d留出。它是PRBS15周期中的非重叠片段，不是随机独立BER试验。候选 `vc-ff40` 只列为预案，没有执行，不纳入结果数量。DC、电压/体结、模型域、训练和验证接收必须同时通过；失败行能量不能作可靠有效吞吐排名。

## 后处理与报告

```sh
python scripts/driver_methods_20261111/micro_summary.py
python scripts/driver_methods_20261111/micro_diagnostics.py
python scripts/driver_methods_20261111/micro_figures.py
python scripts/driver_methods_20261111/micro_validate.py
python scripts/driver_methods_20261111/vcsel/compare.py
python scripts/driver_methods_20261111/vcsel/validate.py
python scripts/driver_methods_20261111/link_sensitivity.py
python scripts/driver_methods_20261111/validate_stage.py --final
python scripts/driver_methods_20261111/plot.py
python scripts/driver_methods_20261111/figures.py
python scripts/driver_methods_20261111/report.py
python scripts/driver_methods_20261111/validate_report.py
```

`link_sensitivity.py`只处理前版A/B的固定3.2Gb/s原生电流，不是本轮新A/B；原200ps/1GHz格点必须复现基线。最初计算源码在归档中保留，后续缓存身份验证的源码变更单独可追溯。独立审查重算32格，而不是只相信缓存。

科学图使用Matplotlib、Pillow、CairoSVG；本机Cairo需要 `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`。报告环境为 `build/blue-emitter-speed-review-20261110/report-venv/`，ReportLab4.4.9、pypdf6.10.0、pdfplumber0.11.9、Markdown3.9。HTML优先PingFang SC；PDF嵌入Heiti SC TrueType及Arial，跨平台替换为有许可的可嵌入CJK字体。

第二版报告正文与后面的24页历史附录自动生成。附录引用第一版图表，因此网页阅读时需要保留相邻的第一版目录；单个PDF已经包含完整图文。

## 备份与未包含范围

Git保存源码、公开报告与紧凑证据；Release保存本阶段冻结原始波形、网表、执行脚本快照、日志、协议及诊断。失败的接收与模型域案例同样保留。分卷成员与SHA见 [raw-backup-manifest](../../../evidence/driver-methods-20261111/raw-backup-manifest.json)。最终上传及远端回读结果另写 `delivery.json`，只有实际验证完才能称备份完成。

不包含PDK/VM/环境、论文原件、无关用户工作、渲染临时PNG或历史Release已保存的大波形。本次不删除任何本地证据，也不将历史 `microled-dynamic-validation-20261108` 未完成draft宣称为补齐。
