"""Render frozen experiment evidence, not manually entered performance claims."""
from content import ROOT,EV,read,page,p,h,note,table,fig
import json

LABEL={'single-phy4':'单级 + 4/8 µm输入','single-phy12':'单级 + 12/24 µm输入','single-phy4-r25k':'单级 + 4/8 µm + 25 kΩ','double-phy4':'双级 + 4/8 µm输入'}
def f(x,d=3):return f'{x:.{d}f}'
def nominal(r):return r['config']['steps_per_UI']==40 and not r['config']['holdout']
def vcsel_pages():
    s=read('vcsel-interface-summary.json')
    rows=s['rows']
    out=[page('VCSEL · 把有限驱动能力接回电路',
        fig('vcsel-interface-circuit','新增上游两只CMOS反相器，共4只MOS；后面仍保留每路50 Ω外部源电阻，所画单级候选另有150 Ω内部阻尼。图中DI/DBI与GP/GN为实际网表节点。',153),
        p('单级核心69 MOS，加上本轮4只上游MOS后共73 MOS；旧双级核心73 MOS加同样上游后共77 MOS。器件总数、尺寸和供电位置都要写清，不能只用“少一级”代表系统更省电。'))]
    for rate in [6.4,8.8]:
        rr=[r for r in rows if nominal(r) and r['config']['net_Gbps']==rate]
        out.append(page(f'VCSEL · 同净{rate:g} Gb/s下的完整边界',
          table(['改动','幅度 µAeq','时间 UI','E+ pJ/b','联合'],[
            [LABEL.get(r['candidate'],r['candidate']),f(r['full_receiver']['worst_signed_margin_uAeq']),f(r['full_receiver']['one_sided_margin_UI'],5),f(r['energy_pJ']['positive'],5),'通过' if r['combined_screen_pass'] else '域外诊断' if not r['observed']['within_calibrated_electrical_and_optical_current_range'] else '失败'] for r in rr],[.34,.17,.17,.18,.14]),
          p('每行都包含VLASER、VDD、VREF、VSET、VREGSET、两路命令和新增VPHY共8个端口。命令仍为理想PWL；其送入MOS栅极的能量已计入，生成这些命令的更上游逻辑/时钟尚未建模。'),
          p('每个候选先验证3/7 mA两态DC与所有MOS端压。接收幅度/时间、模型域和应力必须同时满足；即使零观察错，余量不够仍列失败。'),
          note('“域外诊断”表示电流越过2–7.5 mA参考域，其光学/RX数值不能作为可信链路性能。旧双级保留50 Ω内部阻尼，单级为150 Ω，因此旧架构对照不是只改变级数的因果试验。失败点的pJ/b不能代表有效吞吐收益。')))
    out.append(page('VCSEL · 输入级的能量不能藏在边界外',
       table(['候选 / 净Gb/s','输入部分E+','其余部分E+','总E+'],[
        [LABEL.get(r['candidate'],r['candidate'])+' / '+f(r['config']['net_Gbps'],1),f(r['interface_observed']['interface_source_energy_pJ_per_payload_bit']['positive_J'],5),f(r['energy_pJ']['positive']-r['interface_observed']['interface_source_energy_pJ_per_payload_bit']['positive_J'],5),f(r['energy_pJ']['positive'],5)]
        for r in rows if nominal(r)],[.43,.19,.19,.19]),
       p('单位均为pJ/尝试净位。输入部分=VPHY+两路命令端；其余部分包含激光器偏置/调制、既有缓冲和参考/供轨。这里没有把输入级转移到系统外后再宣称效率提升。'),
       note('E+=正供能；表中未扣返能。净能量另见汇总JSON。瞬态从已求得DC工作点开始，不含从零上电及首次储能充电。源端供能不等于芯片热耗散，也不包括未建模的主机SerDes、时钟、完整接收器和外部参考IC损耗。')))
    out.append(page('VCSEL · 从输入边沿到接收余量',
       fig('vcsel-interface-waveforms','同一8.8 Gb/s片段，未平移波形。红虚线分别为7.5 mA模型上界与62.5 µAeq判决阈值。应同时看幅度建立与脉宽；延后采样无法恢复已压缩的脉冲。',145),
       p('弱输入级DI上升沿比一个线路UI更长，孤立比特未充分建立就开始反向变化，后级换流不完整。加宽恢复的是实际充放电能力，不只是调整整体延迟。')))
    edges=read('vcsel-interface-edges.json')['rows']
    er=[]
    for x in edges:
        if x['candidate'] not in ['single-phy4','single-phy12','single-phy4-r25k']:continue
        nd=next(n for n in x['nodes'] if n['node']=='v(xdrv.di)')
        er.append([LABEL[x['candidate']]+' / '+f(x['net_Gbps'],1),f(nd['DC_at_data1_V'],3),f(nd['edges']['data_rise']['edge_ps_quantiles']['median'],2),f(nd['edges']['data_fall']['edge_ps_quantiles']['median'],2)])
    out.append(page('VCSEL · 单项修改如何改变充放电',
       table(['候选 / 净Gb/s','DI高电平 / V','上升 / ps','下降 / ps'],er,[.43,.19,.19,.19]),
       p('边沿按各自两态DC端点定义10–90%，只统计验证段中前后至少连续3位的转换；这里列中位数，不用于重新选择接收相位。弱输入DI高电平约2.446 V，下拉分流约0.978 mA：50+150 Ω串联电阻压降约0.196 V，有限上拉MOS另有约0.658 V压降，使d_src从3.3 V降至2.642 V。'),
       p('加宽使上、下沿都缩短，但命令端栅负载也增加。25 kΩ降低静态分流、恢复较高电平，却减弱向地下拉并改变后级翻转过程；下降沿反而变慢。这是为何静态功率最小的候选不一定适合最高速率。'),
       note('25 kΩ在6.4 Gb/s虽通过，时间仅比0.37 UI门槛多约0.51 ps；8.8 Gb/s失败。当前将12/24 µm冻结为本轮复核对象，不等于预选最终芯片架构。')))
    confirm=[r for r in rows if r['candidate']=='single-phy12' and r['config']['net_Gbps']==8.8]
    out.append(page('VCSEL · 冻结后复核与仍未闭合的边界',
       table(['数据与步长','幅度 µAeq','时间 UI','E+ pJ/b','联合'],[
        [('新留出8192' if r['config']['holdout'] else '开发片段')+' / S'+str(r['config']['steps_per_UI']),f(r['full_receiver']['worst_signed_margin_uAeq'],4),f(r['full_receiver']['one_sided_margin_UI'],6),f(r['energy_pJ']['positive'],6),'通过' if r['combined_screen_pass'] else '失败'] for r in confirm],[.31,.19,.19,.19,.12]),
       p('候选先冻结为Wn/Wp=12/24 µm、L=0.28 µm、内部150 Ω和2.5 kΩ下拉，再执行最大时间步长由UI/40减为UI/80及偏移8192的新片段。应力筛查仍包括新增4只输入MOS，不能只检查69 MOS核心。'),
       p('物理断开上游的DC诊断中，DI=DBI=0 V、GP=GN≈3.10016 V，光源电流仍约3.98068 mA。输入下拉定义默认逻辑，却没有关光；独立VCSEL关断需要控制偏置和调制支路，再验证掉电回灌、先后上电与残余发光。这次断开实验不等于上游掉电试验。'),
       note('新输入器件没有新版图/PEX、PVT/失配和实际PAD/ESD验证。8.8 Gb/s通过只对应列出的条件；32 Gb/s目标仍未实现，VCSEL连续电热和独立保护也未在本轮取得资格。')))
    return out

def result_pages():
    from micro_content import micro_pages,stage_summary
    return [stage_summary()]+vcsel_pages()+micro_pages()
