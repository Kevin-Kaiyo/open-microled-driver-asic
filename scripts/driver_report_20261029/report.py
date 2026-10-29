#!/usr/bin/env python3
"""Render a comparison report from immutable experiment receipts, without changing results."""
from pathlib import Path
import hashlib,json,re,os
import markdown,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/vcsel-reference-microled-dynamics-20261029'
EV=ROOT/'evidence/vcsel-robustness-20261029'
FIG=DOC/'figures'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def table(head,rows):return '\n'.join(['| '+' | '.join(head)+' |','|'+'|'.join(['---']*len(head))+'|']+['| '+' | '.join(map(str,x))+' |' for x in rows])+'\n'
def figure(name,caption):return f'<figure><a href="figures/{name}"><img src="figures/{name}" alt="{caption}"></a><figcaption>{caption}</figcaption></figure>\n'
def save(fig,name):
 fig.tight_layout()
 for ext in ['png','svg']:fig.savefig(FIG/(name+'.'+ext),dpi=150,metadata={'Date':'2026-10-29'})
 plt.close(fig)
def case(s,name):
 name,label=name.split('#',1) if '#' in name else (name,'fixed-v3-r2')
 rows=[x for x in s['cases'] if x['case']==name and x['analysis_label']==label]
 assert len(rows)==1,(name,len(rows));return rows[0]
def dc(s,name):return next(x for x in s['dc'] if x['case']==name)
def selection():return read(EV/'report-cases.json')
def selected(s,v,c):return case(s,selection()['frames'][c][v])
def expframes(s):return [selected(s,v,c) for c in ['TT','SS','FF'] for v in ['baseline','reference','regulated']]

def conclusions(s):
 rev=selection()['revision'];r=[selected(s,'regulated',c) for c in ['TT','SS','FF']];b=[selected(s,'baseline',c) for c in ['TT','SS','FF']]
 assert all(x['passed'] for x in r),'Do not announce closure for a failed main candidate'
 ts=' / '.join(f"{x['time_margin_ps']:.2f}" for x in r);es=' / '.join(f"{x['energy']['positive_pJ_per_offered_payload_bit']:.3f}" for x in r)
 delta=(r[0]['energy']['positive_pJ_per_offered_payload_bit']/b[0]['energy']['positive_pJ_per_offered_payload_bit']-1)*100
 return f'''**本轮用 {rev} 原理图候选改善了 VCSEL 慢热电流不足与正常发送时的快冷过冲，并保留中间失败；产品级供电和光链路验证仍未完成。**

- 建立后的单帧净速率固定为 3.2 Gb/s，同一负载与接收规则下，TT/SS/FF 均为 0/4096 观察错误，单侧时间余量约 **{ts} ps**。SS 从接收失败恢复；FF 正常发送最大端压从约 **{b[2]['stress_max_V']:.3f} V 降到 {r[2]['stress_max_V']:.3f} V**。
- 这有明确代价：三个 1.28 µs 实验帧约 **{es} pJ/尝试净位**，TT 相比旧电路增加约 {delta:.1f}%。它包含已建模供电与数据端口，尚非完整光链路能效；电容储能、启动等待另外列出。**快冷 20 ns 上电仍超出 3.63 V 筛查线约 0.879 mV**，100 ns 上电也仅剩约 2.147 mV，供电可靠性尚未闭合。
- MicroLED 的公开数据确有 GHz 级幅频，但包含测量链且缺少相位/阻抗。它修正了旧瓶颈解释，**没有被擅自换算成新的瞬态接收成绩**。继续保留 A/B/C 与 VCSEL 候选，暂不预选路线。
'''

def baseline(s):
 old=read(EV/'audit-baseline-dc.json')['rows'];rows=[]
 for x in old:rows.append([x['corner'],f"{x['IREF_uA']:.2f}",f"{x['IBIAS_low_mA']:.4f}",f"{x['IBIAS_high_mA']+x['IMOD_high_mA']:.4f}",f"{x['tail_ratio_high']:.3f}"])
 text=table(['旧组合条件','IREF / µA','低档 / mA','高档 / mA','调制支路 / IREF'],rows)
 text+='\nTT=typical/25°C/3.3 V；SS=slow/125°C/2.97 V；FF=fast/−40°C/3.63 V。VCSEL 的静态温度模型未随此变化。\n\n'
 labels={'TT':'全部典型','MOSss':'仅 MOS 慢角','TEMPhot':'仅 125°C','Vlow':'仅供电 2.97 V','SS':'慢角 + 热 + 低压'}
 text+=table(['拆分实验（其余典型）','高档电流 / mA'],[[label,f"{dc(s,'baseline-'+n+'-1')['current_mA']:.4f}"] for n,label in labels.items()])
 peak=read(EV/'audit-ff-peak.json')
 text+=f"\n快冷峰值出现在 XDUMP 的漏—体压差：{peak['peak_dummy_V']:.4f} V。该时刻从原模型重建的本地激光轨约 {peak['laser_rail_from_cathode_and_IV_V']:.4f} V，dummy 高出轨约 {peak['dummy_above_reconstructed_laser_rail_V']*1000:.2f} mV，且 GN 正在上升。节点证据说明过冲发生在局部切换节点，与开关耦合机制一致；它排除了整条电源轨出现同幅振铃，但尚未分离栅漏耦合、沟道电荷与支路换流的各自贡献。重建方法和相互核对见[独立节点审计](../../../evidence/vcsel-robustness-20261029/audit-ff-peak.json)。\n"
 return text

