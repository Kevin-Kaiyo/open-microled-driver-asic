# VCSEL 有限 CMOS 输入级：MOS PVT 与供电筛查

本目录延续 2026-11-15 冻结的 69 MOS 核心 + 4 MOS 有限上游 CMOS（N/P = 12/24 µm，L = 0.28 µm）。新结果写入本阶段目录，不改历史冻结证据。

## 研究问题和边界

1. 名义条件下通过的完整帧，在 GF180 MOS 工艺角、−40/25/85°C 和四路 3.3 V 供电 ±5% 后是否仍满足电气应力与接收余量？
2. 原生波形若显示输入级负向注入，增加实际栅前电阻能否降低负峰？速度和命令端/上游能量代价是多少？
3. 在修复输入应力后，若慢角依旧失去接收余量，减少内部输入串联阻尼是否能修复 DI→GP→电流脉冲的收窄？否则需明确降速边界。

这是 **MOS PVT 与供电扫角**，不是完整发光器件 PVT。850 nm VCSEL 图读 I–V、光动态代理、150 fF 电容、0.5 Ω/0.2 nH 封装和 5 GHz 接收器保持原先条件；温度没有进入这些图读/假定参数。VSET/VREGSET 与所有理想电阻不加容差，因此 DC 的小电流误差不代表真实产品精度。无新的 Pad/ESD、厂商 PHY、提取后版图、抖动噪声、热稳态或实测 BER 结论。

`protocol.json` 冻结主网格。四路 VLASER/VDD/VREF/VPHY 同扫；独立命令端保持 0–3.3 V/20 ps，不随 VPHY 缩放。两路命令端能量以及六路供电/参考端均进入八源能量账本。

## 复现

使用项目 Python（`build/layout/venv/bin/python`）与 ngspice 47。一次调用只运行一个 SPICE 子进程；外层并行必须遵守总资源约束。

```sh
build/layout/venv/bin/python scripts/driver_pvt_20261117/vcsel/run.py --variant frozen --kind dc
build/layout/venv/bin/python scripts/driver_pvt_20261117/vcsel/run.py --variant frozen --kind short
build/layout/venv/bin/python scripts/driver_pvt_20261117/vcsel/run.py --variant cmd-r330 --kind short
build/layout/venv/bin/python scripts/driver_pvt_20261117/vcsel/run.py --variant cmd-r330 --kind full --corners sshotlow tthigh tt25
build/layout/venv/bin/python scripts/driver_pvt_20261117/vcsel/reuse_nominal.py
build/layout/venv/bin/python scripts/driver_pvt_20261117/vcsel/diagnostics.py
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib build/layout/venv/bin/python scripts/driver_pvt_20261117/vcsel/report_assets.py
```

1024 line-bit 短帧仅筛查原生器件应力与模型域，不计作 4096 位接收结论。完整帧为 4736 line bits / 4096 payload bits，8.8 Gb/s 对应 10.175 GBd；采用原有训练后冻结相位的接收算法和 0.37 UI、7.5 µAeq 门槛。所有图上的能量分母都是尝试发送的净载荷位；未通过点不是合格传输能耗。

## 审计

每例保存 `testbench.spice`、实际 `stimulus.json`、`manifest.json`、完整执行脚本与辅助脚本字节快照、日志和原生全器件节点波形 SHA。四个模型文件只在 `_inputs/` 存一份、每例相对符号链接。`manifest.pvt_config` 是本阶段权威条件；继承的旧 `interface_config` 仅为历史来源。

`result.json` 由原生采样计算全 MOS 端压/体结和八源正向、返能、净能量；`analysis.json` 是固定光模型/RX 的完整帧结果。原生 ASCII 在压缩后解压复核 SHA 才删除，保留 gzip。`diagnostic.npz` 仅供轻量预览，不能替代原生应力筛查；`minimum-event.npz` 与 `comparison-event.npz` 保留事件附近所有原生采样。后一文件使用相同绝对时间窗口，不把不同全局极值强行平移重叠。

首个 `frozen/sshotlow/short-net8.8-s40` 在成功求解/压缩之后发生 NumPy 布尔 JSON 序列化错误；其 `postprocess-recovery-source.py` 与结果中的 `postprocess_recovery` 记录说明了只重新后处理的恢复。原始执行源码、网表、日志与原生波形未改写。

`nominal-reuse.json` 公开引用原阶段 TT25 的完整帧，未把复用改称新仿真。该完整帧的器件清单、四个模型文件、八源端口和刺激前缀已与新 TT25 短帧核对。
