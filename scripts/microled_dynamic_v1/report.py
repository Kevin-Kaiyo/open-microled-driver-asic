#!/usr/bin/env python3
"""Build the Chinese report exclusively from recorded experiments and fit receipts."""
from pathlib import Path
import hashlib, html, json, math, re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import markdown

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/microled-dynamic-validation-20261108'
EV=ROOT/'evidence/microled-dynamic-v1'
FIG=DOC/'figures'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def table(head,rows):
 clean=lambda v:str(v).replace('|','&#124;').replace('\n','<br>')
 return '\n'.join(['| '+' | '.join(head)+' |','|'+'|'.join(['---']*len(head))+'|']+['| '+' | '.join(clean(v) for v in row)+' |' for row in rows])
def image(name,caption):return f'![{caption}](figures/{name})\n\n*{caption}*\n\n'
def fonts():
 for path in ['/System/Library/Fonts/PingFang.ttc','/System/Library/Fonts/Hiragino Sans GB.ttc']:
  if Path(path).exists():
   font_manager.fontManager.addfont(path);plt.rcParams['font.family']=[font_manager.FontProperties(fname=path).get_name(),'DejaVu Sans'];break
 plt.rcParams.update({'font.size':12,'font.weight':300,'axes.labelweight':300,'axes.titleweight':300,'axes.unicode_minus':False,'svg.fonttype':'none','svg.hashsalt':'microled-dynamic-v1-20261108'})
def save(fig,stem):
 fig.tight_layout(pad=1.8)
 for ext in ['png','svg']:
  p=FIG/(stem+'.'+ext);fig.savefig(p,dpi=150,metadata={'Date':'2026-11-08'} if ext=='svg' else {})
  if ext=='svg':p.write_text('\n'.join(s.rstrip() for s in p.read_text().splitlines())+'\n')
 plt.close(fig)