def circuit(s):
 text='新候选共 **73 个源网表 MOS 实例**：基础与调制电流各有实际 MOS 反馈放大器，激光轨和缓冲轨各有实际 PMOS 稳压电路。图中的并联组完整对应源网表，不代表已完成版图指状结构。\n\n'
 text+=figure('servo-current-core.svg','图 1｜感测电阻反馈设定 3 mA 基流与 4 mA 调制尾流；高速数据仍由转向管选择通路。')
 text+='工作过程可以按三步理解。先用 OTA-B（把电压误差转为控制信号的跨导放大器）调节基础支路 MOS，使其源极感测电压逼近外部 VSET=0.15 V，得到 `IBIAS≈0.15/50=3 mA`。再用 OTA-T 产生 `IMOD≈0.15/37.5=4 mA`。数据为低时，调制电流流向 dummy（虚设负载支路），VCSEL 仍保有约 3 mA 偏置；数据为高时，调制电流转入 VCSEL，与基础电流叠加成约 7 mA。参考控制环主要处理较慢的误差，高速数据通过转向管切换，不要求反馈放大器逐 bit 重新建立电流。\n\n'
 text+='主要修改按原因展开：单级 OTA 的输出摆幅不足，改为带 Miller 补偿的两级结构；尾电流管 L 从 1 µm 改为 0.28 µm，转向管每只 W 从 20 µm 改为 40 µm，降低慢热时的压降。两条稳压输出目标为 3.10 V；慢热低输入电压时允许进入 dropout，实际输出由调整管压降决定。该值全角落相同，不逐角校准。\n\n'
 rows=[]
 for rev,desc in [(3,'单级 OTA'),(4,'两级 OTA'),(5,'短沟道尾管'),(6,'加宽转向管')]:
  rows.append([f'r{rev}：{desc}',f"{dc(s,f'reference-SS-1-r{rev}')['current_mA']:.4f}",f"{dc(s,f'regulated-SS-1-r{rev}')['current_mA']:.4f}"])
 text+=table(['保留的迭代','仅参考反馈：SS 高档 mA','再加稳压：SS 高档 mA'],rows)
 text+='\n以上是不同迭代的机制证据，不把每一步都称为可交付设计；r6 在完整帧和启动验证中失败，保留为对照，不能把每轮修改都称为完成设计。\n\n'
 text+=figure('ota-b.svg','图 2｜基础偏置 OTA 的实际器件连接。PMOS 差分输入、NMOS 镜像负载及第二级调节 BCTRL；5 pF 为明确的补偿假设。')
 text+='调制、激光稳压与缓冲稳压放大器的完整展开分别见 [OTA-T](figures/ota-t.svg)、[OTA-L](figures/ota-l.svg)、[OTA-D](figures/ota-d.svg)。\n\n'
 text+=figure('regulated-rails.svg','图 3｜两条 PMOS 调整支路与 85 kΩ/10 kΩ 反馈分压。r10 激光轨采用外部 10 nF/0.1 Ω，缓冲轨为 1 nF/0.1 Ω；基线未计输出电容 ESL，另做敏感性控制。这些无源器件还没有片上面积与封装实现证据。')
 text+='稳压目标按 `VOUT≈VREGSET×(1+85k/10k)` 得到：VREGSET=0.326316 V 对应约 3.10 V。r10 的激光/缓冲 Miller 支路均串联 100 kΩ，补偿电容均为 30 pF；两输出各接 5 kΩ 最小负载。它沿用 r8 的参考伺服，针对供电跌落恢复另增大激光轨外部去耦并调整补偿；第 4 节保留失败和单因素过程。两级放大器与 PMOS 调整管引入多个极点，串联电阻会改变补偿零点；不能只把电容做大便认定稳定。大信号建立还受 `I=C·dV/dt` 限制，因此上一版 100 pF 会让控制栅充电变慢。具体稳定性和启动结果见第 4 节。\n\n'
 text+=figure('input-network.svg','图 4｜输入衰减网络的完整连接；不改变理想输入源幅度，代价是持续的电阻耗能。')
 text+='两条两级 CMOS 缓冲的八个 MOS 见[缓冲器展开](figures/buffer-detail.svg)。所有供电、数据和参考端口进入能量统计。\n'
 return text

