# Registered PWM 与 GF180 standard-cell synthesis

2026-10-04（Asia/Tokyo），已把单像素 `pwm` 改为 rising-edge flip-flop output，并完成锁定 GF180 standard-cell library 的 synthesis、原 exhaustive regression 和两种 gate-level simulation。本页记录 synthesis 小阶段；后续已完成的 standalone PWM physical implementation、9-corner STA、实际 SDF replay 与独立 DRC 请优先看 [physical.md](physical.md)。

## 为什么注册输出

原设计把 `active_enable && counter < active_duty` 直接接到 `pwm`。RTL 中，同一 clock edge 的更新通常表现为一次输出事件；真实 counter bits 和 comparator 路径具有不同 propagation delay，不能据此排除输出毛刺。

当前输出由 FF 驱动。普通 slot 在 rising edge 注册 `next_counter < active_duty`；frame 边界注册新 `enable && bounded_duty != 0`，以保持 slot 0 使用刚锁存的输入。reset 同步清零输出；下一次 reset release 后的 rising edge 仍从 slot 0 开始。没有增加一周期延迟，clock / reset / duty / enable / pwm 接口保持不变。

9-bit duty 仍表示 0–256 个高电平 slot，257–511 saturate 为 256。每帧 256 cycles，默认 clock=1 MHz，frame=256 µs，PWM frequency=3906.25 Hz。`duty=256` 连续导通，不在 frame 边界掉低；`duty=0` 或 disabled 连续关闭。帧中输入变化只在下一帧生效。

## 实际证据

| 检查 | 条件和结果 |
| --- | --- |
| RTL exhaustive | 518 完整 frame、133159 次 slot/value checks；全部 257 合法 duty、255 clamp 输入、边界更新、enable、reset 通过 |
| RTL event monitor | 543 已知 PWM events；只在 rising edge 发生，每个 edge 最多一次；最短完整 high/low 都为 1000 ns |
| Synthesis | Yosys 0.69+post，git `143eb14f9cc55d6f8927e68523b0c9d2166ed02c`；ABC 1.01；95 standard cells，其中 19 个 `dffq_1` |
| Library | Ciel/open_pdks build `54435919abffb937387ec956209f9cf5fd2dfbee`，`gf180mcuD`，`gf180mcu_fd_sc_mcu7t5v0`，TT / 25°C / 3.3 V synthesis Liberty |
| Library cell area | 2434.4768 µm²，仅 mapped cells 的 Liberty area 之和；不是 core/die area |
| Structural check | `pwm` 的唯一直接 driver 是 `dffq_1.Q`，该 FF 的 `CLK` 直接连接输入 clock；没有未映射 Yosys internal cells |
| Functional gate simulation | 官方 cell/UDP Verilog，`FUNCTIONAL`，0 delay；同样的 518 frame / 133159 checks、543 events 通过 |
| Placeholder-delay gate simulation | 官方 Verilog 的 `specify` 标量 `1.0`，明确继承 `1ns/1ps`；100 ns 后采样；同样 exhaustive checks 通过，实际输出边沿整体晚 1 ns；最短 high/low 1000 ns |
| Trace comparison | 10 个 duty/enable cases 的实际 RTL 与 functional gate CSV 完全一致，包括 off、1-slot pulse、255/256、full-on、clamp、disabled |
| Bridge unit tests | `tests/test_bridge.py` 实际通过，覆盖 RTL→PWL 边沿、完整时间窗及不规则样本的 time-weighted integration |

首条 RTL reset-low event 仍为 500 ns，第一 frame 为 2500 ns；默认 measurement window 保持 514500–1538500 ns。注册输出前后的默认 CSV 在本地逐字节比较一致。带 1 ns 占位 delay 的 gate CSV 则从 501 ns 开始，它用于数字延迟检查，不替代 coupled regression 的理想 RTL 输入。

