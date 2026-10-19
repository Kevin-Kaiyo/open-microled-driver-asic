# 独立故障关断实验：先分清“数字已经关掉”与“电流已经收敛”

实验从 2026-10-13 开始，2026-10-14 完成这一轮。定位仍是实验方法验证与教学。

本轮证明的是：在明确的供电、输入边沿、合成 LED 和 selected signal PEX 条件下，新增保护可以绕过 PWM 的帧更新，也可以在时钟停止时压低像素电流。它没有完成 POR、brownout、真实 LED 的光学熄灭验证或新保护电路的版图。

## 解决什么问题

原 `pixel_pwm` 在时钟边沿运行。时钟停止且输出卡在高电平时，再修改 duty/enable 不会自动关掉像素。因此故障关断必须有一条无需等待时钟的路径。

第一项受控实验只有 10 MOS 的组合保护 gate。数字输出约纳秒级下降，但 `|ILED| < 1 nA` 要等 **2.638 µs**，超过先验 **1 µs** 截止时间。LED cathode 电压在缓慢变化，说明数字关断不等于节点电荷已经处置。原始失败保留在 `build/safety/fault-gate-4he1rnag/`，没有放宽门槛。

第二项候选在 LED anode 与 cathode 之间增加实际 PMOS clamp。fault 高时，NMOS 把 PMOS gate 拉低，让 cathode 接近 anode；fault 低时，100 kΩ 电阻把 gate 拉回 anode，PMOS 关闭。该电路把正、负电流和电源消耗带来新的验证问题，不能仅看 signed charge 的抵消。

## 实际实现及证据层级

| 内容 | 本轮实现 | 边界 |
|---|---|---|
| 原 PWM | 原 RTL 未修改，133159 原检查通过 | 本轮没有加入全数字 FF 晶体管或新的 SDF |
| 正常时保护输出 | 134687 实际 RTL 采样与原输出一致 | 硬件恢复寄存器未实现 |
| `fault_gate` | GF180 6-V wrappers，10 schematic MOS | pre-layout，扩散落点 0.44 µm 是明确假设 |
| active clamp | NMOS W/L=2/1 µm；PMOS W/L=2/1 µm；100 kΩ | 两个 schematic MOS 与理想电阻，未做布局或 resistor PDK/TC 验证 |
| 旧 joint cutout | 原 12 MOS / 45 R / 77 C 模型复用 | 34 个邻居仍为 ideal 0 V；PG、body 与供电阻抗不在该 cutout 内 |
| Reference 联合作用 | beta nominal fault；servo nominal d1/clock-stop fault | Reference 自身 PVT 的证据在 `evidence/reference/`；此处未联合覆盖全部 PVT |

旧模型 SHA-256 始终为 `03813e63e64bf505570dbd1f81e6809366e6b4d31bbee129c28022956e1cc623`。新增电路总计 12 schematic MOS；含旧 selected PEX 时为 24 MOS，beta 或 servo reference 会再增加其自身晶体管。

电路源见 [fault_gate.spice](../../analog/safety/fault_gate.spice)、[fault_led_clamp.spice](../../analog/safety/fault_led_clamp.spice)，恢复逻辑见 [pixel_safety.v](../../rtl/safety/pixel_safety.v)。

## 故障、保持与恢复

- `fault=1` 直接进入组合 gate，与 `permit` 状态一起限制输出。即使时钟停了、permit 还错误地保持高，fault 仍能关断。
- RTL `inhibit` 由 fault 异步置位。fault 解除后，保护保持禁止；只有故障低、`recover_request=1`、一个有效上升时钟边沿且边沿前 raw PWM 低时，才能恢复。
- 模拟 `permit` 来自实际 RTL event replay。没有把它表述为已完成的晶体管锁存器。
- 初始 fault 由外部强制高。1 MΩ 上拉也验证了输入连接断开时的 default-off 条件。有效 logic/LED 电源是前提；电源掉电、上电不确定状态和故障传感器尚未实现。

## 先验门槛与方法

原门槛保留在 [contract.json](contract.json)，新候选条件和额外预算在 [clamp-contract.json](clamp-contract.json)：fault 后 1 µs 内稳定至 `|ILED|<1 nA`，后续 1–2 µs 维持该守卫，首 1 µs 的 **Q+≤10 pC**。新增负尾 **|Q−|≤20 pC**、负峰≤10 mA、模型 reverse peak≤0.5 V。后面三项是教学预算，不能代替真实 LED 的绝对最大额定值。

实际 RTL 转换成 **10 ns 0–100% PWL 边沿**。早先 1 ns 条件的数值中止保留，不对这些条件宣称通过。Core transient 用 `reltol=1e-7, abstol=1e-14, vntol=1e-9, Gear`。Servo DC 保持这些严格容差；servo transient 按作者已验证的 `1e-6 / 1e-12 / 1e-7, Trap`，再比较 10→2 ns maxstep。容差不等于门槛；本轮没有修改 1 nA 或 1 µs 守卫。

LED 电流由单独串联 0 V 电流计读取；clamp rail 有第二个独立电流计。保存 diode `[id]`、`[capcur]`，其差用于模型导电分量诊断。Internal device reads 的瞬态数值不必与外部串联电流计逐点完全相等，因此所有安全守卫始终用外部电流计；诊断闭合误差另行审计。MOUT `[id]` 是模型内部变量，不据其符号直接推断抽取后交换 D/S 的真实端口电流。

