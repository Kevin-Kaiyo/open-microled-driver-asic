# NRZ 电压驱动与电流转向：PVT 修正版图

本阶段以真实的新 GDS 检验输入边沿整形、局部布线和衬底返回路径能否修复
快冷端电压超限，同时保持慢热接收余量。它是实验晶体管核心，不是完整流片芯片。
电学结论与速率、能耗、接收条件见[研究报告](../../docs/research/highspeed-nrz-pvt-20261023/index.html)。

## 最终实现

| 项目 | A 电压驱动 | B 电流转向 |
|---|---:|---:|
| 原核心端口顺序 | `DATA OUT VDD VH VL VSS` | `DATA OUT VDD VSS BIAS DUMMY` |
| 3.3 V MOS | 6 | 9 |
| 新增设计电阻 | 1 个，`ppolyf_u_1k_6p0` | 1 个，`ppolyf_u_1k_6p0` |
| 设计电阻 W × L | 1 × 48 µm | 1 × 58 µm |
| 实际核心外框 | 42.31 × 57.60 µm | 60.63 × 67.60 µm |
| 外框面积 | 2437.056 µm² | 4098.588 µm² |
| 提取的互连电阻 R 元件 | 84 | 127 |
| 显式寄生 C 元件 / 总和 | 61 / 35.879755426 fF | 76 / 35.655088120 fF |
| 完整提取电气网络数（含 VSS） | 9/9 | 10/10 |

**计数定义：**设计电阻是 SPICE 三端 `X` 子电路；表中 84/127 个 `R` 是额外的
互连寄生电阻。设计电阻内部的本体/端点电阻和衬底电容保留在完整 PDK 模型中，
不重复记作显式 PEX R/C。MOS 本征电容也由 BSIM 根据实际几何计算。

所有 MOS 尺寸保持原值。首级反相器栅极改接 DI，输入通过 `DATA—XRIN—DI`。
XRIN 第三端接 VSS 衬底。DI 总线缩短到首级栅极附近；电阻和 MOS 行之间增加连续
P+ 衬底接触条，以 M1/M2 和通孔连接 VSS；电阻保护环四边接触均打开。
新增接触条在实际 GDS 中含 A 122 / B 143 个 contact 切孔。

B 的外部 RREF 从变化的 VDD 改接原来就存在的固定 3.3 V VDUMMY。
该变化属于 testbench 的外部偏置电源边界，核心中没有新增稳压器。
A 的 VH/VL 仍为核心外理想双向电源。后续产品设计必须实现并验证这些外部功能。

版图在 GF180MCU D 的硅 CMOS 平台上使用 M1–M4，工艺配置本身提供 5 层金属。
6 V 高阻多晶硅电阻与 3.3 V MOS 共存；这表示该 PDK 的器件/隔离区域选项，
不是换用了 GaN 等另一种衬底。核心采用直条电阻和独立扩散区，尚未进行紧凑面积优化。

## 数据与失败原因的物理对应

首次 `poly58-r1` 两路均采用 58 µm 电阻并通过 DRC/LVS，但电学仍失败。
长 DI 增加输入整形后的负载；输入下降沿通过电阻模型的端点—衬底电容注入电流，
高阻衬底返回路径使逻辑 MOS 的体端电位发生偏移。

| 指标 | A 首次 → 最终 | B 首次 → 最终 |
|---|---:|---:|
| DI 对地 C | 3.55596 → 2.09861 fF | 3.57162 → 2.12594 fF |
| DI 对地与所有入射耦合 C 之和 | 4.5849008 → 2.5283680 fF | 4.5997255 → 2.5426815 fF |
| XRIN 体端到外部 VSS 的自阻 | 1900.274 → 20.820 Ω | 1617.843 → 21.746 Ω |
| XRIN 体端注入电流对第二 NMOS 体端的转移电阻 | 280.594 → 0.013707 Ω | 146.913 → 0.167021 Ω |

电阻结果在**提取的 VSS 电阻网络**中注入 1 A、固定外部 VSS=0 V 求解；
它可解释共用返回路径的变化，但不等同三维衬底场求解，也不替代完整瞬态仿真。
DI 入射 C 之和把每个耦合支路计入一次，不含 MOS 本征和设计电阻内部电容；
相邻信号的运动会改变实际动态负载，不能直接称为精确的一阶极点。

完整 PDK 电阻模型在 3.6 V DC 下的实测仿真值如下。三列联合条件属于本次测试选择，
不是全部独立工艺、供电和温度组合。

| 器件 | TT / 27°C | SS / 125°C | FF / −40°C |
|---|---:|---:|---:|
| A，48 × 1 µm | 49.545016 kΩ | 55.384598 kΩ | 42.704521 kΩ |
| B，58 × 1 µm | 59.830795 kΩ | 66.899849 kΩ | 51.539144 kΩ |

