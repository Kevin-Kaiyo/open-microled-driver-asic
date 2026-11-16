# 复现电路、波形和数据

本轮各试验保存相对路径、实际网表、输入身份、执行脚本快照、ngspice 日志和压缩的原生波形。结果汇总在 `evidence/driver-pvt-20261117/`，仿真原始数据在 `build/driver-pvt-20261117/`。

## 环境与固定输入

从本仓库恢复[上一阶段交付](../driver-interface-20261115/reproduce.html)列出的历史原始输入，尤其是 `MicroLED/A-protected_v3r`、`MicroLED/B-protected_v6r` 和 `VCSEL/single-phy12`。使用 Python 3.12、NumPy 和 ngspice 47/KLU。参考工作区的解释器为 `build/layout/venv/bin/python`。报告册用 Python-Markdown、Playwright 和 Chrome 构建。

MicroLED 冻结输入使用先前物理环境中的 GF180 模型接口，VCSEL 使用原版子电路名的锁定模型。两者有同名 `.ngspice` 文件，实际字节和器件命名不同。按各案例 manifest 的 SHA-256 恢复。完整物理 PDK 和运行环境遵循各自的安装与许可证说明。[模型依赖清单](../../../evidence/driver-pvt-20261117/model-dependencies.json)列有排除模型的路径示例和身份。

## 检查恢复内容

将本阶段 Release 的分卷放入 `release-assets/`，在仓库根目录运行下列命令。恢复器检查全部归档成员，并在目标路径已有不同内容时停止。

```sh
python scripts/backup/release_bundle.py verify \
  --manifest evidence/driver-pvt-20261117/raw-backup-manifest.json \
  --asset-dir release-assets
python scripts/backup/release_bundle.py restore \
  --manifest evidence/driver-pvt-20261117/raw-backup-manifest.json \
  --asset-dir release-assets --root .
python scripts/driver_pvt_20261117/restore_inputs.py \
  --model-dir /path/to/matching/MicroLED-PDK \
  --model-dir /path/to/matching/VCSEL-PDK
```

恢复命令按 SHA-256 选用两套输入模型，并重建 VCSEL 各工况到共享 `_inputs/` 的相对链接。两个模型目录各提供 matching `design.ngspice` 和 `sm141064.ngspice`。如原案例模型目录仍在，可直接使用它们。先加 `--check-only` 可核对计划与冲突。

原始字节恢复后，可重新核对溯源及固化条件。这里的审计通过表示数据、网表和输入身份一致，功能是否通过请看每例独立报告。

```sh
python scripts/driver_pvt_20261117/validate.py --rehash-uncompressed
python scripts/driver_pvt_20261117/led_voltage_budget.py
python scripts/driver_pvt_20261117/clamp_probe.py
python scripts/driver_pvt_20261117/plot_clamp.py
```

## 原生数据和评分

每例 `testbench.spice` 可在原病例目录由 `ngspice -b testbench.spice` 运行。独立复跑先复制到独立的输出树并保留包含文件相对路径，避免覆盖原生记录。短窗只用于机制验证。完整帧使用固定 4736 线路位与 4096 有效评分位。A/B 的保护窗保留持续翻转，恢复量由故障前已有的采样相位评估。功耗统计覆盖网表边界内所有源端口，返还能量单独记录。

## 更新报告

```sh
python scripts/driver_pvt_20261117/render_html.py
node scripts/driver_pvt_20261117/print_report.mjs /path/to/playwright/index.mjs /path/to/Chrome
```

报告源是 `README.md`。波形预览以静态 PNG 供 PDF/网页阅读，原生网表和数值证据可独立审核。
