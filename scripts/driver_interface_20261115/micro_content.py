"""MicroLED continuous/protection chapters from final summary records."""
from content import ROOT,read,page,p,h,note,table,fig

def f(x,d=4):return f'{x:.{d}f}'
def data():return read('micro-summary.json')
def base(s,route):
    return next(x for x in s['rows'] if x['route']==route and x['variant']=='baseline' and x['result'].get('mode')=='continuous' and len(x['result'].get('frames',[]))==4)
def selected(s,route,key):
    path=s['selections'][route][key]
    if isinstance(path,dict):path=path.get('source_case',path.get('path'))
    return next(x for x in s['rows'] if x['source_case']==path)
def stage_summary():
    s=data();v=read('vcsel-interface-summary.json')
    vc=next(x for x in v['rows'] if x['candidate']=='single-phy12' and x['config']['net_Gbps']==8.8 and x['config']['steps_per_UI']==40 and not x['config']['holdout'])
    rows=[]
    for route in ['A','B']:
        old=base(s,route)['result']['frames'][-1]
        new=selected(s,route,'continuous_case')['result']['frames'][-1]
        rows.append([route+' · 基线 → 新增关断',f(old['energy_pJ_per_attempted_payload_bit']['positive'])+' → '+f(new['energy_pJ_per_attempted_payload_bit']['positive'])+' pJ/b',f(new['first_frame_phase_receiver']['timing_UI'])+' UI；各连续10.24 µs'])
    rows.append(['VCSEL · 有限输入修正',f(vc['energy_pJ']['positive'])+' pJ/b',f(vc['full_receiver']['one_sided_margin_UI'])+' UI；净8.8 Gb/s'])
    return page('先看结论：修正了哪些理想化条件',
      table(['验证点','完整边界的能量','接收与时间范围'],rows,[.27,.35,.38]),
      p('VCSEL原单级候选接上较弱MOS输入级后，在8.8 Gb/s虽零观察错，但幅度/时序不通过；加宽上游输出MOS恢复余量，新增能耗同时进入结果。减轻输入下拉负载的尝试更省电，却没有恢复8.8 Gb/s。'),
      p('A/B连续运行先检查供轨和储能，再评价每位能耗；独立关断单独验证数据持续翻转时的导电电流、LED端压、过渡峰流和恢复。保护是否通过及其代价见后面的前后对照。'),
      p('B新增保护和门控后，末帧E+相对基线变化'+f((new['energy_pJ_per_attempted_payload_bit']['positive']/old['energy_pJ_per_attempted_payload_bit']['positive']-1)*100,2)+'%，单侧时间余量由'+f(old['first_frame_phase_receiver']['timing_UI'],4)+'变为'+f(new['first_frame_phase_receiver']['timing_UI'],4)+' UI。保护功能有明确能量与时序代价，不能沿用未加保护时的性能排名。'),
      note('新增A/B保护仅在净1.6 Gb/s验证，不能继承前版无新增保护时的A 2.0、B 1.8 Gb/s结果。以上是名义模型与实际时长内的研究证据，不是实物接口合规、长期热稳态、光学BER或流片资格。'))

