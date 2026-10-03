# Standalone PWM physical implementation

2026-10-04（Asia/Tokyo）。一个 registered PWM macro 已完成锁定 GF180MCU D / MCU7 standard-cell 的 placement、CTS、routing、RC extraction、9-corner STA、Magic DRC、Netgen LVS 和独立 KLayout DRC。实际 GDS/LEF 是 180 × 180 µm，19 个 registers；完整结果索引是 [physical summary](../../evidence/physical/summary.json)。此处是独立数字 macro；analog cell 的独立版图和 electrical replay 没有被包装为共同 physical top。

## 实际检查

| 检查 | 本次实际结果 |
| --- | --- |
| LibreLane Classic | 完整 76 steps，CLI exit 0；最终 run `pwm-v0.2-sized` |
| STA | nom/min/max RC × TT 25°C / 3.3 V、SS 125°C / 3.0 V、FF −40°C / 3.6 V，共 9 corners |
| Setup / hold | 全部 9 corners violation count=0；最差 overall margins 793.656477 ns / 0.436677 ns |
| 显式 R2R STA | 每个 corner 查询全部 19 个 register endpoints；最差 setup 985.838745 ns；setup/hold 均通过 |
| Design rules | max transition 3 ns、max capacitance 0.2 pF、max fanout 10 保持原约束；最终 slew/capacitance/fanout violations=0 |
| Routing / connectivity | route DRC=0，critical / all disconnected pins=0；OpenROAD antenna violating nets/pins=0 |
| Digital Magic DRC / Netgen LVS | 0 errors；实际 final netlist 与 extracted layout 比较 |
| 独立 digital KLayout DRC | 锁定完整 PDK `run_drc.py`，variant D / `pixel_pwm`；XML items=0 |
| 独立 analog KLayout DRC | 同一环境和完整 deck，`pixel_driver_layout`；XML items=0；GDS SHA256 `20ff3a9d180eb0ef19de7a17a82e492e9153d2d7cf8ae77585024b10c7f431ad` |
| Analog LEF consumer | OpenROAD/OpenDB 实际读入：95 × 37.66 µm、ORIGIN (0, 0.3)、7 ports 的 direction/use、Metal3 port geometry、228 OBS 与 origin-adjusted boundary 全部通过 |

KLayout 本次启用 FEOL、BEOL、connectivity、offgrid；没有运行它的 density 或 antenna modes。LibreLane 内置 KLayout DRC 因缺少 `KLAYOUT_DRC_RUNSET` 被跳过，上表结果来自其后独立执行的完整 PDK deck。OpenROAD 对部分 LEF58 enclosure 属性报告不支持；最终实际 GDS 的 Magic 和独立 KLayout checks 均通过。IR-drop 阶段没有明确 `VSRC_LOC_FILES`，不作为 supply sign-off。所有 warnings 保留在 [digital warnings](../../evidence/physical/digital/warnings.log)。

原 flow 汇总把 setup R2R 写为 infinity / N/A，因为每个 endpoint 的 worst setup path 来自 input。额外用同一 implemented netlist、final SDC、匹配 SPEF 和 Liberty 显式限制 register→register 路径，获得每 corner 19 个有限正 slack。compact metrics 将非有限值转为 `null`；完整原始 metrics 保存在 `build/physical-flow/pwm-v0.2-sized/final/`。

## Sizing 与失败记录

最初的 complete run 虽然 setup/hold、DRC/LVS 通过，SS corner 仍有 21 个 slew violations，不能据 CLI exit 0 宣称 timing closure。将 repair margins 拉到 50% 导致 OpenROAD post-placement repair 消耗约 5.6 GiB RSS 并被独立 VM 的 Linux OOM killer 终止；切换 DEFAULT_CORNER 到 SS 没有改善。排除 delay buffers 后，弱 `buf_1` 驱动十个 loads 仍留下 11 个 slew violations。

