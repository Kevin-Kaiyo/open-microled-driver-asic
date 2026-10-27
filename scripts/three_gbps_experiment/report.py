#!/usr/bin/env python3
"""Render source-bound tables and figures from the new experiment receipts."""
from pathlib import Path
import hashlib, importlib.util, json, os, re
import markdown
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/three-gbps-experiment-20261027'
EV=ROOT/'evidence/three-gbps-experiment-20261027'
FIG=OUT/'figures'
COLORS=['#267b82','#4b73a3','#b57840']

def read(p):return json.loads(Path(p).read_text())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def mod(p,name):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def table(header,rows):return '\n'.join(['| '+' | '.join(header)+' |','|'+'|'.join(['---']*len(header))+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows])+'\n'
def image(name,caption):return f'<figure><a href="figures/{name}.png"><img src="figures/{name}.png" alt="{caption}"></a><figcaption>{caption}</figcaption></figure>\n'
def save(fig,name):
    fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(FIG/(name+'.'+ext),dpi=150,metadata={'Date':'2026-10-27'})
    plt.close(fig)

def case_label(x):
    if x.get('stimulus_seed')==0x1ACE:return 'TT 3.2 / 重叠相移对照'
    if x.get('stimulus_seed')==0x57AE:return 'TT 3.2 / 非重叠窗口'
    return x['case'].replace('frame-','').replace('-r1','')

