"""Chinese teaching report: observations, hypotheses, interventions and evidence."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'evidence/ab-improvement-20261111'

def read(name):return json.loads((EV/name).read_text())
def p(s):return {'type':'p','text':s}
def h(s):return {'type':'h','text':s}
def note(s):return {'type':'note','text':s}
def table(head,rows,widths=None):return {'type':'table','head':head,'rows':rows,**({'widths':widths} if widths else {})}
def fig(path,caption,height=100):return {'type':'figure','path':'assets/'+path,'caption':caption,'height':height}
def pg(title,*blocks):return {'kicker':'2026-11-11 · 电路改进、因果对照与性能边界','title':title,'blocks':list(blocks)}
def fmt(x,n=3):return '—' if x is None else f'{x:.{n}f}'
LABELS={'a-base':'A 原版','a-rin1':'A 输入R降低','a-rin1wide':'A 输入R加宽','a-rin1wide-buf03':'A 缓冲03v3','a-rin1wide-buf03-out2-matched':'A 缓冲03 + 输出加宽','a-rin1wide-core03-matched':'A 六管核心03v3','B_baseline':'B 原版','B_rin1':'B 仅输入R降低','B_fast':'B 仅快缓冲','B_fast_wide':'B 快缓冲 + 宽R','B_wide_ff20':'B 前馈20fF','B_wide_ff31p275':'B 前馈31.275fF','r10-baseline':'VCSEL 原版','vc-atten50':'仅输入50Ω','vc-steer20':'仅换流W20µm','vc-atten50-steer20':'VCSEL 输入 + 换流改进'}
def label(x):return LABELS.get(x,x)


def pages():
    data=read('summary.json');selected=read('selection.json');vc=read('vcsel-improvement.json')
    rows=data['transient'];pages=[]
    overview=[]
    for route in ['A','B','VCSEL']:
        s=selected[route]
        overview.append([route,label(s['candidate']),fmt(s['highest_passing_Gbps'],2),fmt(s['next_failing_Gbps'],2)])
    pages.append(pg('从“跑得通”到“为什么变快”',
        p('MicroLED A/B 与 VCSEL Driver 电路改进及验证报告。研究重点是把技术难点变成可验证的假设，再用单项修改解释性能变化。'),
        table(['路线','本轮候选','最高通过测试点\n净 Gb/s','下一失败测试点\n净 Gb/s'],overview,[.10,.42,.24,.24]),
        p('此前最高已测试通过点分别为 A 1.2、B 0.4、VCSEL 4.8 Gb/s。本轮 A 通过减小输入 RC、改用较快核心器件和重校输出轨改善；B 通过前馈电容补充瞬态电荷改善；VCSEL 通过输入电阻及换流管尺寸优化改善。'),
        note('通过点同时检查直流匹配、训练与验证错误、接收幅度、时序及器件应力。它不是精确最大速率、实物 BER、PVT 签核或量产规格。'),
        p('A/B 保持相同的 MicroLED 负载和接收条件；VCSEL 使用其独立的 850 nm 模型与接收器。最终产品路线仍未选定。C 暂缓，不把当前译码器失效等同于 PAM4 技术路线不可行。'),
        p('[前阶段报告](../blue-emitter-speed-review-20261110/index.html)保留原始基线；本报告只扩展经过本轮实际求解的改善和限制。')))
    pages.append(pg('01 · 先固定公平比较的边界',
        table(['项目','MicroLED A/B','VCSEL'],[
            ['发光负载','20 µm 黄光静态 I–V 参考；200 fF 假设电容','850 nm 图读模型；150 fF'],
            ['封装','1 Ω / 0.5 nH','0.5 Ω / 0.2 nH'],
            ['光学 / 接收','200 ps 单极点 / 1 GHz 接收极点','原光学代理 / 5 GHz 接收极点'],
            ['直流目标','25 / 100 µA','3 / 7 mA'],
            ['本轮名义条件','GF180；TT、27°C、VDD 3.3 V','GF180；TT、25°C、VDD 3.3 V'],
            ['外部数据边沿','20 ps','20 ps']],[.20,.40,.40]),
        p('每帧 4736 位，其中 4096 位为独立验证载荷，净速率 / 线速率 = 32/37。每个新速率都生成真实 PWL 并重新运行 ngspice，未缩放已有波形。'),
        p('接收相位只由训练段选择。主判据为训练、验证均零错，最差有符号幅度 ≥7.5 µAeq、单侧时间余量 ≥0.37 线速率 bit UI。另检查 MOS 端间电压、体结正向电压 ≤0.3 V、模型电流范围。'),
        note('同一“直流目标”不等于同一“瞬态峰值”。若加入预加重，必须单列峰值、平均电流和能量。所有 µAeq 为研究模型归一化电气量，不是光探测器实测电流。')))
    pages.append(pg('02 · 电流为何会跟不上数据',
        p('MicroLED 电流分为导电电流和结电容充放电电流。能发光的是导电分量；电容电流先改变端电压。驱动器必须同时满足两者，而不仅是让门极出现正确的 0 和 1。'),
        note('I端口 = I导电 + C × dV/dt；所需电荷 Q = C × ΔV。'),
        table(['局部估算','结果','含义'],[
            ['25 → 100 µA 电平','LED 正向电压变化约 0.407 V','来自冻结静态 I–V 插值'],
            ['200 fF 电容','Q ≈ 81 fC','需要从输出端移动的电荷'],
            ['净 3.2 Gb/s，半个 UI','约 135 ps，需要约 0.60 mA','是额外位移电流预算，不是直流电流'],
            ['25 µA 附近的 rd × C','约 2.15 ns','低位恢复可能出现长尾'],
            ['100 µA 附近的 rd × C','约 0.59 ns','电流不同，动态阻抗也不同']],[.34,.27,.39]),
        p('rd 是静态 I–V 的局部微分电阻。以上 RC 只用于解释机理，未包含驱动输出导纳、封装和大信号时变效应，不能直接当作整个链路的截止频率。'),
        p('[理想电流与电荷计算证据](../../../evidence/ab-improvement-20261111/ideal-bounds.json)')))
    pages.append(pg('03 · A：逐级定位，而不是一起改尺寸',
        fig('a-circuit-method.png','A 的六 MOS 输出核心；实际两套参考分压与分流调节轨仍完整保留。所有修改都有独立网表。',111),
        p('先观察 D0 → DI → N1 → CTRL → OUT → LED 导电电流。在稳定长码型前后测量同一极性的过阈延迟，分清输入 RC、反相器内部延迟和输出电压建立时间。'),
        p('N1 驱动第二级，CTRL 驱动输出对。NMOS 的源端为 VL、体端为 VSS；PMOS 的网表源和体端接 VH。稳态时 LED 电流可从 OUT 经 PMOS 流入 VH 分流轨；瞬态拉高阴极时，电荷可由轨电容提供。'),
        note('数字缓冲和模拟输出具有不同的耐压、驱动和负载要求。“改用更快 MOS”不是全芯片一键换型。')))
    pages.append(pg('04 · A 的原因证据与修改依据',
        table(['长码型过阈时间中位数','原版：下降 / 上升','仅降低输入 R 后'],[
            ['DI','63.3 / 66.0 ps','19.3 / 19.6 ps'],
            ['CTRL','474.5 / 403.9 ps','368.1 / 304.6 ps'],
            ['OUT 电压中点','837.0 / 704.2 ps','730.9 / 604.0 ps']],[.36,.32,.32]),
        p('原版第一级反相器自身还增加约 196～293 ps，第二级约 118～142 ps，输出级约 300～363 ps。因此输入电阻降低确实有效，但不能解释或消除全部延迟。'),
        p('在净 1.6 Gb/s，RIN 单项修改使幅度余量从 2.54 增到 6.40 µAeq，单侧时间从 94.17 增到 147.69 ps，仍未满足 200 ps 的本速率门槛。4 µm × 4 µm 的宽电阻对照保留了相近改善。'),
        p('下一项只把四只预驱动 MOS 改为 3.3 V、L=0.28 µm 器件，输出与 5 V 供电调节器保留 6 V MOS。此时 1.6 Gb/s 时序提高到约 191.84 ps，但仍略不足；才进一步检查输出电阻及尺寸。'),
        p('输出管加宽后必须重新校准 VH/VL；该方案虽增大眼高，时序仍未过，且电流峰值与能耗增加。最终把输出两管也改为03v3、L0.28µm并保持原宽度，重新拟合RH/RL；六管核心03v3配合14管06v0真实轨发生器，才在1.6Gb/s通过。'),
        p('最终 RH≈185.509 kΩ、RL≈93.448 kΩ，DC 为 24.997/99.985 µA。选定改版的 CTRL 中位延迟约161.6/144.0 ps、OUT约330.7/250.7 ps；这种逐级缩短与接收改善相互支持，不能把延迟倍数当吞吐倍数。'),
        note('这些是原生波形中的条件性过阈延迟，不是随机抖动或全码型最坏传播延迟。63 个下降和 76 个上升的已定义长码型事件用于本次机理比较。'),
        p('[初始延迟统计](../../../evidence/ab-improvement-20261111/a-diagnosis-initial.json) · [最终延时链](../../../evidence/ab-improvement-20261111/a-latency-chain.json) · [器件与尺寸对照](../../../evidence/ab-improvement-20261111/a-component-comparison.csv)')))
    for route,title in [('A','05 · A：修改前后的晶体管仿真记录'),('B','08 · B：有效改善与失败尝试')]:
        rr=[r for r in rows if r['route']==route and r['case']['steps_per_symbol']==40]
        for batch in range(0,len(rr),8):
            chunk=rr[batch:batch+8]
            page=pg(title+('（续）' if batch else ''),table(['候选 / 净 Gb/s','位错','幅度\nµAeq','时间\nbit UI','E+\npJ/尝试位','联合筛查'],[[label(r['candidate'])+' / '+fmt(r['case']['net_rate_Gbps'],2),str(r['full_receiver']['errors']),fmt(r['full_receiver']['worst_signed_margin_uAeq'],2),fmt(r['full_receiver']['one_sided_margin_bit_UI'],3),fmt(r['energy_pJ_per_attempted_payload_bit']['positive'],3),'通过' if r['joint_screen_pass'] else '未通过'] for r in chunk],[.34,.10,.13,.13,.15,.15]),
                p('所有结果使用相同负载和接收门槛。能量包含完整帧的七个已实例化电源 / 信号端口。失败点的 pJ/尝试位不是可靠交付有效数据的能效。'),
                p('[逐项网表、波形哈希、DC 匹配和应力记录](../../../evidence/ab-improvement-20261111/summary.json)'))
            if route=='A':pages.append(page)
            else:pages.append(page)
        if route=='A':
            pages.append(pg('06 · B：门极变快，为何还不够',
                p('原 B 在净 0.8 Gb/s 下没有位错，但幅度余量仅 0.734 µAeq、时序仅 0.0977 UI。长码型由低转高后 0.5 / 1 / 2 ns，电流约为 39 / 59 / 87 µA；输出建立跨越一个以上 UI。'),
                p('减小输入电阻单独试验反而把余量降到 0.263 µAeq / 0.0578 UI，并使体结正向电压峰值达到约 0.314 V，超过本项目 0.3 V 筛查线。仅把缓冲器改为更快的 3.3 V MOS，也没有消除输出慢尾。'),
                p('这两个反例说明需要同时考虑输入 RC、互补门极的时差、快速边沿激发的过冲，以及低电流负载本身的充放电能力。不能把“用了更快器件”直接当成系统提速。'),
                note('保留失败记录是本轮的关键成果：它阻止我们沿着“继续减 R 或一味加大 MOS”盲目迭代。')))
            pages.append(pg('07 · B：用电容提供瞬态电荷',
                fig('b-charge-assist.png','CFF 从 GB 接到 OUT。本轮为显式集中电容模型，未实例化 PDK MIM/PEX。前馈支路没有独立能量源；七个供电和数据端口统一计能，初始储能与连续运行仍需另核对。',119),
                p('CFF 在直流时开路，因此不靠持续增加尾电流来改变 25/100 µA 的目标。在 0.8 Gb/s 的选定边沿头 200 ps，31.275 fF 电容移走约 85.93 fC 或注入约 74.11 fC，平均位移电流约 −0.430 / +0.371 mA，覆盖所需约 81 fC 的数量级。'),
                p('这些瞬态电流主要承担结电容充放电；本例 LED 导电电流峰值约 109 µA。不能把位移电流全部当作发光电流。GB 的有限驱动、输出电压变化和封装振铃已包含在真实求解中。'),
                note('峰值电流可能超出 100 µA，平均电流也可能改变。即使接收变好，也须报告这项代价，不能称为“完全相同光功率下免费提速”。')))
    pair=[next(r for r in rows if r['candidate']==selected[route]['candidate'] and r['case']['net_rate_Gbps']==1.6 and r['case']['steps_per_symbol']==40) for route in ['A','B']]
    pages.append(pg('08B · 在同一 1.6 Gb/s 上比较 A/B',
        table(['项目','A 改版','B 改版'],[
            ['完整接收错误',[r['full_receiver']['errors'] for r in pair][0],[r['full_receiver']['errors'] for r in pair][1]],
            ['最差幅度 / µAeq',*[fmt(r['full_receiver']['worst_signed_margin_uAeq'],2) for r in pair]],
            ['单侧时间 / ps',*[fmt(r['full_receiver']['one_sided_margin_ps'],2) for r in pair]],
            ['超过200ps门槛的余量',*[fmt(r['full_receiver']['one_sided_margin_ps']-200,2)+' ps' for r in pair]],
            ['E+ / pJ每尝试载荷位',*[fmt(r['energy_pJ_per_attempted_payload_bit']['positive'],3) for r in pair]],
            ['瞬态导电电流 / µA',*[fmt(r['current_range_uA'][0],2)+'～'+fmt(r['current_range_uA'][1],2) for r in pair]],
            ['全电路MOS数',*[str(r['MOS_count']) for r in pair]]],[.44,.28,.28]),
        p('A 在这个工作点的源端帧能量较低；B 的时序余量更大，并把输出慢尾显著缩短。这是实际的工程取舍，不能只看各自最高速率或错误位数。'),
        note('B 的 CFF 依赖负载和门极波形，A 的电流依赖输出轨与LED I–V。下一步应比较容差与PVT下是否还能保留这些优势，再决定最终技术主线。')))
    pages.append(pg('09 · VCSEL：输入与换流负载分别修改',
        fig('vcsel-circuit-method.png','保留 r10 的实际参考电流和供电调节器，只对输入电阻和两只换流 MOS 做单因素及组合对照。',118),
        p('ATTEN 从 200 Ω 降到 50 Ω，同时改变输入 RC 和分压：进入缓冲器的高电平约从 3.000 V 提高到 3.173 V。因此不能把全部收益仅归因于 RC。'),
        p('换流 MOS 的宽度从 40 µm 减到 20 µm，有望减小门极和扩散负载，但会提高导通电阻并压缩电流合规余量。3/7 mA 的 DC 验证用于确认这项交换没有破坏目标电流。')))
    causal=read('vcsel-causal-comparison.json')['rows']
    pages.append(pg('10 · VCSEL：同速率的因果对照',
        table(['净 6.4 Gb/s 候选','幅度\nµAeq','单侧时间\nps','E+\npJ/尝试位'],[[label(r['candidate']),fmt(r['full_amplitude_uAeq'],2),fmt(r['full_margin_ps'],2),fmt(r['positive_pJ_per_attempted_bit'],3)] for r in causal],[.43,.19,.19,.19]),
        p('本速率时序门槛为 50 ps。仅减 ATTEN 时刚过门槛；仅减换流管宽度时略未过。组合修改达到约 51.49 ps，说明两个独立改善确实可以叠加，但剩余约 1.49 ps 仍然很薄。'),
        p('在相同 6.4 Gb/s 下，组合的正向输入能量约从 5.952 降到 5.880 pJ/尝试位，降低约 1.21%。显式电容储能审计显示改版借能更少约 24.1 pJ，不能用额外借用这部分储能解释约 294.3 pJ 的源端节省；它仍是有限帧结果，未闭合全部器件储能。'),
        p('7.2 Gb/s 与 8.0 Gb/s 虽仍是短帧零错，却分别只有约 0.331 UI 与 0.240 UI，未通过时序门槛。因此本轮新增的是“6.4 可用研究点”，没有证明净 32 Gb/s。'),
        note('4.8 → 6.4 是最高已测试通过点的变化。旧版 4.8～6.4 区间没有完整细扫，不能据此声称物理最大速度精确提升 33%。')))
    pages.append(pg('10B · VCSEL：沿同一时间轴看改善',
        fig('vcsel-waveforms.png','同一输入序列、同一真实时间轴，逐级比较输入、门极、导电电流与接收波形。没有平移波形来制造更好对齐。',145),
        p('相位选择是接收器的采样设置，不能把其数值误当作独立器件传播延迟。保留各级曲线，可以检查改善究竟来自输入、门极还是输出电流。')))
    pages.append(pg('11 · 还有多少改善空间',
        fig('rate-envelope.png','固定条件下各路线的幅度与时序余量。水平线是研究门槛；实线连接离散点，仅便于阅读。',105),
        p('理想 25/100 µA、20 ps 导电电流对照在净 2.0 Gb/s 有较充足余量，2.4 Gb/s 接近时序边界，3.2 Gb/s 即使零错也严重缺少余量。这说明驱动器优化之外，当前光学和接收响应同样限制目标。'),
        note('这个对照只限制“无预加重的两电平矩形电流”类别。允许额外瞬态峰值、均衡或不同器件响应后，结果可能改变，不能把它当作所有架构的绝对上限。'),
        p('在 2.4 Gb/s 边界附近，训练相位网格会影响极小余量差异；加密采样与独立相位网格诊断已记录。主比较仍保留原 1/64 UI 相位合同。')))
    pages.append(pg('12 · 更快不一定更省电',
        fig('energy-and-current.png','同吞吐比较输入能量，同时列出电流峰值与平均值，避免只挑低 pJ 数字。',105),
        p('E+ = 完整帧正向输入能量 / 4096 个尝试载荷位。固定参考和供电功耗被更高吞吐分摊后，pJ 数字会下降，但前提是该点满足接收和应力要求。'),
        p('返能与净能量单独保留。没有假定上游供电芯片能够无损回收返能；也没有把未实例化的参考 IC、接收器、时钟和主机开销算成零。'),
        note('技术主线应先满足可靠性余量、直流电流和应力约束，再在相同吞吐、负载与系统能源范围内比较能效。不能单凭错误数更少或 pJ 数字更低决定。')))
    targets=[r for r in rows if r['candidate'] in [selected['A']['candidate'],selected['B']['candidate']] and r['case']['net_rate_Gbps']==3.2 and r['case']['steps_per_symbol']==40]
    pages.insert(-1,pg('11B · 回到净 3.2 Gb/s 的目标',
        table(['最终候选','完整接收\n错位 / 4096','完整接收\n幅度 µAeq','电气接收\n时间 / UI'],[[r['route'],str(r['full_receiver']['errors']),fmt(r['full_receiver']['worst_signed_margin_uAeq'],3),fmt(r['electrical_receiver']['one_sided_margin_bit_UI'],3)] for r in targets],[.22,.27,.27,.24]),
        p('两条改版都重新生成 3.2 Gb/s 激励并实际求解。改善提高了较低速率的可用余量，但尚未达到这个目标。负幅度表示至少有采样值跨到了判决门槛的错误一侧；它不是“还差一点电压”就必然能补齐。'),
        p('直接用 LED 导电电流作电气接收时，A 约为 24.02 µAeq / 0.4117 UI，B 约为 30.01 µAeq / 0.4443 UI，均零错并通过应力。加上固定 200 ps 光学响应与 1 GHz RX 后才失败。这是两条改版的共同定位结果，不是已经实现 3.2 Gb/s 光链路。'),
        p('下一步共同检查光学响应、接收带宽和预加重波形，对缺少实测依据的参数继续做敏感性分析。A 仍需控制输出轨漂移和电流尖峰；B 仍需检验前馈电容容差和保护关断。不能仅凭此次两者位错数的差距选定主线。'),
        note('这轮证据支持 A/B 并行推进，尚不足以选定最终产品架构。净 3.2 Gb/s 和 VCSEL 净 32 Gb/s 继续作为研发目标，不写成已实现规格。')))
    pages.append(pg('13 · 验证是否能站得住',
        p('基线复跑复现了前阶段的 A 1.6 Gb/s 和 B 0.8 Gb/s 数值。所有新电路先校准 DC，所有实际速率都重新求解；MOS 应力使用原生求解采样，接收不使用压缩时间轴。'),
        p('候选边界做最大时间步长减半对照。A 的 1.6/1.8、B 的 2.0/2.4 Gb/s 通过和失败判定均不变，时序变化分别不超过 0.0245 / 0.00045 ps。VCSEL 6.4 Gb/s 的 S40/S80 判定一致，时序变化约 0.0031 ps、能量变化约 −0.0011%。'),
        p('开发过程中始终使用固定 PRBS 帧便于归因；最终候选另用预先锁定的 0x317E 种子复查。它对应 PRBS15 周期中相隔 16749 位的另一窗口，不根据该结果重新调参。'),
        table(['另一 PRBS 窗口','幅度 / µAeq','单侧时间 / UI','验证位错'],[['A · 1.6 Gb/s','17.400','0.39858','0 / 4096'],['B · 2.0 Gb/s','13.309','0.38211','0 / 4096'],['VCSEL · 6.4 Gb/s','31.121','0.38774','0 / 4096']],[.34,.22,.25,.19]),
        note('第二个窗口的联合筛查均通过，候选未据此再调参。但它仍不是统计 BER 测量，也没有随机噪声、抖动或真实时钟恢复。'),
        p('[固定复查协议](../../../evidence/ab-improvement-20261111/holdout-protocol.json) · [A/B 结果及步长对照](../../../evidence/ab-improvement-20261111/summary.json) · [VCSEL 结果](../../../evidence/ab-improvement-20261111/vcsel-improvement.json)')))
    pages.append(pg('14 · 从电路有效到版图可制造',
        table(['本轮发现','影响与下一步'],[
            ['低阻输入电阻','不能只改电阻值。核查高阻 poly 的电流密度、最小尺寸及底板寄生；1 方块最终对照使用更宽几何。'],
            ['小值 CFF','最小 MIM 板和边缘电容限制实际最小值；31.275 fF 是所选模型的名义几何计算，不等于已完成版图。'],
            ['3.3 V 快速缓冲 MOS','仍是硅 CMOS；与 6 V MOS 的差异是器件选项与结构参数，不能继承旧 3.65 V 高供电角。'],
            ['输出 MOS 尺寸','加宽可能降低导通电阻，也增加门极和扩散电容。VCSEL 减宽有效，A 则需针对实际负载验证，不能一概而论。'],
            ['寄生与供电','VH/VL 的大电容仍是外部无源模型， GHz 下的实际供电轨阻抗尚未验收。新版完整核心需要重新布局、提取、检查 PAD/ESD、回流、供电阻抗和封装；旧 PEX 不覆盖新电路。']],[.28,.72]),
        p('[高阻 poly 规则](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_10_03.html) · [MIM Option B 规则](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_10_4_2.html)。[PDK 规则、模型参数与适用条件](../../../evidence/ab-improvement-20261111/physical-sources.json)保留了具体定位。GF180 的金属层数并不自动指定 MIM 选项或密度，最终须匹配完整 PDK 和制造选项。'),
        note('本阶段没有新增可流片 GDS、DRC/LVS/PEX 或光学实测。新增电路图是原理连接，不能升级成版图验收证据。')))
    pages.append(pg('15 · 下一阶段研发顺序',
        h('先冻结有效改法，再扩大验证范围'),
        p('保留 A/B 双主线。分别以同速率电流、能量、余量和应力建立比较表，继续检查真实参考、供电、阻尼和负载交互。VCSEL 独立推进高速路径，保留慢速偏置和保护。'),
        p('首先补长帧或周期通信稳态、真实轨电流与储能闭合。当前A的VH有约2.1mV帧内漂移，有限帧能量不能直接当连续运行效率。随后增加 MOS/电阻工艺角、供电、温度、封装与关键无源容差。3.3 V 缓冲候选先建立新的电源上限；不能简单复用旧 3.65 V 角。当前发光模型缺少温度拟合，电路角验证也不等于完整光源温度验证。'),
        p('当候选在上述扰动下仍有余量，再做完整高速核心布局和 PEX。若固定光学 / RX 仍限制净 3.2 或 32 Gb/s，就依据链路预算选择更快光源、接收器、均衡或工艺，而不继续盲目调整晶体管。'),
        h('本阶段真正积累的能力'),
        note('把错误定位到具体参考面；用单项修改验证原因；用 DC、波形、能量和应力共同判断；记录无效尝试；明确下一步要测什么。这条可复现的解决问题流程，比单一峰值数字更有价值。'),
        p('[复现步骤、原始数据与验收记录](reproduce.html)')))
    pages.insert(-1,pg('14B · 保护关断不能继承旧结论',
        p('本轮通信测试均为已建立偏置、正常使能的工作条件。显示 PWM 支线的启动和保护证据，不能替代高速通信改版的验证。'),
        table(['电路','目前确知','下一步必须验证'],[
            ['A 高速核心','DISABLE 引脚预留，尚未实现关断','建立独立关断路径，并检查输出轨在上电、掉电及数据继续翻转时的状态。'],
            ['B 前馈改版','DISABLE 可钳位参考源，但 GB 仍可能随数据变化','参考关断期间持续发送数据，测 LED 导电电流、位移电荷及过冲；不能只测静止输入。'],
            ['B 可选补救','可冻结互补门极、钳位输入或隔离前馈支路','这些属于待测试方案；评估隔离开关的寄生、电压应力及重新使能瞬态，不预先宣称有效。']],[.20,.36,.44]),
        note('CFF 能改善正常通信充放电，也可能绕过原来的电流关断路径。发现这项边界不推翻正常使能速度结果，但它是新版图和产品化之前的功能门槛。')))
    for prefix,newpage in [
        ('04 ·',pg('04B · A：同一时间轴上的逐级改善',
            fig('a-waveforms.png','净 1.6 Gb/s、相同输入和同一物理时间窗口；曲线未平移或缩放。接收采样标记使用各自训练段确定的相位。',168),
            p('观察顺序是输入 D0 → 输出门极 CTRL → LED 导电电流 → 完整接收模型。图中改版 CTRL 更早翻转，导电电流建立更快，但瞬态尖峰也增大；最终判断使用整帧和应力数据。'))),
        ('07 ·',pg('07B · B：电荷补偿的直接证据',
            fig('b-edge-charge.png','在同一 0.8 Gb/s 下，快门驱对慢尾改善有限；前馈补偿使上升与下降更快。下图显示电荷量，与约81 fC的结电容需求作数量级对照。',151),
            p('20 fF 与 31.275 fF 都是集中电容对照。后者提供更多边沿电荷，同时带来过冲和额外门极供能。最佳值必须随器件电容、封装、PVT 和真实 MIM 寄生重新确认。')))
    ]:
        i=next(i for i,x in enumerate(pages) if x['title'].startswith(prefix))
        pages.insert(i+1,newpage)
    return pages
