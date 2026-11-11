"""Second-edition research report, generated from bound experiment evidence."""
import copy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'evidence/driver-methods-20261111'
def read(n):return json.loads((EV/n).read_text())
def p(s):return dict(type='p',text=s)
def h(s):return dict(type='h',text=s)
def note(s):return dict(type='note',text=s)
def table(head,rows,widths=None):return dict(type='table',head=head,rows=rows,**({'widths':widths} if widths else {}))
def fig(path,caption,height=110):return dict(type='figure',path=path,caption=caption,height=height)
def pg(title,*blocks):return dict(kicker='第二版 · 2026-11-11 · 新方法、物理机制与产品路径',title=title,blocks=list(blocks))
def f(x,n=3):return f'{x:.{n}f}'

def pages():
    micro=read('micro-summary.json')['records'];vc=read('vcsel-methods.json')['rows'];comp=read('vcsel-comparison.json')['rows']
    def mr(c,r,s=40,hold=False):
        return next(x for x in micro if x['candidate']==c and x['kind']=='transient' and x['case']['net_rate_Gbps']==r and x['case']['steps_per_symbol']==s and ('holdout' in x['result'])==hold)
    def vr(c,r,s=40,hold=False):return next(x for x in vc if x['candidate']==c and x['net_Gbps']==r and x['steps_per_UI']==s and x['holdout']==hold)
    an='A_rcff31p275';bn='B_vin3p3_dummy27p6k';ab='a-rin1wide-core03-matched';bb='B_wide_ff31p275';vn='vc-single-r150'
    pages=[]
    pages.append(pg('速度、能耗与可制造性：第二版成果报告',
        p('MicroLED A/B 与 VCSEL Driver。这个阶段实际测试三类不同方法：瞬态电荷补偿、降低虚支路供电、减少缓冲级数并阻尼。重点是解释改善的原因与代价，建立可继续开发的证据。'),
        table(['路线','本轮有效方法','最高已测通过\n净 Gb/s','边界'],[
            ['A','N1 → RFF → CFF → OUT','2.0','2.4失败；2.0时序余量很薄'],
            ['B','VIN 3.3 V + RDUMMY 27.6 kΩ','1.8','2.0失败；保留旧5 V版2.0'],
            ['VCSEL','单级交叉输入 + 150 Ω阻尼','8.8','更高速率本轮未测']],[.12,.42,.19,.27]),
        p('相同净1.6 Gb/s：A能耗增加约7.95%，换来更宽时序与更小尖峰；B能耗降低约22.55%。VCSEL相同净6.4 Gb/s、两版均通过时，能耗降低约3.32%，时序余量扩大。'),
        note('这些是名义条件、有限数据帧的原理图级联合筛查结果。不是最大物理带宽、硬件BER、连续运行效率或流片规格。MicroLED净3.2与VCSEL净32 Gb/s仍是尚未达到的研发目标。'),
        p('第二版前半为新增实验与产品路径；后半保留第一版24页作为历史基线。旧页中的“本轮”指第一版，当前决策以前半部分为准。')))
    pages.append(pg('01 · 比较之前，先固定条件',
        table(['项目','MicroLED A/B','VCSEL'],[
            ['负载','20 µm黄光静态参考；200 fF假设值','850 nm图读代理；150 fF'],
            ['封装','1 Ω / 0.5 nH','0.5 Ω / 0.2 nH'],
            ['光学 / RX','200 ps单极点 / 1 GHz','保留前版光学代理 / 5 GHz'],
            ['DC目标','25 / 100 µA，偏差≤1%','3 / 7 mA，偏差≤1%'],
            ['MOS / 温度','GF180公共模型，TT / 27°C','GF180公共模型，TT / 25°C'],
            ['输入','20 ps PWL边沿','20 ps互补PWL边沿']],[.20,.40,.40]),
        p('净速率/线速率=32/37，每帧4736位，验证载荷4096位。训练评分标签为第64–511位，可见波形前缀截至第576位；验证为第576–4671位。相位只用训练前缀，不能借验证数据选相。'),
        p('通过需要同时满足：训练与验证零错、最差幅度≥7.5 µAeq、单侧时间≥0.37线速率UI，以及DC、电压/体结筛查和负载模型电流范围。µAeq是接收代理归一化量，不是实测探测器电流。'),
        p('E+为七个源端正向供能积分÷4096个尝试有效载荷位，单位pJ/bit；返还与净能量另记。它不是系统总能耗，也不是净热耗散；未通过点只保留诊断值。'),
        note('A/B之间条件相同；VCSEL使用另一类负载、偏置和接收模型，不能直接把两者pJ数字排成同一系统的输赢。20 µm只是例子，尚未确定产品尺寸。')))
    pages.append(pg('02 · A：在输出开关之前补充电荷',
        fig('assets/a-new-circuit.png','原理图按候选网表绘制。橙色为新增串联RC前馈；三个CMOS反相级和供电轨保持不变。',137),
        p('LED阳极电位固定时，阴极OUT降低会增加正向电压，使导电电流变大。主输出级CTRL较晚到达；N1提前翻转，因此可以先通过电容把OUT往正确方向推动。'),
        p('RFF为PDK高阻多晶硅4×4 µm电阻；CFF=31.275 fF仍是理想集总。电容在DC开路，两态目标不变；高速时新增电荷通路与能耗。')))
    pages.append(pg('03 · A：改善在哪里发生',
        fig('assets/micro-a-waveforms.png','同一净1.6 Gb/s、同一时间窗口，未平移波形。判定使用全帧原生采样，图形抽样仅用于展示。',153),
        p('旧版在应变亮时先出现电流下冲，应变暗时先出现过冲。新增支路使初始变化方向正确，电流范围由17.19–129.89缩至24.58–101.86 µA；时间余量由216.92增至241.15 ps。'),
        note('该现象与输出MOS栅漏耦合造成的反向初始跃变相符。本轮没有单独关闭或提取Cgd，不能把全部改善定量归给某一个寄生参数。')))
    pages.append(pg('04 · A：用电荷计算解释结果',
        fig('assets/micro-a-ff-nodes.png','N1、FF与OUT说明前馈的时序；电荷由Q=CFF(VFF−VOUT)计算，未用数值微分峰值作器件额定判断。',113),
        p('负载电容需要的电荷量级约为 CLED×ΔVOUT = 200 fF×0.4 V = 80 fC。选取连续四个相同比特后的边沿，前200 ps的CFF电荷变化约−67.62 / +50.43 fC，量级相当。'),
        p('这些电荷主要改变节点电压，不等于全部通过LED复合发光。电流导通、电容位移电流和光功率必须分开，才能解释“尖峰变小但时序变好”。'),
        p('同速E+从1.05783升至1.14188 pJ/bit。VDD端增加0.13541，VLED端减少0.05123 pJ/bit；新增CFF整帧储能变化仅−0.000255 pJ，不能解释源能量增量。'),
        note('这是以额外数字开关能量换取瞬态质量。平均LED电流由64.643降至62.944 µA；相同DC目标不代表逐帧相同平均光功率。')))
    pages.append(pg('05 · B：降供电，必须保留顺应电压',
        fig('assets/b-new-circuit.png','保持发光支路VLED=5 V和逻辑VDD=3.3 V；只降低参考/虚支路VIN并调整RDUMMY。',135),
        p('电流转向需要让未流向LED的约75 µA有合适的去路。虚支路压降过大时，开关和尾电流源失去顺应电压，切换时内部节点要经历更大恢复过程。'),
        p('以DUMMY约1.23 V为目标：RDUMMY≈(3.3−1.23)V/75 µA≈27.6 kΩ。它不是随速率反复拟合的参数；冻结后用于全部数据率与留出验证。')))
    pages.append(pg('06 · B：用单因素对照区分两个作用',
        table(['净1.6 Gb/s','E+\npJ/bit','时间\nps','峰值\nµA'],[
            ['旧版5 V / 50 kΩ','1.09443','233.01','112.32'],
            ['只降压3.3 V / 50 kΩ','0.84394','201.88','123.90'],
            ['降压+27.6 kΩ','0.84759','229.80','113.36']],[.44,.18,.19,.19]),
        p('只降压时，LED两态DC依然达标，但低态DUMMY只有0.3140 V、VX为0.2335 V，虚支路约59.72 µA。说明只检查LED稳态电流，可能漏掉内部换流工作点错误。'),
        p('调整27.6 kΩ后，DUMMY=1.2256 V、VX=1.0362 V、虚支路约75.16 µA，接近旧版。相比只降压控制，仅增加0.00365 pJ/bit，却恢复27.93 ps时间余量并降低过冲。'),
        p('VIN端正向能量由0.54628降至0.29871 pJ/bit，是主要节能来源。低压版在2.0 Gb/s只有157.52 ps，未到160 ps门槛，因此不能把该点的低pJ数值当成有效链路能效。'),
        note('VIN与VDD虽同为3.3 V，仍是两套独立供电网络。外部VREF=2.5 V仍保留；尚未实现片上自给式带隙参考或合并电源。')))
    pages.append(pg('07 · B：波形显示节能的边界',
        fig('assets/micro-b-waveforms.png','原版、只降压与补偿虚支路在同吞吐下比较。接收余量与源端能量必须一起看。',151),
        p('新B在1.8 Gb/s通过，时间余量190.97 ps，比门槛多约13.20 ps。2.0时只有零错位而没有足够时序，旧5 V版2.0仍作为更高速候选保留。'),
        note('降低供电不保证所有速度都更好；电压余量、工作点恢复和器件过驱动共同决定边界。当前可保留高性能与节能两个工作点，产品模式如何切换还未设计。')))
    rows=[]
    for c,label,rs in [(an,'A 新RC',[1.6,2.0,2.4,3.2]),(bn,'B 低压',[1.6,1.8,2.0,3.2])]:
        for rate in rs:
            r=mr(c,rate);x=r['full_receiver']
            rows.append([f'{label} / {rate:g}',str(x['errors']),f(x['worst_signed_margin_uAeq'],2),f(x['one_sided_margin_ps'],2),f(r['energy_pJ']['positive'],4),'通过' if r['pass_screen'] else '未过'])
    pages.append(pg('08 · MicroLED：通过点、失败点都保留',
        table(['路线 / 净Gb/s','错误','幅度\nµAeq','时间\nps','E+\npJ/bit','联合筛查'],rows,[.25,.10,.17,.17,.16,.15]),
        p('A的2.0 Gb/s时序门槛为160 ps，实际约161.62 ps。留出片段仍通过，但只多约1.58 ps，不能直接作为产品额定值。B低压1.8的余量更宽；旧B5 V仍可在2.0通过。'),
        p('A在2.4零错但幅度仅2.775 µAeq、时间77.00 ps，明显失败。零错只说明这帧的判决结果；距离边界很近的电路可能在下一种噪声、温度或码型下出错。'),
        p('净3.2时，新A完整链650错，且电气-only虽零错但只有95.43 ps，低于100 ps门槛；旧A电气原本通过。新B完整链259错，但电气仍有120.19 ps并通过。因此新A还出现电驱波形代价，不能把失败全部归给光学/RX。'),
        note('最高通过是离散测试点，不是连续扫频找到的最大速率。失败行的E+仅作诊断，不参与可靠有效载荷能效排名。')))
    pages.append(pg('09 · VCSEL：减少一级缓冲，再处理副作用',
        fig('../../../evidence/driver-methods-20261111/vcsel-single-stage-circuit.png','73 MOS改为69 MOS：删除两条通路的第一级反相器共4 MOS；互换DI/DBI进入剩余一级，保持换流极性。',148),
        p('最终GP与GN仍驱动原来的电流转向管；偏置约3 mA、调制约4 mA，实际参考调节与激光供电保留。减少级数减轻内部开关负载和脉冲失真，但让上游输入直接驱动更大的栅电容。'),
        note('“级数更少”并非通用最优。只有在输入接口足够强、极性正确、峰值与接收都合格时，删级才成立；产品需要真实PHY、PAD/ESD与封装联仿。')))
    pages.append(pg('10 · VCSEL：前馈为什么反而失败',
        fig('../../../evidence/driver-methods-20261111/vcsel-ff20-native.png','20 fF前馈方案的原生门极波形；它是实际失败试验，并未从报告中删除。',145),
        p('从输入直接补充门极电荷，最初看似能提前动作，但主缓冲与前馈作用不匹配。输入下降后GP先降至约2.584 V，又在80 ps内回到约2.988 V；低脉冲未充分拉低，LED低谷从约3.039升至3.940 mA。'),
        p('净7.2 Gb/s虽零错，时间余量仅0.159 UI，E+=5.434 pJ/bit，较旧版更差。阈值交叉数没有增加，证据支持脉冲压缩与回弹，不支持“出现额外双重翻转”。'),
        note('前馈不是一加就有效；符号、注入节点、相位、负载阻抗与主驱动恢复过程都要一致。40 fF候选只预留，未执行，不列作实测结果。')))
    pages.append(pg('11 · VCSEL：两次失败帮助定位改法',
        table(['试验 / 净7.2 Gb/s','观测','判断'],[
            ['降低预驱动轨约3.1→2.45 V','E+约5.039 pJ；230位错误；幅度−4.37 µAeq','摆幅减小同时损失过驱动，当前方法不成立'],
            ['单级，RAD/RADB=50 Ω','时间0.4463 UI；E+5.1293 pJ；峰值7.584 mA','接收改善，但超出固定7.5 mA模型上界'],
            ['单级，RAD/RADB=100 Ω','时间0.4485 UI；峰值7.5155 mA','峰值下降，仍不合格'],
            ['单级，RAD/RADB=150 Ω','时间0.44894 UI；峰值7.44753 mA','当前联合筛查通过']],[.32,.43,.25]),
        p('输入阻尼限制边沿过快造成的门极/输出耦合。在删掉一级后的较大直接栅负载上，阻尼增加可能压低过冲；但过大也会拖慢切换，因此必须同时检查眼图和峰值。'),
        p('用50→100 Ω两点得到局部峰值斜率约−1.376 µA/Ω。为保留约50 µA模型余量，计算选150 Ω，预测7.44669 mA，实际7.44753 mA。这是局部经验估算经第三点确认，不是可无限外推的定律。'),
        note('7.5 mA是所用公开图读负载模型的拟合范围上界，并非实物校准结果或VCSEL绝对最大额定电流。越界意味着模型不能支持结论，不能直接解释成器件损坏。')))
    pages.append(pg('12 · VCSEL：接收改善与输入代价',
        fig('../../../evidence/driver-methods-20261111/vcsel-single-stage-comparison.png','相同速率下比较门极、导通电流和接收信号；删级后脉冲保真改善。',139),
        p('在净7.2 Gb/s，新版输入源峰值电流约7.411 mA，旧版约3.561 mA，约2.08倍。每路内部RAD/RADB=150 Ω之外仍串固定50 Ω源电阻；七源能量已计入，但真实PHY限流、内部损耗和频变/非线性输出阻抗未建模。'),
        p('本轮体结正向筛查上限固定0.3 V。新版GP相关体结约0.264 V，超过0.25 V的单段最长约5.26 ps；通过当前研究筛查，不代表已通过代工厂可靠性/ERC要求。'),
        note('这项改善把部分负担从片内缓冲转给输入接口。若真实FPGA/SerDes无法提供该电流和边沿，收益可能缩水，必须把接口纳入下一轮闭环。')))
    vrows=[]
    for rate in [6.4,7.2,8.0,8.8]:
        old=next((x for x in comp if x['label']=='baseline73MOS' and x['net_Gbps']==rate),None)
        if old:vrows.append([f'旧73 / {rate:g}',f(old['timing_UI'],4),f(old['energy_pJ_per_attempted_payload_bit']['positive'],4),f(old['I_range_mA'][1],4),'通过' if old['combined_screen_pass'] else '未过'])
        r=vr(vn,rate);vrows.append([f'新69 / {rate:g}',f(r['full_receiver']['one_sided_margin_UI'],4),f(r['source_energy_pJ_per_attempted_net_bit']['positive'],4),f(r['observed']['electrical_current_range_mA'][1],4),'通过' if r['combined_screen_pass'] else '未过'])
    pages.append(pg('13 · VCSEL：提速有效，能耗收益有边界',
        table(['MOS / 净Gb/s','时间 / UI','E+ pJ/bit','峰值 mA','联合筛查'],vrows,[.25,.20,.20,.20,.15]),
        p('严格同速、两者均通过的6.4 Gb/s：E+由5.88021降至5.68495 pJ/bit，降低3.32%；时间余量由0.38104增至0.46333 UI。8.8是本轮最高已测通过点，更高速率尚未验证。'),
        p('显式供轨/补偿电容的帧内释放能量，旧版约282.2 pJ、新版176.6 pJ；新版少借约105.6 pJ，源端节省约799.8 pJ。该检查支持节能并非靠更多借用这些电容，但不构成全电路稳态能量闭合。'),
        note('新版6.4→8.8的pJ下降时，帧平均正向源功率反从约36.384升至37.624 mW。每比特能量改善不等于总发热下降，源端功率也不是完整热耗散测量；32 Gb/s仍未实现。')))
    pages.append(pg('14 · MicroLED净3.2：还卡在哪里',
        fig('assets/link-sensitivity.png','仅对第一版冻结A/B的原生3.2 Gb/s电流重新施加光学/RX模型；32格均非新电路仿真。',107),
        p('200 ps光学时间常数对应单极点约0.796 GHz。固定它时，即使把假设RX带宽从1增至8 GHz，原版A/B也没有通过当前联合接收门槛。提高RX带宽并不能自动弥补发光响应。'),
        p('条件性通过例子：A在假设50 ps光学时间常数、4 GHz RX时约0.3772 UI；B在100 ps、2 GHz时约0.3762 UI。它们为器件和接收器提出需求，不证明已有对应光源、噪声性能或功耗。'),
        note('这张图没有把新RC版A或低压B的波形混进去，也没有用改模型来冒充Driver改进。更快光源、真实RX以及预加重需作为独立假设继续验证。')))
    pages.append(pg('15 · 用物理量判断下一种方法',
        table(['机制','为什么可能有效','为什么也可能失败'],[
            ['栅极/输出RC','t约随R×C增加；减少串级或负载可提速','MOS变小会增大导通阻抗；删级加重输入负担'],
            ['边沿电荷 Q=CΔV','提前提供充放电电荷，缩短建立时间','相位或注入点错误会回弹、脉冲压缩及过冲'],
            ['降低电压','开关负载能量近似随CΔV²下降；静态功耗随VI变化','过驱动/顺应电压减少；线性稳压上游能量未必同比下降'],
            ['电流转向','偏置保持、调制电流在两支路分配','虚支路仍耗能；匹配、尾源和寄生限制切换'],
            ['光源动力学','MicroLED载流子寿命、RC；VCSEL弛豫振荡与阻尼','尺寸、偏置、温度与封装共同作用，不能按波长单变量排名']],[.23,.37,.40]),
        p('本轮驱动MOS仍是硅CMOS，03v3/06v0是器件选项差异；没有改用GaN功率MOS。III-V发光材料与硅驱动芯片是不同对象，不能用MicroLED或VCSEL的材料名称替代ASIC工艺。'),
        p('功耗更低的目标应是达到指定接收可靠性时的系统pJ/bit。单独把偏置电流压低，可能降低带宽、光功率或信噪比；VCSEL偏置还需要考虑激射阈值及其温漂。'),
        note('本轮模型未包含完整载流子/光子速率方程、随机噪声或自热，因此不能从这些波形推定真实器件的极限。')))
    pages.append(pg('16 · VCSEL净32需要新的链路预算',
        p('净32 Gb/s按当前32/37开销对应37 Gb/s线速率，单UI约27.03 ps。当前PWL输入的0–100%边沿20 ps已占约74% UI；5 GHz RX单极点时间常数约31.83 ps。即使输出开关进一步变快，现有整条链路条件也需要重新评估。'),
        table(['后续候选方法','依据','必须验证'],[
            ['可编程边沿预加重','公开VCSEL驱动研究使用过预加重；本轮被动前馈失败提示相位重要','受控延迟、极性、脉宽和峰值；不能套用论文数字'],
            ['输出阻抗/匹配联合优化','减少反射与封装谐振；适配真实激光器端口','S参数、PAD/ESD、带宽/功耗和工艺角'],
            ['更小摆幅/电流复用','公开28 nm CMOS研究展示过低功耗短距收发器','必须有足够过驱动、参考与输出顺应电压'],
            ['更快工艺与真实高速PHY','减少逻辑/栅电容延迟，同时解决输入边沿','完整授权PDK、器件fT/fmax与噪声/可靠性模型']],[.28,.34,.38]),
        p('[IBM 2005](https://research.ibm.com/publications/a-20gbs-vcsel-driver-with-pre-emphasis-and-regulated-output-impedance-in-013mm-cmos)报道130 nm、20 Gb/s预加重及输出阻抗调节；[Yazaki 2018](https://globals.ieice.org/en_transactions/fundamentals/10.1587/transfun.E101.A.402/_p)报道65 nm、25 Gb/s/ch；[Yang 2025](https://www.mdpi.com/2072-666X/16/5/587)的28 nm独立TX为25 Gb/s、39.8 mW≈1.59 pJ/原始位，完整链路测试为20 Gb/s。'),
        note('文献条件、编码与能源范围不同；它们支持继续研究这些方法，不代表本项目GF180已复现，也不是改换工艺后必然达到的承诺。')))
    audit=read('scientific-validation.json')
    pages.append(pg('17 · 如何防止把仿真假象当改善',
        table(['检查','本轮做法','仍不能证明'],[
            ['输入与源文件身份','原始PWL、网表、模型及执行脚本SHA绑定','使用错误模型但自洽的结果也可能存在'],
            ['DC与应力','两态DC；原生采样的MOS端压、体结及电流域','PVT、随机失配、长期可靠性'],
            ['数值复核','最终候选S40→S80；新PRBS15窗口0x4c2d','任意码型、噪声与统计BER'],
            ['独立审查','重新计算七源能量、应力、32格光/RX矩阵','物理硬件与光学模型真实性'],
            ['训练隔离','破坏验证区间的反事实检查不改变训练选相','真实时钟恢复和接收抖动容限']],[.20,.43,.37]),
        p('新留出窗口位于PRBS15周期[27081,31817)，与开发窗口及第一版留出不重叠。电路参数在查看留出结果之前冻结，不因留出结果重新调参。'),
        p('A2.0与B1.8均通过S80及新窗口；A留出仅多约1.58 ps时序余量，B约13.03 ps。VCSEL8.8新窗口零错、0.43281 UI、E+=4.27821 pJ/bit，峰值7.47256 mA，距模型上界仅27.44 µA；S80也通过。'),
        note('每帧4096载荷位且无随机噪声。即使零错，也不能宣称BER为零或达到10⁻¹²；没有条件支持把它当随机独立伯努利误码试验。'),
        p('[独立科学审查](../../../evidence/driver-methods-20261111/scientific-validation.json) · [MicroLED筛查](../../../evidence/driver-methods-20261111/micro-validation.json) · [VCSEL筛查](../../../evidence/driver-methods-20261111/vcsel-validation.json)')))
    pages.append(pg('18 · 从Driver电路到可用的产品',
        p('产品链路包括：数据源/SerDes → 输入接口与PAD/ESD → 预驱动 → 电流调制 → 封装与发光器件 → 光通道 → 接收/TIA/时钟恢复。参考、供电、启动与保护贯穿整条链路。'),
        table(['尚缺的边界','为什么影响结论','下一步交付'],[
            ['真实输入PHY','69MOS方案转移了瞬态栅驱动负担','有限输出阻抗、摆幅、抖动、PAD/ESD联合模型'],
            ['自主参考/供电','A/B仍依赖2.5 V外部参考；VCSEL仍用VSET/VREGSET外部精密基准','参考容差、PSRR、噪声、温漂和上游电源静态功耗'],
            ['启动/故障关断','A未实现DISABLE；前馈可在关断时传递边沿电荷','上电顺序、掉电、输入持续翻转、过温/开短路测试'],
            ['完整能量与热','供轨大电容会在有限帧中释放储能','连续通信稳态、热边界、全源能量闭合']],[.23,.40,.37]),
        note('本轮已经包含实际实例化电源与输入端口能量；没有实例化的参考IC、上游驱动内部、RX/主机和转换效率仍在范围之外。报告不把这些开销视为零。')))
    pages.append(pg('19 · 现有版图做到哪里，新版还缺什么',
        table(['已有独立证据','当前状态','不能继承给本轮'],[
            ['显示analog r5','39 MOS；345 R / 288 C；29/29网络，既有DRC/LVS/PEX','新高速A/B/VCSEL连接与器件已改变'],
            ['显示joint-r2','7277 MOS；36588 R / 30230 C；6512/6512网络','全瞬态回归未完成，未含完整PAD/ESD/封装'],
            ['旧高速A/B核心','旧A 95 R / 64 C；旧B 127 R / 76 C','新参考/前馈/供电/输入不能用旧PEX替代'],
            ['当前新增候选','可追溯原理图、晶体管瞬态及接收计算','尚无匹配的新GDS、DRC/LVS/PEX签核']],[.24,.42,.34]),
        p('本地锁定的GF180物理选项为5LM_1TM_11K，指金属互连选项，不代表芯片只有5层材料或5张掩模。MOS、阱、接触、通孔、钝化和BEOL需要完整工艺层映射。'),
        p('显示joint-r2边界916×204 µm≈0.186864 mm²仅是该宏单元包围盒，不是可封装裸片面积。PAD间距、ESD、供电、测试和封装约束往往决定最后die边界。'),
        note('显示PWM支线的1 MHz计数时钟/256≈3.90625 kHz PWM，不能宣传为1 MHz载波或已验证0.15–7.33 mA量产范围。')))
    pages.append(pg('20 · 新版物理设计要怎么做',
        table(['步骤','具体工作与验收'],[
            ['选定工艺与接口','先锁定制造方接受的PDK、器件/金属/MIM选项、PAD/ESD与封装接口'],
            ['分区与匹配','快速差分路径对称；基准/电流镜隔离数字噪声；补偿和回流尽量短'],
            ['井与器件规则','GF180未编码规则DN.Note1禁止3.3 V和6 V器件共用同一DNWELL；需要按选项单独布置'],
            ['电阻与电容实现','RFF/RDUMMY的几何、寄生、容差、电流密度；CFF的底板、连线与开关耦合'],
            ['DRC / LVS / ERC / PEX','检查几何、连接、供电/体端规则；各寄生角重新跑同一接收与能量合同'],
            ['电源/封装','静态IR+动态供轨阻抗、EM、电感耦合与S参数；必要时3D电磁与热分析']],[.27,.73]),
        p('开源ngspice、Magic/KLayout、Netgen、OpenROAD等可以继续支持开发与许多检查，但每项工具必须绑定匹配的PDK和规则。OpenRCX需要对应工艺/角的提取规则；静态PDNSim不能代替GHz电源动态与完整EM/热签核。'),
        p('[GF180未编码规则](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_16.html) · [OpenRCX](https://openroad.readthedocs.io/en/latest/main/src/rcx/README.html) · [PDNSim](https://openroad.readthedocs.io/en/latest/main/src/psm/README.html)'),
        note('二维GDS看几何，Blender三维图帮助理解层次；两者都不能单凭可视化证明电磁、热、工艺或可靠性正确。本轮未新做版图或3D仿真。')))
    pages.append(pg('21 · 向制造方交什么，怎样避免“做出却不能用”',
        table(['交付对象','数据包','前提'],[
            ['晶圆/MPW制造方','层次GDSII、top cell/单位/layer map、工艺与金属选项、签核报告/waiver、版本与SHA清单','以对方书面接受的完整PDK和交付清单为准'],
            ['封装与光学装配方','裸片与PAD坐标、pin/bond map、极性与电源、封装/散热/光学接口、测试要求','封装寄生与机械/热/光耦合预先联仿'],
            ['测试方','测试模式、向量与限值、探针/板卡、校准步骤、I–V/L–I/S21/眼图/BER/温度计划','设置观测点、偏置监测与可调参数，先留诊断能力']],[.22,.43,.35]),
        p('在流片前约定每个失效如何被观察：参考启动失败、输出饱和、输入不够快、封装振铃、光源带宽不足和RX噪声都需要可区分。保留偏置/调制可编程、内部监视节点、慢速测试与PRBS模式会提高首轮样片的学习价值。'),
        p('截至2026-11-11，Google公开GF180仓库显示已归档且开放版本标注Experimental Preview。这不等于商业GF180工艺停产，也不代表本项目版本已被制造方接受。需确认实际服务方、完整规则与生产选项。[公开PDK状态](https://github.com/google/gf180mcu-pdk) · [GF180交付检查](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_06.html)'),
        note('当前还不能发送为“可流片设计”。价格、良率和量产可行性要在规格、die面积、封装、测试时间、产量及真实报价明确后评估，现阶段不编造成本。')))
    pages.append(pg('22 · 下一阶段建议：先补会改变选型的证据',
        h('优先一：接口、能量与保护闭环'),
        p('固定本轮电路，在真实输入阻抗/限流/抖动下重测VCSEL单级方案；对A/B与VCSEL完成连续通信稳态及储能闭合。补A关断、B前馈旁路抑制、启动/掉电/数据持续翻转保护。它们会直接决定改法能否落地。'),
        h('优先二：从单点通过扩展为稳健工作区'),
        p('以A2.0、B低压1.8、VCSEL8.8作为名义边界候选，另选更保守工作点做PVT、独立电阻/电容角、负载与封装变化。A仅1.6 ps额外时序、VCSEL峰值距模型上界几十µA，均不宜直接定额定速度。'),
        h('优先三：按链路需求选择器件，再做完整新版图'),
        p('MicroLED净3.2需要真实光学S21和RX数据；VCSEL净32需要重新配置输入、光源、RX和工艺预算。取得可追溯器件/封装数据后验证可编程预加重、阻抗匹配等方法，再决定是否迁移工艺与进入新版图。'),
        note('可持续协作的方式是：每一阶段锁定假设 → 实施单项变化 → 保留成功与失败 → 独立复查 → 更新报告与备份。我可以继续承担设计、仿真、版图与资料工作；制造商接受、实物测量和生产认证仍需相应外部资源。')))
    pages.append(pg('23 · 复现、来源与历史基线',
        p('本轮来源和范围逐项列在[产品化详细说明](productization-notes.html)、[19项公开一手来源](../../../evidence/driver-methods-20261111/product-sources.json)、[11项流片门槛](../../../evidence/driver-methods-20261111/tapeout-readiness.json)。公开论文按实际器件、调制、接收和能量口径引用，未复制商业设计。'),
        table(['证据','用途'],[
            ['micro-summary / micro-selection','逐个DC/速率/步长/留出结果，网表与原生波形SHA'],
            ['micro-causal / micro-mechanisms','A的电荷与B的内部工作点、七源能量分解'],
            ['vcsel-methods / vcsel-comparison','成功与失败电路、源端能量、负载域与复查'],
            ['scientific-validation','独立重算、训练隔离、冻结前后摘要一致性'],
            ['link-sensitivity','旧A/B的32格条件性光学/RX预算'],
            ['reproduce / Release清单','跨电脑恢复、脚本版本、环境与大文件范围']],[.40,.60]),
        p('[完整复现步骤](reproduce.html) · [第一版冻结报告](../driver-improvement-20261111/index.html) · [上一版原始证据Release](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/driver-improvement-20261111)'),
        note('下列附录保留第一版24页内容与图表，便于追溯原始架构改善。它们的当时最高通过点不再是本版最新结论；历史版图与仿真资格也不会自动继承给新电路。')))
    old=json.loads((ROOT/'docs/research/driver-improvement-20261111/content.json').read_text())
    for i,page in enumerate(copy.deepcopy(old),1):
        page['kicker']=f'历史附录 · 第一版第{i:02d}/24页 · 仅作基线追溯'
        for b in page['blocks']:
            if b['type']=='figure':
                b['path']='../driver-improvement-20261111/'+b['path']
                if 'original' in b:b['original']='../driver-improvement-20261111/'+b['original']
            elif 'text' in b:b['text']=b['text'].replace('(reproduce.html)','(../driver-improvement-20261111/reproduce.html)')
        pages.append(page)
    return pages
