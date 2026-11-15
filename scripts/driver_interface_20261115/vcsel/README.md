# VCSEL 有限 CMOS 输入实验

此目录只负责输入级工程模型；不是 LVDS/CML/FPGA 实物资格，未完成 VCSEL 连续热工作或独立激光关断。固定光源、电流目标、RX 与完整帧规则见 `evidence/driver-interface-20261115/vcsel-interface-protocol.json` 及 `vcsel-interface-notes.md`。

## 运行顺序

从仓库根目录，用项目 Python 环境执行。每次只运行一个 ngspice，和其他通道合计不超过两进程。

```sh
build/layout/venv/bin/python scripts/driver_interface_20261115/vcsel/run.py --candidate single-phy4 --rates 6.4 8.8
build/layout/venv/bin/python scripts/driver_interface_20261115/vcsel/run.py --candidate single-phy12 --rates 6.4 8.8
build/layout/venv/bin/python scripts/driver_interface_20261115/vcsel/run.py --candidate single-phy4-r25k --rates 6.4 8.8
build/layout/venv/bin/python scripts/driver_interface_20261115/vcsel/run.py --candidate double-phy4 --rates 6.4
```

已有目录只接受参数/网表/输入身份匹配的结果；复用不是新的仿真。每个候选先执行独立 DC-L0/L1。源供出、返还和净能量分别保留，8 个端口包括命令栅极源。

`vcsel-interface-selection.json` 是看留出之前写入的实际冻结记录，不应为了重跑而覆盖。选中 `single-phy12` 的复核命令为：

```sh
build/layout/venv/bin/python scripts/driver_interface_20261115/vcsel/run.py --candidate single-phy12 --rates 8.8 --steps 80
build/layout/venv/bin/python scripts/driver_interface_20261115/vcsel/run.py --candidate single-phy12 --rates 8.8 --holdout
build/layout/venv/bin/python scripts/driver_interface_20261115/vcsel/default_inputs.py single-phy4
build/layout/venv/bin/python scripts/driver_interface_20261115/vcsel/default_inputs.py single-phy4-r25k
build/layout/venv/bin/python scripts/driver_interface_20261115/vcsel/edge_diagnostics.py
build/layout/venv/bin/python scripts/driver_interface_20261115/vcsel/confirmation.py
build/layout/venv/bin/python scripts/driver_interface_20261115/vcsel/validate.py
build/layout/venv/bin/python scripts/driver_interface_20261115/vcsel/report_assets.py
build/layout/venv/bin/python scripts/driver_interface_20261115/vcsel/schematic.py
```

图的 PNG 由 `cairosvg.svg2png` 以 1.2 倍生成；macOS 如需 Cairo，可在该单次命令设置 `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`。字体为 Arial Unicode MS 的中文和符号兼容渲染；原图保留 SVG 文字。

## 证据与恢复

- 19 个新 SPICE 案例：8 个正常 DC、7 个开发帧、1 个半步长、1 个新留出、2 个开路默认态 DC。三种失败均保留：弱上游8.8、仅25k的8.8、旧双级接弱上游6.4（最后一个电流超模型域）。
- `build/driver-interface-20261115/VCSEL` 存放每例网表、模型子集、源码/依赖快照、结果、原生压缩波形及日志；compact JSON 在 `evidence/driver-interface-20261115/vcsel-*`。
- 每个 gzip 同时保存压缩文件和解压原始 SHA-256。`validate.py` 检查实际多行 PWL、全部 MOS D/G/S/B 与几何、8 源算术、冻结身份和原始字节哈希。
- 新发生器读取 20261111 两个被冻结的基线目录。跨电脑从零生成时必须先恢复此前 Release 中 `driver-methods-20261111/VCSEL/vc-single-r150` 和 `ab-improvement-20261111/VCSEL/vc-atten50-steer20` 的参考输入；Git 本身不包含这些 ignored build 文件。模型许可和版本仍由原项目锁定信息管理。
- 若只复跑某个已经恢复的 deck，可复制该案例到新的 scratch 目录，并以该目录为 cwd 执行 `ngspice -b testbench.spice`；不要覆写冻结案例。之后用相同分析源码/模型/训练规则重算。相同电路重跑不自动意味着求解输出字节逐一相同。
- `_diagnostics/open-input-*` 只删除4个上游输出 MOS来表达物理断开，保留69核心和所有节点。它测默认态，不能称为保护关断或供电掉电回灌试验。

这些新增原理图没有对应的新 layout、DRC/LVS/PEX 或实测 BER。原来源记录中的历史 `case` / `method_config` 留作基线出处，新实例的权威配置是 `interface_config` 和实际网表字节。