def continuous_pages(s):
    out=[page('MicroLED · 连续供能与电容储能',
      p('本轮在同一次SPICE瞬态内连续发送4个相同4736位PRBS片段，净1.6 Gb/s，每帧2.56 µs，共10.24 µs。完整电流先经过一次200 ps光学极点和1 GHz RX，再切帧评分，避免滤波器状态被逐帧重置。电脑的求解耗时不是器件运行时间；这里验证的电路时间只有10.24 µs。'),
      p('A的两条输出轨各有100 kΩ馈电电阻和10 nF电容，被动RC约1 ms。但它还有主动分流调节；不能仅凭RC直觉断言会失效，也不能用一帧结果声明长期稳定。实际用逐帧供能、轨端点变化与显式储能核对。'),
      p('每帧分别积分所有七个源端：VIN、VDD、VREF、VLED、VD0、VD1、VDISABLE。电容储能差按ΔU=½C(V_end²−V_start²)计算，电感按½L(I_end²−I_start²)。负ΔU表示该储能元件向外释放能量。'),
      p('这些瞬态从已求得的直流工作点开始。电源从零上电、参考建立和初始电容充电的全过程不在本轮连续数据帧能耗内。'),
      note('监测显式C/L不等于完整能量守恒模型：MOS内部电荷和光源动态储能没有全部闭合，光学代理也不是电光热守恒模型。因此源端能耗不能直接写成热耗散。'))]
    for route in ['A','B']:
      r=base(s,route)['result']
      out.append(page(route+' · 连续四帧的实际结果',
        table(['帧','E+ pJ/b','净能量 pJ/b','固定相位幅度','固定相位时间'],[
         [str(x['frame']),f(x['energy_pJ_per_attempted_payload_bit']['positive'],6),f(x['energy_pJ_per_attempted_payload_bit']['net'],6),f(x['first_frame_phase_receiver']['amplitude_uAeq'],3)+' µAeq',f(x['first_frame_phase_receiver']['timing_UI'],6)+' UI'] for x in r['frames']],[.08,.21,.21,.25,.25]),
        p('最后两帧E+相对变化：'+f(r['steady_screen']['energy_change_percent'],8)+'%；末帧所监测轨最大端点变化：'+f(r['steady_screen']['max_monitored_rail_endpoint_delta_mV'],6)+' mV。每帧仍使用首帧训练得到的采样相位，另保留逐帧训练结果。'),
        table(['帧','显式电容ΔU代数和 / pJ','显式电容|ΔU|合计 / pJ'],[
         [str(x['frame']),f(sum(c['delta_pJ'] for c in x['explicit_storage_caps'].values()),5),f(sum(abs(c['delta_pJ']) for c in x['explicit_storage_caps'].values()),5)] for x in r['frames']],[.12,.44,.44]),
        note('有限窗口筛查：末两帧E+变化≤0.1%，监测轨端点变化≤0.1 mV，显式电容|ΔU|≤每帧源净能量的0.1%。通过只说明这个重复片段的电气响应接近周期状态；未测长连0/1、整周期PRBS、热稳态或寿命。')))
    return out

def protection_pages(s):
    out=[page('保护问题：偏置低，不等于发光通路已切断',
      p('A原先没有实现DISABLE。B原DISABLE能把参考偏置拉低，但数据仍翻转，前馈电容仍连接数据节点和输出。电容位移电流及重新充电可以绕过“偏置已关闭”的直觉。'),
      p('新方案在LED阳极加入高边PMOS隔离，并在LED两端并联NMOS钳位。关断时切断LED阳极供电，并使两端电位靠近；实际先后需要由波形验证。B的参考保持工作，以避免补偿节点从零重新建立。参考始终工作会增加关断期间的静态功耗。'),
      p('DISABLE由测试平台给出；本轮实现的是独立关断执行电路，没有新增过温/过流检测器、故障锁存或安全控制协议。'),
      p('高边栅需要0/5 V控制，因此使用实际交叉耦合电平转换；没有用理想5 V逻辑开关代替。W=300 µm单PMOS第一次超出模型bin，失败日志保留；改成三只W=100 µm显式并联后，所有端区面积、周长和MOS应力分别计入。'),
      note('研究关断目标：20 ns内|I_cond|≤0.1 µA并保持，恢复目标≤1 µs。0–0.1 µA区间是I–V参考外推；nA级结果只称数值关断筛查，不能当作实测漏光、安全或量产保证。')),
      page('首版v2保护 · 可求解仍会失败',
        fig('micro-protection-v2','两只3.3 V控制MOS、四只6 V电平转换MOS、三只并联6 V高边PMOS与一只6 V跨LED钳位NMOS，共新增10 MOS。A/B核心与各自负载保持冻结。',151),
        p('这是首个可求解的v2保护电路，后续应力检查失败。DISABLE高：PMOS截止、钳位导通；DISABLE低：恢复供电。钳位与隔离并非理想同时切换，必须检查全部端压。')),
      page('从波形追到两条非预期电流路径',
        fig('micro-protection-physics','原v2的失败定位。A恢复供电时的电容位移电流与B稳定关断时的前馈注入是不同问题；阴极与OUT之间仍保留封装R/L，不能把它们混成一个电压节点。',164),
        p('关断只看LED导电电流，会遗漏位移电流及MOS体结注入。修改必须针对真实电流路径；仅推迟开通而不降低实际电压斜率，也不保证消除冲击。'))]
    return out