def circuit():
 p=[]
 def t(x,y,s,size=21,color='#233e50',bold=False):
  for j,part in enumerate(s.split('\n')):
   part=part.replace('｜',' | ')
   content=''.join(f'<tspan font-family="Arial">{html.escape(c)}</tspan>' if c in 'Ωτµμ∫→−–' else html.escape(c) for c in part)
   p.append(f'<text x="{x}" y="{y+j*(size*1.55)}" font-size="{size}" fill="{color}" font-weight="{600 if bold else 400}">{content}</text>')
 def line(x,y,X,Y,color='#233e50',w=3):p.append(f'<path d="M{x} {y} L{X} {Y}" stroke="{color}" stroke-width="{w}" fill="none"/>')
 def box(x,y,w,h,s,fill='#f3f7f8'):
  p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" stroke="#cedbdf" stroke-width="2" fill="{fill}"/>');t(x+18,y+34,s)
 def dot(x,y):p.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#233e50"/>')
 t(50,54,'图 1｜把电荷、导电电流和接收代理放在正确参考面',30,bold=True)
 t(50,94,'源网表未改；C 与光响应为本轮声明的敏感性参数，测量整链 S21 单独拟合。',20,'#657986')
 box(50,135,710,805,'实际 SPICE 负载：仅 C 值发生扫描')
 t(95,224,'VLED = 5 V');line(260,217,315,217);p.append('<rect x="315" y="204" width="100" height="26" fill="white" stroke="#233e50" stroke-width="3"/>');line(415,217,510,217);t(325,193,'0.25 Ω',18)
 line(510,217,510,300);line(510,300,225,300);line(225,300,225,360);dot(225,300);dot(510,300);t(535,279,'Va')
 p.append('<polygon points="202,360 248,360 225,400" fill="white" stroke="#233e50" stroke-width="3"/>');line(202,405,248,405);line(225,405,225,444)
 t(82,354,'I–V 行为负载',18);t(82,385,'文献静态数据',18)
 # Emission arrows clarify that the symbol represents an emitting junction.
 for x,y in [(270,355),(282,387)]:
  line(x,y,x+42,y-25,'#287c83');line(x+42,y-25,x+30,y-25,'#287c83');line(x+42,y-25,x+37,y-14,'#287c83')
 p.append('<circle cx="225" cy="472" r="28" stroke="#233e50" stroke-width="3" fill="white"/>');line(225,500,225,560);t(76,472,'VSENSE = 0 V',15);t(82,507,'只测 I导电',18,'#287c83')
 line(510,300,510,416);line(480,416,540,416);line(480,436,540,436);line(510,436,510,560);line(225,560,510,560);dot(225,560);dot(510,560)
 t(550,402,'CLED',20);t(550,438,'0–800 fF',18);t(550,474,'假设值',18,'#ad6f3e');t(535,556,'Vk',19)
 line(225,560,225,606);p.append('<rect x="212" y="606" width="26" height="65" stroke="#233e50" stroke-width="3" fill="white"/>');t(260,643,'Rpkg = 1 Ω',18)
 line(225,671,225,700)
 for cy in [710,730,750]:p.append(f'<path d="M225 {cy-10} C255 {cy-10},255 {cy+10},225 {cy+10}" fill="none" stroke="#233e50" stroke-width="3"/>')
 line(225,760,225,805);t(275,733,'Lpkg = 0.5 nH',18);t(245,797,'OUT',18,'#287c83')
 box(95,817,590,90,'A 电压输出 / B 电流转向 / C 四电平\n共同真实参考、供电和数据缓冲', '#e5f1ef')
 line(225,805,225,817)
 box(800,135,750,255,'从导电电流到同一接收代理')
 box(830,195,210,90,'I导电(t)\n原生时间序列','white');box(1070,195,190,90,'H光响应','white');t(1088,262,'τ:0/25/75/200 ps',16);box(1290,195,220,90,'固定 RX 1 GHz\n原 v2 判决','white')
 line(1040,239,1070,239,'#287c83');line(1260,239,1290,239,'#287c83')
 t(828,333,'阈值与幅度 / 时间门槛不随负载或路线重新设定。',19)
 box(800,425,750,245,'电荷与能量分别守恒')
 t(830,490,'I端口 = I导电 + C · d(Va − Vk)/dt',23,'#287c83')
 t(830,541,'七个输入源：VIN / VDD / VREF / VLED / D0 / D1 / DISABLE',18)
 t(830,587,'E = ∫(各独立输入端口功率)dt / 4096 个尝试净位',20)
 t(830,628,'积分覆盖完整 1.28 µs 帧；正向 / 返回 / 净能量分别记录。',18)
 box(800,705,750,235,'整链频响是另一项证据','#f8efe6')
 t(830,771,'VNA → bias tee → LED → 光路 → 检测器 → VNA',21)
 t(830,820,'仅对公开归一化幅度作独立频域拟合和留出检验。',20)
 t(830,865,'缺 S11、相位和去嵌：尚不能分配唯一 C、寿命与 RX 极点。',18)
 t(830,907,'H整链没有再次接到上方已含 CLED / RX 的仿真中。',19,'#ad6f3e')
 t(50,1000,'证据层级：实际原理图 SPICE + 合成动态敏感性；无新 GDS、PEX、器件实测或光学 BER。',21)
 t(50,1041,'图中二极管 / C / R / L 连接对应 testbench；完整 MOS、参考与辅助轨见报告所链原理图。',19,'#657986')
 svg='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1100" viewBox="0 0 1600 1100"><title>MicroLED动态负载电路与参考面</title><style>text{font-family:"PingFang SC","Hiragino Sans GB","Noto Sans CJK SC",Arial,sans-serif}</style><rect width="1600" height="1100" fill="white"/>'+''.join(p)+'</svg>\n'
 (FIG/'model-circuit.svg').write_text(svg)
 import cairosvg
 cairosvg.svg2png(bytestring=svg.encode(),write_to=str(FIG/'model-circuit.png'))