def compare(s):
 frames=expframes(s);names={'baseline':'旧电路','reference':'参考反馈','regulated':'参考 + 稳压'};rows=[]
 for x in frames:
  rows.append([{'typical':'TT','ss':'SS','ff':'FF'}[x['corner']]+'/'+names[x['variant']],x['errors'],f"{x['time_margin_ps']:.2f}",f"{x['optical_margin_min_mW']:.3f} ({x['min_signed_margin_uAeq']:.2f})",f"{x['energy']['positive_pJ_per_offered_payload_bit']:.4f}",f"{x['stress_max_V']:.4f}",'条件性通过' if x['passed'] else '未通过'])
 text=table(['组合条件/设计','错误 /4096','单侧时间 ps','幅度 mW (µAeq)','pJ/尝试净位','最大端压 V','联合筛查'],rows)
 text+='\n失败点的 pJ/bit 只表示尝试发送的能量，不能当作有效交付能效；本轮没有把旧慢热低电流所带来的低耗电称为优势。表中的稳态帧从工作点开始；后面的启动后码流是独立检查。\n\n'
 fig,axs=plt.subplots(2,3,figsize=(11.6,7),sharex=True,sharey=True)
 for j,c in enumerate(['TT','SS','FF']):
  for i,v in enumerate(['baseline','regulated']):
   x=selected(s,v,c);q=np.load(ROOT/x['plot_data']);ax=axs[i,j]
   for trace in q['eye_rx_power_W']:ax.plot(q['eye_phase_UI'],trace*1e3,color=['#a7754e','#287c83'][i],alpha=.13,lw=.6)
   ax.axhline(2.55083655,color='#68797c',ls='--',lw=.8);ax.axvline(0,color='#283f48',lw=.8)
   ax.set(title=f"{c} / {names[v]}\n{x['time_margin_ps']:.1f} ps；{x['errors']} 错误",ylim=(.75,5.3),xlabel='相对冻结采样点 / UI',ylabel='RX 功率代理 / mW');ax.grid(alpha=.12)
 save(fig,'paired-eyes');text+=figure('paired-eyes.png','图 5｜上下采用相同纵轴。每图显示前 160 个验证位，指标使用全部 4096 位；快冷旧眼图有开口仍因端压和模型越域失败。')
 return text

def energy(s):
 fig,ax=plt.subplots(figsize=(11,4.5));labels=[];allrows=[]
 for c in ['TT','SS','FF']:
  for v in ['baseline','regulated']:
   x=selected(s,v,c);labels.append(c+(' 旧' if v=='baseline' else ' 改')+('\n未通过' if not x['passed'] else ''));allrows.append(x)
 ports=['VLASER','VDD','VREF','VD','VDB','VSET','VREGSET'];bottom=np.zeros(6)
 colors=['#267b82','#4b73a3','#b57840','#a17f98','#c2a7ba','#809c65','#a6b995']
 for port,color in zip(ports,colors):
  vals=np.array([x['ports'].get(port,{}).get('positive_J',0)/4096*1e12 for x in allrows]);ax.bar(labels,vals,bottom=bottom,label=port,color=color);bottom+=vals
 for i,x in enumerate(bottom):ax.text(i,x+.15,f'{x:.3f}',ha='center',fontsize=10)
 ax.set(ylabel='正向 pJ / 尝试 payload bit',ylim=(0,max(bottom)*1.18));ax.legend(ncol=4,loc='upper left');ax.grid(axis='y',alpha=.15);save(fig,'energy-ports')
 text=figure('energy-ports.png','图 6｜输入端口 VD/VDB 的电阻衰减功耗清楚保留；VSET/VREGSET 输入端功率较小，不代表外部基准内部免费。')
 rows=[]
 for c in ['TT','SS','FF']:
  a=selected(s,'baseline',c);b=selected(s,'regulated',c);ea=a['energy']['positive_pJ_per_offered_payload_bit'];eb=b['energy']['positive_pJ_per_offered_payload_bit']
  rows.append([c,f'{ea:.4f}',f'{eb:.4f}',f'{eb-ea:+.4f}',f'{(eb/ea-1)*100:+.1f}%'])
 text+=table(['条件','修改前 pJ/尝试净位','修改后 pJ/尝试净位','差值','相对变化'],rows)
 text+='\n### 电容不是免费电源\n\n激光轨外部 10 nF 在 3.10 V 时储能约 `½CV²=48.05 nJ`，与一个实验帧的源端能量同量级。判断外部电源消耗时必须同时看初末状态：`ΔU=½C(V末²−V初²)`，负值表示本帧用掉了一部分先前储能。\n\n'
 er=[]
 labels=dict(selection().get('control_labels',{}));labels.update({f'frame-{c}-r10':c+' / 标称数据帧' for c in ['TT','SS','FF']});labels.update({f'continuous-{c}-r10-restored-frame':c+' / 上电后数据帧' for c in ['TT','SS','FF']})
 for path in selection().get('capacitor_audits',[]):
  for x in read(EV/path)['rows']:
   ep=x['energy_port_comparison'];er.append([labels.get(x['case'],x['case']),f"{ep['positive_pJ_per_offered_payload_bit']:.5f}",f"{ep['returned_J']/4096*1e12:.5f}",f"{x['delta_U_pJ_per_offered_payload_bit']:+.5f}"])
 if er:text+=table(['原生波形独立积分','正向源能量 pJ/位','回送 pJ/位','所列显式电容 ΔU pJ/位'],er)
 text+='\n此表只列供电与补偿显式电容，不包含全部 MOS 电荷和负载/封装储能，不能称为完整能量守恒校验。TT −5% 扰动帧中约 0.1925 pJ/位来自电容储能释放；既不把它算作节能，也不假设回送源端的能量可无损回收。持续能效仍需足够长的重复帧与恢复窗口验证。\n'
 return text

