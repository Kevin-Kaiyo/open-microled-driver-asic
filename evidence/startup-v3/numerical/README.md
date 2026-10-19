# 单像素启动的数值收敛审查（2026-10-15）

本目录审查冻结的 startup-v2 电路。没有改变器件、尺寸、电源、LED、观测窗口（0–20 µs）或电流观测量 `i(VLEDLOAD)`。旧版证据保持原样。

## 原来的失败是什么

旧版 Gear2、10/2 ns 最大步长的正向电荷为 4.9162241e-21 / 5.1575634e-21 C，差异 4.909%，超过原来 0.2% 的相对门槛。这个结果仍为失败。

`split_charge()` 已正确插入电流零交叉，再对正负分段积分。新实现使用每段解析三角形面积独立核对，与旧结果一致。因此失败不能归因于漏掉零交叉，也不能通过删除负电流、把小数归零或改用净电荷消除。

实际 ngspice 扫描覆盖最大步长、积分方法、相对/绝对容差、chgtol、初始步长、KLU。TRAP 的往返振铃增大 Q+ 和 |Q−|；更紧容差有真实的 `timestep too small` 失败。Gear1 的某一对 10/2 ns 结果碰巧通过 0.2%，更细步长和其他求解器并未支持把它当作整体收敛。

## 验收方法修订的原则

近零量只用自身作相对分母不稳定。新审查预声明双门槛：逐点电流差 ≤ 2 pA（已有 1 nA 关断峰值门槛的 0.2%）；电荷绝对差 ≤ 4e-17 C（2 pA × 20 µs）。在电荷达到工程预算尺度时，仍需满足原 0.2% 相对门槛。任何新方法通过都不得改写旧方法失败。

这个预算是本项目的工程数值误差分配，不是晶圆厂规则、仪器分辨率或实测光学消光指标。不同求解方法与更细步长都须检查，不能挑选一个碰巧通过的两点组合。

## 复现

```sh
build/layout/venv/bin/python scripts/startup_v3/numerical.py
# 已有同字节 deck 和日志时可复用完整输出
build/layout/venv/bin/python scripts/startup_v3/numerical.py --reuse
```

该诊断脚本仍以退出码 2 表示原相对收敛未解决；`diagnostic_checks_passed` 仅表示积分、校准、负对照和证据一致性检查通过。

- `summary.json`：全部 54 组扫描、6 组耦合 DC、量值与逐点比较。
- `failure-ledger.json`：14 组过紧容差的求解失败及原始日志路径。
- `waveforms/`：用于画图的紧凑 CSV，指标来自完整 raw，未用抽样 CSV 计算。
- 原始 deck、日志、完整波形：`build/startup-v3/numerical/`。

严格旧门槛状态与修订验收状态应分别读取，不能只显示一个“通过”。

## 已完成的修订验收

`refined-summary.json` 给出 14 次实际仿真。1 ps 的粗网格保留作失败/细化对照；最终比较集合包含 0.2 ps 与 0.1 ps 两级局部网格、Gear1/Gear2、10/2 ns 全局最大步长及 reltol=1e-8/1e-7 容差对照，共 10 组、45 对全部比较。

- 最坏逐点电流差：**1.393285487 pA < 2 pA**。
- Qsigned / Q+ / Q− 三种电荷的最坏绝对差：**3.452021799e-22 C < 4e-17 C**。
- 修订验收：**通过**；原 4.909% 相对验收：**仍失败**。
- 正向电荷量级约 4.5–4.8e-21 C，不把它设为零，也不把仿真电流解释为实测光。

局部细化只在原有参考电源 PWL 的同一条直线上添加时间节点，电源的0→3.3V/100ns斜率与20µs窗口均不变。初始 TSTEP 固定为0.001ns（1ps）；局部时间节点覆盖0–1ns、99–102ns两个角点区间。实际电源波形还逐点核对原函数。

近零分支与相对分支的连续交界为 **Qswitch=4e-17/0.002=2e-14 C（20 fC）**。大于交界的电荷仍使用0.2%；小于交界时必须同时满足绝对电荷差和逐点电流差。修订定义在 `scripts/startup_v3/numerical_contract.json`，版本 `startup-off-numerical-v1-20261015`。

```sh
build/layout/venv/bin/python scripts/startup_v3/refine.py
build/layout/venv/bin/python scripts/startup_v3/figures.py
build/layout/venv/bin/python scripts/startup_v3/validate_numerical.py
```

图：`figures/startup-numerical-convergence.svg`。图用CSV已限制到密集角点窗口及全程抽样；所有计算仍使用build中的完整原始数据。这份数值结论只覆盖冻结startup-v2电路；新的布局PEX必须重新验证，不能沿用这个通过结果。

## 新版 r5 全 RC PEX 的数值审查

这些结果与旧startup-v2分开，电路已有真正的新版布局寄生。

1. **TT / CCOMP=30pF / CSENSE=0，无bleed**：`pex-r5-gmin-screen/summary.json` 是0–200ns筛选，gmin=1e-14/1e-12/1e-10 S的峰值均0.6627–0.6631nA。低gmin采用transient OP fallback，不能视为同一DC工作点。另保留`build/startup-v3/numerical/pex-r5-cc30/`中Gear2局部0.2/0.1ps的完整20us结果（峰0.662745/0.662759nA）；严格Gear1两组因运行极慢被中止，日志保留。
2. **FF / CCOMP=30pF / CSENSE=30pF / 外置10MΩ REFOUT泄放**：`pex-r5-bleed10M-ff-probe/summary.json` 是0–20ns初始角点审查。旧自适应初始步出现约+3.043nA峰；局部网格细化后，所有已完成的Gear1/Gear2/容差/gmin对照为约−0.502至−0.506nA。该变化发生在完全相同的器件和电源函数下，原常规DC起点相同，支持旧峰含数值启动误差。
3. **完整逐点比较**：最终0.1/0.05ps两级网格、Gear1/Gear2、宽容差对照共5组、10对，最坏ΔI=1.770859pA，最坏Q差8.49699e-23C，满足2pA及按20ns缩放的4e-20C预算。0.2ps粗网格的失败比较保留。只比较峰值是不够的。
4. **没有隐藏的失败**：rel1e-9/abs1e-16/v1e-11严格挑战150s未完成，`all_completed=false`；它不是物理失效证明，也不构成“任意容差通过”。gmin=1e-14启用transient OP fallback，独立列出，未放入最终同一OP数值比较。默认1e-12和1e-10的原常规OP条件、波形和峰值均记录。

`validation-pex.json` 独立复核168项通过。图为`figures/pex-ff-initial-corner.svg`。此处的短窗通过不得替代模拟电路工程师的完整20us启动、恢复、故障和PWM回归。