def fit_section(f):
 rows=[]
 for key,v in f['fit_summary'].items():
  a=v['residual']['full_30MHz_to3GHz'];b=v['residual']['restricted_30MHz_to2p5GHz']
  rows.append([key,'三极点/一零点条件模型',f"{a['rmse_dB']:.3f} / {a['max_abs_dB']:.3f}",f"{b['rmse_dB']:.3f} / {b['max_abs_dB']:.3f}"])
 text=table(['偏置 / µA','整链数学模型','30M–3G：RMSE / 峰值 dB','≤2.5G：RMSE / 峰值 dB'],rows)
 text+='\n\n这些是**条件化幅频拟合**，不是器件动态参数校准完成。高频残差、频率外推、偏置留出与参数触边见[完整拟合验证](../../../evidence/microled-dynamic-v1/fit-validation.json)。不把拟合零点解释为 LED 物理机制，也不把最小相位当成测量结果。\n'
 text+='\n模型族及阶数使用完整源曲线选择；以下留出仅在既定模型族下重新拟合或预测，未进行嵌套选模或独立器件盲测，因此属于条件化内部检验。≤2.5 GHz 只是截取的频域范围，缺少仪器噪声数据时不能称已验证的高信噪比区间。\n\n'
 hold=[]
 for split in sorted(set(x['split'] for x in f['frequency_holdouts'])):
  q=[x['holdout']['full_30MHz_to3GHz'] for x in f['frequency_holdouts'] if x['split']==split]
  label={'contiguous_frequency_0p8to1p2GHz':'连续留出 0.8–1.2 GHz','high_edge_extrapolation_2p6to3GHz':'高频外推 2.6–3.0 GHz','interleaved_frequency_mod5eq2':'交错留出：每 5 点取 1 点'}[split]
  hold.append([label,f"{min(x['rmse_dB'] for x in q):.3f}–{max(x['rmse_dB'] for x in q):.3f}",f"{min(x['max_abs_dB'] for x in q):.3f}–{max(x['max_abs_dB'] for x in q):.3f}"])
 text+=table(['频率留出类型（五个偏置）','留出 RMSE 范围 /dB','留出峰误差范围 /dB'],hold)
 text+='\n\n另以**假定 50 Ω 激励源和 3 GHz 一阶检测器**测试 C/τ 简化组合，属于对源测量链的兼容性检验。这一假定检测器与下文 A/B/C 固定 1 GHz RX 属不同参考面。简单组合的残差不能证明真实电容或寿命不合格，只说明这些参数与测量链尚未联合识别。\n'
 text+=image('frequency-fit.png','图 2｜公开整链幅频与独立数学拟合；测量链、归一化和高频噪声仍在数据内。')
 return text

def plots_fit(f):
 a=np.genfromtxt(EV/'fit-residuals.csv',delimiter=',',names=True,encoding='utf-8')
 fig,axs=plt.subplots(1,2,figsize=(12,4.5))
 for bias,col in zip([25,50,60,80,100],['#234956','#407f81','#739e91','#a27c51','#8b698a']):
  q=a[a['bias_uA']==bias];x=q['frequency_Hz']/1e9
  axs[0].plot(x,q['source_S21_dB'],color=col,alpha=.45,lw=1)
  axs[0].plot(x,q['conditional_model_dB'],color=col,lw=1.4,ls='--',label=f'{bias} µA')
  axs[1].plot(x,q['model_minus_source_dB'],color=col,lw=1,label=f'{bias} µA')
 axs[0].set(title='实线：源数据；虚线：整链数学拟合',xlabel='频率 / GHz',ylabel='源归一化幅度 / dB')
 axs[1].set(title='残差保留；不把噪声或零点解释为器件机理',xlabel='频率 / GHz',ylabel='拟合 − 源数据 / dB')
 for ax in axs:ax.grid(alpha=.16);ax.legend(frameon=False,fontsize=10);ax.axvline(2.5,color='#777',ls=':',lw=1)
 save(fig,'frequency-fit')

def chosen(records,route,cap,tau,corner='typical',steps=40,stage='full'):
 q=[r for r in records if r['route']==route and abs(r['capacitance_fF']-cap)<1e-7 and r['optical_tau_ps']==tau and r['corner']==corner and r['steps_per_symbol']==steps and r['stage']==stage]
 return q[0] if len(q)==1 else None