def robustness(s):
 cfg=selection();rows=[];fig,axes=plt.subplots(3,3,figsize=(13,9),sharex=True)
 for i,c in enumerate(['TT','SS','FF']):
  for label,color,name in [('r6 失败对照','#a7754e',cfg['startup_before'][c]),(cfg['revision'],'#267b82',cfg['startup_after'][c])]:
   w=ROOT/'build/vcsel-robustness-20261029'/name;x=read(w/'startup-review.json');q=np.load(w/'startup-plot.npz');m=x['metrics']
   rows.append([c+'/'+label,f"{m['current_mA']['final']:.4f}",f"{m['laser_rail_V']['final']:.4f}",f"{m['buffer_rail_V']['final']:.4f}",' / '.join('未进入' if v['entered_and_stayed_in_dc_band_us'] is None else f"{v['entered_and_stayed_in_dc_band_us']:.2f}" for v in m.values()),'通过' if x['startup_joint_screen_passed'] else '失败'])
   for j,(arr,key,yl) in enumerate([('current_mA','current_mA','电流 / mA'),('vl','laser_rail_V','激光轨 / V'),('xdrv.dr','buffer_rail_V','缓冲轨 / V')]):
    ax=axes[i,j];ax.plot(q['time_s']*1e6,q[arr],label=label,color=color,lw=1.1)
    if label==cfg['revision']:ax.axhline(m[key]['dc_target'],ls=':',color=color,lw=.8)
    ax.set(title=c+' / '+yl,xlabel='上电后 / µs');ax.grid(alpha=.15)
    if i==0 and j==0:ax.legend()
 save(fig,'startup-rails')
 text='r6 的 2.85 V 稳压方案使 TT/SS 的单侧时间余量降到 85.45/39.06 ps，低于固定 100 ps 门槛。30 µs 上电仿真又暴露稳压轨未建立、快冷时电流随环路振荡的问题。仅看头 2 µs 电流，或只从 DC 工作点发码，都会遗漏这个失败。\n\n'
 text+='后续改动把目标设为 3.10 V，并修改补偿与最小负载。慢热 2.97 V 原始电源低于设定值，此时调整管进入 dropout；它不是凭空升压，实际轨电压应与该条件下的 DC 解比较。最小负载帮助空闲缓冲轨放电并改变输出极点，也增加静态功耗。\n\n'
 af,axs=plt.subplots(2,1,figsize=(10,6),sharex=True)
 for name,label,color in [('ac-TT-L-rz0.0-bleed0.0-c1e-10','r6 TT 激光轨','#a7754e'),('ac-final-TT-L-r8','r8 TT 激光轨','#267b82'),('ac-final-TT-L-r10','r10 TT 激光轨','#4b73a3')]:
  w=ROOT/'build/vcsel-robustness-20261029'/name;q=np.load(w/'plot.npz');a=read(w/'result.json')
  axs[0].semilogx(q['frequency_Hz'],q['loop_gain_dB'],color=color,label=label)
  axs[1].semilogx(q['frequency_Hz'],q['phase_deg'],color=color,label=label)
  # Show both downward and upward crossings. This ratio is not a validated return ratio.
  f=q['frequency_Hz'];g=q['loop_gain_dB'];p=q['phase_deg']
  for k in np.flatnonzero(g[:-1]*g[1:]<0):
   u=-g[k]/(g[k+1]-g[k]);fc=np.exp(np.log(f[k])+u*np.log(f[k+1]/f[k]));pc=p[k]+u*(p[k+1]-p[k])
   axs[0].plot(fc,0,'o' if g[k+1]<g[k] else '^',color=color);axs[1].plot(fc,pc,'o' if g[k+1]<g[k] else '^',color=color)
 axs[0].axhline(0,color='#60747a',ls=':',lw=.8);axs[1].axhline(-180,color='#60747a',ls=':',lw=.8)
 axs[0].set(ylabel='注入电压比幅度 / dB',ylim=(-60,120));axs[1].set(ylabel='注入电压比相位 / 度',xlabel='频率 / Hz',xlim=(1,1e9))
 for ax in axs:ax.grid(alpha=.2);ax.legend()
 save(af,'ldo-loop-diagnostic')
 text+=figure('ldo-loop-diagnostic.png','方法复核：保留 1 Hz–1 GHz 全扫频和向下（圆点）/向上（三角）全部 0 dB 交越。此电压注入比含高频加载项，不是经验证的环路返回比；不能据图宣称相位裕量或稳定性签核。')
 text+='原脚本只统计向下交越，曾给出 r8 TT 约 92.84° 的“近似相位裕量”。独立审查发现 r10 六条轨/角落曲线均在约 8.83–10.45 MHz 再次向上穿越 0 dB。仅有分压等效电阻 `Rth=85k||10k` 和放大器输入电容 Cin、完全没有有源反馈时，这种注入电压比也含 `s·Rth·Cin` 项，仍可产生高频交越。故撤回把首个交越数值作为稳定性依据的解释；保留原始诊断以便复核。SS dropout 没有向下交越，同样不表示稳定性已经通过。\n\n'
 text+='本轮能支持的是所列启动与供电扰动的时域结果；不能外推到任意负载、ESR、封装或运行点。也不能反过来把高频上穿直接判成实际电路振荡。完整交越、被动 RC 反例和方法文献见[独立方法审查 §14](../../../evidence/vcsel-robustness-20261029/independent-review.md)与[全部交越记录](../../../evidence/vcsel-robustness-20261029/audit-ac-all-crossings.json)。下一步要用能保留双向加载的返回比方法（例如双注入）并覆盖偏置/负载条件，才能建立可靠的环路相位与增益余量。环路相位余量、接收时间余量及电源抑制比（PSRR）也是三个不同指标。\n\n'
 if cfg.get('supply_after_plot'):
  sf,sa=plt.subplots(3,1,figsize=(11,9),sharex=True)
  for fn,label,color in [('audit-supply-transient-r8.npz','r8 失败对照','#a7754e'),(cfg['supply_after_plot'],cfg['revision'],'#267b82')]:
   q=np.load(EV/fn);t=q['time_s']*1e6
   sa[0].plot(t,q['VL_V'],color=color,label=label+' 激光轨 VL')
   if label==cfg['revision']:sa[0].plot(t,q['rawlaser_V'],color='#4b73a3',ls='--',label='共同原始激光供电')
   for ax,key,scale in [(sa[1],'JMON_A',1e3),(sa[2],'STAIL_V',1e3)]:
    bt=q[key+'_bin_center_s']*1e6;lo=q[key+'_bin_min']*scale;hi=q[key+'_bin_max']*scale
    ax.fill_between(bt,lo,hi,color=color,alpha=.16);ax.plot(bt,hi,color=color,lw=.8,label=label+' 分箱上包络')
  sa[0].set(ylabel='电压 / V');sa[1].set(ylabel='VCSEL 导电电流 / mA');sa[1].axhline(7.5,color='#8d4e50',ls='--',lw=1,label='模型上界 7.5 mA')
  sa[2].set(ylabel='尾源感测电压 / mV',xlabel='本帧开始后 / µs');sa[2].axhline(150,color='#60747a',ls=':',lw=1,label='0.15 V 目标')
  for ax in sa:ax.legend(loc='best',fontsize=9);ax.grid(alpha=.15)
  save(sf,'supply-recovery')
  text+=figure('supply-recovery.png','TT −5% 供电扰动的完整 1.28 µs；NRZ 电流与感测电压使用每 0.5 ns 原生最小/最大包络以免密集跳变混叠，判定仍用全部原生样点。')
  text+='r8 在供电恢复时导电电流峰值约 7.727 mA，超过冻结 P–I 数据的 7.5 mA 上界，即使零观察错误也判失败。固定高电平的单因素实验显示，仅扰动 VREF 时约 6.921–7.070 mA；仅扰动激光原始轨时约 6.186–7.902 mA，支持激光供电瞬态是主要问题来源。\n\n'
  diagnostic=[('hold-TT-minus-r8-candidate','r8 基础'),('hold-TT-minus-refRC-candidate','仅参考供电 RC'),('hold-TT-minus-servo1p-candidate','仅电流伺服补偿 5 pF→1 pF'),('hold-TT-minus-Cout10n-candidate','仅激光去耦 1 nF→10 nF'),('hold-TT-minus-Cout10n-Rz100k-candidate','10 nF + 激光补偿 Rzero=100 kΩ')]
  dr=[]
  for name,label in diagnostic:
   r=read(ROOT/'build/vcsel-robustness-20261029'/name/'result.json');dr.append([label,f"{r['current_range_mA'][0]:.3f}",f"{r['current_range_mA'][1]:.3f}"])
  text+=table(['固定高电平机制对照（不是接收验证）','最小电流 mA','最大电流 mA'],dr)
  text+='\n仅加大输出电容会改变环路动态。早期注入诊断曾给出 FF 约 25°，但上述方法审查说明它不能当作可靠的实际相位裕量。r10 同时把激光 Miller 串联电阻改为 100 kΩ；目前支持此候选的是重新执行的启动、供电扰动和完整数据帧结果，严格返回比稳定性验证仍待完成。10 nF 明确属于外部去耦，ESR=0.1 Ω 是本实验设定；完整实体电容与封装网络还没有实测。\n\n'
 text+=figure('startup-rails.png','图 7｜同一行比较电流、激光轨和缓冲轨；虚线是新版独立 DC 目标，曲线仅覆盖实际仿真时长。')
 text+=table(['条件/设计','末点 mA','末点 VL / V','末点 DR / V','进入并保持 DC 带内 µs：I / VL / DR','联合启动筛查'],rows)
 text+='\n本轮在发现两轨未建立后补充了启动诊断条件：电流进入对应 DC 值 ±5%、两电源轨进入 ±1%，并检查末段波动和全程端压。这不是把新增条件追溯说成最初已经预注册的门槛。求解器的“仿真结束”不等于这些指标通过；也不把始终未进入稳压状态的末点拿来重新定义目标。\n\n'
 text+='VCSEL 原静态曲线的可信工作区间从 2 mA 开始；从零启动会经过人工延拓区。因此这里的建立时间只验证**这份数值负载下的控制环**，还不是实际发光器件的上电规格。通信帧的负载工作域另行筛查。\n\n'
 text+=cfg.get('startup_interpretation','')+'\n\n'
 peak=read(EV/'audit-r10-startup-peak-windows.json')['rows']
 pf,pa=plt.subplots(2,1,figsize=(10,6),sharex=True)
 for x,color in zip(peak,['#267b82','#a7754e']):
  w=ROOT/'build/vcsel-robustness-20261029'/x['case'];m=read(w/'manifest.json');r=read(w/'result.json');a=np.loadtxt(ROOT/r['waveform']['path'],skiprows=1);ix={n:k+1 for k,n in enumerate(m['expressions'])}
  dev=next(d for d in m['devices'] if d['instance']==x['stress_max']['instance']);gate=a[:,ix['v('+dev['nodes'][1]+')']];body=a[:,ix['v('+dev['nodes'][3]+')']]
  t=a[:,0]*1e9-x['config']['ramp_ns'];mask=(t>=-2)&(t<=10);label=str(x['config']['ramp_ns'])+' ns 同步上电'
  pa[0].plot(t[mask],abs(gate-body)[mask],color=color,label=label);pa[1].plot(t[mask],gate[mask]*1e3,color=color,label=label)
 pa[0].axhline(3.63,color='#8d4e50',ls='--',label='3.63 V 项目筛查线');pa[0].set(ylabel='基础 OTA 输入管 |VGB| / V',ylim=(3.615,3.635));pa[1].set(ylabel='感测节点 SBASE / mV',xlabel='距电源斜坡结束 / ns',ylim=(-2,20))
 for ax in pa:ax.grid(alpha=.15);ax.legend(fontsize=9)
 save(pf,'startup-peak');text+=figure('startup-peak.png','FF 短窗原生数据：XBP1_0 为基础电流 OTA 的 PMOS 输入管，G=SBASE、B=VREF。快速上电末端 SBASE 短暂低于地，形成栅—体端压越线；横轴对齐斜坡结束便于比较，完整波形保留。')
 text+=table(['FF 上电峰值复核（前 0.5 µs，约 50 ps 步长）','最大端压 V','距 3.63 V / mV','峰值所在器件/端对'],[[str(x['config']['ramp_ns'])+' ns 同步斜坡',f"{x['stress_max']['V']:.9f}",f"{x['stress_max']['headroom_mV']:+.6f}",x['stress_max']['instance']+'/'+x['stress_max']['pair']] for x in peak])
 text+='\n**20 ns 快速上电仍失败。** 100 ns 细步与原粗步的峰值只差约 0.406 µV，说明薄余量不是原步长造成的假象；不能用正常发送的 0/4096 掩盖这个上电失败。短窗只检查峰值，不能因为尚未进入 DC 电源带而将它计作完整启动验收。当前没有自主上电复位（POR）、电源就绪（PGOOD）或异步参考排序保护；“100 ns 同步斜坡 + 等待 60 µs”只是已测试的外部条件，也不是全部斜率与量产容差保证。下一修订需限制上电端压并加入启动许可，再重跑整个链路。\n\n'
 rows=[]
 for name in cfg.get('controls',[]):
  x=case(s,name);rows.append([cfg.get('control_labels',{}).get(name,name),f"{x['errors']}",f"{x['time_margin_ps']:.2f}",f"{x['optical_margin_min_mW']:.3f} ({x['min_signed_margin_uAeq']:.2f})",f"{x['energy']['positive_pJ_per_offered_payload_bit']:.4f}",f"{x['stress_max_V']:.4f}",'通过' if x['passed'] else '失败'])
 if rows:text+=table(['独立控制实验','错误','时间 ps','幅度 mW (µAeq)','pJ/尝试净位','端压 V','联合'],rows)
 text+=cfg.get('control_interpretation','')+'\n'
 continuous=[case(s,n) for n in cfg.get('continuous',[])]
 if continuous:
  text+='\n### 上电后直接发送，是否与工作点启动一致\n\n以下保持同一次瞬态状态：同步上电、等待至 60 µs，再发送同一 1.28 µs 帧；没有重新计算工作点。等待期保持高电平，不是休眠。\n\n'
  cr=[]
  for x in continuous:
   r=read(ROOT/x['result']);e=r['continuous_run']['startup_energy_J']['positive_J'];cr.append([{'typical':'TT','ss':'SS','ff':'FF'}[x['corner']],x['errors'],f"{x['time_margin_ps']:.3f}",f"{x['min_signed_margin_uAeq']:.3f}",f"{x['energy']['positive_pJ_per_offered_payload_bit']:.5f}",f'{e*1e6:.6f}',f'{e/4096*1e12:.2f}'])
  text+=table(['连续启动 → 数据','错误 /4096','时间 ps','幅度 µAeq','数据帧 pJ/尝试净位','前 60 µs 正向能量 µJ','若只发一帧：额外摊销 pJ/净位'],cr)
  text+='\n3.2 Gb/s 指进入发送状态后的净吞吐。若每个 4096 bit 短包都冷启动并等待 60 µs，包含等待的平均吞吐只有 `4096/(60+1.28)µs≈66.84 Mb/s`，且必须加入表中的启动/等待能量。此处没有证明连续许多帧的储能周期稳态，也没有重新训练验证位；接收规则和独立验证窗口保持冻结。\n'
 text+='\n### 电流误差由什么决定\n\n'
 groups=[('nominal','理想 VSET/R，失配关闭'),('Rsense-minus','两 Rsense 同时 −1%'),('Rsense-plus','两 Rsense 同时 +1%'),('Rbase-minus-tail-plus','RBASE −1% / RTAIL +1%'),('Rbase-plus-tail-minus','RBASE +1% / RTAIL −1%'),('VSET-minus','VSET −1%'),('VSET-plus','VSET +1%'),('REGSET-minus','VREGSET −1%'),('REGSET-plus','VREGSET +1%')]
 rows=[]
 for key,label in groups:
  states=[]
  for level in [0,1]:
   vals=[dc(s,(f'regulated-{c}-{level}-'+cfg['revision'] if key=='nominal' else f'dc-{c}-{key}-{level}-'+cfg['dc_revision']))['current_mA'] for c in ['TT','SS','FF']]
   states.append(f'{min(vals):.4f}–{max(vals):.4f}')
  rows.append([label]+states)
 text+=table(['确定性设定（范围覆盖三个组合条件）','低档 mA','高档 mA'],rows)
 text+='\n'+cfg.get('dc_tolerance_note','')+'\n'
 text+='\n理想 VSET 与 R 的六个 nominal DC 点误差约 −0.015% 至 −0.002%，只表示这组条件下的有限增益残差，**不能称为芯片达到 0.015% 电流精度**。48 个新增容差点分别改变 VSET、稳压参考或电阻，包含两支感测电阻反向偏差；不是所有误差叠加的最坏组合，也不是随机失配统计。实际精度还需温漂、放大器失调、噪声和校准验证。\n'
 return text

