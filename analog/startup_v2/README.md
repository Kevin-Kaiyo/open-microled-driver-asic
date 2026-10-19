# 启动隔离候选：先切断扰动，再保持像素关闭

本轮只完善有效 logic/LED 电源下的参考电源启动与独立故障关断；没有实现 POR、欠压监测或任意电源顺序安全。新增电路仍为 GF180MCU schematic MOS，0.44 µm 扩散落点是已声明假设。

## 选定候选

[reference_isolator_tg.spice](reference_isolator_tg.spice) 在参考源输出与像素 BIAS 之间放一对 CMOS transmission gate。fault 高时，N/P pass 管均关闭，XDIS 把 BIAS 拉到 VSS；fault 低时，N/P pass 管开启、XDIS 释放。参考环路继续运行，故障期间输出支路空载；这不是关闭参考源自身电源。

| 器件 | D | G | S | B | W/L µm | 作用 |
|---|---|---|---|---|---:|---|
| XFN | fault_b | fault | VSS | VSS | 2/1 | fault 反相器 NMOS |
| XFP | fault_b | fault | logic VDD | logic VDD | 4/1 | fault 反相器 PMOS |
| XISO | REFOUT | fault_b | BIAS | VSS | 20/1 | transmission gate N 支路 |
| XPISO | BIAS | fault | REFOUT | logic VDD | 20/1 | transmission gate P 支路 |
| XDIS | BIAS | fault | VSS | VSS | 2/1 | 故障时放电／保持 BIAS |

本轮继续使用原 fault gate、W2 LED PMOS shunt clamp 和旧12 MOS selected signal PEX。数字恢复状态来自真实 RTL event replay，模拟新模块没有新的版图抽取。PMOS body 接 logic rail；本轮 reference rail 最终与 logic rail 同电压，不能在另一电源域直接照搬。

## 未选定的四 MOS 方案

[reference_isolator.spice](reference_isolator.spice) 与 [reference_isolator_4mos.spice](reference_isolator_4mos.spice) 保留初试同字节设计；只用 NMOS pass。原始网表注释的约0.83 V来自早期假设，正式DC的TT BIAS约1.37 V；为保留as-run字节不改写该历史注释，以本节及JSON为准。它确实压低启动位移电流，但 SS / 85°C / logic2.97 V 条件下，正常 BIAS=1.397 V、REFOUT=2.564 V，串联压降1.167 V，使 PMOS参考复制输出失去足够压差，LED仅68.05 µA。该方案没有通过±5%全开电流目标。增加PMOS并联降低正常压降；最终候选SS BIAS=1.542 V、REFOUT=2.069 V，LED=97.739 µA，满足本轮±5%目标，但新增串联开关仍带来精度和面积代价。

## 为什么四 MOS 方案和 transmission gate 都不能替代数字保护

fault 解除会重新建立 BIAS，但 permit 仍由锁存的 RTL inhibit 阻止 PWM通过。必须在故障低、显式恢复请求、时钟有效且边沿前 raw PWM低时才接受恢复。取消 fault 本身不能让LED提前导通。恢复期间必须另外测量端口位移脉冲：本轮TT观测到约−4.838 µA的短脉冲，模型导电峰仅4.855 fA；不能把它删掉，也不能把它表述成已测光学发光。

证据及复现入口见 [evidence/startup-v2](../../evidence/startup-v2/README.md)。