def measurement(r):
 return '待运行' if r is None else f"{r['bit_errors']} / {r['min_signed_margin_uA']:.2f} / {r['min_time_margin_ps']:.2f}"

def matrix_plots(records):
 caps=[0,10,50,200,800];taus=[0,25,75,200]
 fig,axs=plt.subplots(1,3,figsize=(12,4.6),sharey=True)
 for ax,route in zip(axs,'ABC'):
  z=np.full((4,5),np.nan)
  for j,tau in enumerate(taus):
   for i,cap in enumerate(caps):
    r=chosen(records,route,cap,tau)
    if r:z[j,i]=r['min_signed_margin_uA']
  im=ax.imshow(z,cmap='RdYlGn',vmin=-60,vmax=30,aspect='auto')
  for j in range(4):
   for i in range(5):
    if np.isfinite(z[j,i]):ax.text(i,j,f'{z[j,i]:.1f}',ha='center',va='center',fontsize=9)
  ax.set(title=f'路线 {route}',xticks=range(5),xticklabels=['0*','10','50','200','800'],yticks=range(4),yticklabels=['0*','25','75','200'],xlabel='假设 C / fF')
 axs[0].set_ylabel('假设光响应 τ / ps')
 fig.suptitle('相同 1 GHz RX；负值表示落在错误判决区，幅度门槛 +7.5 µAeq；* 理想诊断',fontsize=12)
 fig.subplots_adjust(left=.07,right=.86,top=.82,bottom=.18,wspace=.16)
 coloraxis=fig.add_axes([.895,.18,.016,.64])
 fig.colorbar(im,cax=coloraxis,label='最小有符号幅度余量 / µAeq')
 for ext in ['png','svg']:
  p=FIG/('sensitivity-margin.'+ext);fig.savefig(p,dpi=150,metadata={'Date':'2026-11-08'} if ext=='svg' else {})
  if ext=='svg':p.write_text('\n'.join(s.rstrip() for s in p.read_text().splitlines())+'\n')
 plt.close(fig)

def eyes(records):
 fig,axs=plt.subplots(2,3,figsize=(12,7.5),sharey=True)
 for j,route in enumerate('ABC'):
  for i,(cap,tau) in enumerate([(200,200),(10,25)]):
   ax=axs[i,j];r=chosen(records,route,cap,tau)
   if r and r.get('eye_path'):
    q=np.load(ROOT/r['eye_path'])
    for y in q['output_uA']:ax.plot(q['offset_ps'],y,color='#287c83',alpha=.15,lw=.65)
    for th in q['thresholds_uA']:ax.axhline(th,ls='--',color='#ad7750',lw=.7)
    ax.set_title(f"{route}: C={cap} fF, τ={tau} ps\n{r['bit_errors']}/4096；{r['min_time_margin_ps']:.1f} ps",fontsize=11)
   else:ax.set_title(f'{route}: C={cap}, τ={tau}（待运行）')
   ax.set(xlabel='相对训练后采样点 / ps',ylabel='固定 RX 输出 / µAeq',ylim=(-5,130),xlim=(-270.27027,270.27027));ax.grid(alpha=.15)
   ax.axvline(0,color='#233e50',lw=.7)
   for xpos in [-100,100]:ax.axvline(xpos,color='#888',lw=.6,ls=':')
 save(fig,'paired-eyes')

