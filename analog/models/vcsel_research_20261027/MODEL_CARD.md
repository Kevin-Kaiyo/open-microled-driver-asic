# VCSEL 公开图读约束的研究代理模型

本目录提供**可运行、可追溯的研究代理**，不提供作者原始 VCSEL 模型。Giannakopoulos 等 2021 年论文展示了测量与模型的 I–V、P–I 和归一化 S21 对照，但正文没有给出足以复现的 Cp / Rm / Rj / Cm 数值、动态方程系数或 Spectre 网表。因此，本目录的 SPICE 与 Python 实现是独立编写的近似。

主要来源：[Frontiers in Physics 9:672941 (2021)](https://doi.org/10.3389/fphy.2021.672941)，VCSEL measurements/modeling 章节、Fig.6–8；本地原图及其 SHA-256 见 `parameters.json`。数据不是本项目器件的测量。

## 原始证据

![Giannakopoulos 等原 Fig.8；A 为 DC，B 为归一化 S21](../../../docs/research/three-gbps-vcsel-20261027/figures/frontiers-2021-figure8.webp)

原始 Fig.8，© 2021 Giannakopoulos 等；[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)，[原文与图注](https://doi.org/10.3389/fphy.2021.672941)。原图未修改。A 的图例标注 25 / 55 / 85 / 100°C；B 只标出 3 / 5 / 7 mA，**B 的温度没有明确标注**。完整版权信息在 `NOTICE.md`。

## 模型组成与参数来源

| 组成 | 采用值 / 方法 | 证据和边界 |
|---|---|---|
| 静态 I–V | 25°C 浅蓝测量点的近似读数，单调分段线性插值；3 / 5 / 7 mA 对应约 1.834 / 2.004 / 2.136 V | Fig.8A 右图；电压图读约 ±20 mV，电流约 ±0.05 mA；各点和附近像素支撑保存在 `figure8a-iv-manual-points.csv` |
| 静态 P–I | 25°C 蓝色轨迹像素读数；3 / 7 mA 对应约 1.431 / 3.671 mW | Fig.8A 左图；蓝色实线与测量标记重合，**不能称为独立实测数据提取**；图读约 ±0.08 mW；像素与方法在 CSV / prepare 脚本 |
| 等效并联电容 CJ | 50 / 150 / 500 fF | **工程敏感性假设**，不是论文参数、S11 拟合值或器件额定值 |
| 额外串联 R | 本子电路不额外添加 | 终端 I–V 已包含静态串联压降；这不表示物理串联电阻为零。封装 R/L 须在外部另标假设 |
| `figure3mA_proxy` | 稳定三阶、单位 DC 增益的幅频形状近似：二阶共振段乘一阶极点 | Fig.8B 的 3 mA 测量轨迹人工读点；不含作者模型系数，也不是速率方程 |
| 派生形状系数 | f0≈9.171 GHz、ζ≈0.3031、fp≈15.330 GHz | 本项目确定性幅度最小二乘近似的结果；**不能解释为已提取的物理弛豫频率、阻尼或寄生极点** |
| 8 / 4 GHz 单极点 | `lowpass8GHz_assumed` / `lowpass4GHz_assumed` | 额外敏感性条件，不来自器件参数提取 |

静态 I–V 的研究域是 2–8 mA，P–I 支撑到 7.5 mA，**联合图读域为 2–7.5 mA**。数值实现为保证求解还包含域外延拓：低电流 I–V 连到原点，P–I 在 0 电流取 0，大电流使用最后两点斜率外推。这些延拓没有物理验证；输出分析应记录越域峰值与样本比例。模型不根据 `.temp` 变化，不支持自热、反向击穿或温度外推。

## 电学与光学的接口

```spice
.include analog/models/vcsel_research_20261027/vcsel_research.spice
XVCSEL anode cathode jmon vcsel_research CJ=150f
```

`v(jmon)` 的数值等于正向导电电流（1 V 对应 1 A），**排除 CJ 位移电流**；`jmon` 是理想观测端，不接外部电路负载。外部电源电流还包括电容充放电、驱动和封装功耗。

```python
from vcsel_model import static_power, optical_power, response_metadata
p_W = optical_power(time_s, conduction_current_A, response="figure3mA_proxy")
```

Python 文件位于 `scripts/three_gbps_experiment/vcsel_model.py`。输入必须为等间隔采样；输出单位 W。初始状态设置为第一点的 DC 平衡，无额外纯延迟、随机噪声或输出裁剪。`static_power` 返回同一 P–I 表；禁止在其他 analyzer 内复制一套不同的默认模型。

传递函数为本项目选择的形状：

`H(s) = ω0² / (s² + 2ζω0s + ω0²) × ωp / (s + ωp)`。

选用无零点、稳定极点的相位是一项**未验证的因果实现假设**。时域采用输入零阶保持的精确极点积分；它只消除数值积分误差，不能消除物理模型不确定性。

## 最重要的联合模型限制

1. **S21 没有去嵌。**公开图中的电到光响应不能唯一分离电学前端与内禀光学动力学。在独立 CJ 后，再把该幅频形状用于导电电流，有重复计入电学衰减的风险；缺少同器件的复数 S11 / S21，无法求出唯一修正。不能称为“电学与光学已共同标定”。
2. **固定 3 mA 小信号形状覆盖 3–7 mA 大信号，是研究假设。**源图显示明显偏置依赖。3 mA 曲线虽较窄、共振更强，但它不是经过证明的全波形保守界限。这里没有载流子–光子速率方程、相位测量、温度动态数据、RIN 或模态信息。
3. **数值通过不等于光链路通过。**没有实际激光器、光路、PD / TIA 或光学 BER 测量。后续 driver 的 3.7 Gb/s 线路 / 3.2 Gb/s 净载荷结论只能属于明确假设下的晶体管电路与行为代理联合仿真。

## 实现检查及复现

![模型来源约束与实现检查](../../../evidence/three-gbps-experiment-20261027/vcsel-model/model-checks.png)

图为本项目派生图，不是作者结果。3 mA 幅频读点的 in-sample RMS 误差约 0.502 dB、最大误差约 1.180 dB；最大值超出约 ±0.6 dB 的图读不确定度，因此仅称粗略形状一致，**不称精确拟合或独立验证**。

`validation.json` 中 3 个 CJ 条件的 ngspice DC / AC 实现检查及 12 个滤波频率检查通过。DC 对照编码的 I–V，AC 对照 `G+jωC`，光学数值增益对照上式；这些都属于实现自洽检查。3→7 mA 代理阶跃的峰值约 4.350 mW，稳态约 3.671 mW；共振过冲没有被裁掉，也未得到真实大信号测量验证。

```sh
build/layout/venv/bin/python scripts/three_gbps_experiment/vcsel_model_prepare.py
build/layout/venv/bin/python scripts/three_gbps_experiment/vcsel_model_validate.py
```

依赖沿用现有 Python 环境的 NumPy / Pillow / Matplotlib 和 ngspice；版本写入证据。原始 HTML、读图辅助裁剪、仿真网表与日志保留在 `build/three-gbps-experiment-20261027/vcsel-model/`；公开紧凑证据在 `evidence/three-gbps-experiment-20261027/vcsel-model/`。未覆盖旧 MicroLED 模型、旧仿真结果或作者原图。
