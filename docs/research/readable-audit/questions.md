# 技术疑点与验证决策清单

2026-10-08，基线 `781ceb266eb1f1dc16780d806cdcd0d5005716ae`。配套[研究说明](report.md)。本轮只读审计，没有改电路、模型、仿真代码，也没有新增EDA实验。下述“下一验证”全部是建议，尚未执行。

## Q1　真实LED动态参数尚未进入模型（最高优先）

**已确认**：`lin2026-yellow20-dc.spice`只有PWL静态I(V)，C、TT、温度、自热、光学模型为空；`measured-load-summary.json`的0.2／2／20pF是人为恒定电容。20pF duty1面积通过，但约18.455%的signed conduction charge在未测低端正向延拓区；该case最低LED电压约1.496V，未进入reverse。0.2pF案例才有约−9.77mV小负偏压。

**风险／可能原因**：面积近似正确可能来自真实导电响应，也可能依赖数值低端延拓；同一DC曲线可以对应不同charge dynamics。不能据此宣称真实PWM、leakage或光学响应成立。

**下一验证**：先获取同样品低电流／reverse I–V、偏置C与脉冲／S21；同时记录bias、温度、仪器、重复数和de-embedding。将conduction与displacement分开；对延拓形式做独立敏感性实验，只用于衡量依赖，不作为拟合事实。[输入与输出](../../../evidence/characterization/measured-load-summary.json)，[model-card](../../../analog/models/measured-led/model-card.json)。

## Q2　理想IREF掩盖reference的可实现性（最高优先）

**已确认**：片上reference generator未实现；startup早开理想100µA源出现bias比reference rail高约1.372V，源瞬时主动供能约137.235µW。关闭PWM后IREF仍持续，nominal reference rail约330µW。

**可能原因**：理想源没有compliance／startup约束；PG与保护器件也未建立。现有finite-compliance行为对照仍不是实现电路。

**下一验证**：先声明accuracy、drift、compliance与startup/fault门槛，再实现reference；单独扫source supply与bias负载，区分源饱和和MOUT headroom。用同条件pre/post检查startup signed energy与轨外电压。[startup原case](../../../evidence/robustness/boundary-summary.json)。

## Q3　joint PEX的真实PG／body及邻居仍被截断（最高优先）

**已确认**：12 MOS、45R、77C来自共同GDS；全部PG/source/body R被投影，PG-only C移除，34邻居main用0V理想源，包括floating fillcap／FF内部节点。实际raw有5644MOS，当前求解未包括全部。

**可能原因**：quiet clamp减弱／改变耦合；真实floating节点初态和active driver impedance可改变边沿。PG压降、body effect和decap energy没有在现有图中闭合。

**下一验证**：按hierarchy/GDS身份定义每邻居的驱动／floating条件，逐项扫相位和阻抗；保留实际PG/body网络后重复DC、最短pulse、startup和功耗分解。观察误差随PG/邻居变化还是仅输入slew变化。[projection与neighbors](../../../evidence/joint-pex/nominal/summary.json)。

## Q4　bias跌落、电流overshoot和负峰尚无因果分解

**已确认**：typical joint duty1 fine run保存波形有约109.330µA正峰、−15.591µA负峰；bias暂降后恢复；平均和面积仍在目标内。

**可能原因**：MPASS/MCLAMP overlap、MOS charge injection／Miller、LED displacement current、distributed coupling。仅看到峰或平均不能确定主因，也不能称无stress。

**下一验证**：记录switch conduction、每器件charge与内部端电压；分别改control timing、input slew和LED charge项，保持其他输入与积分窗不变。若去除某机制明显改变bias／branch峰却不改变plateau，可建立该机制贡献；仍须恢复物理模型后回归。[原waveform](../../../build/robustness/main-mx5nfi8b/tt_post_d1_fine/waveform.dat)。

## Q5　静态headroom失效已存在，但失效边界尚不完整

**已确认**：同joint／公开静态表／5V LED rail下，假设RLED10kΩ得到88.266µA，失败±5%；1／5kΩ仍在目标内。RLED是敏感性参数，非实测线阻。

**可能原因**：输出MOS退出误差容许的regulation；reference／pass路径限制也可能在其他条件先发生。VDSAT不是精度门槛。

**下一验证**：分别固定cathode扫描Iout、扫LED rail和source reference，记录内部VGS/VDS/IREF，搜索每PVT的允许误差compliance。将输出／source失效分开，再对实际供电阻抗测量。[四次DC](../../../evidence/robustness/boundary-summary.json)。

## Q6　亚ns阈值边沿受人为PWL与数值配置限制

**已确认**：v0.4输入来自RTL event，加人为1ns全摆幅ramp，切口在末级buf输入；上游FF transistor waveform／C-Q不在模型。1ns线性ramp的30%→70%区间本就0.4ns；输出量不是光学响应。

**可能原因**：人为输入过快／供电理想化；adaptive timestep／插值可能影响峰值，已完成step refinement仅支持所记录积分的数值稳定。

**下一验证**：同条件细化timestep和solver tolerance，分别查charge、峰值、slew；再由真实前级和其负载产生输入波形，区别预算敏感性与数字路径实证。不得把SDF事件模型当完整晶体管路径。[main配置与指标](../../../evidence/robustness/main-summary.json)。