def energy_plot(e):
 fig,ax=plt.subplots(figsize=(11.5,4.5));labels=[];cols={p:[] for p in ['VIN','VDD','VREF','VLED','DATA']}
 for route in 'ABC':
  for cap in [200,10]:
   rows=[r for r in e['records'] if r['route']==route and r['case'].get('kind','transient')!='dc' and r['case']['corner']=='typical' and abs(r['case']['led_cap_F']*1e15-cap)<1e-7 and r['case']['steps_per_symbol']==40]
   if not rows:continue
   r=rows[0];labels.append(f'{route}\n{cap} fF')
   for p in ['VIN','VDD','VREF','VLED']:cols[p].append(r['energy_ports'][p]['positive_J']*1e12/4096)
   cols['DATA'].append(sum(r['energy_ports'][p]['positive_J'] for p in ['VD0','VD1','VDISABLE'])*1e12/4096)
 bottom=np.zeros(len(labels))
 for (name,ys),color in zip(cols.items(),['#285769','#568e92','#9bb9a6','#bd9b67','#9a7e9a']):
  ax.bar(labels,ys,bottom=bottom,label=name,color=color,width=.58);bottom+=ys
 ax.set(ylabel='正向源端取能 / pJ/尝试净位',title='相同净3.2 Gb/s帧：电气能量分解，接收失败点不构成有效交付能效')
 ax.legend(ncol=5,frameon=False,fontsize=10);ax.grid(axis='y',alpha=.15);ax.spines[['top','right']].set_visible(False)
 save(fig,'energy-ports')