## 数据及实际判断

Core 的 [summary.json](summary.json) 含 22 transient、141 检查，全部通过；独立 [validation.json](validation.json) 1813 检查核对源 hash、原始波形、积分、RTL 恢复条件和逐 MOS 终端差值。正常最低码在本 fixture 的 DC 归一化面积误差为 **−0.02723%**。该 fixture 与原 SDF joint 报告的刺激边界不同，这不是对旧 0.700133% 指标的性能改善声称。

| 受控条件 | fault→稳定 `|ILED|<1 nA` | 首 1 µs Q+ | 首 1 µs Q− |
|---|---:|---:|---:|
| TT / 27°C / logic3.3 V / LED5 V，d256 | 203.819 ns | 0.4134 pC | −7.3310 pC |
| SS / 85°C / logic2.97 V / LED4.5 V | 302.223 ns | 0.5373 pC | −6.8833 pC |
| FF / 0°C / logic3.63 V / LED5.5 V | 154.818 ns | 0.3232 pC | −7.5513 pC |
| 断开 fault 输入，由上拉驱高 | 212.796 ns | 0.9325 pC | −7.1858 pC |
| 停钟且没有保护：故意的 negative control | 不收敛 | 100.7528 pC | 0 |

上述 SS/TT/FF 是三个明确组合的实验包络，不是完整 foundry signoff。其他 phase、duty、PWM off-phase 与 stale-permit 对照在 JSON 中逐项列出。

TT d256 的负峰约 **205.29 µA**，未观测到模型 reverse voltage。LED 的 signed tail 约 −6.918 pC，但这不能消掉 +0.413 pC 的正尾，也不能消掉 −7.331 pC 的位移/储荷负担。clamp rail 首 1 µs 供给约 **56.516 pC**，包含 fault 时约 50 µA 的 100 kΩ 电阻电流。正常 fault 引脚驱低时 1 MΩ 上拉另耗约 3.3 µA。Reference 在 fault 时仍工作，像素关断不是系统电源关断。

## Servo 联合作用：原故障合同通过，新增启动守卫仍失败

[servo-summary.json](servo-summary.json) 独立给出 `core_contract_passed=true`、`extra_startup_guard_failed=true`、`extra_startup_charge_convergence_failed=true`，overall 保持 false。独立数据审计 [servo-validation.json](servo-validation.json) 511 检查通过，只证明记录与计算完整，不把失败实验升级为通过。

在 TT / 27°C / 3.3 V logic / 5 V LED、外部 VSET=0.5 V、RSET=5 kΩ 下，servo+d1 面积误差 **−0.0320165%**；servo+stopped-clock fault 到 `<1 nA` 为 **204.10 ns**，Q+=0.4101 pC、Q−=−7.3300 pC。10→2 ns maxstep 的面积和 Q+ 变化分别约 0.000000212% 与 0.002516%，低于原 0.2% 收敛门槛。

另一项独立实验只让 reference rail 在 100 ns 内从 0 升至 3.3 V；logic/LED rail 保持有效，外部 fault 高保持 20 µs，然后显式恢复。Reference 输出峰约 **155.96 µA**。新增的“整个 0–20 µs 电流绝对峰≤1 nA”守卫失败：模型 branch 峰 **5.791 nA**，模型导电分量峰仅约 **3.24e−17 A**，变化主要来自电容。这不是光学发光或真实 LED 的反向导电测量。

启动 Q+ 只有约 0.0002895 pC，却在 10→2 ns maxstep 时相差 **56.38%**，说明这项非常小的启动充电指标仍未闭环。W20 clamp 对照把峰降低到 2.815 nA，仍未通过，未被选定。它不能抹去原故障截止时间通过，也不能用来宣称 POR 或启动安全已经完成。

## 下一阶段及可重跑入口

下一阶段先定义实际供电顺序、外部 fault/POR 的状态合同，并针对启动阶段确定测量量：终端电流、模型导电/位移分量、测量带宽与积分窗口。然后把 reference、保护 gate/clamp 和恢复存储纳入实际布局及 PG/body 证据，再联合验证真实 LED 参数。保留全启动守卫失败及步长敏感性，避免直接扩大阵列数量。

```sh
build/layout/venv/bin/python scripts/safety/run.py --suite core --reference-path analog/reference/beta_multiplier.spice --publish-evidence
build/layout/venv/bin/python scripts/safety/validate.py evidence/safety/summary.json --output evidence/safety/validation.json
build/layout/venv/bin/python scripts/safety/run.py --suite servo --servo-path analog/reference/vset_servo.spice
```

Servo suite 预期会因当前新增启动守卫失败而返回非零；失败位置写入它的新 `build/safety/fault-gate-*` 目录。对其 summary 运行 `validate.py`，再用 `export_servo.py` 导出，仍保留 overall false。

Core CSV 在 `evidence/safety/waveforms/<case>/waveform.csv`；servo 的每个条目含 `csvpath`，在 `evidence/safety/servo-waveforms/<case>/waveform.csv`。Full-resolution `.dat`、冻结输入、decks 和失败日志都留在对应 `build/safety/`。逐项失败路径和 hash 见 [failure-ledger.json](failure-ledger.json)。终端 VGS/VGD/VDS/body 值用于捕获压力，不是 HCI、TDDB、latch-up 或 ESD 认证。
