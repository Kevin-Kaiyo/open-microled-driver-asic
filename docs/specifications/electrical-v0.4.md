# 单像素 v0.4：输出级 PEX 与电源／控制边界

日期：2026-10-05。以下条件和门槛在本轮新增电气结果产生前声明。设计保持 registered 256-slot PWM、1 MHz clock、GF180MCU D、20/4 µm mirror、100 µA reference、nominal 3.3 V logic／5 V external LED rail。没有新增片上 reference generator。

## 1. 模型与范围

Pre 为 v0.3 同条件路径：真实 `output12/buf_2` 的公开 schematic SPICE、该 digital macro 的 nominal PWM output SPEF、新跨宏 link 和既有 analog RC。Post 使用从冻结共同 GDS 提取的实际 output-stage junction／cell metal／输出金属与跨宏寄生。必须以 extraction 交付的端口和覆盖范围决定连接；post 已包含的 digital output wire 或跨宏 span 不再叠加旧模型。Analog geometry、LED 模型和 reference 参数保持不变。

开始电气仿真前的 extraction 边界发现：实际共同 top 将 digital PWM 接到 analog M3 右侧，而 standalone analog RC 的 formal `pwm` 在左侧。为了避免把同一片金属从错误切点再串联一次，post 可采用实际共同PEX中裁出的联合 `output_pixel_pex`（buffer六MOS＋相同geometry的analog六MOS），整体替换旧buf／analogRC／SPEF／link。这会重提取相同analog geometry的共同寄生和端口边界，不是修改旧器件尺寸或旧RC证据。共享PG的post只直接报告联合十二MOS rail功耗；不根据同一理想供电节点人为分摊成可独立测得的buffer与analog功耗。

通过前逐项冻结 source／model／geometry hash、ports／body ties、cut boundary 与邻近导体假设。实际提取的 junction area／perimeter 和金属寄生不按测得波形反向拟合。完整 digital preceding logic／FF、全芯片 multi-corner PEX、完整 PG／substrate、pads／ESD／package、silicon／optical 结果仍在本轮范围之外。

开跑前的模型边界收紧：若 joint exporter 将 body／PG resistance 投影到理想供电，并排除 PG-only capacitance／模板负电容，main只使用固定rails下的 selected signal-path RC 与实际MOS junction。PG-only负C不能为了启动仿真重新塞回或静默视为物理零。Startup／非理想rail案例是该 selected signal-path十二MOS模型加声明外部R／C的边界探针，遗漏实际PG metal／well charging、内部PG droop与完整decap／source能量。即使输出功率有十二MOS，也不能称完整实际cell／chip PG功耗。假设1 nF不替代被排除的真实PGcap。

## 2. 同条件稳态检查

| 包络 | MOS corner | MOS T | Vlogic | VLED |
|---|---|---:|---:|---:|
| Nominal | typical | 27°C | 3.3 V | 5 V |
| Slow probe | SS | 85°C | 2.97 V | 4.5 V |
| Fast probe | FF | 0°C | 3.63 V | 5.5 V |

这三个点沿用模拟研究 envelope，不称为已有 digital Liberty 的 matched STA corners。Main comparison 使用合成动态 LED：独立校准在 27°C／100 µA／2.8 V，保持原有 diode、电容及 transit-time 假设。实测 LED 的温度、charge／reverse／optical 未知不会因本轮 PEX 升级为有效动态模型。

RC extraction另有nominal／HRHC／LRHC／HRLC／LRLC五个已锁定物理模型。先五style短edge probe，再以nominal做完整三包络pre/post；追加HRHC×SS和LRLC×FF的最低码／满开，其他RC/PVT组合不称已验证。邻近34导体包含fillcap／FF内部floating nets；main统一人为0 V stiff clamp，不称真实邻居logic状态。另用LED-first启动、compliance reference、all-neighbor随liveVlogic的high clamp做初态敏感性，不以0/high一致证明floating／active neighbor已关闭。

Pre／post 用相同 actual RTL 事件、末级输入完整 1 ns 电压坡度、外部理想 rail、100 µA reference、duty0／1／64／255／256。电流均值和电荷使用整数个 256 µs frame，先暖机两个 frame，再测量两个 frame；报告这两个 frame 的分散及边界状态，不能以平均值隐藏未建立状态。先短 pulse probe 验证端口／模型，再执行必要的主回归。

