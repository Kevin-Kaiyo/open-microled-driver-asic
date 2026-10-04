# 单像素 v0.3：共同顶层与真实输出级

日期：2026-10-04。此范围在新集成结果产生前确定。目标是把已经取得的数字和模拟 macro 证据推进到一个有真实跨宏连线的共同 physical top，同时检验输出级驱动模拟输入的条件。仍只做一个像素。

## 冻结的设计与边界

保留 v0.2 的 registered 256-slot PWM、1 MHz clock、GF180MCU D / MCU7 library、六 MOS analog cell、20/4 µm mirror、100 µA 目标、3.3 V nominal logic 与 5 V nominal external LED rail。数字和模拟 macro 使用已发布的 GDS、LEF、netlist 与 input locks，原报告和 as-run hashes 保留。

外部 LED 阳极电源、reference generator、pads/ESD、package 不包含在本次 top 内。真实 LED 曲线继续只代表已发表的静态 I-V；真实动态、温漂和光学 qualification 不会因集成通过而升级。

## 本轮退出条件

| 项目 | 预设检查与判断条件 |
| --- | --- |
| 共同 physical top | 实际层次化放置两个冻结 macro，并用工艺 Metal/Via 连通 PWM、3.3 V 与 VSS；提供可检查的 GDS、连接计划与 source hashes |
| PWM 接口 | 数字 PWM 唯一输出驱动接模拟 pwm；外部 clk/rst/enable/duty、bias/led_k 和公开监测端口仍有对应关系；不把并列实例或逻辑 net 名相同当作实际连接 |
| 供电与 body ties | digital VDD/VNW 对应 analog vlogic/PMOS bulk，digital VSS/VPW 对应 analog VSS/NMOS bulk；无电源短接、信号误接或未说明的 floating supply |
| Physical verification | 对共同 GDS 做实际 Magic 与独立 KLayout DRC，并用实际 extraction 对 golden top 做 LVS；记录规则范围、leaf blackbox、被忽略 cells/properties，不把层次化 cell connectivity 扩大为全部数字晶体管 LVS |
| 失败检测 | 断开 PWM、错误 PG 或遗漏连接的独立负对照必须被所声明的验证方法拒绝；正确基线通过不足以证明检查能够发现错误 |
| 跨宏寄生 | 尽可能从新增 routing 提取真实 R/C；若只是几何估计，必须明确方法，不能称 joint PEX；避免重复加入 macro 内部寄生 |
| 真实数字输出级 | 用实际 implemented PWM 末级的公开 transistor SPICE 驱动 actual analog RC，并与同条件 ideal-source replay 配对；明确标准单元自身 SPICE 与该 cell routed PEX 的区别 |
| Current / short pulse | 沿用预设 full-on 100 µA±5%、最低码 `Q1/(Ifull×1 µs)-1` ±2%；至少覆盖 off、最低码、中间码与 full-on，并做步长细化；保留未通过结果 |
| 输入负载与 slew | 分开报告 metal capacitance、工作点 small-signal Y/C、切换电荷等效负载；根据 locked Liberty 的实际阈值核查输出边沿和既有 3 ns slew 约束，不事后改变定义 |
| 条件与复算 | Nominal TT / 27°C / 3.3 V，另取模拟研究 envelope 的 SS / 85°C / 2.97 V 与 FF / 0°C / 3.63 V；固定 reference、LED/model、窗口和积分法；与不同温压的 digital STA corner 分开说明 |

上述门槛若未满足，本轮继续修复或保留明确 blocker。共同 top DRC/LVS 与部分 interface electrical probes 通过，仍不等于完整数字晶体管 transient、全芯片多角落 PEX、供电 sign-off、制造接受或 tape-out readiness。

## 证据组织

新增物理实现放在 `layout/integration/`、`scripts/integration/`、`evidence/integration/`；接口电路研究放在 `scripts/interface/`、`evidence/interface/`。原始运行与失败日志分别留在 `build/integration/`、`build/interface/`。新报告必须给出本轮取得与未取得的结果，并保留 [v0.2 指标](single-pixel-v0.2.md)及此前证据。