def revision_pages(s):
    return [page('A · 限制开通斜率，同时保留快速关断',
      fig('micro-protection-v3r-control','A-v3r实际控制连接。100 Ω为保护命令源的有限串联阻抗；新增电平转换把3.3 V逻辑转换到5 V高边栅域。图中MOS体端按实际网表标出。',153),
      p('v2恢复时，LED电容重新充电，瞬时封装电流约1.96 mA，而同一时刻LED导电电流只有约0.091 µA。OUT被推高到VH以上，输出PMOS体结正偏约0.511 V。问题来自位移电流冲击，不是目标100 µA导电电流本身。')),
      page('A · 用栅极RC减慢供电恢复',
      fig('micro-protection-v3r-power','RGATE=100 kΩ串入三只高边PMOS的共同栅极。恢复时经电阻缓慢放电开通；关断时XFASTOFF绕过电阻，把栅极拉回5 V关闭。',155),
      p('v3先加入慢开/快关，但在原理想保护命令源边界下，S40/S80都发生瞬态截断。v3r再把保护命令改为具有100 Ω源阻抗的实际节点，完整求解恢复；这是改变输入边界后重新验证，不是放宽收敛精度或掩盖截断。'),
      note('新A总31 MOS。100 Ω须由将来的控制接口设计兑现；有限源阻抗只在本轮条件下使完整求解通过，尚未证明数值刚性的唯一成因，也不能保证任意控制器和PVT都通过。')),
      page('B · 数据必须等发光通路建立后再进入',
      fig('micro-protection-v6r-input','B-v6r在保护开关以外增加READY节点和DATA输入阻尼。外部数据持续翻转；关断时内部DATA_SAFE被拉低。两方块多晶硅电阻用PDK模型实现，不把其阻值当成精确2 kΩ。',157),
      p('B原前馈电容仍把数据变化耦合到OUT。只关参考，关断期间仍有约5.628 µA导电峰值；加隔离和钳位后，LED_K仍可负冲到−0.307 V，引起NMOS体结正偏。因此关断时还要抑制内部的数据切换。')),
      page('B · READY与数据门控的真实晶体管',
      fig('micro-protection-v6r-logic','四MOS NAND加两MOS反相器产生DATA_SAFE=DATA AND READY。READY采用100 kΩ/1 pF开环延迟，DISABLE控制独立NMOS快速复位；图示为实际器件连接。',156),
      p('v4直接接收快速DATA边沿，新增NAND输出自身出现−0.358 V负冲，相关3.3 V MOS最大端压3.658 V。v5仅在DATA到逻辑栅前增加PDK电阻，一帧机制诊断中最大端压降到3.517 V。原有核心输入电阻保留，没有挪用。'),
      note('READY是RC延迟，不是检测供电已经稳定的power-good比较器。慢边沿还可能增加逻辑交越电流；新增门控的能耗必须实算。')),
      page('B · 快关不等于越快越好',
      fig('micro-protection-v6r-power','最终候选B-v6r使用W=4 µm快关PMOS，慢开电阻仍为100 kΩ；保护命令仍有100 Ω源阻抗。核心参考保持工作，避免关断后从零建立偏置。',155),
      p('v3/v4的W=20 µm快关管把高边栅极拉得过急，经栅漏耦合抬高LED阳极，造成高边PMOS体结正偏。v6只把快关管缩到W=4 µm；v6r再加入有限保护命令源。缩小的是快关上拉的充栅能力；高边PISO尺寸与其Cgd没有缩小。边沿减缓降低耦合冲击，同时仍须满足20 ns关断目标。'),
      note('B新增18 MOS，总39 MOS。隔离/钳位、慢开/快关、内部数据等待、输入阻尼承担不同功能，不能用一个“保护开关”理想符号替代全部代价。')),
      page('保留失败：哪些改动有效，哪些仍不够',
      table(['版本','观察到的问题','下一步针对性修改'],[
        ['v2 · A/B','可以关低导电电流，但A恢复体结0.511 V；B稳定关断LED_K约−0.307 V。','降低A恢复斜率；B还需抑制前馈数据注入。'],
        ['v3 · B','恢复OUT峰值由3.703降到约2.953 V，但关断阳极抬到约5.517 V。','抑制快关耦合；增加内部数据等待。'],
        ['v4 · B','高边体结约0.422 V；新NAND输出负冲−0.358 V。','分开处理高边快关和逻辑输入边沿。'],
        ['v5 · B','一帧诊断：逻辑应力通过，高边体结仍约0.422 V。','只缩小XFASTOFF，检验其收益与关断延迟。'],
        ['v6 · B','DC通过，但瞬态到0.743 µs截断，不能评价完整关断。','引入100 Ω实际控制源后重新跑完整矩阵。']],[.18,.44,.38]),
      note('“候选没有通过”不等于整个电流转向架构不可行。这里定位到的是具体保护连接、边沿与负载耦合；修改后的电路仍需接受同样的接收、能耗、端压和模型范围约束。'))]