## Q7　PWM enable／软件timeout没有建立保护关断

**已确认**：enable在20µs低，注册PWM到258.5µs才低；Pythontimeout在514µsblank、PWM514.5µs低。receiver是功能模型，未实现硬件watchdog。IREF未因此断电。

**可能原因**：正常更新沿用frame边界合同；保护路径／power-good未定义。

**下一验证**：先定义safe-off电流、最长deadline、reset/enable/fault优先级和recovery；实现独立硬件机制后验证异步事件、掉电和源断开。第一off帧charge tail与稳态leakage分开。[控制原结果](../../../evidence/control/validation.json)。

## Q8　负C处理是投影边界，不是全raw问题都解决

**已确认**：存档hierarchical nominal原raw有661负C，flat r3有19小负C；19全部随fixedPG-only项移除，没有clipping。最终导出R>0、C≥0。首次flat标签层错误由r1 log证实，最终r3改变提取输入后未见同警告。

**剩余疑点**：固定rail省略项在startup／真实PG扰动时不再可按固定电位处理；层次化与flat差异不能仅凭最终收敛作普遍解释。

**下一验证**：保留原raw及各项ledger，采用完整动态PG时检查nodal C matrix、符号来源与边界条件，再比较独立抽取器和负对照。导出signal网络passivity与原raw signoff分别验收。[方法与ledger](../joint-pex.md)，[原r1失败log](../../../build/joint-pex/flat-nominal-r1/magic.log)。

## Q9　PVT／RC／mismatch样本数不代表qualification或yield

**已确认**：五RCstyle确实提取，但main仅三MOS envelope×nominal，加SS×HRHC／FF×LRLC补点；不是完整3×5矩阵。135静态grid固定MOS27°C、LED曲线温度未知。MC是PDK条件模型样本，非实物批次。

**下一验证**：按应用灵敏度定义覆盖矩阵与worst-case search；获取LED I–V(T)与reference真实漂移，再分别检查固定process、随机mismatch与系统性梯度。用置信区间／模型适用范围记录统计，不能把0/256超限写成制造良率。[main](../../../evidence/robustness/main-summary.json)，[actual mirror](../../../evidence/characterization/actual-w20-l4-summary.json)。

合成动态main的`.temp`同时改变MOS和synthetic diode；旧独立diode对照呈未校准的正温度系数。这些结果不是MOS-only温漂研究。真实静态表案例则固定LED未知温度曲线，只改MOS条件，二者须分开。

**物理时序的已知限制**：Icarus SDF编译有unsupported ifnone/timing checks；关键delay arcs单独检查，setup/hold依据STA，不依据未执行的检查。数字STA的TT25°C／SS125°C／FF−40°C与v0.4电气27／85／0°C不同。独立KLayout density/antenna modes未运行，OpenROAD antenna pass不替代这些模式；IR-drop也缺明确supply locations。[SDF记录](../../../evidence/physical/sdf/summary.json)，[physical report](../../digital/physical.md)。

## Q10　文档年代与source hash的混用会升级证据

**本轮确认的表达错误**：Zenodo declared publication为2026-05-05，created/modified为2026-06-18；原model-card写published Jun18，应区分。旧报告的“尚无joint”／10/2尺寸／RC值属于旧阶段。phase1广域hash有5项与当前不同，但核心driver／LED／PWM／runner匹配；optional TB日志格式变更有input-mapping证据。

另核实面积分母：robustness实际runner取同条件duty256 transient平均，旧说明有“full DC”表述；control回放才取独立DC。两数近似相同也不能混写计算方法。新报告已按实际代码区分。[robustness计算](../../../scripts/robustness/run.py)，[control计算](../../../scripts/control/run.py)。

**下一核查**：将每个结论绑定as-run deck、input snapshot、raw hash；只在有关输入变更影响该结论时重跑。先报告新run必要性与范围。本轮保存649个tracked文件hash；完成时比较它们，未检测到其他任务修改原输入。原历史文档保留，新入口明确当前报告。[snapshot](snapshot-inputs.json)，[input-mapping](../../../evidence/research/input-mapping.json)。

DRC/LVS/GDS、硅片、光学分别要求独立证据。下一实验不应仅增加“通过计数”，而应能排除一个可改变研究结论的原因。

## 有日志的补充历史失败

模拟版图初次运行有4项M1 spacing<0.23µm，最终compact log为DRC0；文档将修正归因bulk via landing，原日志本身只证明违规与后来零违规。[初次原log](../../../build/layout/pixel-9h7e80ye/magic-generate.log)，[最终log](../../../evidence/layout/magic-generate.log)。数字初次physical flow的exit0仍有21项slew超限；提高repair margin到50%后kernel记录OpenROAD OOM；排除delay buffers后仍11项，最终再排除buf_1、保持3ns门槛后通过。[历史summary](../../../evidence/physical/summary.json)，[OOM原log](../../../build/physical-flow/guest-kernel-after-repair-oom.log)。这些是已有记录，不是本轮新实验；早期缺完整runner快照，归因强度应相应受限。
