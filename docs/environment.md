# 开发环境与复现

环境检查日期：2026-10-03（Asia/Tokyo）。本页记录 **Mac arm64 上的 1-Pixel RTL → SPICE batch simulation 环境**。随后已建立 standalone analog cell 的 Magic / Netgen / RC 与 GDS 流程，安装版本、完整 PDK 锁定与实际复现步骤见 [版图环境](layout/README.md)。完整数字 RTL-to-GDS 与顶层芯片集成尚未建立。

## 当前可运行环境

| 项目 | 本次已验证版本 / 状态 | 用途 |
|---|---|---|
| Host | macOS、arm64 | 原生 batch execution |
| Icarus Verilog | 13.0 | 编译 RTL / testbench，生成实际 PWM event trace |
| ngspice | 47 | 公开 GF180MCU MOS model 的 transistor-level simulation |
| Python | uv 管理的 CPython 3.12.13 | 编排、结果校验和自动绘图 |
| Python dependencies | `uv.lock` | 固定 numpy / matplotlib 等依赖版本 |
| MOS models | `scripts/fetch_models.py` 的固定 commit / SHA256 | 下载并校验公开 model 子集 |
| Docker daemon | 当前未运行 | 本次未通过 container 验证 |

PDK model acquisition、工具角色和版本边界见 [PDK 与工具链调研](research/pdk-and-tools.md)。这里的 SPICE models 是 full PDK 的子集；安装 ngspice / Icarus 成功并不代表已经具有 layout、DRC/LVS/PEX 或 GDS flow。

## 原生复现

在仓库目录运行。首次需要已有 Homebrew 和网络，brew 指令显式关闭自动 update / install cleanup：

```sh
HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install ngspice icarus-verilog uv
uv python install 3.12.13
export UV_PYTHON=3.12.13
uv sync --locked
make setup
make test
make sim
make evidence
```

`make setup` 再次执行 locked dependency sync，并下载、校验固定 GF180MCU models。`make test` 检查脚本及 RTL self-check；`make sim` 执行 transistor-level 联动仿真、检查结果并生成波形；`make evidence` 重新生成并保存可随仓库检查的证据。

检查实际运行版本：

```sh
iverilog -V
ngspice --version
uv run python --version
```

Homebrew 安装指令获取执行当天的 formula，**并未固定 Homebrew 内的 ngspice/Icarus binary**。本次验证版本为上表所列值；在另一台机器或以后重跑，应保存实际版本及日志，比较结果后再声明复现成功。`uv.lock`、公开 model commit / SHA256 与保存的 netlist/log/metrics 提供依赖和输入追溯；它们不能代替 EDA binary 环境锁定。

## 查看输出与验收

`build/phase1/` 保存运行日志、生成的 SPICE testbenches、RTL event traces、waveform data、自动绘图、`metrics.csv` 和 `summary.json`。最终判断以命令成功退出、`summary.json` 的实际 checks、模型校准以及原始波形为依据；仅看到绘图或日志中的正常结束字样不足以判断设计正确。

复现时特别检查：LED model 在指定 current / temperature 下是否校准；PWM duty 是否来自 RTL；平均电流是否在完整 frame window 上积分；negative control 是否确实暴露 headroom 不足；step refinement 的结果是否收敛。LED 电气模型为 synthetic model，未对真实 MicroLED 的 measured I-V / capacitance / optical output 拟合。

## 后续完整 EDA 环境

- **模拟 schematic / layout：** 推荐锁定版本的 IIC-OSIC-TOOLS arm64 container，获取 Xschem、Magic、Netgen、KLayout 与完整 `gf180mcuD` PDK。需要验证 image digest、PDK build hash、GUI/batch 操作和第一块 analog cell 的 DRC/LVS/PEX。这套 container 本次未安装或验证。[IIC-OSIC-TOOLS 官方仓库](https://github.com/iic-jku/IIC-OSIC-TOOLS)
- **数字 physical implementation：** 推荐 macOS 15+ 的 LibreLane native Nix，以及其测试过的 Ciel PDK build。需要锁定 flow revision / lockfile、做 smoke test，再对本项目数字 block 执行 hardening。这套 Nix / LibreLane flow 本次未安装或验证。[LibreLane macOS 官方说明](https://librelane.readthedocs.io/en/stable/installation/nix_installation/installation_macos.html)
- **完整 PDK：** 用 Ciel 获取完整 `gf180mcuD`，同时保存 build hash、tool/deck versions 和 library selection。当前原始 `nmos_6p0` / `pmos_6p0` model 名称和打包 PDK 的器件名称可能不同，需要重新核对 netlist 和单位。[Ciel 官方仓库](https://github.com/fossi-foundation/ciel)

这些是后续推荐路径，当前安装验证范围仍为第一阶段原生仿真。