def final_result_pages(s):
    out=[]
    rows=[]
    for route in ['A','B']:
        r=selected(s,route,'continuous_case')['result']; new=r['frames'][-1]; old=base(s,route)['result']['frames'][-1]
        dc=[next(x for x in s['rows'] if x['source_case']==path)['result'] for path in s['selections'][route]['dc_cases']]
        rows.extend([[route+' 原基线',f(old['energy_pJ_per_attempted_payload_bit']['positive'],6),f(old['first_frame_phase_receiver']['amplitude_uAeq'],3),f(old['first_frame_phase_receiver']['timing_UI'],6)],
                    [route+' 新保护',f(new['energy_pJ_per_attempted_payload_bit']['positive'],6),f(new['first_frame_phase_receiver']['amplitude_uAeq'],3),f(new['first_frame_phase_receiver']['timing_UI'],6)]])
        out.append(page(route+' · 新保护加入后，正常通信是否退化',
          table(['量','结果'],[
            ['网表 / 器件数',s['selections'][route]['variant']+' / '+str(r['MOS'])+' MOS'],
            ['DC低 / 高电流', ' / '.join(f(x['current_uA'],4) for x in dc)+' µA'],
            ['DC相对目标误差',' / '.join(f(x['DC_error_percent'],4) for x in dc)+' %'],
            ['全程导电电流最小 / 最大',' / '.join(f(x,4) for x in r['current_range_uA'])+' µA'],
            ['末帧E+ / E− / E_net',' / '.join(f(new['energy_pJ_per_attempted_payload_bit'][k],6) for k in ['positive','returned','net'])+' pJ/b'],
            ['末两帧E+变化',f(r['steady_screen']['energy_change_percent'],8)+' %'],
            ['末帧所监测轨端点最大变化',f(r['steady_screen']['max_monitored_rail_endpoint_delta_mV'],6)+' mV'],
            ['全程最大体结正偏',f(r['body_forward_V'],6)+' V；端压与体结筛查通过']],[.47,.53]),
          p('能耗取同一10.24 µs连续仿真的末帧并覆盖完整源端；接收使用首帧冻结相位。两级电流的目标和±1% DC门槛保持不变；DC精度不代表切换峰值也在±1%内。'),
          p(('A高态误差距±1%门槛只剩'+f(1-abs(dc[1]['DC_error_percent']),4)+'个百分点，是名义筛查边缘；还不能声明跨工艺、温度与供电的±1%电流精度。') if route=='A' else 'B的输入阻尼、READY与数据门控增大延迟及取能；必须与原无保护版本在同速率下比较，不能仅凭关断后电流低就判定更高效率。'),
          note('A高态电流因高边压降略低于基线。因此即使pJ/b略降，也不能把微小差值独立归因为效率提升。' if route=='A' else '正常运行的每位能耗同时包含输入与新增保护逻辑，不因这些器件承担安全控制功能就排除其消耗。这里的保护仍是研究执行电路，并无安全认证。')))
    out.insert(0,page('正常连续通信 · 修改前后的同条件比较',
      table(['路线','末帧E+ pJ/b','幅度 / µAeq','单侧时间 / UI'],rows,[.22,.26,.26,.26]),
      p('净速率均为1.6 Gb/s，MicroLED负载、光学极点与接收器相同；各自连续4帧。以上时间余量使用首帧相位，四帧没有重置电容或接收滤波状态。'),
      note('两路线通过本轮正常运行筛查后，仍不能推断在原先更高速度也通过。新增保护电容和逻辑需要重新扫描速率；本轮不以1.6 Gb/s结果宣布最高带宽。')))
    oldb=base(s,'B')['result']['frames'][-1];newb=selected(s,'B','continuous_case')['result']['frames'][-1]
    er=[]
    for name in ['VIN','VDD','VREF','VLED','VD0','VD1','VDISABLE']:
      a=oldb['source_energy_J'][name]['positive_J']*1e12/4096;b=newb['source_energy_J'][name]['positive_J']*1e12/4096
      er.append([name,f(a,6),f(b,6),f(b-a,6)])
    out.append(page('B · 新增能耗主要落在哪个端口',
      table(['源端','原基线E+','新保护E+','差值'],er,[.22,.26,.26,.26]),
      p('单位为pJ/尝试净位，取各自连续第四帧。VDD包含原缓冲与新增门控等逻辑供电；VD0为外部DATA命令端。电源边界一致，新增逻辑没有被放到统计范围之外。'),
      p('总增量约0.1591 pJ/b，其中VDD增加约0.1523、DATA端增加约0.0173，其余部分有所抵消。证据把主要负担定位到了逻辑/输入侧，而不是证明LED本身效率下降。'),
      note('这还不是逐MOS耗散分解。不能把全部增量归给交越电流或某一只管子；下一步先记录各级栅电荷与上下拉重叠电流，再在保持相同关断/接收门槛的前提下优化尺寸和阻尼。')))
    for route in ['A','B']:
        r=selected(s,route,'fault_case')['result'];q=r['shutdown'];rx=r['frames'][-1]['first_frame_phase_receiver'];rec=q['recovery_screen']
        out.append(page(route+' · 从关断到重新接收的量化结果',
          table(['量','开发序列结果'],[
            ['关断命令 / 释放命令','640 ns / 1280 ns；1 ns命令边沿'],
            ['最后超过0.1 µA的时刻',f(q['last_above_threshold_ns'],4)+' ns（相对关断命令）'],
            ['20 ns后最大|I_cond|',f(q['max_abs_current_uA'],7)+' µA；仅模型延拓诊断'],
            ['恢复接收的有限轨迹上界',f(rec['upper_bound_ns'],4)+' ns；之后持续'+f(rec['all_subsequent_observation_ns']/1000,3)+' µs满足采样余量'],
            ['最终完整帧幅度 / 时间',f(rx['amplitude_uAeq'],4)+' µAeq / '+f(rx['timing_UI'],6)+' UI'],
            ['全程最大体结正偏',f(r['body_forward_V'],6)+' V（筛查线0.3 V）'],
            ['20 ns后关断窗口E+平均功率',f(q['total_source_positive_power_during_settled_off_mW'],6)+' mW'],
            ['20 ns后关断窗口源端净功率',f(sum(q['average_source_power_during_settled_off_mW'].values()),6)+' mW']],[.49,.51]),
          p('功率取关断后20 ns至释放前的窗口；其中数据仍翻转、节点仍有储能变化，不是纯静态待机功耗。该窗口不承载正常有效数据，不能用其pJ/b宣称节能吞吐。'),
          p(('B在20 ns后窗口首个采样点，VAK仍约2.153 V，残流是继续衰减的电气尾段，不代表两端已经等电位。开发片段的关断电流余量仅'+f((0.1-q['max_abs_current_uA'])*1000,3)+' nA，时间距20 ns限值仅'+f(20-q['last_above_threshold_ns'],3)+' ns。即使名义通过，仍要优先检查R/C容差、温度、控制源阻抗和不同故障相位。') if route=='B' else 'A的低残流并不代表所有电流都已消失：数据仍驱动输出节点，跨LED电容和保护支路仍有充放电电流。'),
          note('恢复上界采用已知时钟、首帧训练相位及固定阈值，对释放后的样本逐个检查；不是CDR、帧同步或系统重新训练的实现时间。低电流/反向区没有实测校准，不能据此给出绝对漏光或激光安全结论。')))
    rows=[]
    for route in ['A','B']:
      for key,label in [('fault_case','开发 S40'),('half_step_case','半步长 S80'),('holdout_case','新留出8192')]:
        r=selected(s,route,key)['result'];q=r['shutdown'];rx=r['frames'][-1]['first_frame_phase_receiver']
        rows.append([route+' '+label,f(q['last_above_threshold_ns'],3),f(q['recovery_screen']['upper_bound_ns'],3),f(rx['timing_UI'],6),f(r['body_forward_V'],6)])
    out.append(page('冻结后确认：步长与新数据窗口',
      table(['案例','关断/ns','恢复/ns','时间/UI','体结/V'],rows,[.29,.16,.16,.20,.19]),
      p('S80把每线路UI的最大时间步长减半。新留出采用预声明PRBS15偏移8192，在电路与控制参数冻结后生成；没有用其结果继续调参。关断和恢复的时间定义与前页相同。'),
      p('确认覆盖完整故障瞬态、全部MOS端压、源能量和最终完整接收帧。正常电流模型域由独立DC与连续案例核对；故障低电流及反向区继续标为外推。保留原始网表、运行器快照、命令波形、原生数据和独立复算记录。'),
      note('这些确认提高了对当前确定性结果的信心，不等于噪声误码率、失配良率、任意异步故障相位或PVT通过。下一轮应把这些未建模因素逐项加入，而不是只增加同一序列的位数。')))
    return out