模型含独立的本体/端点温度系数及端点至衬底电容；A/B 模型内部总衬底 C
分别为约 4.122253 / 4.981057 fF。SS 电阻乘以上表 DI 入射显式 C，
A 从约 307 ps 降至 140 ps，B 从 308 ps 降至 170 ps；这些是附加延迟的数量级估算，
实际脉宽/眼图由非线性瞬态仿真判断。

## 复现与证据校验

完整环境必须先恢复仓库已固定的 `build/layout/pdk/gf180mcuD`、本地 Magic/Netgen、
`build/layout/venv` 和 `asic` Lima/Linux 容器。依赖版本、SHA-256、构建方法见
[`layout/pdk-lock.json`](../pdk-lock.json)、[`scripts/layout/bootstrap_macos.sh`](../../scripts/layout/bootstrap_macos.sh)
及已有的[物理流程说明](../highspeed_nrz/README.md)。完整 PDK 未复制到本目录。

```sh
# 目标 run 必须是新名字；保留原始 final-r4。
build/layout/venv/bin/python scripts/highspeed_nrz_pvt_layout/run.py \
  --spec layout/highspeed_nrz_pvt/selected-design.json --run reproduction-01

# 只校验已冻结交付，无须启动 EDA 或完整 PDK；需要 klayout Python 模块。
build/layout/venv/bin/python scripts/highspeed_nrz_pvt_layout/validate_delivery.py \
  --out build/highspeed-nrz-pvt-layout/physical-delivery-validation.json
```

`run.py` 依次执行原生 Magic DRC/LVS、实际 GDS 回读 DRC/LVS、全网络 R 提取、
独立 KLayout DRC、C 记账校正、RC 折叠 LVS、GDS 器件几何核对，以及真正修改
GDS 的栅极断线与电源短接反例。`final-r4` 两路各项通过，两个反例均被 LVS 拒绝。
最终独立 DRC 在固定 Linux 镜像中运行 **KLayout 0.30.7**，以该次命令与日志为准；
旧 `layout/pdk-lock.json` 中 macOS 原生 KLayout 的历史状态不是本次执行结果。

[`evidence/highspeed-nrz-pvt/physical/`](../../evidence/highspeed-nrz-pvt/physical/) 保存 GDS、MAG、
独立原理图、GEOM/C/RC/RCLUMP 网表、实际 `.ext`、未校正反例、日志、矩阵审计、
原执行脚本、DC 探针、首次失败的紧凑物理证据和逐文件 SHA-256。
`physical-contract.json` 记录层面积、外框、器件/端子坐标、所有新增布线矩形与提取实例映射。
发布器仅复制白名单并拒绝覆盖不同内容；大瞬态波形和其他探索失败记录继续保留在 `build/`。

## 提取方法与尚未闭合的边界

固定 Magic 版本的原生 C/RC 导出存在已记录的记账问题，不能直接用于性能结论。
当前 RC 以 GDS 回读 `.ext` 为对地/耦合 C 基准，保留全部互连 R 和完整 MOS/电阻模型；
对地 C 按 Magic 电阻简化后保留的权重分配，耦合 C 在原逻辑节点计入一次。
最终 DATA 没有耦合 C，也没有分配权重，因此将其精确的 0.513794 fF 对地 C
显式放在 DATA。RCLUMP 保持相同 R、器件和 C 矩阵，仅改变对地 C 位置。

高阻电阻的 `.ext` 另含一个无端子的中央器件标记；只在确认其 C=0 且无耦合后，
对它执行公开 `extresist ignore`，避免生成悬空互连 R。三端 PDK 电阻完整保留。
冻结 coverage 的 `node_count` 仅统计普通 node 行，不含 substrate 行；完整网络数
以 `pex-audit.json` 的 `extracted_nets/expected_nets` 为准（A9/B10）。

独立校验器重新解析 `.ext` 和三种 C 模型、检查全部器件/R 保持、验证四个反例的
实际多边形变化、测量 GDS 中 MOS W/L/结几何与电阻 W/L、核对完整日志和交叉哈希。
矩阵守恒证明的是记账正确；权重并非独立场解，不能据此证明高频空间电容分布。
仍需衬底/封装电磁验证、实测 LED 参数、参考源/电源实现、pad/ESD、全芯片密度/
天线、EM/IR、可靠性和制造方签核。项目的 3.63 V 筛查线也不是代工厂的寿命保证。

公开依据与许可证：

- [GF180 电阻模型、温度系数与端点电容](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_4.html)
- [GF180 3.3 V / 6 V 电阻器件名称](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_1_4_4.html)
- [源代码与依赖 NOTICE](NOTICE.md)：项目独立代码为 MIT；公开 GF180 依赖保留原 Apache-2.0 及上游通知。

官方电阻模型页的 limitations 仍未完整列出，当前仿真和开放规则结果不能升级为流片验收或可靠性保证。