def sections(e,rx,f):
 rec=rx['records'];full=[r for r in rec if r['stage']=='full' and r['group']=='TT_capacitance' and r['steps_per_symbol']==40]
 passed=[r for r in full if r['combined_electrical_and_RX_screen_pass']]
 ideal=[r for r in full if r.get('ideal_limit_diagnostic',False)]
 summary=f"**本轮完成公开幅频的条件化拟合，并以冻结 A/B/C 电路进行动态负载敏感性实验。电气计划 {e['completed']}/{e['planned']} 项已记录，典型条件全链假设点 {len(full)} 个（含 {len(ideal)} 个理想限制诊断），其中原接收与 MOS 端对压差联合筛查通过 {len(passed)} 个。**\n\n"
 summary+='这些通过或失败只属于明确的 C/τ 假设和电流域接收代理。幅频拟合仍只能解释已测整链幅度，尚不能作为真实器件瞬态预测；器件物理动态校准未闭合。暂不预选路线。'
 dc=e.get('dc',[])
 dctext=table(['路线/电容/电平','目标 / µA','导电电流 / µA','误差 / %'],[[f"{d['route']} / {d['C_fF']:g} fF / L{d['level']}",f"{d['target_uA']:g}",f"{d['current_uA']:.5f}",f"{d['error_percent']:.4f}"] for d in dc]) if dc else 'DC 回归正在记录，最终值见 electrical-summary.json。'
 if dc:dctext+=f"\n\n{len(dc)} 点的最大绝对目标误差为 **{max(abs(d['error_percent']) for d in dc):.6f}%**。这是冻结晶体管模型对目标电流的仿真偏差，不包含真实样品测量、失配或生产公差，也没有为本轮重新调整电流参数。"
 dctext+='\n\n改变常数并联电容不改变稳态电容电流。两个电容组的 DC 一致性控制单独保存，不能用动态幅频拟合重新调整目标电流。'
 baseline=[]
 old=read(ROOT/'evidence/three-gbps-experiment-20261027/microled-summary.json')
 for rte in 'ABC':
  r=chosen(rec,rte,200,200);o=next(x for x in old['records'] if x['route']==rte and x['group']=='baseline' and x['corner']=='typical')
  baseline.append([rte,o['stages']['full']['bit_errors'],r['bit_errors'] if r else '待运行',f"{r['energy_positive_pJ_per_attempted_payload_bit']:.6f}" if r else '待运行',r['min_time_margin_ps'] if r else '待运行'])
 basetext=table(['路线','历史错误 /4096','新重跑错误 /4096','新正向 pJ/尝试净位','新时间余量 /ps'],baseline)
 basetext+='\n\n[原生求解复现回执](../../../evidence/microled-dynamic-v1/electrical-baseline-reproduction.json)独立核对样本数、七端口能量、器件端压和旧接收判决；新增导出电压用于诊断，不改变电路参数。'
 rows=[]
 for cap in [10,50,200,800,0]:
  for rte in 'ABC':rows.append([rte,cap]+[measurement(chosen(rec,rte,cap,tau)) for tau in [0,25,75,200]])
 matrix=image('sensitivity-margin.png','图 3｜三路线使用相同色标与 RX；这是负载假设扫描，不是实测器件性能。')
 matrix+='\n每格为 **观察错误数 / 最小有符号幅度 µAeq / 最小单侧时间 ps**。幅度需≥7.5 µAeq、时间需≥100 ps，并满足其余接收与电气筛查。\n\n'
 matrix+=table(['路线','C / fF','τ=0 ps *','τ=25 ps','τ=75 ps','τ=200 ps'],rows)
 matrix+='\n\n完整记录与精度见[RX 矩阵 CSV](../../../evidence/microled-dynamic-v1/rx-matrix.csv)。* 0 fF 或 0 ps 为理想限制控制，不能据此宣称器件可制造。'
 eyetext=image('paired-eyes.png','图 4｜上排旧200 fF/200 ps，下排另一假设10 fF/25 ps；共同纵轴和±270.27 ps观察窗，虚线标±100 ps；展示80个窗口，指标取全部验证位。C符号UI为540.54 ps，A/B为270.27 ps。')
 stage_rows=[]
 for rte in 'ABC':
  for cap in [200,10]:
   stage_rows.append([rte,cap,measurement(chosen(rec,rte,cap,0,stage='electrical')),measurement(chosen(rec,rte,cap,0)),measurement(chosen(rec,rte,cap,200))])
 eyetext+=table(['路线','C / fF','仅电气','电气+同 RX（τ=0）','电气+光响应200ps+同 RX'],stage_rows)
 ab=chosen(rec,'A',10,0,stage='electrical');aa=chosen(rec,'A',10,0)
 be=chosen(rec,'B',10,0,stage='electrical');bf=chosen(rec,'B',10,0)
 ce=chosen(rec,'C',10,0,stage='electrical')
 if all(x is not None for x in [ab,aa,be,bf,ce]):
  eyetext+=f"\n\n**分层结果怎样解释。** 在10 fF假设下，A的仅电气观察错误为{ab['bit_errors']}位，加入同一RX后为{aa['bit_errors']}位：当前输出波形及其与RX的配合仍有问题，不能只把光响应做快。B的仅电气为零观察错误，但最小时间仅{be['min_time_margin_ps']:.2f} ps；加入同RX后幅度仅{bf['min_signed_margin_uA']:.2f} µAeq、时间{bf['min_time_margin_ps']:.2f} ps，仍达不到两项门槛。C仅电气仍有{ce['bit_errors']}位错误，需继续分离译码、单位电流建立和电平间串扰；这里没有把某一个内部机制当成已经独立证实的唯一原因。\n"
  eyetext+='\n完整矩阵中0 fF/0 ps控制仍未恢复所有联合门槛，排除了“只减小并联电容就足够”的解释；但它保留真实Driver、封装和固定RX，不能进一步断言所有电路或接收方法都不可行。\n'
 controls=rx.get('ideal_conduction_controls',[])
 if isinstance(controls,dict):controls=controls.get('records',[])
 if controls:
  eyetext+='\n\n**固定接收规则本身的控制实验。** 另外给出具有20 ps线性边沿的理想导电电流，全帧和接收规则完全相同。它不含真实 Driver，也没有可比较的电路取能。\n\n'
  eyetext+=table(['格式','光响应 τ /ps','错误 /4096','幅度 /µAeq','时间 /ps','原接收筛查'],[[r['modulation'],r['optical_tau_ps'],r['bit_errors'],f"{r['min_signed_margin_uA']:.3f}",f"{r['min_time_margin_ps']:.3f}",'通过' if r['passed'] else '未通过'] for r in controls])
  eyetext+='\n\n这些是特定波形和既定幅度优先训练规则的结果，不是任意波形的可行性上界。零观察错误仍可能不满足100 ps时间门槛；τ更短也未保证所有指标单调改善。因此，不能把每个失败都归因于 Driver 或 LED。'
 energy_rows=[]
 for rte in 'ABC':
  for cap in [200,10,0]:
   r=chosen(rec,rte,cap,75)
   if r:energy_rows.append([rte,cap,f"{r['energy_positive_pJ_per_attempted_payload_bit']:.6f}",f"{r['energy_returned_pJ_per_attempted_payload_bit']:.6f}",f"{r['energy_net_pJ_per_attempted_payload_bit']:.6f}",f"{r['mean_LED_conduction_uA']:.3f}"])
 energy=image('energy-ports.png','图 5｜七输入端口正向取能分解；DATA 合并 D0/D1/DISABLE，返回能量另外列出。')
 energy+=table(['路线','C / fF','正向 pJ/尝试净位','返回 pJ/尝试净位','净值 pJ/尝试净位','平均导电 /µA'],energy_rows)
 a0=chosen(rec,'A',200,75);a1=chosen(rec,'A',10,75)
 if a0 and a1:
  ep=(a1['energy_positive_pJ_per_attempted_payload_bit']/a0['energy_positive_pJ_per_attempted_payload_bit']-1)*100
  en=(a1['energy_net_pJ_per_attempted_payload_bit']/a0['energy_net_pJ_per_attempted_payload_bit']-1)*100
  energy+=f"\n\n例如A从200 fF到10 fF，正向取能变化{ep:.2f}%，净取能变化{en:.2f}%；返回能量也同时改变。B/C在表中变化很小，与持续尾流、参考和数字等取能仍然存在相符；仅凭这组相关变化不能给出各内部损耗的唯一分解。所有这些点还需通过相同接收条件，才能讨论有效交付能效。\n"
 pvt=[]
 for corner in ['ss','ff']:
  for cap in [200,10]:
   for rte in 'ABC':
    r=chosen(rec,rte,cap,75,corner=corner)
    if r:pvt.append([corner,rte,cap,measurement(r),r['device_voltage_pass'],f"{r['max_body_forward_V']:.3f}"])
 fails=table(['组合条件','路线','C / fF','错误 / 幅度 / 时间（τ=75ps）','MOS端压筛查','最大体结正偏 /V'],pvt)
 fails+='\n\n这里 τ=75 ps 只是列示相同假设，未根据哪个结果更好而逐角选择。其他光响应和电气失败见完整矩阵。SS/FF 的 LED 光学温漂仍未建模。'
 bodyrows=[]
 for route in 'ABC':
  for cap in [200,10,0]:
   rr=[x for x in e['records'] if x['route']==route and x['case'].get('kind','transient')!='dc' and x['case']['corner']=='typical' and abs(x['case']['led_cap_F']*1e15-cap)<1e-7 and x['case']['steps_per_symbol']==40]
   if rr:
    q=read(ROOT/rr[0]['result_path']);dev=max(q['metrics']['stress'],key=lambda z:z['max_body_forward_V'])
    bodyrows.append([route,cap,dev['instance'],f"{dev['max_body_forward_V']:.3f}",rr[0]['device_voltage_passed']])
 fails+='\n\n**端对电压通过不等于体结/可靠性通过。** 下面单独列出同一TT帧的最大体结正向偏置及器件。较小电容可能暴露新的切换过冲；没有匹配工艺的可靠性规则，不能把此类点当作产品候选。\n\n'
 fails+=table(['路线','C /fF','最大体结正偏器件','正偏 /V','原MOS端对筛查'],bodyrows)
 fails+='\n\n体结正偏定义与栅压不同：NMOS取 `max(VB−VS, VB−VD)`，PMOS取 `max(VS−VB, VD−VB)`。正值表示相应体PN结受到正向偏置。原有端对筛查检查的是任意两端电压差上限，两者不能互相代替。A小电容与C译码器的这些现象，需要在后续修改电平兼容、回路与体端连接后独立复验；本文不依据该现象直接选B。\n'
 fails+='\n具体连接也可回到源网表检查：A的 `XPOUT` 为 D=OUT、G=CTRL、S=B=VH；C的 `XORPA` 为 D=P_OR、G=D1、S=B=VDD。两只PMOS的源与体同网，因此记录到的正偏来自漏端瞬间高于体端。这里记录的是电压现象；各耦合路径、电荷注入和体结电流的贡献仍需额外内部节点/电流探针实验，不能仅由一个峰值断言唯一原因。\n'
 valid='数值复核分别报告状态积分、旧基线复现、DC电容控制和 S40/S80 最大步长减半。它们验证数值路径，不替代新实测参数。详见 [RX 验证](../../../evidence/microled-dynamic-v1/rx-validation.json)和[电气回执](../../../evidence/microled-dynamic-v1/electrical-summary.json)。'
 hs=rx.get('halfstep_checks',[])
 if hs:
  valid+=f"\n\n当前 {len(hs)} 组 τ 条件的半步长检查：幅度变化最大 {max(abs(v['amplitude_delta_uA']) for v in hs):.6f} µAeq，时间变化最大 {max(abs(v['time_delta_ps']) for v in hs):.6f} ps，正向取能变化最大 {max(abs(v['energy_positive_delta_percent']) for v in hs):.6f}%。观察错误数变化最大 {max(abs(v['bit_error_delta']) for v in hs)} 位；通过/失败判定保持不变的条件为 {sum(v['pass_unchanged'] for v in hs)}/{len(hs)}。这些差异完整保留，不能写成所有数值完全相等。"
 if e['missing'] or rx.get('analysis_failures') or rx.get('electrical_failures'):valid+='\n\n**当前仍有未完成或失败记录；不能按完整矩阵闭合解读。**'
 reproduce='复现说明、工具/源码哈希和备份范围见[reproduce.md](reproduce.md)。[模型卡](../../../analog/models/microled_dynamic_v1/MODEL_CARD.md)、[频域验证](../../../evidence/microled-dynamic-v1/fit-validation.json)、[电气矩阵](../../../evidence/microled-dynamic-v1/electrical-summary.json)与[接收矩阵](../../../evidence/microled-dynamic-v1/rx-summary.json)均可检查。'
 return {'SUMMARY':summary,'DC':dctext,'FIT':fit_section(f),'BASELINE':basetext,'MATRIX':matrix,'EYES':eyetext,'ENERGY':energy,'FAILURES':fails,'VALIDATION':valid,'REPRODUCE':reproduce}