def main():
 font=Path(os.environ.get('MICROLED_REPORT_FONT',str(ROOT/'build/fair-driver-v1/report-font/NotoSansCJKsc-Regular.otf')))
 font_manager.fontManager.addfont(font);plt.rcParams.update({'font.family':font_manager.FontProperties(fname=font).get_name(),'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','svg.hashsalt':'reference20261029'})
 s=read(EV/'summary.json');expframes(s);FIG.mkdir(exist_ok=True)
 body=(DOC/'README.md').read_text()
 parts={'CONCLUSIONS':conclusions(s),'BASELINE':baseline(s),'CIRCUIT':circuit(s),'COMPARISON':compare(s),'ENERGY':energy(s),'ROBUSTNESS':robustness(s)}
 for k,value in parts.items():body,n=re.subn(r'<!-- '+k+r' -->.*?<!-- END '+k+r' -->',lambda _:f'<!-- {k} -->\n\n{value}\n<!-- END {k} -->',body,flags=re.S);assert n==1
 (DOC/'README.md').write_text(body)
 css='''<style>:root{color-scheme:light;--ink:#263c45;--teal:#267b82;--line:#d9e2e3}*{box-sizing:border-box}body{margin:0;background:#f7f8f7;color:var(--ink);font:16px/1.75 "PingFang SC","Noto Sans CJK SC","Microsoft YaHei",Arial,sans-serif}main{max-width:1160px;margin:auto;padding:42px 36px 80px}h1,h2,h3{line-height:1.35}h1{font-size:34px;margin:20px 0 30px}h2{font-size:25px;margin:46px 0 20px;padding-bottom:12px;border-bottom:1px solid var(--line)}h3{font-size:20px;margin-top:30px}p{margin:18px 0}a{color:#1d6b76;text-underline-offset:3px}nav{display:flex;gap:22px;font-size:14px}table{width:100%;border-collapse:collapse;font-size:14px;margin:25px 0;display:block;overflow:auto}th,td{padding:11px 14px;text-align:left;border-bottom:1px solid var(--line)}th{background:#e8eff0;white-space:nowrap}tr:nth-child(even){background:white}figure{margin:28px 0;padding:20px;background:white;border:1px solid var(--line);border-radius:8px}figure img{width:100%;height:auto}figcaption{font-size:14px;color:#61777d;margin-top:14px}code{font-family:Menlo,Consolas,monospace;font-size:.88em;background:#edf1f2;padding:2px 5px;border-radius:3px}pre{background:#edf1f2;padding:18px;overflow:auto}blockquote{border-left:4px solid var(--teal);margin:25px 0;padding:12px 22px;background:#eef5f4}li{margin:8px 0}@media(max-width:700px){main{padding:22px 18px}h1{font-size:28px}figure{padding:8px}}@media print{body{background:white}main{max-width:none;padding:0}h2,h3{break-after:avoid}figure,tr{break-inside:avoid}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}</style>'''
 html='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VCSEL参考与供电改进 / MicroLED动态依据</title>'+css+'</head><body><main><nav><a href="../three-gbps-experiment-20261027/index.html">上一轮结果</a><a href="README.md">完整文字</a><a href="experiment-plan.md">实验约定</a><a href="reproduce.md">恢复与复现</a></nav>'+markdown.markdown(body,extensions=['tables','fenced_code','toc'])+'</main></body></html>\n'
 (DOC/'index.html').write_text(html)
 micro=(DOC/'microled-dynamic-evidence.md').read_text()
 microhtml='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MicroLED动态模型证据</title>'+css+'</head><body><main><nav><a href="index.html">返回主报告</a><a href="microled-dynamic-evidence.md">文字版与复现</a></nav>'+markdown.markdown(micro,extensions=['tables','fenced_code','toc'])+'</main></body></html>\n'
 (DOC/'microled-dynamic-evidence.html').write_text(microhtml)
 selected=[Path(__file__),DOC/'README.md',DOC/'index.html',DOC/'microled-dynamic-evidence.html',DOC/'microled-dynamic-evidence.md',DOC/'reproduce.md',EV/'report-cases.json',EV/'summary.json',EV/'circuit-figures.json',EV/'independent-review.md',EV/'engineer-notes.md']+sorted(FIG.glob('*'))+sorted(EV.glob('audit-*.json'))
 (EV/'report-manifest.json').write_text(json.dumps({'scope':'schematic circuit and bounded research proxy','files':[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in selected]},ensure_ascii=False,indent=2)+'\n')
 print('Rendered '+str(DOC/'index.html'))
if __name__=='__main__':main()
