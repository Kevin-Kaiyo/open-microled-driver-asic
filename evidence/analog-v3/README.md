# 单像素参考源与保护：新增验证（2026-10-15）

**最终选定入口：[final/summary.json](final/summary.json)。** 统一采用 r5 完整 RC、外置 CCOMP=30 pF、SENSE 对地附加电容=30 pF、REFOUT→VSS 10 MΩ。6 个 DC anchor 和 17 个选定 transient 全通过原功能门限。270 点 DC 为97.2547–100.6162 µA，关断最大52.51 pA。10 个启动均包含 t=0 和完整40 µs，使用保持原线性电源函数的共线局部网格，最坏总支路峰值0.65634 nA。3 个 fault 与4个正常 PWM case 来自相同电路的完整套结果；每项均列出来源文件与哈希。

原普通首步求解的 FF/晚到VSET起始尖峰仍以失败保留。选择规则是所有启动统一使用细化求解，不是逐项挑选通过结果；独立局部数值交叉见 `evidence/startup-v3/`。CCOMP=30 pF、SENSE=30 pF 的 TT/SS/FF 局部相位裕量为74.58/79.26/70.18°。最终 d1 电荷误差为−0.06225/−0.48133/+0.02678%，关断最慢303.39 ns。

电源瞬态仍是后续设计问题：TT 下 VREF 的3.3→2.97→3.3 V、100 ns边沿实验，LED电流瞬时60.16–147.24 µA，恢复至最终值±0.5%需2.49 µs。通过恢复时间不代表已满足产品的峰值电流或亮度误差规格。

`compact.csv`和`waveforms/*.csv`是抽样可视化资料，不用于积分或判定。完整稠密数据保存在结果指向的`build/`目录，`compact-views.json`记录可逆备份与哈希。本目录保留每次候选、失败与修改。几何候选为 `layout/startup_v3` 的39 MOS test macro；RSET/VSET/RBIAS/CCOMP/RRELEASE 和新增 REFOUT 泄放电阻均在芯片外部。

## 1. 从旧信号 PEX 到完整 RC 的差异

- `summary.json` / `dc.csv`：旧 selected joint PEX 上的新参考源与 TG，270 个 MOS 角/温度/电源/LED rail/开关状态组合均通过。这里的新参考源和保护仍是有限结面积假设的 schematic；不可把这一轮当作新版图电气通过。
- `pex-r4-cc3/summary.json`：新 39 MOS 宏包含所有提取网络的电阻和电容，DC/独立保护通过，但 100 ns 启动产生约 0.5 µA 位移电流，超过原 1 nA 总 LED 支路门限。模型二极管导电电流只有 fA 级，也不能据此把总支路失败改成通过。
- `pex-r4-ablation.json`：诊断删除 REFOUT—LED_K 的 8.24068 fF 电容后，峰值从 514.47 nA 降到 109.57 nA；删除全部提取电容后仍有 43.43 nA。这些被删元件的网表不是可制造的解决方案。
- `pex-r5-cc30/summary.json`：真实物理修改为缩短各 net 的横向总线和更低阻的地网络。CCOMP=30 pF、SENSE 无额外电容时，TT/SS/FF 的 100 ns 启动分别为 0.6753/0.6243/0.7147 nA。数值网格独立复核属于 `startup-v3` 的后续证据，不能仅凭一次峰值称为数值闭环。

## 2. 为什么外部补偿从 3 pF 改为候选 30 pF

RSET 反馈端 SENSE 的线缆、pad 和板上寄生电容会增加环路相移。`ac-pex-r5/summary.json` 在实际完整 RC 中，CCOMP=3 pF 且 SENSE 对地附加 30 pF 时，TT/SS/FF 的局部小信号相位裕量约 29.86/39.10/23.93°。CCOMP=30 pF 时变为 74.58/79.26/70.18°。