| 项目 | 预设门槛 |
|---|---|
| Full-on | 与 100 µA 相对误差≤±5% |
| Lowest-code charge area | `Q1/(Ifull×1 µs)−1` 绝对值≤2%，off 不用于改写目标分母 |
| Off model guard | `<1 nA`；是数值 guard，不是量产 leakage 规格 |
| Slew | 根据 locked Liberty 的 30–70% rise／70–30% fall，与现有 3 ns transition budget 比较；delay threshold 为50% |
| Short pulse | 50% threshold 下 high／low 最短值≥950 ns，沿用既有模型 guard |
| Fine-step convergence | 关键 post duty1 在 maxstep10→1 ns 时，平均电流／charge 相对改变量≤0.2%；仅当原值绝对值<1 nA时使用1 nA绝对数值容限；duty1仍严格使用0.2% |
| Frame repeatability | main两个完整测量frame平均电流差≤0.2%，仅当均值绝对值<1 nA时使用1 nA数值容限；另公开同相节点状态，不以该门槛证明全部内部电荷已周期稳态 |
| Pre/post difference | 公开电流、面积、slew、瞬态极值与功耗变化，不预设结果必须相等；上面工程门槛保持不变 |

## 3. 电源／reference／控制探针

这些是探索性边界研究，未给真实系统启动安全性或器件可靠性保证。报告实际未通过点和适用条件，不为得到 pass 事后放宽 main 指标。

- 上电顺序：logic 与 LED 同时；logic 先、LED 后；LED 先、logic 后。nominal rail 完整 rise100 ns；首次 rise 在1 µs、延迟 rail 在8 µs。记录20 µs短窗内 rail charge／signed energy、LED peak current／charge、PWM／gate／bias相对当时rail的超出范围；明确 upstream voltage stimulus 随 powered logic 还是独立 stiff domain。
- Reference 边界：ideal100 µA早于／晚于 Vlogic，和有显式headroom的外部行为模型对照。理想源能在零供电时强制电流，若产生负bias或非物理电压，保留结果并将其视为模型边界。Compliance模型是先前公开的教学误差预算，head_min=1 V、Rout=10 MΩ，仍不是真实reference电路；IREF上升100 ns。安全排序探针使reference在供电已建立之后启动，未加入自动POR逻辑来隐藏现有行为。
- 控制语义：运行实际RTL的同步reset与frame-latched enable轨迹。reset于20 µs置高、30 µs释放；enable于20 µs变低、300 µs变高，duty256。记录输入变化至PWM及LED电流响应；enable本来在frame边界提交，不预先假定它能立即紧急关断。没有实际供电监测／POR单元。
- 非理想rail：先取共同logic supply series R=0／10／100 Ω，LED supply R=0／100／1000 Ω；公开load-dependent droop、电流、能量及电阻耗散，不把它们称为实际package或PDN提取。可加显式1 nF logic／LED对ground去耦作hypothesis；值不是测量。nominal最低码／满开及有意义启动case优先，发现边界后只增加必要probe。
- 实测静态负载的供电边界：以已发表I–V在nominal TT／27°C MOS条件下，单独做DC series LED R=0／1000／5000／10000 Ω。实测LED测温仍unknown且不做温度缩放；此较大R范围用于定位已知较小headroom的current失败边界，不称实际PDN阻抗，也不把DC通过当dynamic qualification。
- 邻近导体：按实际extraction端口先采用明确静止rail／ground或切断边界，再对已识别clock等端点做声明的活动probe；不把理想aggressor waveform称作全digital transistor仿真。

上述参数是可检查的研究假设。若需要变更运行范围、数学模型或窗口，应先补充原因并另记证据；原始失败与输入保留。

## 4. 功耗分母与输出

分别积分 external LED rail、analog logic/reference branch、output-buffer branch、输入刺激源、series-R损耗、假设去耦的端点储能。Post分母是selected signal-path十二MOS模型的共享logic rail，reference独立；实际PG-only charging／内部PG R若被模型投影排除，必须另标excluded，而不是认为源能量已经完整。Current按已保存piecewise-linear I(t)积分；power按各自插值V(t)、I(t)的二次乘积精确积分，不能把这些数值方法升级为未保存连续波形的恢复。Signed energy允许理想源吸收回馈，不取绝对值伪装成耗能；同时给源端与负载端。稳定周期的power=energy/明确窗口长度；startup给energy及该窗口average，不能与整个digital功耗混称。没有reference generator的效率／startup／真实供电噪声，所以没有本轮系统standby规格。

新增代码和证据放在 `scripts/robustness/`、`evidence/robustness/`，raw在 `build/robustness/`；保留v0.3模型和所有旧证据。输出为15位小数表示时，完整性检查仅允许端点8个浮点ULP的表示误差；仍按预设窗口积分，并拒绝真正缺失区间。最后做不导入runner积分函数的独立复算、单位／hash检查及实际失败检测，然后更新研究说明。
