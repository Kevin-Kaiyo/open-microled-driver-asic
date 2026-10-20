# 单通道高速 MicroLED Driver：版图与寄生参数验证

入口：[中文研究报告](index.html) · [实际 GDS 分层查看器](layout-viewer.html) · [独立审阅](verification-notes.md)。

本阶段以相同 MicroLED 电气负载、PRBS 与接收代理，对电压驱动 A 和电流转向 B 做原理图 → 网格量化 → 实际器件几何 → C → RC 的控制实验。物理核心使用 GF180MCU D，A 为 6 MOS，B 为 9 MOS。它不是完整的可流片 ASIC，也不是光学 BER 测量。

## 设计和证据入口

| 内容 | 路径 |
|---|---|
| 原始晶体管网表 | `analog/highspeed_nrz/` |
| 独立物理原理图、生成连接表、许可证 | `layout/highspeed_nrz/` |
| 版图与提取脚本 | `scripts/highspeed_nrz_layout/` |
| 仿真、分析、验证及报告脚本 | `scripts/highspeed_nrz_pex/` |
| 固定完整 PDK 与工具版本 | `layout/pdk-lock.json` |
| 物理精简数据和 GDS | `evidence/highspeed-nrz-pex/physical/` |
| 独立几何、电容与来源审计 | `evidence/highspeed-nrz-pex/audit/` |
| 正式逐 case 汇总 | `evidence/highspeed-nrz-pex/summary.json`、`summary.csv` |
| 仿真交付核验 | `evidence/highspeed-nrz-pex/validation.json` |
| 被动互连指定端点电阻 | `evidence/highspeed-nrz-pex/wire-paths.json` |
| 原始物理运行 | `build/highspeed-nrz-layout/r3`；修正模型 `r4` |
| 正式仿真原始数据 | `build/highspeed-nrz-pex/run-0m3zyewc/` |
| 被审计暂停的诊断仿真 | `build/highspeed-nrz-pex/run-a3o5_yew/`，保留中断和原始结果 |
| 原理图基线复用来源 | `build/highspeed-nrz/run-0xqxvspp/`，只读引用，未重跑或覆盖 |

路径以仓库根为基准。物理 GDS 在 r3 冻结，r4 不改变几何、全部 R 或 MOS。r4 是**经过审计的 RC 模型组装**：从原 `.ext` 取得高精度 C，防止当前固定工具的原生导出重复或错误移动电容。它不是未经修改的 Magic RC 输出。对地 C 的空间分配仍为近似，RCLUMP 控制检查这一近似的敏感性；耦合 C 在两版中都保留在原逻辑节点。

## 阅读顺序

1. 先看报告第 1～3 节，理解结果边界、实际电路、MOS 与金属层对应。
2. 再看第 4～6 节，区分几何效应、互连效应、电源回灌、确定性接收筛查与数值误差。
3. 需要复核时，从汇总的 `result_json` / `analysis_json` / `waveform` 找到每条原始数据；每份输入、波形和分析均有哈希。
4. 设计方向见第 7 节；不要把通过的一个实验阶段升级为完整产品或生产签核。

## 本地打开

直接打开 `index.html` 和 `layout-viewer.html` 即可；查看器的几何数据已嵌入 HTML，不依赖远程服务。也可以从仓库根启动只绑定本机的服务，使报告中的仓库文件链接完整可用：

```sh
python3 -m http.server 8772 --bind 127.0.0.1 --directory .
```

浏览器打开 `http://127.0.0.1:8772/docs/research/highspeed-nrz-pex-20261020/index.html`。图片可点击查看完整 SVG；查看器可以隐藏单层金属、选择网络及器件端子。

## 恢复和复算既有结果

本轮是增量备份，依赖上一阶段的原理图基线。恢复说明与 GitHub Release 清单见 [`../../development-handoff.md`](../../development-handoff.md)。恢复时保留相同仓库相对路径；工具遇到不同内容的现有文件会停止，不能强制覆盖。

在准备好 Python/NumPy/Matplotlib、固定 PDK/工具和字体输入后：

```sh
build/layout/venv/bin/python scripts/highspeed_nrz_pex/analyze.py \
  --work build/highspeed-nrz-pex/run-0m3zyewc
build/layout/venv/bin/python scripts/highspeed_nrz_pex/validate.py \
  --work build/highspeed-nrz-pex/run-0m3zyewc
build/layout/venv/bin/python scripts/highspeed_nrz_pex/diagrams.py
build/layout/venv/bin/python scripts/highspeed_nrz_pex/render_layout.py
build/layout/venv/bin/python scripts/highspeed_nrz_pex/wire_paths.py
build/layout/venv/bin/python scripts/highspeed_nrz_pex/report_physical.py
build/layout/venv/bin/python scripts/highspeed_nrz_pex/report_results.py
build/layout/venv/bin/python scripts/highspeed_nrz_pex/report.py
python3 scripts/highspeed_nrz_pex/validate_report.py
```

`analyze.py` 重新核验并计算既有波形，不等于重新运行 ngspice。图形脚本使用 `build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf`，字体随备份的报告输入组恢复。报告解释文字在 `report-content.json` 与 `report-template.html`；数值表和数据图自动从汇总生成。

## 重新运行实验

物理流程及新运行目录参数见 [`../../../layout/highspeed_nrz/README.md`](../../../layout/highspeed_nrz/README.md)。运行需要完整固定 PDK、Magic、Netgen、KLayout 和独立 DRC 容器，不能只用晶体管模型子集。

仿真前检查：

```sh
build/layout/venv/bin/python scripts/highspeed_nrz_pex/run.py --preflight
```

以 `evidence/highspeed-nrz-pex/physical-contract-r4.json` 的结构创建指向新模型的合同。`run.py --contract <合同>` 会建立新的冻结运行并打印 `WORK`；后续使用 `--work <该路径>`，不要覆盖已有正式运行。

```sh
build/layout/venv/bin/python scripts/highspeed_nrz_pex/run.py \
  --contract evidence/highspeed-nrz-pex/physical-contract-r4.json --stage smoke --variants GEOM,C,RC
# 将下方 NEW_RUN 替换成刚才输出的仓库相对路径。
build/layout/venv/bin/python scripts/highspeed_nrz_pex/run.py --work NEW_RUN --stage dc --variants GEOM,C,RC,SNAP
build/layout/venv/bin/python scripts/highspeed_nrz_pex/run.py --work NEW_RUN --stage nominal --variants GEOM,C,RC,SNAP
build/layout/venv/bin/python scripts/highspeed_nrz_pex/run.py --work NEW_RUN --stage convergence --variants GEOM,C,RC
build/layout/venv/bin/python scripts/highspeed_nrz_pex/run.py --work NEW_RUN --stage pvt --variants RC
build/layout/venv/bin/python scripts/highspeed_nrz_pex/controls.py --work NEW_RUN
```

这些命令沿用现有模型，没有重新校准偏置。需要改变 LED、供电、负载或器件尺寸时，创建新控制实验和新的来源清单，重新做 DC 校准及耦合回归。原理图基线依赖源与已有数据若不一致，preflight 应失败，不应绕过。

## 未完成范围

公开 PDK 下的 DRC/LVS、RC 守恒与电气实验已分开记录；实际制造需厂方认可的规则与交付流程。当前没有 pad/ESD、电源调节器、完整密度和金属填充、天线、EM/IR、热/老化/失配统计、封装电磁模型或真实光接收机。CLED、封装 R/L、光学时间常数和接收带宽仍是实验假设。