测量在 PMOS 输入对的 SENSE 门极连接处进行：电压源 DC=0 保持闭环工作点，电流源 DC=0 不改变 DC 负载；分别测量 Tv 和 Ti 后计算 `T=(Tv*Ti−1)/(Tv+Ti+2)`。各注入网表的 DC 工作点都与原闭环比较。`loop-control.json` 用已知单极点放大器和非零输入/输出阻抗独立检查极性与加载修正，最大相对误差约 4.44e−12。此方法仍是局部小信号指标，多环路/反向传输/全局稳定性和实际封装须继续验证。

方法原始定位：

- [ADI TNJ-055：电压与电流双注入及加载误差](https://www.analog.com/jp/lp/003/jp-web-lab/tnj-055.html)
- [JKU analog IC lecture：双注入公式与方法边界](https://iic-jku.github.io/analog-circuit-design/slides/middlebrook_method.html)

## 3. REFOUT 初值与外置泄放电阻

`body-audit.json` 显示，VREF=0 而安全电源预先有效时，POUT 的输出侧 diffusion 高于其 well 约 216.7 mV，已经存在于 t=0 的 DC 工作点。将 VSET 也设为 0 不消除此电压；全部电源为 0 时消失。该浮节点电压及 pA 级 BSIM junction current 随 gmin 改变，不能作为真实衬底注入测量或可靠性合格证据。

`bleed-control.json` 在相同 r5 布局中增加外接 REFOUT→VSS 电阻，保留 39 MOS 几何：

| TT 控制 | LED DC | 初始 POUT 源-well 电压 | 100 ns 启动支路峰值 |
|---|---:|---:|---:|
| 不加泄放 | 99.8841 µA | 216.739 mV | 0.6753 nA |
| 外置 10 MΩ | 99.7391 µA | 48.63 µV | 0.6847 nA |
| 外置 100 MΩ | 99.8696 µA | 486.05 µV | 0.5693 nA |

10 MΩ 的输出电流代价约0.145 µA，已进入全套回归。电阻为理想外置模型，容差、板上表面漏电、封装/pad/ESD等仍须有真实边界。初步 FF + SENSE30 pF 的普通首步求解产生 ps 级尖峰，保留在 `pex-r5-bleed10M-fftrial`。随后在相同电源函数上增加共线节点、细化起始步长，完整40 µs通过，并保留了不同积分法/网格的局部交叉证据；没有因脉冲短而删除原结果。body-audit 的低gmin试验经过 Transient operating-point fallback，求解路径见validation.json，不能把不同初值全部解释成物理漏电变化。

## 4. 可复现入口

```sh
build/layout/venv/bin/python scripts/analog_v3/run.py
build/layout/venv/bin/python scripts/analog_v3/macro.py \
  --netlist build/layout-v3/r5/roundtrip/startup_test_macro_rc.spice \
  --tag pex-r5-final-bleed10M --cc-pf 30 --csense-pf 30 --bleed-ohm 10000000
build/layout/venv/bin/python scripts/analog_v3/macro.py \
  --netlist build/layout-v3/r5/roundtrip/startup_test_macro_rc.spice \
  --tag pex-r5-bleed10M-startup-grid --cc-pf 30 --csense-pf 30 \
  --bleed-ohm 10000000 --only-kind startup --startup-grid
build/layout/venv/bin/python scripts/analog_v3/ac_macro.py \
  --netlist build/layout-v3/r5/roundtrip/startup_test_macro_rc.spice \
  --tag pex-r5-bleed10M --bleed-ohm 10000000
build/layout/venv/bin/python scripts/analog_v3/loop_control.py
build/layout/venv/bin/python scripts/analog_v3/select_final.py
build/layout/venv/bin/python scripts/analog_v3/validate.py
```

每次执行生成独立 `build/analog-v3/` raw 目录，包含冻结 DUT、testbench、ngspice/RTL 日志和稠密原始波形。`summary.json` 中的 `passed` 是该次具体实验门限，不能升级成 DRC/LVS/PEX、封装、silicon 或 optical 通过。源码中的 ngspice save 器件映射已核对 D/G/S/B；物理提取会交换 MOS 的 D/S，junction 读数也应随提取后的端名解释。