def microled(m):
    baseline=[x for x in m['records'] if x['group']=='baseline'];assert len(baseline)==9
    rows=[]
    for x in baseline:
        s=x['stages']['full'];rows.append([x['name'].split('-')[1]+'/'+x['route'],s['bit_errors'],f"{s['min_signed_margin_uA']:.2f}",f"{s['min_time_margin_ps']:.2f}",f"{x['energy_pJ_netbit']:.4f}",f"{x['max_body_forward_V']:.3f}"])
    text='**新跑的九个原条件目标速率点全部未通过接收筛查。** 以下 pJ/bit 对应失败工作点，不能称为有效交付能效。\n\n'
    text+=table(['条件/路线','错误 bit /4096','最小判决距离 µA','单侧时间 ps','正向 pJ/尝试 bit','最大体结正偏 V'],rows)
    tt=[x for x in baseline if x['corner']=='typical'];caps=[x for x in m['records'] if x['group']!='baseline']
    rows=[]
    for route in 'ABC':
        b=next(x for x in tt if x['route']==route);c=next(x for x in caps if x['route']==route)
        rows.append([route,b['stages']['electrical']['bit_errors'],c['stages']['electrical']['bit_errors'],b['stages']['full']['bit_errors'],c['stages']['full']['bit_errors']])
    text+='\n'+table(['TT 诊断','200 fF 电气错误','0 fF 电气错误','200 fF 完整错误','0 fF 完整错误'],rows)
    text+='\n去掉外接电容后，各电路仍未通过完整筛查；A 的部分指标甚至更差，说明移除外接 C 不足以解决电路动态与波形问题。错误数不可按各层简单相减：滤波会改变波形形状，每层独立训练相位，可能消除部分尖峰，也可能加重码间干扰。\n\n'
    rows=[]
    for x in m['ideal_controls']:
        label='理想导电电流波形' if x['kind']=='ideal_conduction_waveform' else f"理想 sink + {x['capacitance_F']*1e15:g} fF"
        s=x['stages']['full'];rows.append([label,{'A':'NRZ','C':'PAM4'}.get(x['route'],x['route']),x['stages']['electrical']['bit_errors'],s['bit_errors'],f"{s['min_signed_margin_uA']:.3f}",f"{s['min_time_margin_ps']:.2f}"])
    text+=table(['隔离输入/负载','格式','电气错误','完整代理错误','完整距离 µA','完整时间 ps'],rows)
    text+='\n理想波形对照不是所有真实驱动的严格性能上界；它只检验未加预加重的固定两/四电平。最细 1.25 ps 参考网格下，理想 NRZ 完整代理仍只有约 0.499 µA、26.06 ps；PAM4 仍有 215 bit 错误。即使 MOS 瞬间切换，这组原负载/代理也没有自动满足目标。\n\n'
    stages=['electrical','optical_only','rx_only','full'];labels=['导电电流','仅光学极点','仅 RX 极点','完整代理']
    fig,axs=plt.subplots(1,2,figsize=(11,4.4))
    for j,x in enumerate(sorted(tt,key=lambda x:x['route'])):
        axs[0].plot(labels,[x['stages'][s]['min_signed_margin_uA'] for s in stages],'o-',color=COLORS[j],label=x['route'])
        axs[1].plot(labels,[x['stages'][s]['bit_errors'] for s in stages],'o-',color=COLORS[j],label=x['route'])
    axs[0].axhline(7.5,color='#6d7a80',ls='--',label='7.5 µA 门槛');axs[0].axhline(0,color='#aab3b5',lw=.7)
    axs[0].set(ylabel='最小有符号判决距离 / µA',title='TT / 净 3.2 Gb/s：距离为负表示越过错误边界')
    axs[1].set(ylabel='错误 bit / 4096',title='各观察点独立用训练段选相位')
    for ax in axs:ax.grid(alpha=.2);ax.legend()
    save(fig,'microled-stages');text+=image('microled-stages','实际 A/B/C 晶体管波形的分层诊断；两个面板共享相同条件。旁路不是新物理实现。')
    # Two-symbol optical-proxy eyes, aligned to each route's frozen training phase.
    rx=mod(ROOT/'scripts/fair_driver_v1/receiver_equal_latency_v2.py','report_rx');fig,axs=plt.subplots(1,3,figsize=(11.5,3.8))
    for ax,x,color in zip(axs,sorted(tt,key=lambda x:x['route']),COLORS):
        a=np.loadtxt((ROOT/x['source_result']).with_name('waveform.dat.gz'),skiprows=1)
        _,y=rx.filter_trace(a[:,0],a[:,1]);ui=(2 if x['route']=='C' else 1)/3.7e9;delay=x['stages']['full']['delay_ps']*1e-12
        phase=np.linspace(-.5,1.5,161);start=288 if x['route']=='C' else 576
        for k in range(start,start+128):ax.plot(phase,np.interp((k+phase)*ui+delay,a[:,0],y*1e6),color=color,alpha=.16,lw=.6)
        for threshold in ([37.5,62.5,87.5] if x['route']=='C' else [62.5]):ax.axhline(threshold,color='#666',ls='--',lw=.8)
        ax.axvline(0,color='#202f36',lw=.8);ax.set(title=x['route']+' / '+('PAM4' if x['route']=='C' else 'NRZ'),xlabel='相对冻结采样点 / symbol UI',ylabel='RX 代理 / µA');ax.grid(alpha=.12)
    save(fig,'microled-eyes');text+=image('microled-eyes','TT 完整代理眼图，展示前 128 个验证符号；错误数和最差余量使用全部 4096 bit 计算。纵轴是等效电流，不是光功率。')
    checks=read(EV/'microled-validation.json');delta=max(abs(x['capacitance_DC_delta_uA']) for x in m['dc_capacitance_checks'])
    text+=f'\n**检查范围：**16 个 DC 点，200/0 fF 的最大 DC 电流差 {delta:.3g} µA；三条 TT 路线把最大步长从 UI/40 收紧至 UI/80，原数值门槛均满足、错误数不变。原模型及接收源未修改。\n\n'
    text+='C 的 TT 体结正偏峰值约 0.858 V；A 的 0 fF 对照约 0.731 V。端子两两压差筛查不能替代体结/可靠性签核。原条件和对照都不能因求解成功而宣称电气安全。\n'
    return text

