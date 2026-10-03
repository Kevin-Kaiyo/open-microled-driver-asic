# 单像素 PWM

`rtl/pixel_pwm.v` 是独立设计的单像素 PWM。一个 frame 固定包含 256 个 clock slot，8-bit counter 覆盖 0–255。`duty` 使用 9 bits，是为了同时表示完全关闭和完全导通两个端点；它不是 9-bit 灰阶引擎。

| Port | 含义 |
| --- | --- |
| `clk` | 驱动时钟；本项目仿真默认 1 MHz |
| `rst` | 高有效同步 reset；在 rising edge 生效 |
| `duty[8:0]` | 每个 frame 的高电平 slot 数，合法范围 0–256；257–511 clamp 为 256 |
| `enable` | 1 表示启用，0 表示整帧关闭 |
| `pwm` | 注册后的当前slot比较结果；唯一直接driver为output FF |

在 1 MHz 时，一个 frame 为 256 µs，PWM frequency 为 3906.25 Hz。有效 duty 为 `duty / 256`，因此 0、64、128、192、256 分别对应 0%、25%、50%、75%、100%。`duty=255` 为 255/256，仍有一个关闭 slot。

## 更新与 reset

`duty` 和 `enable` 只在 frame 边界锁存。帧中修改输入不会立刻改变 `pwm`，下一帧使用边界前最后一次输入值。输入需要满足同一个 clock domain 的 setup/hold；跨时钟或异步控制需要在系统集成时增加同步/握手。

reset 将 counter 置为 255，并清除锁存的 duty、enable 与 PWM output FF。reset 释放后的第一个 rising edge 从 counter=0 开始完整新帧，同时锁存新的输入与slot0输出。reset 可以在帧中中断 PWM，但只在下一个 rising edge 将输出清零。同步 reset 前，RTL 寄存器没有定义的初始状态。

v0.2 使用 output FF 注册 PWM，保持这里的 frame/slot 时序，避开组合 comparator 直接驱动像素的结构性毛刺风险。mapped gate 回归和实际 digital physical 结果分别见 [数字逻辑](digital/README.md)及[physical](digital/physical.md)。基本模拟桥接仍使用执行 RTL 的边沿与10 ns假设slew；实际SDF的使用与simulator限制单独记录。这些结果不代表硅片或上板测量。

## 波形导出

`sim/rtl/tb_pixel_pwm.v` 先输出用户指定的波形，随后运行完整 self-check。波形文件只包含真实 RTL 输出进入已知 0/1 的事件，CSV 格式为 `time_ns,pwm`。`+TRACE_ONLY=1` 跳过长 self-check，供模拟仿真批处理使用。

支持的 plusargs：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `+OUT=<path>` | `events.csv` | CSV 输出路径 |
| `+DUTY=<integer>` | 64 | 9-bit 输入，接受 0–511 |
| `+ENABLE=<0 or 1>` | 1 | 整帧 enable |
| `+TRACE_ONLY=<0 or 1>` | 0 | 1 只导出波形 |
| `+TRACE_REALTIME=<0 or 1>` | 0 | 1用实数ns导出SDF边沿；默认保持整数CSV |
| `+WARMUP_FRAMES=<integer>` | 2 | 模拟测量前的预热帧数 |
| `+MEASURE_FRAMES=<integer>` | 4 | 模拟测量覆盖的完整帧数 |

默认 clock period 为 1000 ns。reset 覆盖 500 ns 和 1500 ns 的 rising edge，2000 ns 释放。第一帧在 2500 ns 开始；模拟测量区间为 **514500–1538500 ns**，包含四个完整 frame。结束边界若产生 PWM 边沿，也保留在 CSV 中。恒定输出不人为添加边沿或终止点。

第一条已知输出记录为 `500,0`，来自同步 reset；0–500 ns 是 RTL 未初始化区间。模拟桥接应将这一已知 reset low 向前延伸到 SPICE 的 0 ns 初始点，并记录该启动假设。之后所有切换时刻均来自 RTL。SPICE 的有限 gate transition time 是模拟桥接参数，不是此 RTL 的 clock period 或测量证据。

## 检查覆盖范围

完整 testbench 对每个有效 duty 0–256 都检查一整帧的 256 个 slot，并独立统计高电平数量；同时覆盖所有可表示的越界值 257–511。其他检查包括 256→0→256 的连续帧边界切换、帧中 duty 变化、下一帧生效、disable 的边界生效、重新 enable、帧中 reset、持续 reset、释放后从 slot 0 重新开始。

检查使用 DUT 输出，不读取其内部 counter 或锁存寄存器。帧中 duty 变化还监测是否出现额外 PWM event。只有实际运行 testbench 且得到 `PASS pixel_pwm` 才算通过；仿真不构成综合、布局、DRC/LVS 或硅片验证。

2026-10-04 本地 Icarus Verilog self-check 已通过：**518 个完整 frame、133159 次 slot/value 检查、543个known events**；最短high/low为1000 ns。`duty=0` 和 `enable=0` 只有reset low事件，`duty=256` 和 `duty=511` 只在2500 ns导通，没有frame边界低脉冲。可选TRACE_REALTIME变更前后的默认轨迹已独立对照，10组逐字节一致，见[输入映射](../evidence/research/README.md)。可以通过仓库验证入口重新生成。
