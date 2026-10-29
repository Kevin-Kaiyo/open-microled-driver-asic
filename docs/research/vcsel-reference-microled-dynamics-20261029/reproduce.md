# 恢复、复现与证据位置

本说明区分三件事：读报告、恢复原始证据、在另一台机器重跑。文件哈希相同证明字节一致；只有重新执行与对比才证明该机器上可复现。这里不声称已经在另一台机器运行了新的晶体管仿真。

## 1．先读什么

- [主报告](index.html)：问题、修改、对照数据与当前边界。
- [动态模型证据专章](microled-dynamic-evidence.html)：MicroLED 原始表格、参考面、论文索引与下一步模型契约。
- `evidence/vcsel-robustness-20261029/report-cases.json`：主报告使用的精确案例名。
- `evidence/vcsel-robustness-20261029/independent-review.md`：由另一实现独立复算的接收、能量、端压与模型域结论。
- `evidence/vcsel-robustness-20261029/summary.json`：本轮全部已记录成功仿真和失败，保留中间版本。

## 2．恢复原始文件

源网表、脚本、公开研究报告与紧凑证据由 Git 保存；忽略的 `build/` 原始数据由同阶段 GitHub Release 保存。当前阶段为 `vcsel-reference-microled-dynamics-20261029`。实际上传/读回状态以 `archive-remote.json` 为准；没有该回执时，不把下面的恢复步骤当作已经上传的证明。

下载该 Release 的 JSON 清单与所有分卷，在仓库根目录执行：

```sh
python3 scripts/backup/release_bundle.py verify \
  --manifest /path/to/downloads/vcsel-reference-microled-dynamics-20261029.json \
  --asset-dir /path/to/downloads
python3 scripts/backup/release_bundle.py restore \
  --manifest /path/to/downloads/vcsel-reference-microled-dynamics-20261029.json \
  --asset-dir /path/to/downloads --root .
```

程序逐分卷和成员校验 SHA-256，恢复相对路径；遇到已有不同内容会拒绝覆盖。原始 deck 中含旧机器绝对路径，所以跨机重跑应使用生成脚本，不能直接假设恢复的 deck 路径自动有效。

本阶段归档保留 VCSEL 的原生压缩波形、输入网表、PDK 模型子集、求解日志、冻结配置、后处理及失败记录。MicroLED 只收录显式许可清单中的数值工作簿和 Zenodo 元数据；论文 PDF、原图摘录及私有阅读视图留在本地。原始完整数值 ZIP、字体及旧基线是已记录的外部/前阶段依赖，见 [MicroLED 恢复说明](../../../scripts/microled_dynamic_20261029/README.md)。完整物理 PDK、系统安装及所有历史 `build/` 不属于这一阶段备份。

## 3．重跑晶体管案例

本阶段使用 ngspice、Python 3.12、NumPy。图表另需 Matplotlib、Markdown；可在项目专用虚拟环境中安装，版本以运行与验证回执为准。公开 MOS 模型的来源及固定版本见 `analog/models/pdk-lock.json`，用 `scripts/fetch_models.py` 获取后核对哈希。这是电学模型子集，不能用于宣称完整 DRC/LVS/PEX 或流片资格。

先恢复原始证据并安装匹配依赖。选择 `report-cases.json` 中的普通 frame/DC/startup 案例，例如最终 TT 帧，在新目录重跑：

```sh
python scripts/driver_report_20261029/replay.py frame-TT-r10 \
  --prefix independently-replayed
```

`replay.py` 比较保存网表与当前版本，拒绝覆盖已有目录，再按原配置重新生成本机路径和刺激。完整帧后处理使用固定接收器，例如：

```sh
python scripts/vcsel_robustness_20261029/analyze.py \
  independently-replayed-frame-TT-r10 --label fixed-v3-r2 --grid-ps 2.5
```

启动接帧与 AC 注入属于专门实验，应使用其专用脚本，不应当作普通从工作点启动的 frame 重跑。连续实验使用 `run_continuous_restored_r10.py`，对应 `continuous-{TT,SS,FF}-r10-restored`；按保存的 `manifest.json` 配置在新名称下生成。该脚本仅延长原连续编排的进程时限，原 `continuous-TT-r10` 超时记录保留。然后用 `extract_frame_r10.py` 提取含 20 ns 光学预历史的数据窗口，以 `analyze_continuous.py` 的 `continuous-v3-r1` 标签处理；提取结果绑定父波形 SHA-256，不是另一次 SPICE。

启动判定额外执行 `startup_analyze.py <启动案例> <同角落独立DC案例>`，同时检查电流及两条电源轨，不能只看旧 `result.json` 的“进入末值电流带”字段。原始 `fixed-v3` 标签的早期输出含错误的代理描述元数据，最终报告采用 `fixed-v3-r2`，没有借此修改物理模型或门槛。

## 4．重新生成图与核对报告

```sh
python scripts/driver_report_20261029/diagrams.py \
  --source analog/circuits/vcsel_robustness_20261029/regulated-r10.spice
python scripts/driver_report_20261029/report.py
python scripts/driver_report_20261029/verify.py
```

图表默认使用前阶段归档的 Noto CJK 字体，也可用环境变量 `MICROLED_REPORT_FONT` 指定合适的本地字体。原理图包含真实 MOS 连接与明确的并联组；它们不是版图图形。`verify.py` 检查历史基线未变、报告对应的原始波形/输入哈希、源端口能量、已通过点的门槛、全部 MOS 图示覆盖与本地链接，不代替独立数值审查和人工看图。

## 5．保持边界

固定 3.2 Gb/s 净速率、3.7 GBd 线路速率、同一 VCSEL 负载及接收器。不要用失败点的低 pJ/bit 排能效，也不要因短帧零错误就宣称低 BER。外部精密 VSET/VREGSET 的内部功耗、实际光路、探测器噪声、失配、异步电源顺序、版图寄生、发光器件温度模型和可靠性仍需另行验证。