def waveform_pages():
    return [page('连续运行波形：能量变化与固定相位余量',
      fig('micro-continuous-comparison-energy','同净1.6 Gb/s，完整源端能量按每4096验证载荷位计；比较四帧中的变化，避免仅引用开始一帧的储能释放。',86),
      fig('micro-continuous-comparison-margin','连续波形只滤波一次；首帧相位冻结后逐帧检查单侧时间余量。0.37 UI为既定研究筛查门槛。',86),
      note('两图来自各自完整10.24 µs波形；并未证明热稳态或任意码型稳定。最终正常DC实际电流与能耗表必须一起读。')),
      page('A · 从关断全程看到恢复体结应力',
      fig('micro-protection-A-waveforms-overview','外部数据持续翻转，关断命令没有停码。比较原基线、首版保护和修订版的LED导电电流。',86),
      fig('micro-protection-A-waveforms-body','恢复局部窗口：观察OUT与VH之差，即输出PMOS漏端相对体端的正偏。全原生点计算峰值，展示曲线不代替峰值判据。',86),
      p('慢开把大幅瞬态充电分散到更长时间，降低输出体结注入；保护引入的电容与串联压降仍可能改变正常接收。')),
      page('A · 导电电流与位移电流必须区分',
      fig('micro-protection-A-waveforms-current','恢复窗口分别显示封装支路电流与200 fF·dVAK/dt；后者是原生非均匀网格的数值导数，不是独立实测电流。',86),
      fig('micro-protection-A-waveforms-gate','慢开/快关控制节点展示实际高边栅极的变化。相同DISABLE命令并不表示不同开关节点具有相同边沿。',86),
      note('光学代理由LED导电电流驱动，不能把所有电容脉冲当成发光电流；但位移电流仍会影响电源、封装和MOS应力。')),
      page('B · 关断时抑制内部前馈注入',
      fig('micro-protection-B-waveforms-overview','B原偏置关断与新增独立保护的全程对照；完整波形同时覆盖数据继续到来、稳定关断和释放后恢复。',86),
      fig('micro-protection-B-waveforms-ready','外部DATA仍在运行，READY及DATA_SAFE控制内部何时恢复数据。READY是开环RC，不是电压就绪检测器。',86),
      note('关断时间同时受高边栅充电、钳位、门控及残余电荷释放影响，不能只看EN逻辑何时翻转。')),
      page('B · 把关断速度与过冲一起优化',
      fig('micro-protection-B-waveforms-assert','关断局部窗口：快关管缩小后，阳极抬升与高边体结正偏降低；代价是必须重新验证20 ns关断限值。',86),
      fig('micro-protection-B-waveforms-recovery','恢复窗口对比各版本OUT；门控时序见前页。恢复时间按冻结相位下的接收幅度与时间余量判定，两态DC电流另行校准。',86),
      note('最终候选的开发片段关断约17 ns，距20 ns门槛仅约3 ns；PVT、控制接口阻抗和不同故障相位可能消耗这段余量，不能把名义通过写成充裕。')),
      page('B · 关断尾段为什么仍值得优先研究',
      fig('micro-protection-B-offtail-current','20 ns处约89.10 nA，比100 nA门槛低10.90 nA。0.1 µA以下为未校准I–V延拓，曲线拐点不代表实测特性。',86),
      fig('micro-protection-B-offtail-voltage','同一时刻LED_A约4.020 V、LED_K约1.868 V；钳位NMOS的有效VGS约1.432 V，并不是外部命令的3.3 V。',86),
      p('源端电位抬高且体端接地，VSB也约1.868 V。体效应与栅极驱动余量是下一步检查方向；本轮没有导出VTH或单项隔离证明，因此不把体效应写成唯一已确认原因。'),
      p('下一轮先导出实际VTH、钳位沟道/体结电流与PISO电流，区分夹钳能力和高边尾流；再分别比较钳位栅驱动电压与器件宽度。加宽改变导通能力，并不直接提高栅驱动电压，还可能增大注入和能耗；任何更高栅压都须重新检查端压、交叠与完整接收。'))]