def vcsel(v):
    rows=[]
    for corner in ['TT','SS','FF']:
        d=[next(x for x in v['dc'] if x['case']==f'dc-final-{corner}-{level}') for level in ['low','high']]
        rows.append([corner,f"{d[0]['current_mA']:.4f}",f"{d[1]['current_mA']:.4f}",f"{d[0]['reference_current_mA']*1000:.2f}"])
    text='### 4.1 校准后冻结，角落不重新调参\n\n'+table(['GF180 条件','低档 mA','高档 mA','参考 µA'],rows)
    text+='\nTT/25°C/3.3 V，SS/125°C/2.97 V，FF/−40°C/3.63 V。这里同时改变了 MOS 角、温度与供电；VCSEL 静态曲线仍固定 25°C，不能称为真实光器件的全温度验证。SS 高档下降，FF 高档越过公开图域，说明电阻参考、镜像输出阻抗和顺从电压需要继续改进。\n\n'
    tol={x['case']:x for x in v['dc'] if x['case'].startswith('dc-R')}
    if tol:
        text+=f"独立参考电阻 ±1%（TT）对照：低档 {tol['dc-Rplus1-low']['current_mA']:.4f}–{tol['dc-Rminus1-low']['current_mA']:.4f} mA，高档 {tol['dc-Rplus1-high']['current_mA']:.4f}–{tol['dc-Rminus1-high']['current_mA']:.4f} mA。这是电阻容差，不是 MOS 工艺角，也没有覆盖片上电阻温漂或器件失配。\n\n"
    text+='## 5．VCSEL：实际瞬态结果与接收训练对照\n\n'
    baselines=[x for x in v['cases'] if x['analysis_label']=='baseline']
    rows=[]
    for x in baselines:
        name=case_label(x)
        rows.append([name,x['errors'],f"{x['min_signed_margin_uAeq']:.2f}",f"{x['time_margin_ps']:.2f}",f"{x['energy']['positive_pJ_per_offered_payload_bit']:.4f}",'通过' if x['device_screen_passed'] else '失败','域内' if x['domain']['IV_outside_time_fraction']==0 and x['domain']['PI_above_graph_time_fraction']==0 else '越域'])
    text+=table(['条件 / 净 Gb/s','错误 /4096','距离 µAeq','单侧时间 ps','正向 pJ/尝试 bit','端压筛查','静态模型域'],rows)
    text+='\n这是 **v2 幅度优先训练的原结果**。TT 3.2 Gb/s 零观察错误，但约 87 ps 小于 100 ps；SS 高档光功率代理低于固定判决阈值，所以改变采样相位无法补偿偏置/电流不足。FF 虽有约 106 ps，却有约 3.822 V 的端压峰值，超过本轮 3.63 V 筛查值；约 48.94% 时间超过 P–I 的 7.5 mA 上界，不能使用该点证明高速能力。\n\n'
    text+='### 5.1 低速时序余量反而较小，说明什么\n\nTT 0.8 Gb/s 的 v2 结果同样无错误，却只有约 54 ps。原算法先最大化最差幅度距离，仅在幅度几乎并列时考虑时间。带共振的波形可能让算法选中接近过冲峰值的相位。因此不能把这一非单调现象说成驱动器的物理速率上限。\n\n'
    text+='为验证这一机制，本轮在观察失败后**另立 v3 诊断规则**：每个候选相位计算 `min(训练幅度距离/7.5 µAeq, 训练时间余量/100 ps)`，取最大者，完全并列时取最早相位。仍只使用 448 bit 训练，阈值、100 ps 门槛、8 ns 搜索范围、5 ps 网格、滤波和能量都不变；验证段不参与选择。v2 数据保留，v3 不覆盖原结论，也不是硬件 CDR。最初的 v3 对照复用了已看过的验证帧，所以属于事后方法诊断，不能称为全流程预注册的独立确认；后续另立非重叠 PRBS 窗口对照。\n\n'
    v3=[x for x in v['cases'] if x['analysis_label'].startswith('v3')]
    assert len(v3)>=8,'Wait for all paired diagnostic records'
    rows=[]
    for x in v3:
        old_label={'v3-diagnostic':'baseline','v3-optical8-control':'optical8-control','v3-rx1-control':'rx1-control'}[x['analysis_label']]
        old=next(a for a in v['cases'] if a['case']==x['case'] and a['analysis_label']==old_label)
        rows.append([case_label(x)+('/'+old_label if old_label!='baseline' else ''),f"{old['time_margin_ps']:.2f}",f"{x['time_margin_ps']:.2f}",f"{x['min_signed_margin_uAeq']:.2f}",x['errors'],'条件性通过' if x['combined_screen_passed'] else '未通过'])
    text+=table(['同一波形/模型','v2 时间 ps','v3 时间 ps','v3 距离 µAeq','v3 错误','通信+端压+图域'],rows)
    holdout=next(x for x in v3 if x.get('stimulus_seed')==0x57AE)
    text+=f"\n**非重叠序列复核：**冻结电路、模型与 v3 后，新增 PRBS15 周期偏移 8192 的 seed `0x57AE`，完整窗口与原帧不重叠。新帧 {holdout['errors']}/4096 错误、{holdout['time_margin_ps']:.2f} ps、{holdout['quantities']['optical_margin_min_mW']:.4f} mW 模型功率余量、{holdout['energy']['positive_pJ_per_offered_payload_bit']:.4f} pJ/尝试 payload bit。支持该条件下结果可在另一段码型保持；仍不是独立随机噪声 BER 实验。先试的 seed `0x1ACE` 被审计发现有 1582 个验证 bit 的周期位置重叠，保留为相移对照，没有当作非重叠确认。\n\n"
    text+='\n“条件性通过”只表示该代理、短帧、端压筛查和图读域满足本轮门槛，不含真实相位响应、全温度、抖动噪声、启动或光学 BER。MicroLED 全部 12 个基线/零电容点的**完整代理阶段**，在原网格内的最佳训练幅度距离均为负，换成这种联合评分也不能满足固定幅度门槛。\n\n'
    tt=next(x for x in baselines if x['case']=='frame-TT-3p2-r1');p=np.load(ROOT/tt['plot_data'])
    fig,axs=plt.subplots(3,1,figsize=(10.6,7.0),sharex=True);time=(p['trace_t_s']-p['trace_t_s'][0])*1e9;mask=time<=4
    axs[0].plot(time[mask],p['trace_gp_V'][mask],label='GP');axs[0].plot(time[mask],p['trace_gn_V'][mask],label='GN',alpha=.8);axs[0].set(ylabel='栅电压 / V')
    axs[1].plot(time[mask],p['trace_current_A'][mask]*1e3,color=COLORS[0],label='VCSEL 导电电流');axs[1].set(ylabel='电流 / mA')
    axs[2].plot(time[mask],p['trace_optical_W'][mask]*1e3,label='发射端光功率代理');axs[2].plot(time[mask],p['trace_rx_W'][mask]*1e3,label='5 GHz RX 后代理');axs[2].set(ylabel='代理功率 / mW',xlabel='验证区局部时间 / ns')
    for ax in axs:ax.grid(alpha=.2);ax.legend(loc='upper right',fontsize=9)
    fig.suptitle('TT / 净 3.2 Gb/s：晶体管模型电气输出与假设光学响应分开展示');save(fig,'vcsel-waveforms')
    text+=image('vcsel-waveforms','GP/GN 与导电电流来自晶体管瞬态；光功率是公开曲线约束的研究代理，未测量。取验证区前约 4 ns 展示。')
    fig,axs=plt.subplots(1,3,figsize=(11.5,4.1))
    for ax,corner in zip(axs,['TT','SS','FF']):
        x=next(a for a in v3 if a['case']==f'frame-{corner}-3p2-r1' and a['analysis_label']=='v3-diagnostic');q=np.load(ROOT/x['plot_data'])
        for row in q['eye_rx_power_W']:ax.plot(q['eye_phase_UI'],row*1e3,color=COLORS[0],alpha=.15,lw=.6)
        ax.axhline(2.55083655,color='#666',ls='--');ax.axvline(0,color='#222',lw=.8);ax.set(title=f"{corner}: {x['errors']} 错误 / {x['time_margin_ps']:.1f} ps",xlabel='相对 v3 采样点 / UI',ylabel='RX 功率代理 / mW',ylim=(.75,5.3));ax.grid(alpha=.15)
    save(fig,'vcsel-eyes');text+=image('vcsel-eyes','v3 训练后冻结相位的眼图：每图展示前 160 个验证 bit；数值取全验证帧。FF 的图外高功率不代表有效器件能力。')
    fig,ax=plt.subplots(figsize=(8.5,3.9));ports=list(tt['energy_by_port']);energies=[tt['energy_by_port'][k]['positive_J']/4096*1e12 for k in ports]
    bars=ax.bar(ports,energies,color=['#267b82','#4b73a3','#b57840','#8b9aa0','#8b9aa0']);ax.bar_label(bars,fmt='%.3f',padding=3);ax.set(ylabel='正向 pJ / 尝试 payload bit',ylim=(0,max(energies)*1.18),title='VCSEL TT 3.2 Gb/s：五端口能量，参考与 dummy 均在内');save(fig,'vcsel-energy')
    text+=image('vcsel-energy','按原生时间样点分段线性功率的过零点精确积分。VLASER 包括 VCSEL、dummy 和串联损失；VDD 包括两条真实缓冲链。v2/v3 共用同一电路能量。')
    text+='\n数值检查包括 TT SPICE 最大步长 UI/40→UI/80，光学重采样 2.5→1.25 ps，以及独立输入能量重算。门槛附近的时间差需保留到后续真实抖动预算；不能把代理算法的数字精度当成器件模型精度。\n'
    return text