def main():
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--diagram-only',action='store_true');args=ap.parse_args()
 FIG.mkdir(parents=True,exist_ok=True);fonts();circuit()
 if args.diagram_only:return
 e=read(EV/'electrical-summary.json');rx=read(EV/'rx-summary.json');f=read(EV/'fit-summary.json')
 plots_fit(f);matrix_plots(rx['records']);eyes(rx['records']);energy_plot(e)
 text=(DOC/'report-template.md').read_text()
 for key,value in sections(e,rx,f).items():text=text.replace('<!-- '+key+' -->',value)
 assert '<!--' not in text
 (DOC/'README.md').write_text(text)
 parser=markdown.Markdown(extensions=['tables','fenced_code','toc'],extension_configs={'toc':{'toc_depth':'2-3'}})
 body=parser.convert(text);body=re.sub(r'<img([^>]*?) src="([^"]+)"([^>]*?)>',r'<a href="\2" title="查看原尺寸"><img\1 src="\2"\3></a>',body)
 body=body.replace('<h2','<details><summary>阅读目录</summary>'+parser.toc+'</details><h2',1)
 # Reuse the established project report presentation; do not modify prior documents.
 spec=__import__('importlib.util',fromlist=['']).spec_from_file_location('prior_report',ROOT/'scripts/microled_device_codesign_20261029/report.py')
 prior=__import__('importlib.util',fromlist=['']).module_from_spec(spec);spec.loader.exec_module(prior)
 page='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>20µm动态负载与A/B/C净3.2Gb/s验证</title><style>'+prior.CSS+'</style></head><body><header>OPEN MICROLED DRIVER ASIC · 2026-11-08 · 动态负载验证</header><main>'+body+'</main></body></html>'
 (DOC/'index.html').write_text(page)
 print(json.dumps({'electrical_completed':e['completed'],'planned':e['planned'],'rx_records':len(rx['records']),'status':'report generated; completion requires frozen full-matrix validation'},ensure_ascii=False))

if __name__=='__main__':main()