def source_impedance_page():
    rows=[]
    for route in ['A','B']:
      d=read('micro-source-impedance-'+route+'.json');m=d['metrics'];a=m['entire_common_prefix'];b=m['outside_control_edge_windows']
      rows.append([route,f(d['common_end_s']*1e6,6),f(a['iled_cond']['max_abs_difference']*1e6,5),f(b['iled_cond']['max_abs_difference']*1e6,5),f(b['out']['max_abs_difference']*1e3,5)])
    return page('100 Ω控制源：改变了什么，没有证明什么',
      p('原理想保护命令节点直接驱动多只MOS栅极，反馈电荷会被理想源瞬间吸收。新增100 Ω以后，实际DISABLE节点有有限变化，命令源端能量也按电阻前的节点统计。这是输入电路边界修改，不是仿真精度放松。'),
      table(['路线','旧可用前缀/µs','全前缀max ΔI/µA','边沿外max ΔI/µA','边沿外max ΔOUT/mV'],rows,[.10,.21,.23,.23,.23]),
      p('只在旧仿真真正产生的共同时间范围内比较：把完整新波形插值到旧原生采样时刻。另排除关断/释放边沿各±25 ns，区分控制瞬态和其余正常响应。没有补造旧截断之后的波形，也没有把旧运行升级成成功。B旧前缀尚未到1.28 µs释放时刻，因此这里不支持旧、新恢复过程一致的结论。'),
      note('共同前缀相近支持“有限源改动没有大幅改变已有正常响应”的判断，不能证明数值失败只有一个原因，更不能替代新电路全程、半步长与留出检查。两个保护命令仍由理想PWL产生，真正控制器的PAD/ESD与输出阻抗范围待验证。'))

def micro_pages():
    s=data()
    return continuous_pages(s)+protection_pages(s)+revision_pages(s)+[source_impedance_page()]+final_result_pages(s)+waveform_pages()