最终 [no-pnr.cells](../../scripts/physical/no-pnr.cells) 保留完整 PDK 的两个原始 exclusion entries，并排除 delay buffers 与 `buf_1`，使 resizer 使用较强的普通 `buf_2`。修复保留 3 ns 约束、9 个 corners 和原 repair margins 20% / 10%。最终 [config.json](../../layout/digital/config.json) 可重现该选择。失败 logs、命令、exit codes 和 OOM kernel log 均留在 `build/physical-flow/`；summary 保留 prior-attempt 状态和 hashes。

## STA 假设和 SDF replay

clock period=1000 ns，clock transition=0.15 ns，uncertainty=0.25 ns，input/output delay=200 ns，early/late derate=−5%/+5%。输入 driving cell 是 `inv_1`，clock driving cell 是 `inv_4`。输出 load **72.91 fF 是配置假设，并非实测 analog input capacitance**。没有把 analog RC 的输入负载反馈到 digital Liberty/SDF delay calculation。

9 个实际 routed SDF 分别使用相应 Liberty corner 和 nom/min/max extracted SPEF。Icarus 13.0 用 canonical cell/UDP Verilog、`-gspecify -ginterconnect` 和 1 ns / 1 ps time precision；原 testbench 在 100 ns 后采样，并允许 output edge 落在 input rising edge 后 0–50 ns。每个 corner 均通过原 518 frames / 133159 slot checks、全部 257 合法 duty、255 clamp inputs、reset、enable、frame updates。event monitor 检查每个 rising edge 最多一次 PWM toggle，reset 后不出现 X，完整 high/low pulse 不短于 950 ns。

关键 clk→clock buffers→output FF→output buffer→pwm 路径的实际 SDF arcs 另行求和，与导出 CSV 的时间戳在 5 ps guard 内一致；没有编辑官方 cell models。TT / nominal RC 的 output rise delay=2.644 ns、fall delay=2.360 ns，最短完整 high pulse=999.716 ns。9 corners 的 rising delays 为 1.544–5.212 ns，最短 high pulse=999.391 ns（max SS），最短 low pulse=1000.150 ns（min FF）。这些数字仅适用于上述抽取、PVT、load 和 simulator model。

compiler 对完整 canonical library 保留 120 条 unsupported edge-sensitive `ifnone` paths 和 1926 条 unsupported timing checks。每个 SDF replay 另有 **24 个 XOR/XNOR ModPath 不匹配、19 个 TIMINGCHECK unsupported**；runner 确认未匹配 cells 不位于关键 clock/output path，所有 INTERCONNECT 与关键 output arcs 正常注入。原官方 XOR/XNOR 的部分 path delay 没有得到完整 annotation，timing checks 也未由 simulator执行。setup/hold 证据来自独立 STA；这里的 waveform 检查不是完整 SDF sign-off。

实际 TT SDF CSV 和 ideal RTL CSV 各自驱动冻结的 20/4 analog RC netlist，再用完整锁定 PDK 的 ngspice model 仿真。duty 0/1/64/255/256 共 **10 个 transient runs + 3 个独立 LED DC calibrations**，所有 paired current guards 通过；duty=1 的平均 branch current 为 RTL 0.392103669 µA、SDF 0.391991966 µA，差 −0.000111703 µA。固定 measurement window 仍是 514.5–1538.5 µs，采用 time-weighted integration；SDF 的实际 duty 按 fractional-ns events 计算，不强制改写成 ideal duty。

该 electrical path 是 **单向 event replay、ideal voltage source 加 10 ns ramp**，没有 analog feedback、共同 placement、共同 top LVS/PEX、完整 digital transistor transient、pads、silicon 或 optical measurement。MicroLED load 仍为 synthetic，average branch current 仍是 electrical brightness proxy。详细条件和每 corner 的实际警告见 [SDF summary](../../evidence/physical/sdf/summary.json)。

## 独立工具环境与复现