精简成功证据位于 `evidence/digital/`：summary（包括实际工具版本、binary hashes、source/library hashes、cell counts、仿真条件）、mapped netlist、exhaustive logs、bridge log 和三个 PWM CSV。完整生成文件、命令参数、安装记录及诊断保存在 `build/digital/`。

## 延迟模型边界

公开 GF180 cell Verilog 内的 `1.0` 是 timing template 占位值，并非 synthesis Liberty 的查表延迟。本页表格中的早期 synthesis regression 没有生成 SDF、模拟 extracted interconnect 或执行 STA；后续 [physical implementation](physical.md) 已独立生成 SPEF/SDF 并执行 STA，证据保存在 `evidence/physical/`。

Icarus 13.0 在解析整库时报告 **120 条 conditional edge-sensitive `ifnone` path 不支持、1926 条 timing checks 不支持**。这些诊断保留在 `build/digital/gate-placeholder-delay-compile.log`，计数和日志 hash 保存在 summary。实际 CSV 证明本次使用的 FF clock-to-Q 输出路径为 1 ns；通过结果仅涵盖该 simulator 所支持并实际执行的模型。setup/hold、recovery/removal、clock skew、时钟毛刺、PVT timing closure、未支持的 path、噪声/供电效应和硅片 PWM 都未验证。

注册输出把组合 comparator 与像素开关输入隔开，但其 D-input 仍需要在时钟边沿前满足 setup/hold。后续已针对实际 mapped netlist 完成 placement、CTS、routing 和 STA，并把支持的实际 SDF 输出边沿 replay 到独立 analog RC。早期 1 ns template simulation 的适用范围保持不变；最终 physical 结果仍不建立共同 top、silicon 或 tape-out readiness。

## 复现

先按 [layout 环境](../layout/README.md) 建立与 `layout/pdk-lock.json` 相符的完整 PDK，默认路径为 `build/layout/pdk/gf180mcuD`。本目录的 [library-lock.json](../../scripts/digital/library-lock.json) 单独锁定实际 synthesis Liberty、canonical cell Verilog、UDP primitives 和 PDK `SOURCES` 的 SHA256；不同字节的输入会拒绝运行。

```sh
HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install yosys icarus-verilog
uv sync --locked
uv run python scripts/digital/run.py
uv run python scripts/digital/run.py --publish-evidence
```

支持 `--pdk=<path>` 和 `--output=<path>`。runner 先检查锁定输入与工具，运行 RTL / bridge checks，执行 `synth -noabc`、`dfflibmap`、`abc -liberty`，再检查映射结构与 gate simulation。只有所有检查成功才写新 summary 和发布 evidence。Homebrew binary 本身没有由 package manager 锁定；本次实际版本和 SHA256 记录在 evidence，未来重跑需要比较。

本次 Homebrew Yosys 的 dependency 安装把默认 Tcl/Tk link 切换到 9.1.0。既有 Magic/Netgen 原生构建应继续使用其固定 Tcl/Tk 8.6.18 路径；旧版本安装目录没有删除。

## 公开来源

- [Yosys 官方 synthesis / Liberty mapping 示例](https://github.com/YosysHQ/yosys/blob/main/README.md)：先 `dfflibmap`，再用 ABC mapping combinational cells。
- [Yosys 官方 technology-mapping command reference](https://yosyshq.readthedocs.io/projects/yosys/en/stable/cmd/index_passes_techmap.html)：`dfflibmap` 和 `abc -liberty` 的作用与范围。
- [Icarus 官方 compiler flags](https://steveicarus.github.io/iverilog/usage/command_line_flags.html)：`-g2012`、`-gspecify`、`-D`、`-P` 和 top-module selection；实际不支持项以本次 compiler diagnostics 为准。
- [GlobalFoundries 公共 MCU7 standard-cell source](https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_sc_mcu7t5v0)：public Liberty、Verilog/UDP 与 Apache-2.0 source notices。此处实际运行输入使用上表锁定的完整 PDK build。
