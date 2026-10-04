# 开发环境与复现

环境状态日期：2026-10-05（Asia/Tokyo），v0.4。本页记录 **Mac arm64 的一像素仿真、原生寄生提取与Linux物理工具环境**。原生analog layout见[版图环境](layout/README.md)；数字PWM／共同top的Linux工具见[digital physical](digital/physical.md)。v0.4从冻结共同GDS实际执行五种RCstyle提取，见[joint PEX](research/joint-pex.md)；完整带pad/ESD芯片仍未建立。

## 当前可运行环境

| 项目 | 本次已验证版本 / 状态 | 用途 |
|---|---|---|
| Host | macOS、arm64 | 原生 batch execution |
| Icarus Verilog | 13.0 | 编译 RTL / testbench，生成实际 PWM event trace |
| ngspice | 47 | 公开 GF180MCU MOS model 的 transistor-level simulation |
| Python | uv 管理的 CPython 3.12.13 | 编排、结果校验和自动绘图 |
| Python dependencies | `uv.lock` | 固定 numpy / matplotlib 等依赖版本 |
| MOS models | `scripts/fetch_models.py` 的固定 commit / SHA256 | 下载并校验公开 model 子集 |
| Physical container | LibreLane3.0.14，锁定OCI digest，arm64 Linux | 项目独立Lima VM/containerd；实际数字physical与独立KLayout |
| Docker Desktop | 原有VM遇storage attachment错误，未reset用户磁盘 | 失败日志保留，成功流程采用上面的独立环境 |

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

基本回归复现时检查：LED model在指定current／temperature下是否校准；PWM是否来自RTL；平均电流是否按完整frame积分；negative control是否暴露headroom不足；step refinement是否收敛。该baseline LED为synthetic。独立[真实静态LED](research/measured-led.md)已经拟合公开I–V，但没有真实capacitance／temperature／optical模型，不能混作同一套验证。

## 已取得的完整 PDK 与两种工具环境

完整 `gf180mcuD` 已由 Ciel 取得，open_pdks build=`54435919abffb937387ec956209f9cf5fd2dfbee`。[Layout lock](../layout/pdk-lock.json)固定原生 Magic8.3.684 / Netgen1.5.324；[physical lock](../scripts/physical/pdk-lock.json)固定708份实际输入。Linux container 使用 Magic8.3.623 / Netgen1.5.316 / KLayout0.30.7；不同运行记录自己的工具版本，不把它们混称一个 binary 环境。

共同top的Magic／KLayout／LVS使用既有Linux容器；v0.3 metal-only link extraction用原生Magic。v0.4 joint extraction同样实际执行原生Magic8.3.684，锁定`gf180mcuD.tech`的nominal／HRHC／LRHC／HRLC／LRLC五种style；其系数、geometry、commands及全部physical inputs hash见[抽取方法](../evidence/joint-pex/extraction-method.json)。RCstyle与MOS PVT是不同维度。

新run先在私有build生成和检查，再发布，[joint PEX复现](../evidence/joint-pex/README.md)与[电气研究](research/robustness.md)说明端口及cut boundary。Magic实例／R-C记录排序可变化，复现要比较ordered formal ports、device geometry、数值和拓扑multiset，保留as-run与public文件的各自hash；语义一致不等于字节一致。v0.4电气post仅实例化joint模型一次，不叠加v0.3的SPEF／link／analog RC。

Joint信号模型理想化PG／body电阻和PG-only电容；其startup／series-R探针不是完整PG／substrate／数字芯片模型。阅读[预设电气范围](specifications/electrical-v0.4.md)后再重跑，以免把新增外部R/C假设称作package或PDN测量。实际reference generator、真实LED动态、provider接受与带pads/ESD芯片不由工具安装成功建立。

报告使用 Markdown3.8.2、Playwright1.62.1与Chrome154.0.8037.95（本次实际版本）。公开 `scripts/research/render_report.py` / `print_report.cjs`；后者默认加载可用的 `playwright`，也允许通过 `REPORT_PLAYWRIGHT_MODULE` 和 `REPORT_CHROME_PATH` 使用已有安装。HTML / PDF 是排版结果，不作为物理仿真输入；另一环境打印后仍需逐页检查。

## 历史调研的其他安装方式

- **模拟 schematic / layout：** 推荐锁定版本的 IIC-OSIC-TOOLS arm64 container，获取 Xschem、Magic、Netgen、KLayout 与完整 `gf180mcuD` PDK。需要验证 image digest、PDK build hash、GUI/batch 操作和第一块 analog cell 的 DRC/LVS/PEX。这套 container 本次未安装或验证。[IIC-OSIC-TOOLS 官方仓库](https://github.com/iic-jku/IIC-OSIC-TOOLS)
- **数字 physical implementation：** 推荐 macOS 15+ 的 LibreLane native Nix，以及其测试过的 Ciel PDK build。需要锁定 flow revision / lockfile、做 smoke test，再对本项目数字 block 执行 hardening。这套 Nix / LibreLane flow 本次未安装或验证。[LibreLane macOS 官方说明](https://librelane.readthedocs.io/en/stable/installation/nix_installation/installation_macos.html)
- **完整 PDK：** 用 Ciel 获取完整 `gf180mcuD`，同时保存 build hash、tool/deck versions 和 library selection。当前原始 `nmos_6p0` / `pmos_6p0` model 名称和打包 PDK 的器件名称可能不同，需要重新核对 netlist 和单位。[Ciel 官方仓库](https://github.com/fossi-foundation/ciel)

这些可选安装方式没有在本项目执行，保留为历史调研。当前实际完整PDK、原生模拟物理流程、独立Linux数字/共同top流程以上述locks和成功运行证据为准。
