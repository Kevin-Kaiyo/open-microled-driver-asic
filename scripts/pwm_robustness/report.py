#!/usr/bin/env python3
"""Render evidence-backed PWM subsection and verify frozen raw artifacts."""
from pathlib import Path
import csv,gzip,hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2]
FONT=ROOT/'build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf'
font_manager.fontManager.addfont(str(FONT))
FONT_NAME=font_manager.FontProperties(fname=str(FONT)).get_name()
W=ROOT/'build/pwm-robustness/20261024';E=ROOT/'evidence/pwm-robustness/20261024'
D=ROOT/'docs/research/driver-robustness-20261024';F=D/'pwm-figures';F.mkdir(parents=True,exist_ok=True)
def read(n): return json.loads((W/n/'result.json').read_text())
def raw(n):
    with gzip.open(W/n/'waveform.dat.gz') as f:return np.atleast_2d(np.loadtxt(f,skiprows=1))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
rows=[json.loads(p.read_text()) for p in sorted(W.glob('*/result.json'))]
by={r['case']['name']:r for r in rows}
validation=[]
for r in rows:
    p=W/r['case']['name'];checks={'deck_sha256':sha(p/'testbench.spice')==r['deck_sha256'],'log_sha256':sha(p/'ngspice.log')==r['log_sha256']}
    if r['completed']:
        h=hashlib.sha256()
        with gzip.open(p/'waveform.dat.gz') as f:
            while chunk:=f.read(4*1024*1024):h.update(chunk)
        checks['raw_gzip_roundtrip_sha256']=h.hexdigest()==r['raw_sha256'];checks['compressed_sha256']=sha(p/'waveform.dat.gz')==r['raw_gzip_sha256']
    validation.append(dict(name=r['case']['name'],checks=checks,passed=all(checks.values())))
num=[]
for a,b in [('step_ref_10ns','step_ref_10ns_fine'),('step_all_10ns_package_stress','step_all_10ns_package_stress_fine'),('step_ref_10ns_filtered8p2n','step_ref_10ns_filtered8p2n_fine')]:
    if b not in by:continue
    x,y=raw(a),raw(b);t=np.unique(np.r_[x[:,0],y[:,0]]);error=np.abs(np.interp(t,x[:,0],x[:,1])-np.interp(t,y[:,0],y[:,1]));peak=float(error.max());di=abs(by[a]['excursion_pct_of_pre_step']-by[b]['excursion_pct_of_pre_step']);ds=abs(by[a]['settle_after_restore_0p5pct_s']-by[b]['settle_after_restore_0p5pct_s']);num.append(dict(a=a,b=b,max_interpolated_current_difference_a=peak,excursion_difference_percentage_points=di,settle_difference_s=ds,passed=peak<.2e-6 and ds<10e-9))