Docker Desktop 曾报告 storage attachment invalid，未 reset、删除 `Docker.raw`、删除用户 VM 或修改 macOS security attributes。独立 Lima 2.2.0 的 arm64 VZ VM 位于 `build/physical-flow/lima`，4 CPUs / 6 GiB RAM / 16 GiB guest disk，仅共享项目目录。初始 10 GiB guest disk 在 image extraction 阶段 no space left，已保留 exit 1 log；只对本项目 VM 执行 fstrim、resize 后重试成功。

容器 index digest 为 `sha256:f91b21d75f79871f9ccf37451020b5d2f7b3236881a997ff709c561e8280a30f`，arm64 child manifest 为 `sha256:f851ed1ae33a641389239dcf93194a8a2077e39eab9b1afdf8f9321078e49a18`。实际工具是 LibreLane 3.0.14、OpenROAD `dcf36133a369abc8f3c5e5738cd4d82e4903c0e0`、Yosys 0.62 `7326bb7d6641500ecb285c291a54a662cb1e76cf`、KLayout 0.30.7、Magic 8.3.623、Netgen 1.5.316。版本、launcher hashes、image / guest-image pins 见 [tool versions](../../evidence/physical/tool-versions.json) 与 [environment inputs](../../evidence/physical/environment-inputs.json)。此工具栈与早期 native synthesis/Magic 环境分别记录。

完整 PDK build 是 `54435919abffb937387ec956209f9cf5fd2dfbee`。[physical PDK lock](../../scripts/physical/pdk-lock.json) 记录实际 resolved physical inputs 和完整 KLayout deck tree 共 708 files；runner 在后续重跑前检查这些字节。第一次实现前没有保存完整 runner source snapshot，真实冻结 config、RTL、exclusion file、CLI argv、container digest 和 post-run PDK hashes 已保留；summary 区分 actual frozen inputs 与 packaging 时的 current source hashes。

```sh
HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install lima
export LIMA_HOME="$PWD/build/physical-flow/lima"
limactl start --tty=false --name=asic scripts/physical/lima.yaml
uv pip install --target build/physical-flow/linux-python -r scripts/physical/requirements.txt
uv run python scripts/physical/run.py tools
uv run python scripts/physical/run.py digital --run-name pwm-v0.2-sized
uv run python scripts/physical/run.py sta-reg --run-name pwm-v0.2-sized
uv run python scripts/physical/run.py klayout --run-name digital-klayout-v0.2 --gds build/physical-flow/pwm-v0.2-sized/final/gds/pixel_pwm.gds --topcell pixel_pwm
uv run python scripts/physical/run.py klayout --run-name analog-klayout-v0.2 --gds evidence/layout/pixel_driver_layout.gds
uv run python scripts/physical/run.py macro-read --run-name analog-macro-read-v0.2
uv run python scripts/physical/run_sdf.py --publish-evidence
uv run python scripts/physical/publish.py
```

首次启动需在该独立 VM 内 pull 上述 immutable container image；raw 下载、运行和失败 logs 保留在 `build/physical-flow/`。每个新的 digital run 使用独立 `frozen-inputs/<run-name>/`；不要复用含不同输入的 frozen directory。compact 成功 reports、GDS/LEF、netlists、SDC、SPEF/SDF 位于 `evidence/physical/digital/`，没有在这里生成共同 analog/digital top。

公开 primary sources：[LibreLane installation](https://librelane.readthedocs.io/en/stable/installation/docker_installation/installation_linux.html)、[configuration variables](https://librelane.readthedocs.io/en/stable/reference/step_config_vars.html)、[Lima installation](https://lima-vm.io/docs/installation/)、[Lima containerd](https://lima-vm.io/docs/examples/containers/containerd/)、[OpenROAD APIs](https://openroad.readthedocs.io/en/latest/main/src/README.html)、[OpenSTA formats and command interface](https://github.com/The-OpenROAD-Project/OpenSTA)、[Icarus flags](https://steveicarus.github.io/iverilog/usage/command_line_flags.html)、[GF180 verification decks](https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_pr)。实际结果和不支持项以锁定工具、输入和本次 logs 为准。
