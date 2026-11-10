"""Result pages generated from the native simulation evidence, with fixed scope."""
from content import page,p,h,note,tab,fig,j

def make_results(micro,vc,caps,micro_table):
    def r(x):return x['full_receiver']
    def energy(x):return x['energy_pJ_per_attempted_payload_bit']['positive']
    def boundary(group):
        good=[x for x in group if x['combined_research_screen_pass']]
        if not good:return '所测网格未通过'
        last=max(good,key=lambda x:x['net_Gbps'])
        fail=sorted([x['net_Gbps'] for x in group if x['net_Gbps']>last['net_Gbps'] and not x['combined_research_screen_pass']])
        return f'最高已通过 {last["net_Gbps"]:g} Gb/s'+(f'；下一已测失效 {fail[0]:g} Gb/s' if fail else '；尚未测到更高失效点')
    bounds='。'.join(a+' '+boundary([x for x in micro if x['route']==a]) for a in 'ABC')+'。'
    b08=next(x for x in micro if x['route']=='B' and x['net_Gbps']==.8)
    rows_all=j('evidence/blue-emitter-speed-review-20261110/speed-sweep-all.json')['rows']
    load=next((x for x in rows_all if x['family']=='MicroLED' and x['route']=='B' and x['net_Gbps']==.4 and abs(x['capacitance_fF']-800)<1e-6 and x['steps_per_symbol']==40),None)
    loadtext='尚未完成低速 800 fF 负载点，不能由现有扫描定义 Cmax。'
    if load:
        rx=r(load)
        loadtext=f'在净 0.4 Gb/s 下，B 的 200 fF 已通过；改为 800 fF 后，错误 {rx["errors"]:,}/4,096，幅度 {rx["worst_signed_margin_uAeq"]:.2f} µAeq，单侧时间 {rx["one_sided_margin_bit_UI"]:.3f} bit UI，综合筛查'+('通过' if load['combined_research_screen_pass'] else '失败')+'。这两个离散点定义测试边界，尚未确定连续的最大电容。'
    energies=[]
    for a in 'ABC':
        x=next(q for q in micro if q['route']==a and q['net_Gbps']==.4)
        energies.append([a,f'{energy(x):.3f}',f'{x["mean_source_positive_power_mW"]:.3f}',str(r(x)['errors']),'通过' if x['combined_research_screen_pass'] else '失败'])
    vctable=[]
    for x in vc:
        rx=r(x)
        vctable.append([f'{x["net_Gbps"]:g}',f'{rx["errors"]:,}',f'{rx["worst_signed_margin_uAeq"]:.2f}',f'{rx["one_sided_margin_ps"]:.2f}',f'{energy(x):.3f}','通过' if x['combined_research_screen_pass'] else '失败'])
    return [
        page('08 MicroLED 从低速到目标点',
             tab(['净 Gb/s','A 错误位','B 错误位','C 错误位','A／B／C 综合'],micro_table,[.14,.16,.16,.16,.38]),
             p('每点验证 4,096 位；负载 200 fF，光极点 200 ps，RX 1 GHz，MOS 为 TT 27°C。未测组合不补算，不按曲线插值。'),
             fig('assets/microled-rate.png','原生晶体管扫速与接收分析。连线仅辅助阅读。幅度 7.5 µAeq 与时间 0.37 bit UI 同时达到才有余量通过；应力另检。',83),
             p(bounds),
             note(f'B 在净 0.8 Gb/s 虽为零错，最小幅度仅 {r(b08)["worst_signed_margin_uAeq"]:.3f} µAeq，时间 {r(b08)["one_sided_margin_bit_UI"]:.3f} bit UI。用“有没有错误”单独作选择会遗漏明显的脆弱工作点。'),
             p('净 3.2 Gb/s 下 A 本轮为 846 错；旧报告为 844。原生波形相同，差异来自统一后的训练延迟窗与选相规则，并非电路性能变化。')),
        page('波形如何解释“零错但余量不足”',
             fig('assets/rate-waveforms.png','由本轮原生导通电流通过冻结光／RX 代理生成。每图围绕其最差幅度采样点取 8 位，横轴按接收采样位置对齐；顶部数字为发送位，圆点为实际判决样本，空心圆圈出最差幅度点。仅展示抽样，判定使用完整帧。',124),
             p('从左到右提升速率，上一位的电荷和光响应留下更长的相对尾迹；输出尚未充分到达预期电平，就进入下一次判决。四个图的验证位计数都为零错，但右侧最差样本已经明显靠近阈值。'),
             p('幅度余量是样本离其正确判决边界的最短距离；时间余量是采样点到相邻错误判决区的最短时间。实际噪声、供电扰动或抖动都可能消耗这些余量，因此需要同时保留两项预算。图中的局部片段用于解释最差幅度，最差时间可能出现在另一位。'),
             p('[绘图抽样 CSV](../../../evidence/blue-emitter-speed-review-20261110/waveform-excerpt.csv) · [完整帧分析](../../../evidence/blue-emitter-speed-review-20261110/speed-sweep-all.json)')),
        page('09 负载极限与当前失败机制',
             tab(['B 的 C / fF','净速率 Gb/s','错误位／4,096','幅度 µAeq'],[[f'{x["capacitance_fF"]:g}','3.2',str(r(x)['errors']),f'{r(x)["worst_signed_margin_uAeq"]:.2f}'] for x in caps],[.23,.23,.28,.26]),
             p('上表只改变并联电容；光极点 200 ps、RX 1 GHz、目标电流、封装 R/L 与原电路保持不变。即使设置理想 0 fF，仍有错误。单纯缩小结电容无法消除目前全部瓶颈。'),
             note(loadtext),
             h('“最大负载”是多维条件'),
             p('电容只是其中一个变量。输出需提供导电电流和充电电流：I端口 = I导电 + C × d(VA−VK)/dt。200 fF 跨越约 0.407 V 需约 81 fC；若在 135 ps 内完成，净充放电电流约 0.60 mA，已大于原 25／100 µA 静态目标。该估算用于找瞬态预算，不能替代实际电路。'),
             h('C 还有独立于接收的译码应力问题'),
             p('C 在净 0.2 Gb/s 可通过接收余量，但译码内部仍有体结正偏。NOR2 的 P_OR 相对 VDD 正冲约 0.858 V，对应 XORPA 漏结／XORPB 源结；N_OR 负冲约 −0.604 V。固定 20 ps 边沿下，降速没有消除。先导出内部波形和体结电流，再验证耦合、节点放电与输入阻尼；现有峰值无法确定持续时间或唯一原因。'),
             p('R、L、电流、温度未被本轮全面扫描，因此不发布通用 Cmax。体结 0.3 V 是项目研究筛查线，尚非器件已发生击穿的证明。[译码应力审计](stage-audit.html)')),
        page('10 VCSEL 的可用范围与十倍目标',
             tab(['净 Gb/s','错误位','幅度 µAeq','时间 ps','E+ pJ/尝试位','综合'],vctable,[.13,.14,.18,.15,.24,.16]),
             p('冻结 r10，TT 25°C，150 fF、0.5 Ω／0.2 nH、850 nm 光响应、5 GHz RX、20 ps 输入边沿。幅度是按该模型 3／7 mA 光功率映射的等效量，不能和 MicroLED 的绝对光功率排序。'),
             fig('assets/vcsel-rate.png','本轮逐速率仿真和已验证锚点重分析。实际门极与接收错误分别统计，低速可用点不外推为 32 Gb/s 通过。',78),
             p(boundary(vc)+'。净 32 Gb/s 对应 37 GBd NRZ，UI 仅 27.03 ps。现有预驱动在该条件下丢失短脉冲，门极极性错误为 1,622 位，完整接收为 1,462 位。'),
             p('旧理想门极旁路使导电电流零错，但仅约 1.03 µAeq／1.68 ps 余量，电流达到 1.696～9.548 mA，dummy 管端压 3.868 V 超过 3.63 V 研究筛查线。需同时改预驱动、换流与负载。[公开 40 Gb/s NRZ 全链路](https://ieeexplore.ieee.org/document/8527238/)支持长期目标有实物先例，当前网表仍需逐档迭代。')),
        page('11 能耗、错误与技术主线选择',
             h('相同净 0.4 Gb/s 的实际实现'),
             tab(['路线','E+ pJ/尝试位','平均源功率 mW','错误位','综合'],energies,[.13,.25,.26,.13,.23]),
             p('能量按当前七个电源／激励端口的正向交付积分，完整 4,736 位帧除以 4,096 payload。另存扣除回灌后的 E净。未包含实际输入 PHY／时钟和光接收器内部功耗。上电过程不在本次数据帧窗口内。'),
             fig('assets/energy-rate.png','同一电路提高尝试速率会摊薄静态偏置，故 pJ/尝试位可下降。叉号标记综合筛查失败的工作点；这些点不参与有效通信能效排名。',84),
             p('当前冻结条件下 A 在 0.4 Gb/s 的源端能量低于 B，并有较高的已验证速度边界。因此下一轮以 A 作实际性能基线更有依据，同时用 B 的门极／换流改版验证低寄生条件下的潜力；C 保留多电平探索。先前“B 优先”应限于改善机理实验，不能表达成当前成熟度领先。'),
             note('正式选择要先满足相同净吞吐、误码／余量、应力和模型可信度，再比较完整链路 pJ/有效位。零错短帧与失败帧的低 pJ 都不足以单独确定最终架构。'))
    ]