validation_summary=dict(date='2026-10-24',case_count=len(rows),artifact_checks=validation,numerical_comparisons=num,passed=all(x['passed'] for x in validation) and all(x['passed'] for x in num),note='Artifact integrity and selected timestep agreement only; this is not an all-circuit-criteria pass.')
save(E/'validation.json',validation_summary)
fields=['name','kind','completed','passed','current_uA','error_pct','min_uA','max_uA','excursion_pct','settle_us','startup_peak_nA','fault_shutdown_ns','pwm_d1_error_pct','terminal_pair_count']
with (E/'compact-metrics.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for r in rows:
        w.writerow(dict(name=r['case']['name'],kind=r['case']['kind'],completed=r['completed'],passed=r.get('passed'),current_uA=r.get('current_a',0)*1e6 if 'current_a'in r else '',error_pct=r.get('error_pct',''),min_uA=r.get('current_min_a',0)*1e6 if 'current_min_a'in r else '',max_uA=r.get('current_max_a',0)*1e6 if 'current_max_a'in r else '',excursion_pct=r.get('excursion_pct_of_pre_step',''),settle_us=r.get('settle_after_restore_0p5pct_s',0)*1e6 if r.get('settle_after_restore_0p5pct_s') is not None else '',startup_peak_nA=r.get('held_fault_peak_a',0)*1e9 if r['case']['kind']=='startup'else '',fault_shutdown_ns=r.get('fault_to_safe_s',0)*1e9 if r.get('fault_to_safe_s')is not None else '',pwm_d1_error_pct=r.get('d1_charge_error_pct',''),terminal_pair_count=len(r.get('terminal_abs_peak_v',{}))//39))
plt.rcParams.update({'font.family':FONT_NAME,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'#fafbf9','axes.facecolor':'#fafbf9','axes.labelcolor':'#233343','text.color':'#233343','axes.edgecolor':'#8b979f','svg.fonttype':'path'})
fig,ax=plt.subplots(2,1,figsize=(9,5.7),sharex=True,gridspec_kw={'height_ratios':[1,2]})
for name,label,color in [('step_ref_10ns','原r5（理想供电）','#b74e4c'),('step_ref_10ns_filtered8p2n','芯片侧8.2 nF＋封装R/L','#3d6b9d'),('step_ref_10ns_filtered','芯片侧100 nF＋封装R/L','#168377')]:
    if name not in by:continue
    data=raw(name);ix=data[:,0]<=50e-6
    ax[0].plot(data[ix,0]*1e6,data[ix,8]-data[ix,12],label=label,color=color,lw=1.5)
    ax[1].plot(data[ix,0]*1e6,data[ix,1]*1e6,color=color,lw=1.5)
ax[0].set_ylabel('芯片侧参考供电 VREF（V）');handles,labels=ax[0].get_legend_handles_labels();ax[1].legend(handles,labels,loc='upper right',frameon=False,fontsize=8.8)
ax[1].axhspan(80,120,color='#3d6b9d',alpha=.07);ax[1].set_ylabel('LED支路电流（µA）');ax[1].set_xlabel('时间（µs）')
for a in ax:a.grid(alpha=.15);a.set_xlim(5,50)
fig.suptitle('100 µA显示PWM：参考供电跌落10%，边沿10 ns',fontsize=12);fig.tight_layout();fig.savefig(F/'pwm-reference-step.svg');fig.savefig(F/'pwm-reference-step.png',dpi=180);plt.close(fig)
fig,ax=plt.subplots(figsize=(8.5,4.8));col={'typical':'#3d6b9d','ss':'#b74e4c','ff':'#168377'}
for co in col:
    for s,ls in [('lo','--'),('hi','-')]:
        rr=[by[f'dc_cross_{co}_{t}_{s}'] for t in [0,27,85]]
        ax.plot([0,27,85],[r['error_pct'] for r in rr],color=col[co],ls=ls,marker='o',label=f'{"TT" if co=="typical" else co.upper()} / RSET{"低值" if s=="lo" else "高值"}')
for co in col:
    for s in ['lo','hi']:
        n=f'dc_cold_tc_independent_{co}_{s}'
        if n in by:ax.plot(0,by[n]['error_pct'],marker='D',mfc='white',mec=col[co],ls='none',label='冷端独立容差/温漂角' if co=='typical' and s=='lo' else None)
ax.axhspan(-5,5,color='#168377',alpha=.06);ax.axhline(-5,color='#8b979f',ls=':');ax.axhline(5,color='#8b979f',ls=':');ax.set_ylim(-7,7);ax.set_xlabel('温度（°C）');ax.set_ylabel('电流相对100 µA的误差（%）');ax.grid(alpha=.15);ax.legend(ncol=4,loc='upper center',fontsize=8.5,frameon=False);fig.suptitle('电阻容差/温漂×MOS×温度：电源固定3.3 V / 5 V',fontsize=11);fig.tight_layout();fig.savefig(F/'pwm-independent-resistor.svg');fig.savefig(F/'pwm-independent-resistor.png',dpi=180);plt.close(fig)
fig,ax=plt.subplots(figsize=(8.5,4.8));ax.axvspan(0,20,alpha=.06,color='#168377');ax.axhspan(0,5,alpha=.06,color='#168377');ax.axvline(20,color='#8b979f',ls='--');ax.axhline(5,color='#8b979f',ls='--')
for name,label,color in [('step_ref_10ns','原r5','#b74e4c'),('step_ref_10ns_filtered8p2n','8.2 nF名义值','#3d6b9d'),('step_ref_10ns_filtered8p2n_lo','8.2 nF: R-/C-','#3d6b9d'),('step_ref_10ns_filtered8p2n_hi','8.2 nF: R+/C+','#3d6b9d'),('step_ref_10ns_filtered','100 nF名义值','#168377'),('step_ref_10ns_filtered100n_lo','100 nF: R-/C-','#168377'),('step_ref_10ns_filtered100n_hi','100 nF: R+/C+','#168377')]:
    if name not in by:continue
    r=by[name];x=r['excursion_pct_of_pre_step'];y=r['settle_after_restore_0p5pct_s']*1e6;ax.scatter([x],[y],color=color,s=45);ax.annotate(label,(x,y),xytext=(5,7 if '_hi' in name else -13 if '_lo' in name else 0),textcoords='offset points',fontsize=8)
ax.set_xlim(0,56);ax.set_ylim(0,24);ax.set_xlabel('电流相对扰动前DC的最大偏离（%）');ax.set_ylabel('恢复至±0.5%的时间（µs）');ax.grid(alpha=.15);fig.suptitle('芯片端口RC折衷：20% / 5 µs是研究预算，非产品规格',fontsize=10);fig.tight_layout();fig.savefig(F/'pwm-filter-tradeoff.svg');fig.savefig(F/'pwm-filter-tradeoff.png',dpi=180);plt.close(fig)
# Startup placement diagnosis uses full raw, not only the selected plot window.
startup_diagnosis=[]
fig,ax=plt.subplots(3,1,figsize=(9,7.2),sharex=True)
for name,label,color in [('startup_package_stress_refined','未加滤波电容','#b74e4c'),('startup_filtered_refined','芯片端口100 nF','#3d6b9d'),('startup_board100n_wide','PCB侧（wide诊断求解）','#168377')]:
    if name not in by or not by[name]['completed']:continue
    a=raw(name);held=a[:,0]<=20e-6;cond=a[:,25]-a[:,26];pk=int(np.argmax(np.abs(a[held,1])));startup_diagnosis.append(dict(name=name,held_branch_peak_a=float(np.max(np.abs(a[held,1]))),held_conduction_peak_a=float(np.max(np.abs(cond[held]))),held_displacement_peak_a=float(np.max(np.abs(a[held,26]))),held_diegnd_peak_v=float(np.max(np.abs(a[held,12]))),branch_peak_time_s=float(a[held,0][pk])))
    mask=(a[:,0]>=1e-12)&(a[:,0]<=20e-6)
    ax[0].semilogx(a[mask,0]*1e6,a[mask,8]-a[mask,12],color=color,lw=1.3,label=label)
    ax[1].semilogx(a[mask,0]*1e6,a[mask,12]*1e3,color=color,lw=1.3)
    ax[2].semilogx(a[mask,0]*1e6,a[mask,1]*1e9,color=color,lw=1.3)
ax[0].set_ylabel('VREF－芯片VSS（V）');ax[1].set_ylabel('芯片VSS地弹（mV）');ax[2].set_yscale('symlog',linthresh=1);ax[2].set_ylabel('LED端口电流（nA，对称对数轴）');ax[2].set_xlabel('时间（µs，对数轴）');ax[2].axhline(1,color='#8b979f',ls=':');ax[2].axhline(-1,color='#8b979f',ls=':')
for a in ax:a.grid(alpha=.15)
ax[0].legend(frameon=False,fontsize=8,ncol=3);fig.suptitle('完整局部网格启动观测：PCB使用wide诊断求解，数值一致性仍未闭合',fontsize=11);fig.tight_layout();fig.savefig(F/'pwm-ground-return.svg');fig.savefig(F/'pwm-ground-return.png',dpi=180);plt.close(fig)
save(E/'startup-placement-diagnosis.json',dict(results=startup_diagnosis,note='Full 20us held-fault window; independently refined 0.1ps local startup mesh. Diode conduction = total diode current minus displacement current.'))
# Human-readable source-backed subsection, refreshed only after completed runs.
lines=['# PWM显示路线：100 µA参考源、独立保护及片外扰动','', '**结论：**39MOS原有完整PEX单像素可以作为本轮研究基线。精密片外RSET的确定性角落、供电扰动和封装R/L已补测；参考轨快速变化仍是主要电流扰动源。100Ω+100nF参考供电滤波可明显抑制瞬变，电容回流位置必须单独处理，代价是更长恢复时间。8.2nF名义点较快，但容差点越过本轮研究预算，不能宣布鲁棒性闭合。','', '## 1. 路线、负载与证据范围','', '本章只讨论显示PWM的100µA单像素。1MHz逻辑时钟、256µs帧和duty=1最小码电荷，与高速NRZ眼图、UI、接收门限无关。VSET=0.5V，RSET=5kΩ；误差放大器使SENSE跟随VSET，PREG/POUT形成参考电流，隔离传输门连接MREF/BIAS，MOUT控制LED支路。10管独立保护门、真实buf_2、参考隔离和LED钳位共同工作。FAULT可在停钟时切断PWM，恢复仍需实际RTL的许可序列。','', '负载保持原合成LED：Vf(100µA,27°C)=2.8V，N=3、RS=50Ω、CJO=2pF、TT=1ns。电气支路电流和电荷不是光功率。片外RBIAS/RRELEASE=100kΩ、RBLEED=10MΩ，CCOMP/CSENSE各30pF。模拟宏仍为r5实际39MOS/345R/288C名义提取网表；本轮没有重新布局或新增DRC/LVS/PEX结论。','', '原有证据来自2026-10-15最终套件：270点DC/PVT、10组启动、3组故障、4组PWM以及物理报告。这些是历史证据。本轮新增的每个仿真及失败候选另存于`evidence/pwm-robustness/20261024/`，没有将旧6MOS或0.1–7mA扫描借来作为39MOS证据。','', '## 2. 独立片外电阻与温度角落','', 'RSET按±1%及±100ppm/°C；RBIAS、RRELEASE、RBLEED按±5%及±200ppm/°C。温度基准27°C，使用R(T)=Rnom·(1+tol)·[1+TC·(T−27)]。这是独立、确定性的工程试验范围，不是foundry片上电阻统计模型，也不是采购元件或良率保证。','', 'TT/85°C下四个电阻的16个独立顶点；RSET两个同号tol/TC方向与TT/SS/FF、0/27/85°C的18点交叉，并补0°C三个MOS角的反号tol/TC六点以覆盖冷端真正极值（R/Rnom=0.987327和1.012727）；其余电阻逐一变化；另用原SS/FF供电包络作组合护栏。RSET±5%/±200ppm保留为精度失败对照。','', '| 新实验 | 电流/误差结果 | 判断 |','|---|---|---|']
for label,names in [('RSET独立MOS/温度交叉',[n for n in by if n.startswith('dc_cross_')]),('冷端独立tol/TC反号',[n for n in by if n.startswith('dc_cold_tc_independent_')]),('四电阻独立16顶点',[n for n in by if n.startswith('dc_passive_vertex_')]),('±5% RSET反例',[n for n in by if n.startswith('dc_rset5pct_')]),('SS/FF包络+封装护栏',[n for n in by if n.startswith('dc_guard_')])]:
    rs=[by[n] for n in names]
    if rs:lines.append(f'| {label}（{len(rs)}点） | {min(r["error_pct"] for r in rs):+.4f}% ～ {max(r["error_pct"] for r in rs):+.4f}% | {"所测点均在±5%" if all(r["passed"] for r in rs) else "保留失败"} |')
lines+=['','![独立电阻与MOS温度扫描](pwm-figures/pwm-independent-resistor.svg)','','单看MOS角会漏掉设定电阻误差：RSET的变化直接进入I≈VSET/RSET。RRELEASE在正常DC下几乎不改变电流，但不能因此推导其故障释放动态无关。VSET仍是理想0.5V，尚未加入其精度、温漂或噪声。所有供电、温度、元件组合尚未全笛卡尔交叉；本轮没有统计失配、热耦合或RC提取工艺角。','','## 3. 供电变化与真实片外滤波候选','','10%跌落发生于10µs，25µs恢复；分别扫描参考轨、LED轨、所有四条供电，10ns/100ns边沿。VSET和数字输入高电平仍以板级地为参考。新提出的“峰值偏离≤20%、恢复±0.5%≤5µs”均以同一试验扰动前/恢复后的DC电流为基准，静态100µA精度另算；这些线仅用于显示设计折衷；它不是用户给定或已经建立的产品规格。','','| 电路/条件 | LED支路范围 / µA | 最大偏离 | 恢复 / µs | 两项研究预算 |','|---|---:|---:|---:|---|']
for n,label in [('step_ref_100ns','原r5，参考轨100ns'),('step_ref_10ns','原r5，参考轨10ns'),('step_led_10ns','原r5，LED轨10ns'),('step_all_10ns_package_stress','原r5，全部轨10ns+封装'),('step_ref_10ns_filtered','die端100Ω+100nF'),('step_ref_10ns_filtered100n_lo','die端100nF，R−5%/C−10%'),('step_ref_10ns_filtered100n_hi','die端100nF，R+5%/C+10%'),('step_ref_10ns_filtered10n','100Ω+10nF，已否决折衷点'),('step_ref_10ns_filtered8p2n','die端100Ω+8.2nF'),('step_ref_10ns_filtered8p2n_lo','die端8.2nF，R−5%/C−10%'),('step_ref_10ns_filtered8p2n_hi','die端8.2nF，R+5%/C+10%'),('step_ref_10ns_board100n','PCB侧100Ω+100nF'),('step_all_10ns_board100n','PCB侧100nF，全部轨10ns')]:
    if n in by:
        r=by[n];lines.append(f'| {label} | {r["current_min_a"]*1e6:.3f}–{r["current_max_a"]*1e6:.3f} | {r["excursion_pct_of_pre_step"]:.3f}% | {r["settle_after_restore_0p5pct_s"]*1e6:.3f} | {"均满足" if r["passed"] else "未同时满足"} |')
lines+=['','![参考供电扰动波形](pwm-figures/pwm-reference-step.svg)','','100ns参考轨旧扰动重现约60.16–147.24µA及2.49µs恢复，与旧报告一致。10ns扰动中SENSE在约0.4166–0.5820V之间变化；有限带宽的参考环路不能瞬时维持0.5V，镜像电流随之下冲和上冲。封装R/L不是这一主要幅度的来源。','','第一批候选是宏端口侧100Ω串联电阻、电容接die-VSS，属于die端口/封装内局部电容假设，不能称为真实PCB片外放置。后续board100n候选保持100Ω/100nF数值，把R和C都移到封装R/L之前、C回板级地。39MOS及其PEX均不变。电阻DC压降、滤波启动及数字故障回放重新计算。100nF强抑制方案可以继续作为研究候选，但是否容许其恢复时间需由系统要求决定。容差扫描对应早期die端口拓扑，不能当作PCB侧拓扑的容差验证；8.2nF的名义通过无法覆盖所测元件容差。未为使候选通过而修改20%/5µs比较线。','','![片外滤波的幅度与恢复折衷](pwm-figures/pwm-filter-tradeoff.svg)','','## 4. 封装、启动、故障和最小PWM码','','封装用五条独立串联R/L路径：VREF、VSAFE、VBUF、LED_A和共用VSS回流。名义每条0.2Ω/2nH，应力每条1Ω/5nH。这里没有pad/ESD、引脚互感、LED_K/SENSE/VSET等信号脚的串联寄生、封装场求解、完整板级网络或阵列共用回流；参数是试验假设。SENSE原有30pF预算、片外电阻及外部VSET参考点均保留。','','启动仍预先供好安全/缓冲/LED电源，参考轨100ns上升，外部FAULT保持20µs；不是任意顺序或同时上电验证。故障在50.125µs施加，时钟47.7µs停止，使用实际RTL事件及10ns模拟引脚边沿。前期duty=1对完整两帧积分；板侧100nF确认采用258.5–514.5µs单个完整帧，已远离10µs参考滤波时间常数的初始过程。两者均与相同网络的DC电流比较，具体窗口记录在case和结果中。','','| 本轮耦合复验 | 主要数据 | 判定 |','|---|---|---|']
for n in ['startup_package_stress','fault_package_stress','pwm_package_stress','startup_filtered8p2n','fault_filtered8p2n','pwm_filtered8p2n','startup_filtered','fault_filtered','pwm_filtered','startup_board100n','fault_board100n','pwm_board100n','startup_board100n_gear1','startup_board100n_wide','startup_package_stress_refined','startup_filtered_refined']:
    if n not in by:continue
    r=by[n];k=r['case']['kind']
    if not r['completed']:
        lines.append(f'| `{n}` | {r.get("failure","incomplete")} | 求解未完成，不能验收 |');continue
    info=f'启动保持峰值 {r["held_fault_peak_a"]*1e9:.4f}nA；恢复 {r["recovered_a"]*1e6:.4f}µA' if k=='startup' else f'关闭 {r["fault_to_safe_s"]*1e9:.3f}ns；Q+ {r["fault_charge"]["positive_c"]*1e12:.4f}pC；Q− {r["fault_charge"]["negative_c"]*1e12:.4f}pC' if k=='fault' else f'duty=1电荷误差 {r["d1_charge_error_pct"]:+.5f}%'
    failed=', '.join(x['name'] for x in r['checks'] if not x['passed']);verdict=('单一wide配置的功能门槛通过；数值一致性未闭合' if n=='startup_board100n_wide' else '所列门槛通过') if r['passed'] else '失败：'+failed;lines.append(f'| `{n}` | {info} | {verdict} |')
lines+=['','![同值RC的两种接地点](pwm-figures/pwm-filter-topology.svg)','','![回流位置与启动波形](pwm-figures/pwm-ground-return.svg)','','同一R/C值的回流路径是本轮新增的重要边界。die端电容的充电电流经过共同封装VSS阻抗，会抬高局部地；PCB侧电容先在板级地闭合充电回路。以下使用完整局部网格的20µs窗口；未收敛数据不画成有效波形，PCB侧只显示wide诊断配置。图中PCB曲线的求解容差与严格基线不同，不能作为同数值设置下的修复闭合证明：','','| 完整网格启动 | 支路峰值 / nA | 导电峰值 / nA | 位移峰值 / nA | die-GND峰值 / mV |','|---|---:|---:|---:|---:|']
for x in startup_diagnosis:
    cond='<0.001（近零数值量）' if x['held_conduction_peak_a']<1e-12 else f'{x["held_conduction_peak_a"]*1e9:.6g}'
    lines.append(f'| `{x["name"]}` | {x["held_branch_peak_a"]*1e9:.6f} | {cond} | {x["held_displacement_peak_a"]*1e9:.6f} | {x["held_diegnd_peak_v"]*1e3:.6f} |')
lines+=['','无滤波的约627nA峰在完整网格下仍为约626.7nA，因此新封装下的启动暗态支路失败不能归零为数值伪影。板侧启动的Gear2/Gear1严格求解失败均保留；wide组合为同电路的数值诊断（reltol=1e−8、abstol=1pA、vntol=100nV）。即使单个wide配置能完成，也没有独立细化一致性闭合，不能据此宣称startup验证完成。网格变化与回流拓扑变化分开记录。','','关断判断包含LED总支路1nA门槛、正负电荷分别积分、停止时钟时的释放导电电流和恢复电流。端口位移电流不能被当成实测发光，正负电荷不能抵消后宣布安全。','','## 5. 端电压与数值可信度','','r5含33只06v0器件、6只05v0 buf_2器件；没有高速NRZ对照路线中的3.3V薄氧核心器件，因此不能套用3.63V筛查。新瞬态记录每只MOS实际分布式RC端点的|VGS|、|VGD|、|VGB|、|VDS|、|VBS|、|VBD|。前期DC及早期候选仅记录5对（未含VGB），摘要明确保留其195项与新234项的区别，不能相减峰值补出VGB。它们是terminal-voltage inventory，不是foundry绝对额定、寿命、ESD或可靠性验收。','']
for group in ['05v0','06v0']:
    valid=[r for r in rows if r.get('terminal_peak_by_model_class') and len(r.get('terminal_abs_peak_v',{}))==234]
    if valid:
        r=max(valid,key=lambda q:q['terminal_peak_by_model_class'][group]['max_abs_voltage_v']);v=r['terminal_peak_by_model_class'][group];lines.append(f'- 完整六对记录中，{group}最大端点差：{v["max_abs_voltage_v"]:.6f}V，`{r["case"]["name"]}` / `{v["terminal"]}`。')
lines+=['','最大步长2ns与1ns代表对照：','']
for x in num:lines.append(f'- `{x["a"]}`：最大插值电流差{x["max_interpolated_current_difference_a"]*1e9:.5f}nA，恢复时间差{x["settle_difference_s"]*1e9:.5f}ns。')
lines+=['','全部指标从完整波形计算；CSV只用于绘图。每份raw先计算SHA-256，再gzip压缩，解压回读哈希相符后才移除未压缩副本。失败、旧instrumentation尝试及ngspice日志保留在build，未把图形降采样当作数值验证。','','## 6. 可继续的研究与复现','','优先确认显示系统对瞬时电流、暗态位移电荷和恢复时间的真实要求，再决定是否采用强滤波片外方案；随后完成任意上电/掉电、POR/欠压及pad/ESD和封装网络。统计失配、电阻实际料号与TC、电容偏压效应、真实LED标定及阵列回流仍未覆盖。','','```sh','.venv/bin/python scripts/pwm_robustness/run.py --suite dc --reuse','.venv/bin/python scripts/pwm_robustness/run.py --suite transient --reuse','.venv/bin/python scripts/pwm_robustness/run.py --suite selected --reuse','.venv/bin/python scripts/pwm_robustness/run.py --suite strong --reuse','.venv/bin/python scripts/pwm_robustness/run.py --suite board --reuse','.venv/bin/python scripts/pwm_robustness/run.py --suite summarize','.venv/bin/python scripts/pwm_robustness/report.py','.venv/bin/python scripts/pwm_robustness/topology_figure.py','```','','主证据：`evidence/pwm-robustness/20261024/summary.json`、`compact-metrics.csv`、`validation.json`与`input-manifest.json`。完整原始波形/冻结模型/输入网表位于`build/pwm-robustness/20261024/`。本轮未建立光学、硅片、整芯片、MPW或foundry可靠性结论。']
if 'startup_package_stress_refined' in by:
    lines.insert(4,'**启动边界：**新增每路1Ω/5nH后，无滤波启动位移电流约626.7nA，原1nA支路门槛失败。PCB侧滤波的启动求解/数值闭合状态另列；供电幅度、故障和PWM通过不能替代启动结论。')
    lines.insert(5,'')
(D/'pwm-section.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(cases=len(rows),validation_passed=validation_summary['passed'],figures=[str(p.relative_to(ROOT)) for p in F.glob('*.svg')]),indent=2))