def main():
    FIG.mkdir(parents=True,exist_ok=True)
    font=Path(os.environ.get('MICROLED_REPORT_FONT',str(ROOT/'build/fair-driver-v1/report-font/NotoSansCJKsc-Regular.otf')))
    if not font.is_file():raise FileNotFoundError('Set MICROLED_REPORT_FONT to an installed CJK font file; see reproduce.md')
    font_manager.fontManager.addfont(font)
    plt.rcParams.update({'font.family':font_manager.FontProperties(fname=font).get_name(),'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','svg.hashsalt':'three-gbps-experiment-20261027'})
    m=read(EV/'microled-summary.json');v=read(EV/'vcsel-driver-summary.json');assert not m['missing'] and not m['failures']
    path=OUT/'README.md';body=path.read_text()
    # Named generated blocks retain a marker pair for repeatable rendering.
    pieces={'MICROLED_RESULTS':microled(m),'VCSEL_RESULTS':vcsel(v),
      'MODEL_RESULTS':'<figure><img src="../../../evidence/three-gbps-experiment-20261027/vcsel-model/model-checks.png" alt="图读静态数据、拟合幅频响应与研究代理阶跃"><figcaption>派生图：左上 I–V 编码与图读点；右上 P–I；左下幅频形状与假设对照；右下为代理阶跃。DC/AC 和滤波实现自洽检查通过，不等于同器件电光联合标定。<a href="../../../analog/models/vcsel_research_20261027/MODEL_CARD.md">模型卡与逐项来源</a>。</figcaption></figure>',
      'REPRODUCIBILITY':'详见 [MicroLED 完整数值](../../../evidence/three-gbps-experiment-20261027/microled-summary.json)、[数值检查](../../../evidence/three-gbps-experiment-20261027/microled-validation.json)、[VCSEL 完整数值](../../../evidence/three-gbps-experiment-20261027/vcsel-driver-summary.json)、[VCSEL 独立复核](../../../evidence/three-gbps-experiment-20261027/vcsel-independent-review.md)、[逐器件图源绑定](../../../evidence/three-gbps-experiment-20261027/circuit-figures.json)。\n\n源脚本位于 `scripts/three_gbps_experiment/`；原网表、日志、校准中间点、失败、全帧压缩波形及运行快照保留在 `build/three-gbps-experiment-20261027/`。新报告的构建命令：\n\n```sh\nbuild/layout/venv/bin/python scripts/three_gbps_experiment/diagrams.py\nbuild/layout/venv/bin/python scripts/three_gbps_experiment/report.py\n```\n\n[复现与备份说明](reproduce.md)说明冻结输入、依赖、Release 恢复及与独立机器验证的区别。'}
    for key,value in pieces.items():
        pattern=r'<!-- '+key+r' -->(?:.*?<!-- END '+key+r' -->)?'
        body,n=re.subn(pattern,lambda _:f'<!-- {key} -->\n\n{value}\n<!-- END {key} -->',body,flags=re.S);assert n==1
    path.write_text(body)
    css=re.search(r'<style>.*?</style>',(ROOT/'docs/research/fair-driver-comparison-20261025/index.html').read_text(),re.S).group(0)
    rendered=markdown.markdown(body,extensions=['tables','fenced_code','toc'])
    html='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>净3.2Gb/s MicroLED与VCSEL实验报告</title>'+css+'</head><body><main><nav><a href="../three-gbps-vcsel-20261027/index.html">文献背景</a><a href="README.md">完整文字</a><a href="reproduce.md">复现说明</a></nav>'+rendered+'</main></body></html>\n'
    (OUT/'index.html').write_text(html)
    selected=sorted(set([Path(__file__),OUT/'README.md',OUT/'index.html']+list(FIG.glob('*'))+[EV/'microled-summary.json',EV/'microled-validation.json',EV/'vcsel-driver-summary.json',EV/'circuit-figures.json']))
    (EV/'report-manifest.json').write_text(json.dumps({'evidence_level':'SCHEM+research-proxy; no new layout or optical measurement','files':[dict(path=str(p.relative_to(ROOT)),sha256=sha(p),bytes=p.stat().st_size) for p in selected]},ensure_ascii=False,indent=2)+'\n')
    print('Rendered '+str(OUT/'index.html'))

if __name__=='__main__':main()
