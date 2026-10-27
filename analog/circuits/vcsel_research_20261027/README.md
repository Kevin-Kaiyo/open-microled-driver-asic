# VCSEL bias + modulation：独立原理图研究

该目录实现 13 MOS 的电阻参考、电流镜、两级 CMOS 输入缓冲及共阳极电流转向候选。它是实验性方法验证，不包含实体高速接口、保护闭环、版图或 PEX。最终结论及 compact evidence 位于 `evidence/three-gbps-experiment-20261027/vcsel-driver-summary.json`。

`vcsel_bias_mod.spice` 每个 MOS 使用 D/G/S/B 端序。晶体管模型是 `analog/models/pdk-lock.json` 锁定的公开 GF180 原始 `nmos_3p3` / `pmos_3p3`；不能把它与历史 open_pdks 的 `nfet_03v3` 名称混用。结面积/周长为统一几何估计，不是提取寄生。

- 参考：3.3 V 经 6.9 kΩ 电阻馈入 5/1 µm 二极管连接 NMOS，TT IREF = 246.786 µA。它不具精密或温度补偿功能。电阻为外部有限阻值假设，±1% 单独控制，不与 MOS process corner 混淆。
- 偏置/调制：XBASE = 60/1 µm；XTAIL = 84/1 µm；两只转向 NMOS = 20/0.28 µm；dummy = 500 Ω。TT 一次 DC 校准得到 3.0014/6.9828 mA，随后所有角落及瞬态保持同值。
- 输入缓冲：D 与 DB 是外部互补 0–3.3 V 数据，经 50 Ω 源阻抗。每路两级 CMOS，首级 N/P = 4/8 µm、末级 = 12/24 µm，L = 0.28 µm。外部双源产生互补数据的芯片内部损耗未实现；两个端口交付/回流能量均计入。

VIBASE/VITAIL 是 0 V 测量源，没有提供理想驱动电流。电流由实际 MOS 和电阻决定。全部五路源端口 VLASER、VDD、VREF、VD、VDB 计能，包含参考、dummy、缓冲、负载和供电网络。供电每路 0.25 Ω / 0.2 nH、1 nF / 0.1 Ω 去耦；封装 0.5 Ω / 0.2 nH 都是明确的电路假设。正常帧从 DC operating point 启动，不是上电资格测试。源能量不包含上游电源/serializer/CDR/实体 RX 内部损耗。

负载是 `analog/models/vcsel_research_20261027/` 的公开图读约束代理。静态 I–V 研究域 2–8 mA，P–I 图读上界 7.5 mA；光学主代理采用 3 mA 幅频形状近似。它没有经验证的相位、大信号、结温或自热模型。GF180 的 SS/125°C 与 FF/−40°C 只作用于电路；负载静态曲线仍是 25°C。Cj = 150 fF 及 500 fF 控制均为未实测假设。

接收 v2 保留原先固定 7.5 µAeq / 100 ps 门槛。P(3 mA) 与 P(7 mA) 映射到 25/100 µAeq，阈值 62.5 µAeq；这里不是 photodiode 电流。见 `receiver-feasibility-v3-diagnostic.json` 的 v3 只改变训练目标为两个门槛的联合分数，其他条件不变，所有旧结果保留。v3 是看到 v2 现象后提出的 post-hoc 方法诊断，重复使用同一验证帧，不能视为独立确认。8 GHz 一阶及 1 GHz RX 分别是显式控制。

在 v3 冻结后，另用 seed 0x57AE / phase 8192 进行了一个新窗口确认；新旧 4736 bit 窗口完全不重叠，v3 的 4096 个新验证比特零错、最小时序 127.749 ps。条件与源码在 `holdout-nonoverlap-contract.json` 预先冻结，未重调。它仍是确定性 PRBS 同周期窗口，不是随机 BER 资格测试。更早的 seed 0x1ACE 用例有 1582 个验证位与旧周期相位重叠，因此只能称相位控制；原 contract 和结果保留，不能把其目录名中的 holdout 当作独立性证据。

3.63 V 端压及 0.3 V 体结正向电压是工程筛选值，不是完整可靠性规则。公开 [GF180 电气规格](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_1.html) 的 3.63 V Ioff 测试条件本身不等于 lifetime rating。公开 [MOS 模型文档](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_2.html) 与模型 subset 均不替代 full PDK / rule decks。

## 复现

在仓库根目录使用项目 Python 环境及 ngspice 47：

```sh
python scripts/fetch_models.py
.venv/bin/python scripts/three_gbps_experiment/vcsel_driver_run.py --name independent-dc-low --level 0
.venv/bin/python scripts/three_gbps_experiment/vcsel_driver_run.py --name independent-frame-TT --mode frame
.venv/bin/python scripts/three_gbps_experiment/vcsel_driver_analyze.py --case independent-frame-TT --label baseline
.venv/bin/python scripts/three_gbps_experiment/vcsel_driver_analyze.py --case independent-frame-TT --label v3-diagnostic --receiver v3
```

每次必须使用新的 case / analysis 名称，已有输入和结果不覆盖。runner 将 PDK、负载、电路和执行器复制到 case/inputs 并记录 SHA-256；分析也单独冻结光学/接收源及参数。新电脑按相同仓库相对路径恢复 sources 后，`fetch_models.py` 可恢复哈希锁定 subset。新运行自动生成适配本机的 include 路径。历史冻结 deck 中 absolute include 若直接重放，应复制 deck 到新目录并只重定位 include 前缀，同时记录重定位后的 SHA；不编辑原始冻结 deck。

原始波形只保存在 build，gzip 后逐字节 SHA-256 回读。`energy-exact.json` 使用与 fair-driver 相同的分段线性功率零交叉积分，append 到 case；不改最初 result.json。最终 compact summary 使用 exact 能量，另记与早期 clipped trapezoid 的差值。首次模型名解析失败及后处理恢复过程保留在各原始 case 和 summary，不隐藏失败。
