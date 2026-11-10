"""Chinese stage report; all sweep tables bind to the checked JSON receipts."""
from pathlib import Path
import json,re

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/blue-emitter-speed-review-20261110'
EV=ROOT/'evidence/blue-emitter-speed-review-20261110'

def p(s):return {'type':'p','text':s}
def h(s):return {'type':'h','text':s}
def note(s):return {'type':'note','text':s}
def fig(path,caption,height=95):return {'type':'figure','path':path,'caption':caption,'height':height}
def tab(head,rows,widths=None):
    q={'type':'table','head':head,'rows':rows}
    if widths:q['widths']=widths
    return q
def page(title,*blocks,kicker='研究与验证 · 2026-11-10'):
    return {'title':title,'kicker':kicker,'blocks':list(blocks)}
def j(p):return json.loads((ROOT/p).read_text())

def pages():
    sweep=j('evidence/blue-emitter-speed-review-20261110/speed-sweep-all.json')
    rows=sweep['rows']
    fresh=sum(r['source_case'].startswith('build/blue-emitter-speed-review-20261110/') for r in rows)
    half=sweep.get('half_step_checks',[])
    convergence=('半步长对照尚未完成。' if not half else
        f'共 {len(half)} 组半步长对照，综合通过／失败判断保持一致 {sum(x["combined_screen_unchanged"] for x in half)}/{len(half)}。最大绝对幅度变化 {max(abs(x["signed_margin_delta_uAeq"]) for x in half):.4f} µAeq，最大时间变化 {max(abs(x["time_margin_delta_ps"]) for x in half):.3f} ps，正向能量相对变化最大 {max(abs(x["energy_relative_delta_percent"]) for x in half):.4f}%。')
    micro=sorted([r for r in rows if r['family']=='MicroLED' and r['capacitance_fF']==200 and r['steps_per_symbol']==40],key=lambda r:(r['net_Gbps'],r['route']))
    vc=sorted([r for r in rows if r['family']=='VCSEL' and r['steps_per_symbol']==40],key=lambda r:r['net_Gbps'])
    caps=sorted([r for r in rows if r['family']=='MicroLED' and r['route']=='B' and r['net_Gbps']==3.2 and r['steps_per_symbol']==40],key=lambda r:r['capacitance_fF'])
    def rx(r):return r['full_receiver']
    def amp(r):return rx(r).get('worst_signed_margin_uAeq',rx(r).get('min_signed_margin_uAeq',rx(r).get('minimum_margin_uAeq',0)))
    def ep(r):return r['energy_pJ_per_attempted_payload_bit']['positive']
    def rate_range(rs):
        passed=[r['net_Gbps'] for r in rs if r['combined_research_screen_pass']]
        zero=[r['net_Gbps'] for r in rs if rx(r)['zero_error']]
        return ('未检出' if not passed else f'{max(passed):g} Gb/s','未检出' if not zero else f'{max(zero):g} Gb/s')
    summary=[]
    for name,group in [(r,[x for x in micro if x['route']==r]) for r in 'ABC']+[('VCSEL r10',vc)]:
        full,zero=rate_range(group);summary.append([name,zero,full])
    rates=sorted(set(r['net_Gbps'] for r in micro))
    micro_table=[]
    for rate in rates:
        chosen=[next((r for r in micro if r['route']==a and r['net_Gbps']==rate),None) for a in 'ABC']
        micro_table.append([f'{rate:g}',*[f'{rx(r)["errors"]:,}' if r else '未测' for r in chosen],'/'.join(('通过' if r['combined_research_screen_pass'] else '失败') if r else '未测' for r in chosen)])
    out=[]
    out.append(page('MicroLED 与 VCSEL Driver\n阶段技术成果报告',
        p('本项目已建立从数字控制、参考源、晶体管驱动到版图寄生与接收判决的可追溯研究平台。本轮增加蓝光器件调查、低速至高速的真实网表扫描，以及按负载和证据层级进行的阶段复盘。'),
        note('核心结论：蓝光 MicroLED 和蓝光 VCSEL 都有公开器件证据。短波长不会自动带来更高的调制速度。当前 3.2 Gb/s 与 32 Gb/s 是研发目标；现有电路的可用范围必须由逐点验证界定。'),
        h('本轮最高已测试通过点'),
        tab(['冻结电路','训练／验证零错','完整研究筛查'],summary,[.28,.36,.36]),
        p('上表限于本报告的 TT、固定参考负载、固定接收器与指定扫速网格。完整筛查还要求幅度、归一化时间、端压、体结与静态模型域满足条件。零错来自 4,096 位验证段，尚不能视为真实链路 BER。'),
        h('建议的研发方向'),
        p('以本轮通过边界建立低速回归基线，再改实际预驱动与换流输出。MicroLED 保留 A/B/C 比较，先前 B 的理想旁路优势须与真实电路扫速结果区分；VCSEL 单独推进低摆幅高速路径。蓝光器件建立独立数据卡，850 nm 器件保留为有高速实测依据的参考。'),
        p('[交互阅读版](index.html) · [蓝光文献细表](literature.html) · [成果核查](stage-audit.html) · [数据与复现](reproduce.html)'),kicker='阶段总结 · 实验性研发方法验证与教学'))
    out.append(page('01 目前做到了什么',
        tab(['层级','已完成的内容','证据边界'],[
            ['显示／照明','单像素 100 µA、8 bit PWM；受控启动、独立保护、参考源补偿；实际模拟宏 PEX 回归','尚无 mA 可调范围、1 MHz PWM 载波或阵列光均匀性实测'],
            ['高速晶体管','MicroLED A/B/C 与 VCSEL r10；真实参考／供电；PVT、寄生、错误定位及本轮扫速','动态负载部分为假设，未有光链路硬件与噪声 BER'],
            ['物理实现','显示宏及共同顶层；历史高速 A/B 核心 DRC、LVS、PEX 与 GDS','新完整高速电路尚无对应新版图 PEX'],
            ['工程资产','公开网表、RTL、脚本、文献台账、原生波形、源哈希、2D／Blender 教学模型','研究交付包尚不等于代工签核包或硅片验证']],[.18,.43,.39]),
        h('本轮新增了什么'),p(f'完成 {fresh} 个新增晶体管瞬态点，复用 {len(rows)-fresh} 个校验哈希的历史点，共 {len(rows)} 行分析记录。每个新速率都改变输入 PWL 的实际位周期并重新运行 ngspice；对照使用同一训练和独立验证规则。保留“零错但余量不够”与“应力失败”的区别。'),
        note('历史资料中的“第一阶段完成”只适用于当时定义的实验范围。显示宏、完整高速芯片、硅片和光链路仍分别验收。'),
        p('[逐项审计及原始 JSON](stage-audit.html) · [历史专业报告](../project-progress-review-20261108/index.html)')))
    out.append(page('02 蓝光器件有哪些可研究选择',
        tab(['类别','公开事实','当前可用于什么判断'],[
            ['蓝光 MicroLED','Aledia 资料有 3.5 × 3.5 µm 蓝光芯片，内部有源尺寸另计；QubeDot 提供可定制波长与尺寸的器件／系统','可作为询样和规格定义入口。库存、交期未核实，也没有本项目的多 Gb/s 通信保证'],
            ['蓝紫光 MicroLED','Pezeshki 2025 外部 50 Ω 测试平台报告 10 Gb/s NRZ、约 10⁻¹⁰ BER；图中光谱峰值约 425 nm','研究样品＋外部均衡。不能直接继承到现有 ASIC、450 nm 或某固定 20 µm 型号'],
            ['蓝光 VCSEL','日亚官方 2025 展示 442 nm、1 mW，明确标记 prototype','确认技术存在；该资料未提供可直接设计 32 Gb/s 链路的 L–I–V／S 参数／BER 规格'],
            ['蓝紫光 VCSEL','419 nm 非极性 InGaN/GaN 研究报告 1 GHz；作者学位论文 Fig.11 说明测试受 APD 带宽限制','可以指导结构研究。1 GHz 不是该器件已确定的物理上限；学位论文原图尚未目视复核'],
            ['近红外 VCSEL','850 nm 器件在 9 mA 时 >35 GHz；106.25 GBd PAM4 对应 212.5 Gb/s 线路位，光眼含 TX FIR／RX FFE','有高速研究依据；线路位率须与净率区分，现有 GF180 电路尚未达到这些值']],[.2,.43,.37]),
        p('蓝光边发射激光器（edge-emitting laser）、VCSEL 和 MicroLED 是不同器件。采购目录中的“blue laser”必须进一步核对出光方向、腔型和调制规格。'),
        p('[官方产品与论文逐项索引、条件及复用状态](literature.html) · [日亚原型原文](https://www.nichia.co.jp/en/newsroom/2025/2025_061801.html)')))
    out.append(page('03 波长与响应速度不是同一个量',
        p('光载波频率由 f光 = c/λ 决定。450 nm 对应约 666 THz，850 nm 对应约 353 THz。Driver 改变的是光功率包络，包络的调制带宽通常按 MHz 或 GHz 评价。光学振荡更快，并不意味着注入电荷和光功率也能更快建立。'),
        fig('assets/reference-planes.png','原创教学图。实际负载还包括非线性电容、接触、焊盘、ESD、封装及回流。每一参考面的响应必须分别建模。',89),
        tab(['器件／环节','决定动态的关键因素'],[
            ['MicroLED','电气 RC、差分复合寿命、量子阱极化场与波函数重叠、电流密度、侧壁及温升'],
            ['VCSEL','阈值与偏置、微分增益、光子寿命、弛豫频率和阻尼、寄生及热限制'],
            ['整个链路','门极驱动、输出换流、光路损耗、PD 响应度、TIA、时钟和均衡']],[.23,.77]),
        p('单极点近似 f₋₃dB ≈ 1/(2π τ)，100 ps 对应约 1.59 GHz，25 ps 对应约 6.37 GHz。这是教学计算，不能直接换算为最高数据率。多级串联、振铃和非线性条件下须用完整响应。较短波长每个光子的能量更高，也不能单独推出更低 pJ/bit；还需计入 PD 响应度、耦合和噪声。')))
    out.append(page('04 尺寸、颜色与最高数据率',
        fig('assets/size-bandwidth-rate.png','按 Dai 等 2025 Table 1/2 重绘。圆形直径；蓝光为硅衬底，紫光为蓝宝石。OOK 距离 0.3 m，优化电流密度及摆幅，FEC 门槛 3.8×10⁻³。带宽与速率最大值未必同偏置；报告速率未扣 FEC 开销。',95),
        p('在这组样品中，10 µm 蓝光器件最大带宽为 360 MHz，高于 20 µm 的 332 MHz；20 µm 的最高 OOK 速率却为 1.032 Gb/s，高于 10 µm 的 0.890 Gb/s。20 µm 紫光器件为 313 MHz、1.347 Gb/s。光功率和信噪比会改变速率排序。两组衬底不同，不能归因为波长的单独影响，也不能把 FEC 门槛下的线路位率视为无错净吞吐。'),
        h('Driver 应如何配合尺寸'),
        p('先区分台面尺寸、注入口径和实际发光面积。固定电流密度 J 比较几何效应，再固定接收 OMA／可靠性目标比较系统能耗。正方形 10／20／40 µm 在 100 µA 下分别为 100／25／6.25 A/cm²。减小尺寸会改变电容、光功率、侧壁损失与热密度，不能只把 C 按面积缩放后宣称已得到新器件模型。'),
        p('另有 5 µm 直径蓝光 GaN 研究报告 2.75 GHz、15 kA/cm²，圆形面积换算电流约 2.95 mA。该工艺及偏置不同于本项目。当前核查至作者机构摘要，晶向与系统净速率未确认，不能归类为非极性器件。'),
        p('[Dai 原文与条件](https://doi.org/10.3788/COL202523.082501) · [5 µm 蓝光论文 DOI](https://doi.org/10.1109/LED.2026.3745737) · [逐项核查边界](literature.html)')))
    out.append(page('05 MicroLED 三条驱动路线',
        fig('assets/b-principle.png','按 B 网表重绘的核心连接。XBASE 与 XTAIL 共用 BIAS，以尺寸比例设定电流；VIN、VLED 分别计能量。参考源、预驱动、RKEEP、负载寄生未展开；扫速使用完整候选。',94),
        tab(['路线','信号如何变成光电流','改善方向'],[
            ['A 电压驱动 NRZ','在两条稳压轨之间切换阴极，依二极管 I–V 得到 25／100 µA 目标','轨阻抗、推挽尺寸、Vf 温漂、充放电路径与过冲'],
            ['B 电流转向 NRZ','基准支路设低位；调制电流经差分开关流向 LED 或 dummy','对称门驱、主动放电、dummy 匹配、合规电压与静态耗电'],
            ['C 电流 DAC PAM4','两位译码为三个单元电流，得到 25／50／75／100 µA 目标','译码偏斜、支路匹配、三只眼的线性与瞬态；同净率符号率减半']],[.2,.42,.38]),
        p('这些电流是名义目标，瞬态需看波形。20 µm 正方形面积下，25／100 µA 仅约 6.25／25 A/cm²，不能直接套用高电流密度论文的 GHz 带宽。当前静态 I–V 来自黄光器件，结电容、光极点及封装仍是条件化假设。'),
        p('[A 电路](../fair-driver-comparison-20261025/figures/a-core.svg) · [C 电路](../fair-driver-comparison-20261025/figures/c-overview.svg) · [负载模型卡](../../../analog/models/microled_dynamic_v1/model-card.json)')))
    out.append(page('06 VCSEL 要把偏置与高速调制分开',
        fig('assets/vcsel-core.png','r10 的独立偏置与调制反馈核心。真实参考、供电及预驱动都在仿真网表中；图示未展开全部 73 只 MOS。',100),
        p('低位电流 I0 由偏置支路建立，高位 I1 = I0 + Imod。选择低位接近或高于激光阈值，有助于减少跨阈值开启延迟，同时增加静态耗电和低位光功率。本项目 r10 名义采用 3／7 mA。'),
        p('高速路径是输入差分接收、预驱动、换流 MOS、光源与回流。慢速路径是偏置／调制设定、温度补偿、稳压、启动和保护。慢反馈环不需要追逐每一位数据，但电源阻抗必须支持高速电流。'),
        note('当前负载是 850 nm 图读代理，不能替代蓝光 VCSEL。蓝光器件需重新取得 Ith、Vf、斜率效率、S 参数、温度和绝对最大电流；只改波长参数没有物理依据。'),
        p('[r10 详细电路与验证](../vcsel-reference-microled-dynamics-20261029/index.html) · [十倍目标诊断](../highspeed-workbench-20261110/bit-errors.html#vcsel)')))
    out.append(page('07 如何测出当前设计的速度边界',
        tab(['控制变量','本轮合同'],[
            ['码流与开销','研究帧 4,736 线路位、4,096 payload 位，效率 32/37。净 3.2／32 Gb/s 对应线路 3.7／37 Gb/s；尚未实现 FEC／重传协议'],
            ['接收器','MicroLED 固定 200 ps 光极点＋1 GHz RX；VCSEL 固定原 850 nm 光响应＋5 GHz RX'],
            ['训练与验证','仅训练段选择一次相位；验证段固定。扫 0～8 个线路 bit UI，1/64 UI 网格'],
            ['通过门槛','训练及验证零错；幅度 ≥7.5 µAeq；单侧时间 ≥0.37 线路 bit UI；器件应力与模型电流域另检'],
            ['数值控制','每个新速率运行原生 ngspice；边界附近将步长减半对照。历史锚点校验压缩与原生 SHA 后复用']],[.22,.78]),
        p('同净速率下 A/B/C 使用相同绝对时间门槛，避免因 PAM4 符号较长就给予两倍宽松条件。0.37 bit UI 在净 3.2 Gb/s 为 100 ps，在净 32 Gb/s 为 10 ps。这是项目研究筛查预算，尚未由真实抖动／CDR／BER 要求分配。'),
        p(convergence),
        note('“最高已通过测试点”只是扫描网格上的结果。还要报告下一失败点、是否单调，以及负载／温度／接收条件。本轮从已建立的 DC 工作点起算，不含上电过程和启动能量；无噪声短帧不能证明量产保证速率。'),
        p('[本轮完整条件与逐点记录](../../../evidence/blue-emitter-speed-review-20261110/speed-sweep-all.json)')))
    out.extend(result_pages(micro,vc,caps,micro_table))
    out.append(page('12 显示 PWM 成果与下一档规格',
        tab(['项目','已有验证','尚未完成'],[
            ['恒流','100 µA 设定；名义 99.7335 µA；144 点误差 −4.436%～+1.985%','0.15～7.33 mA 可编程电流、统计失配与阵列校准'],
            ['PWM','1 MHz clock，256 时间槽；载波 3.90625 kHz；最短槽 1 µs','1 MHz PWM 载波／8 bit 时需 256 MHz clock 与 3.90625 ns 槽'],
            ['恢复与保护','选定扰动最大偏离 8.873%，最长恢复 2.520 µs；TT 停钟约 205.78 ns 达安全条件','任意上电顺序、自主 POR、欠压互锁、全部故障角'],
            ['低码积分','1 µs 脉冲 99.6333 pC，相对同网络 DC 积分误差 −0.1005%','高频低码电荷、绝对光灰度、温升和寿命']],[.17,.43,.40]),
        p('参考目标约为 0.5 V / 5 kΩ = 100 µA。实现依赖外部基准、规定启动顺序和 FAULT／PERMIT。最终片外补偿与滤波必须在共同顶层接口合同中保持一致。'),
        p('扩到 2.5 mA 和 7.33 mA 分别是现设定的 25 倍和 73.3 倍。需重新验证输出 MOS、参考比例、头间电压、限流、金属电流密度、供电压降及热。阵列还增加同步切换、分布式 IR drop、失配、坏点和校准存储。'),
        p('[PWM 最终摘要](../../../evidence/pwm-reference-v2/20261024/final-summary.json) · [数字合同](../../pwm.md)')))
    out.append(page('13 版图、材料与可视化成果',
        fig('assets/physical-evidence.png','左侧为历史高速 A/B 实际 GDS 二维图，右侧为 B 核心的 Blender 几何重建。用于说明器件、金属和通孔关系；图中几何不代表本轮新高速候选。',86),
        tab(['已有物理对象','当前范围'],[
            ['显示 r5 模拟宏','39 MOS；345 R／288 C；29/29 网络。实际 DRC/LVS/PEX 与开短路负控制'],
            ['显示共同顶层','916 × 204 µm 占据范围；7,277 MOS；36,588 R／30,230 C。完整顶层瞬态通过状态仍为空'],
            ['高速历史核心','A 6 MOS＋1 R，B 9 MOS＋1 R；新完整 A/B/C 20/21/49 MOS 与 r10 73 MOS 需重新布局']],[.28,.72]),
        p('公开 GF180MCU D 配置有五层金属；旧高速核心实际使用至 M4。Driver 用硅工艺，InGaN/GaN 发光层或 GaAs 系 VCSEL 可通过倒装、转印或短互连组装。工艺选择依据速度、耐压、模型、ESD、热与制造条件，不能由“蓝光”直接推出特殊 MOS 材料。'),
        p('[可交互 2D／3D 与可编辑 Blender](../highspeed-workbench-20261110/physical/index.html) · [逐层 PWM 动画](../blender-pwm-animation-20261018/index.html)')))
    out.append(page('14 从研究电路到可送样芯片',
        tab(['阶段','应交付的数据与检查','当前状态'],[
            ['需求与模型','I0/I1、数据率、眼图、误码目标、保护、温度、供电、封装与绝对最大值','有研究合同，部分器件动态未校准'],
            ['电路闭合','DC/AC/瞬态、噪声、PVT、失配、启动、故障、功耗、环路稳定性','有指定范围结果，仍有速率与应力失败'],
            ['新版本物理闭合','匹配网表的 GDS、DRC/LVS/ERC、PEX 后回归、密度、天线、EM/IR','旧对象有证据，新高速完整芯片待做'],
            ['封装和装配','die drawing、pad/bump 坐标、bond map、光轴与热路径、公差及测试夹具','已有设计方法，尚未供应商闭合'],
            ['代工与测试','认可 PDK／rule deck、层映射、顶层、版本哈希、waiver、MPW／订单规格、探针与测试规程','未流片，未完成代工签核或实测']],[.22,.49,.29]),
        p('开源环境能够完成现有研究级网表、数字时序、版图和寄生验证。高速封装／电源的三维电磁分析、完整光器件 TCAD 和代工接受的可靠性签核，需要相应模型、求解器与服务商规则。Blender 表达几何和工艺层关系，不能输出这些物理签核结论。'),
        note('给晶圆厂的核心是符合其接受条件的版图与完整交付说明。只提交电路图、三维动画或孤立 GDS，无法保证芯片做出来能用。'),
        p('[制造交付详细清单](../highspeed-workbench-20261110/fabrication.html)')))
    out.append(page('15 下一步研发方向与决策门槛',
        h('一 · 把可用速度和真实器件绑定'),
        p('保留本轮低速通过点为回归基准。给蓝光 MicroLED、蓝光 VCSEL、850 nm VCSEL 分别建立器件数据卡，至少涵盖 L–I–V、偏置／温度下的复数 S11/S21、封装参考面和绝对光功率。缺少数据的参数继续扫范围，不把最佳假设当作名义规格。'),
        h('二 · 改真实门驱和换流路径'),
        p('MicroLED 以 A 作当前低速基线，成对比较 A 的推挽／轨阻抗优化与 B 的对称门驱、受控充放电、dummy 匹配。C 先定位并修复译码内部体结正偏，再验证三只眼。B 的理想旁路说明改善空间，不能替代实际能力排序。VCSEL 独立验证低摆幅差分预驱动、匹配输出与阻尼，保留慢速偏置和保护，逐档向 32 Gb/s 推进。'),
        h('三 · 通过电气门槛后再投入新 PEX'),
        p('先在相同负载、目标电流、接收器与能源边界下达到零错、幅度／时序与应力门槛，再做限制性 PVT、供电、元件容差和封装回归。合格版本重做完整高速核心版图，加入 PAD/ESD 和封装后复测边界。'),
        tab(['决定事项','触发条件'],[
            ['选择主线','同净吞吐和可靠性目标都满足后，比较总功耗、有效位能量、面积、工艺可得性与模型可信度'],
            ['换工艺／架构','真实门驱或输出级在合理尺寸、负载和应力范围仍不能满足预算；用同合同对照更快 CMOS／RF 工艺或另一调制路线'],
            ['扩阵列','单通道在加入实际寄生后通过，再量化公共偏置、同步开关、光串扰、热、良率和校准成本']],[.25,.75]),
        note('当前阶段的主要价值是把“为何失败、怎样改善、何时选择”转化为可复算的工程证据。技术主线由共同门槛下的结果决定，不能仅按失败帧的错误数量或 pJ/bit 排名。')))
    out.append(page('16 证据索引与复现入口',
        p('正文的新数值直接读取 speed-sweep-all.json；逐点记录含网表、波形、结果与分析源的 SHA-256。原始数据保存在 build，紧凑证据保存在 evidence。公开来源的许可与条件逐项保存在 sources.json，未获再发布许可的原图保留在本地研究目录。'),
        tab(['内容','索引'],[
            ['本轮真实扫速','[逐点 JSON](../../../evidence/blue-emitter-speed-review-20261110/speed-sweep-all.json) · [运行与恢复说明](reproduce.html)'],
            ['蓝光器件资料','[论文／产品细表](literature.html) · [来源台账](../../../evidence/blue-emitter-speed-review-20261110/sources.json)'],
            ['当前成果审计','[按证据层逐项核查](stage-audit.html)'],
            ['旧高速证据','[冻结网表复跑](../highspeed-workbench-20261110/index.html) · [位错和32 Gb/s诊断](../highspeed-workbench-20261110/bit-errors.html)'],
            ['静态／动态模型','[MicroLED 模型卡](../../../analog/models/microled_dynamic_v1/model-card.json) · [VCSEL 参考源研究](../vcsel-reference-microled-dynamics-20261029/index.html)'],
            ['物理工作台','[真实 GDS／Blender](../highspeed-workbench-20261110/physical/index.html) · [制造准备](../highspeed-workbench-20261110/fabrication.html)']],[.29,.71]),
        h('阅读本报告时保留的三个限定'),
        p('第一，扫速得到的是指定模型与接收器下的电路边界，尚非蓝光器件的实测最高速率。第二，零错短帧不是 BER 认证；没有随机噪声、抖动与统计样本，就不能声称真实 10⁻¹² BER。第三，旧版图与新电路分别验收，新电路的低速通过也不会自动转化为可流片产品。'),
        p('版本日期 2026-11-10。历史证据保留原日期和条件。本轮没有硬件测试、流片、光器件实测或新完整高速版图签核。')))
    for i,pg in enumerate(out):
        if i:pg['title']=f'{i:02d} '+re.sub(r'^\d+\s+','',pg['title'])
    return out

def result_pages(micro,vc,caps,micro_table):
    # Result-specific prose is kept next to the computed tables for review.
    from results_content import make_results
    return make_results(micro,vc,caps,micro_table)
