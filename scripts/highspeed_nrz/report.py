#!/usr/bin/env python3
"""Build plots and a Chinese teaching report from traceable NRZ results."""
import argparse, csv, gzip, hashlib, html, json, math, sys
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from metrics import receiver_proxy, eye_segments
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/highspeed-nrz-20261019'
FIG=OUT/'figures'
FONT=ROOT/'build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf'
if FONT.exists():
    font_manager.fontManager.addfont(str(FONT));plt.rcParams['font.family']=font_manager.FontProperties(fname=FONT).get_name()
plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.labelcolor':'#233d4b','text.color':'#233d4b','axes.edgecolor':'#b5c6cc','grid.color':'#dce5e8','axes.grid':True,'grid.alpha':.6,'figure.facecolor':'white','svg.fonttype':'none'})
COLORS={'A':'#216b8b','B':'#c27935'}
NAMES={'A':'A 电压驱动','B':'B 电流转向'}
def save(fig,name):
    fig.savefig(FIG/(name+'.svg'),bbox_inches='tight');fig.savefig(FIG/(name+'.png'),dpi=160,bbox_inches='tight');plt.close(fig)
def f(x,n=2):return '—' if x is None else f'{x:.{n}f}'
def table(headers,rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+str(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def figure(name,caption):
    box=ET.parse(FIG/(name+'.svg')).getroot().attrib['viewBox'].split()
    w,h=round(float(box[2])),round(float(box[3]))
    return f'<figure><a href="figures/{name}.svg" target="_blank"><img src="figures/{name}.svg" width="{w}" height="{h}" alt="{html.escape(caption)}" loading="lazy"></a><figcaption>{caption} · 点击查看原尺寸 SVG</figcaption></figure>'
def trace(rec):
    result=json.loads((ROOT/rec['sources']['result_json']).read_text())
    with gzip.open(ROOT/result['waveform'],'rt') as fp:a=np.loadtxt(fp,skiprows=1)
    return a,result['vectors']
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',required=True);args=ap.parse_args()
    work=ROOT/args.work;analysis=json.loads((work/'analysis.json').read_text());records=analysis['cases']
    summary=json.loads((ROOT/'evidence/highspeed-nrz/summary.json').read_text());rows=summary['rows']
    if (ROOT/summary['identity']['work']).resolve()!=work.resolve():raise ValueError('summary/work mismatch; analyze the requested run first')
    if hashlib.sha256((work/'analysis.json').read_bytes()).hexdigest()!=summary['analysis_sha256']:raise ValueError('analysis hash mismatch')
    valid=[r for r in rows if r['analysis_ok']];nom=[r for r in valid if r['kind']=='nominal'];dc=[r for r in valid if r['kind']=='dc']
    FIG.mkdir(parents=True,exist_ok=True)
    recmap={r['case']['name']:r for r in records};st=json.loads((work/'stimulus.json').read_text())
    # Rate, screen margin and energy: failures are visible, not a false optimum.
    fig,axs=plt.subplots(1,3,figsize=(15.2,4.6),layout='constrained')
    for route in 'AB':
        rr=sorted([r for r in nom if r['route']==route],key=lambda r:r['rate_Gbps']);xx=[r['rate_Gbps'] for r in rr]
        for ax,key in zip(axs,['threshold_margin_normalized','timing_min_margin_ui','rail_positive_draw_fJ_per_gross_bit']):
            yy=[r[key] for r in rr];ax.plot(xx,yy,color=COLORS[route],lw=1.5,label=NAMES[route]);
            for x,y,r in zip(xx,yy,rr):ax.scatter(x,y,color=COLORS[route],marker='o' if r['comparison_screen_passed'] else 'x',s=55,zorder=4)
    for ax in axs:ax.set_xscale('log',base=2);ax.set_xlabel('输入毛速率 / Gb/s');ax.legend(fontsize=9)
    axs[0].axhline(.1,color='#9a5160',ls='--');axs[0].set_ylabel('固定门限最小余量 / 75 μA');axs[0].set_title('幅度余量：虚线为比较筛查线')
    axs[1].axhline(.1,color='#9a5160',ls='--');axs[1].set_ylabel('左右较小的时序余量 / UI');axs[1].set_title('相位在训练后冻结')
    axs[2].set_ylabel('全部 DC 轨正向取能 / fJ/bit');axs[2].set_title('○ 通过筛查　× 未通过');axs[2].set_yscale('log')
    save(fig,'rate-energy')
    # Actual traces at common representative rates.
    trace_rates=[.5,1,2]
    trace_available=[]
    for rate in trace_rates:
        rr=[r for r in nom if r['rate_Gbps']==rate]
        if len(rr)!=2:continue
        fig,axs=plt.subplots(5,2,figsize=(15.2,11),sharex='col',layout='constrained')
        for col,route in enumerate('AB'):
            row=next(r for r in rr if r['route']==route);rec=recmap[row['name']];a,v=trace(rec);t=a[:,0];ui=1/rate/1e9
            proxy=receiver_proxy(t,a[:,v['iled_cond']]);start=(st['validation_start_bit']+30)*ui;stop=start+12*ui;mask=(t>=start)&(t<=stop);x=(t[mask]-start)*1e9
            axs[0,col].plot(x,a[mask,v['data']],color='#9b70a3',label='DATA')
            for node in (['xdrv.ctrl'] if route=='A' else ['xdrv.gb','xdrv.gp']):axs[0,col].plot(x,a[mask,v[node]],label=node.split('.')[-1].upper(),lw=1)
            axs[0,col].set_title(f'{NAMES[route]} · {rate:g} Gb/s');axs[0,col].set_ylabel('栅极 / V');axs[0,col].legend(ncol=3,fontsize=9)
            axs[1,col].plot(x,a[mask,v['out']],color=COLORS[route],label='ASIC OUT');axs[1,col].plot(x,a[mask,v['led_k']],color='#667781',ls='--',lw=.9,label='LED_K');axs[1,col].set_ylabel('输出 / 阴极电压 / V');axs[1,col].legend(fontsize=9)
            axs[3,col].plot(x,a[mask,v['package_current']]*1e6,color='#a68a95',label='封装总电流',lw=.8)
            axs[3,col].plot(x,(a[mask,v['package_current']]-a[mask,v['iled_cond']])*1e6,color='#688c7d',label='CLED 位移电流',lw=.8);axs[3,col].set_ylabel('总电流 / 位移电流 / μA');axs[3,col].legend(fontsize=9)
            axs[2,col].plot(x,a[mask,v['iled_cond']]*1e6,color=COLORS[route],label='LED 导电电流');axs[2,col].set_ylabel('电流 / μA');axs[2,col].legend(fontsize=9)
            axs[4,col].plot(x,proxy['receiver_proxy_A'][mask]*1e6,color=COLORS[route],label='接收代理');axs[4,col].axhline(62.5,color='#9a5160',ls='--');axs[4,col].set_ylabel('接收等效电流 / μA');axs[4,col].set_xlabel('同一段输入数据的相对时间 / ns')
        save(fig,f'waveforms-{rate:g}G');trace_available.append(rate)
    # Eye diagrams reuse the frozen sampler, never optimize on validation.
    erates=[r for r in [.5,1,2] if all(any(x['route']==rt and x['rate_Gbps']==r for x in nom) for rt in 'AB')]
    if erates:
        fig,axs=plt.subplots(2,len(erates),figsize=(5*len(erates),7),squeeze=False,layout='constrained')
        for j,rate in enumerate(erates):
            for i,route in enumerate('AB'):
                row=next(r for r in nom if r['route']==route and r['rate_Gbps']==rate);rec=recmap[row['name']];a,v=trace(rec);ui=1/rate/1e9
                p=receiver_proxy(a[:,0],a[:,v['iled_cond']]);eye=eye_segments(a[:,0],p['receiver_proxy_A'],st['validation_bits'],st['validation_start_bit']*ui,ui,rec['transient']['sampler'])
                # API exposes phase_ui + traces_A.
                phase=eye['phase_from_frozen_sample_ui'];ys=eye['signal_A']
                if ys is None:raise KeyError(str(eye.keys()))
                for y in ys:axs[i,j].plot(phase,np.array(y)*1e6,color=COLORS[route],alpha=.16,lw=.8)
                axs[i,j].axhline(62.5,color='#9a5160',ls='--');axs[i,j].axvline(0,color='#61717a',ls=':');axs[i,j].set_ylim(10,115);axs[i,j].set_xlabel('相对冻结抽样点 / UI');axs[i,j].set_ylabel('接收等效电流 / μA');axs[i,j].set_title(f'{route} · {rate:g} Gb/s · {row["errors"]}/511 错位')
        save(fig,'eyes')
    # Capacitance sensitivity, fixed optical/Rx.
    fig,axs=plt.subplots(1,2,figsize=(12.5,4.7),layout='constrained')
    for i,route in enumerate('AB'):
        for cap,style in [(50e-15,':'),(200e-15,'-'),(2e-12,'--')]:
            rr=sorted([r for r in valid if r['route']==route and r['kind'] in ['capacitance','nominal'] and math.isclose(r['cap_F'],cap,rel_tol=1e-6,abs_tol=0)],key=lambda r:r['rate_Gbps'])
            axs[i].plot([r['rate_Gbps'] for r in rr],[r['threshold_margin_normalized'] for r in rr],style,marker='o',label=f'C = {cap*1e15:g} fF')
        axs[i].axhline(.1,color='#9a5160',ls='--');axs[i].set_xscale('log',base=2);axs[i].set_title(NAMES[route]);axs[i].set_xlabel('输入毛速率 / Gb/s');axs[i].set_ylabel('固定门限最小余量 / 75 μA');axs[i].legend()
    save(fig,'capacitance')
    # A sensitivity map reuses the same electrical waveform; only proxy changes.
    senspath=ROOT/'evidence/highspeed-nrz/receiver-sensitivity.json'
    if senspath.exists():
        sens=json.loads(senspath.read_text())['rows']
        fig,axs=plt.subplots(1,2,figsize=(12,4.7),layout='constrained')
        for ax,route in zip(axs,'AB'):
            values=np.array([[next(r['threshold_margin_normalized'] for r in sens if r['route']==route and abs(r['tau_opt_ps']-tau)<.01 and r['rx_GHz']==bw) for bw in [.5,1,2]] for tau in [50,200,1000]])
            im=ax.imshow(values,vmin=-.25,vmax=.5,cmap='RdYlGn',aspect='auto')
            for i,tau in enumerate([50,200,1000]):
                for j,bw in enumerate([.5,1,2]):
                    r=next(r for r in sens if r['route']==route and abs(r['tau_opt_ps']-tau)<.01 and r['rx_GHz']==bw)
                    ax.text(j,i,f"{r['threshold_margin_normalized']:.3f}\n{r['errors']}/511 错位",ha='center',va='center',fontsize=11,color='#152e3a')
            ax.set_xticks([0,1,2],['0.5','1.0','2.0']);ax.set_yticks([0,1,2],['50','200','1000']);ax.grid(False);ax.set_xlabel('假设接收带宽 / GHz');ax.set_ylabel('假设光学时间常数 / ps');ax.set_title(NAMES[route]+' · 1 Gb/s')
        fig.colorbar(im,ax=axs,label='固定门限最小余量 / 75 μA',shrink=.8)
        save(fig,'receiver-sensitivity')
    # Supply-energy ports at 1G, with return explicitly below zero.
    fig,axs=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    for ax,route in zip(axs,'AB'):
        row=next(r for r in nom if r['route']==route and r['rate_Gbps']==1);en=recmap[row['name']]['transient']['energy'];ports=en['rails']|{'DATA':en['ideal_DATA']};labels=list(ports)
        ax.bar(labels,[p['positive_draw_J_per_gross_bit']*1e15 for p in ports.values()],color=COLORS[route],label='正向取能')
        ax.bar(labels,[-p['returned_J_per_gross_bit']*1e15 for p in ports.values()],color='#b4c6cc',label='回灌到理想源')
        ax.axhline(0,color='#233d4b',lw=.8);ax.set_title(NAMES[route]+' · 1 Gb/s');ax.set_ylabel('端口能量 / fJ/bit');ax.legend(fontsize=9)
    save(fig,'energy-ports')
    # Numerical checks tied to each matching nominal case.
    comparisons=[]
    for r in valid:
        if r['kind'] not in ['numerical','integration_control']:continue
        base=next((b for b in nom if b['route']==r['route'] and b['rate_Gbps']==r['rate_Gbps']),None)
        if not base:continue
        comparisons.append({'route':r['route'],'rate_Gbps':r['rate_Gbps'],'control':r['kind'],
             'energy_positive_change_percent':100*(r['rail_positive_draw_fJ_per_gross_bit']/base['rail_positive_draw_fJ_per_gross_bit']-1),
             'eye_normalized_change':r['eye_normalized']-base['eye_normalized'],'errors_changed':r['errors']!=base['errors'],
             'screen_changed':r['comparison_screen_passed']!=base['comparison_screen_passed'],
             'max_abs_terminal_change_V':r['max_abs_terminal_V']-base['max_abs_terminal_V']})
    (ROOT/'evidence/highspeed-nrz/numerical-comparison.json').write_text(json.dumps(comparisons,indent=2)+'\n')
    # Source-linked result table is exported with the human-readable report.
    (OUT/'netlists').mkdir(exist_ok=True)
    for name in ['voltage_driver.spice','steering_driver.spice']:
        (OUT/'netlists'/name).write_bytes((work/'inputs/analog/highspeed_nrz'/name).read_bytes())
    for name in ['summary.json','summary.csv','numerical-comparison.json','mechanism-check.json','numerical-diagnosis.json','receiver-sensitivity.json','window-check.json','analysis-audit.json']:
        p=ROOT/'evidence/highspeed-nrz'/name
        if p.exists():(OUT/name).write_bytes(p.read_bytes())
    highest={rt:max([r['rate_Gbps'] for r in nom if r['route']==rt and r['comparison_screen_passed']],default=0) for rt in 'AB'}
    a05=next(r for r in nom if r['route']=='A' and r['rate_Gbps']==.5)
    b05=next(r for r in nom if r['route']=='B' and r['rate_Gbps']==.5)
    b01=next(r for r in nom if r['route']=='B' and r['rate_Gbps']==.1)
    nominal_table=table(['路线 / Gb/s','错位 / 511','眼开口 / 75 μA','门限余量 / 75 μA','时序余量 / UI','正向 / 回灌 / 净额 fJ/bit','DATA 正向 fJ/bit','筛查'],[
        [f"{r['route']} / {r['rate_Gbps']:g}",r['errors'],f(r['eye_normalized'],3),f(r['threshold_margin_normalized'],3),f(r['timing_min_margin_ui'],3),f"{f(r['rail_positive_draw_fJ_per_gross_bit'],1)} / {f(r['rail_returned_fJ_per_gross_bit'],1)} / {f(r['rail_net_fJ_per_gross_bit'],1)}",f(r['ideal_DATA_positive_draw_fJ_per_gross_bit'],1),'通过' if r['comparison_screen_passed'] else '未通过'] for r in sorted(nom,key=lambda r:(r['rate_Gbps'],r['route']))])
    dc_table=table(['MOS 条件（LED 曲线固定）','A: I₀ / I₁ μA','B: I₀ / I₁ μA'],[
        [f'{c} / {t} °C / {v:g} V',*[ ' / '.join(f(next(r['LED_current_A']*1e6 for r in dc if r['route']==rt and r['corner']==c and r['temp_C']==t and r['vdd_V']==v and r['dc_bit']==b),3) for b in [0,1]) for rt in 'AB']]
        for c,t,v in [('typical',27,3.3),('ss',27,3.3),('ff',27,3.3),('fs',27,3.3),('sf',27,3.3),('typical',-40,3.3),('typical',125,3.3),('typical',27,3),('typical',27,3.6)]])
    control_table=table(['路线 / Gb/s','对照','取能变化 %','眼开口变化','错位 / 筛查改变'],[[f"{c['route']} / {c['rate_Gbps']:g}",c['control'],f(c['energy_positive_change_percent'],3),f(c['eye_normalized_change'],5),str(c['errors_changed'])+' / '+str(c['screen_changed'])] for c in comparisons])
    failed=[r for r in rows if not r['simulation_ok'] or not r['analysis_ok']]
    failure_table=table(['未完成的数值实验','状态'],[[html.escape(r['name']),html.escape(str(r.get('failure','待检查')))] for r in failed]) if failed else '<p>本批已记录的全部实验均完成仿真与分析；这只表示数值计算完成。</p>'
    stress_rows=[r for r in valid if r['kind'] in ['nominal','slow_hot','fast_cold']]
    stress_table=table(['路线 / 条件 / Gb/s','最大端子压差 V','体结正向峰值 V','超过 3.63 V 筛查','信号筛查'],[[f"{r['route']} / {r['kind']} / {r['rate_Gbps']:g}",f(r['max_abs_terminal_V'],4),f(r['maximum_body_forward_V'],4),'是' if r['above_3p63V_screen'] else '否','通过' if r['comparison_screen_passed'] else '未通过'] for r in stress_rows])
    numtext=f'已记录 {len(rows)} 个实验，{len(valid)} 个完成仿真与分析，{len(failed)} 个仍有数值失败或分析失败。'
    htmlout='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>单通道 NRZ：电压驱动与电流转向的晶体管实验</title><style>
:root{--ink:#233d4b;--muted:#627781;--blue:#216b8b;--paper:#f7f8f7;--line:#d9e3e6}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.72 'PingFang SC','Noto Sans CJK SC',Arial,sans-serif}main{max-width:1180px;margin:auto;padding:48px 36px 80px}header{padding:25px 0 32px;border-bottom:2px solid var(--blue)}h1{font-size:36px;line-height:1.35;max-width:960px;margin:16px 0}h2{font-size:26px;margin:0 0 20px}h3{font-size:20px;margin:26px 0 10px}p{max-width:960px;margin:12px 0}a{color:var(--blue);text-underline-offset:3px}nav{position:sticky;top:0;background:#f7f8f7f5;padding:12px 0;border-bottom:1px solid var(--line);z-index:5;display:flex;gap:16px;flex-wrap:wrap;font-size:14px}section{padding:40px 0;border-bottom:1px solid var(--line);scroll-margin-top:90px}.eyebrow{font-size:13px;letter-spacing:.12em;color:var(--blue)}.muted,figcaption{color:var(--muted);font-size:14px}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:24px 0}.card,.note{background:white;border:1px solid var(--line);border-radius:9px;padding:20px}.card b{display:block;font-size:28px;color:var(--blue)}.note{border-left:4px solid var(--blue);margin:20px 0}.caution{border-left-color:#c27935;background:#fffaf3}.formula{font:16px/1.85 'Avenir Next','PingFang SC',sans-serif;padding:18px 22px;background:#eaf0f3;border-radius:8px;overflow:auto;margin:18px 0}figure{margin:26px 0}figure img{display:block;width:100%;height:auto;background:white;border:1px solid var(--line);border-radius:8px}figcaption{padding:9px 2px}.scroll{overflow-x:auto;margin:18px 0}table{border-collapse:collapse;width:100%;background:white;font-size:14px}th,td{padding:11px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:#edf2f4;white-space:nowrap}td:first-child{min-width:110px}code{font-size:13px;background:#edf2f4;padding:2px 4px;overflow-wrap:anywhere}li{margin:6px 0}details{margin:16px 0;padding:16px;background:white;border:1px solid var(--line);border-radius:8px}summary{cursor:pointer;font-weight:600}.two{display:grid;grid-template-columns:1fr 1fr;gap:22px}.small{font-size:14px}@media(max-width:700px){main{padding:24px 18px}h1{font-size:28px}.cards,.two{grid-template-columns:1fr}nav{position:static}section{padding:28px 0}}@media print{body{background:white}main{padding:0}nav{display:none}section{break-inside:avoid}figure{break-inside:avoid}a{color:inherit}details{display:block}}
</style><main><header><div class="eyebrow">OPEN MICROLED DRIVER ASIC · 2026-10-19 · 实验性研发与教学</div><h1>一个比特如何变成 LED 电流？<br>单通道 NRZ 的两种晶体管驱动电路</h1><p>从共同的负载、真实 MOS 电路，到接收判决与逐电源能量积分。比较对象是本项目的两版具体实现；结论服务于下一轮设计，不代表技术路线的性能极限。</p><p class="muted">证据等级：GF180 晶体管级 pre-layout 仿真 + 公开测得的 LED 静态 I–V + 假设的动态负载与无噪声接收代理。尚无高速版图、PEX、硅片或光链路测量。</p></header>
<nav><a href="#result">主要结果</a><a href="#setup">共同条件</a><a href="#circuits">电路与工作过程</a><a href="#wave">波形与眼图</a><a href="#energy">能耗</a><a href="#limits">限制与验证</a><a href="#next">下一步</a><a href="#sources">复现与出处</a></nav>'''
    htmlout+=f'''<section id="result"><div class="eyebrow">01 · 先读结论</div><h2>速率、能量和可实现性，需要同时看</h2><div class="cards"><div class="card">A · TT / 27°C / VDD 3.3 V<br>最高离散信号筛查通过点<b>{highest['A']:g} Gb/s</b><span class="muted">在本次共同模型和已完成测试点中</span></div><div class="card">B · TT / 27°C / VDD 3.3 V<br>最高离散信号筛查通过点<b>{highest['B']:g} Gb/s</b><span class="muted">不是实测最大速率或 BER 保证</span></div><div class="card">校准的 LED 电流状态<b>25 / 100 μA</b><span class="muted">两版电路均在 TT / 27°C 校准</span></div></div><p>{numtext} 两版都使用硅基 GF180 的 3.3 V NMOS / PMOS；本轮没有引入特殊晶体管材料。</p><p>在两版均通过的 0.5 Gb/s，全部 DC 轨加理想 DATA 端口的正向取能为 A <b>{a05["rail_plus_DATA_positive_draw_fJ_per_gross_bit"]:.1f} fJ/bit</b>、B <b>{b05["rail_plus_DATA_positive_draw_fJ_per_gross_bit"]:.1f} fJ/bit</b>。这一边界不含实际稳压器与接收机。1 Gb/s 时 B 的取能虽略低，但出现 6/511 错位，不能把该点称为可用的能效优势。该点的垂直眼开口仍略大于零；问题是固定门限和规定余量下未通过，并非证明任何门限都不能判决。</p><div class="note"><b>如何读“通过”：</b>独立于训练段的 511 个 PRBS9 验证比特零错位、固定门限最小余量 ≥7.5 μA、左右较小的时序余量 ≥0.1 UI。它是预先设定的教学比较筛查，尚未包含接收噪声、时钟抖动或真实光耦合。器件电压应力另行列出。</div>{figure('rate-energy','相同负载与接收代理下的晶体管仿真；能量越低但信号失败的点，不是可用的节能工作点。')}{nominal_table}<div class="note caution"><b>为什么 B 在 0.1 Gb/s 反而标为未通过？</b>该点为 0/511 错位，幅度眼开口约 0.996；训练以垂直余量选出的延迟是 1.0078125 UI，冻结后右侧时序余量只有 {b01["timing_min_margin_ui"]:.5f} UI，略低于预设 0.1 UI。它反映当前采样训练规则与时序预算的限制，不能解释成低速带宽不足。本轮保留规则和结果；下一版可只用训练数据同时优化幅度与时序余量。</div><p class="small">表中 DC 电源轨能量包含 LED 电源、前置驱动、输出轨或 dummy/参考支路；DATA 为单列的理想输入端口能量。各点分母为 511 个毛比特。数值失败的点在后文保留，不能作为物理速率失败。</p></section>'''
    htmlout+='''<section id="setup"><div class="eyebrow">02 · 固定比较前提</div><h2>两条路线只改变驱动电路，共同条件保持一致</h2>'''+table(['项目','共同设置','证据边界'],[
['MOS','GF180 nfet_03v3 / pfet_03v3；最短沟道使用 0.28 μm','公开 PDK 模型，不是先进节点或流片签核'],
['LED','20 μm 方形黄色 InGaN/GaN MicroLED；公开静态 I–V 插值','曲线实测；动态 C、载流子、温度和光功率未由该数据标定'],
['电流 / 电源','I₀=25 μA，I₁=100 μA；VLED=5 V，VDD=3.3 V','I₀ 保留预偏置，不声称完全熄灭；A 另需 VH/VL，B 另有 VDUMMY'],
['动态负载','并联 CLED=200 fF；阴极串联 R=1 Ω、L=0.5 nH','设计假设；另扫 50 fF、2 pF 和 2 nH'],
['输入','0–3.3 V，20 ps 线性边沿；共同 PRBS','理想数据源；未实现串行器、PLL、时钟或数据输入标准'],
['接收代理','LED 导电电流 → τ=200 ps 一阶光学代理 → 1 GHz 一阶接收滤波','单位为等效电流；没有测得的光功率、PD/TIA 噪声与物理 BER'],
['器件几何','所有 MOS：AD=AS=W×0.6 μm，PD=PS=2(W+0.6 μm)','统一的孤立扩散估算；不等于版图提取寄生'],
['校准方式','典型条件校准一次，其余角落不重新校准','A 的设定电源轨保持理想；B 的参考电阻保持不变']])+'''<h3>这里的 NRZ 如何表示数据？</h3><p>NRZ（Non-Return-to-Zero，不归零码）在每个比特周期内保持一个电平，连续相同比特无需回到零。本实验采用 25 μA 与 100 μA 两个 LED 导电电流状态；比特周期 UI=1/速率，因此 1 Gb/s 的一个 UI 为 1 ns。这与显示亮度用的低频 PWM 占空比调制是不同的工作方式。</p><h3>训练负责找时序，验证负责检查结果</h3><p>先发 32 bit 交替预热，再发 254 bit PRBS7 训练、511 bit PRBS9 验证和 32 bit 尾部保护。抽样延迟只在训练段选择，搜索范围为 max(4 UI, 3 ns 向上取整至 UI)，网格 1/128 UI。训练评分裁去末尾相应数量的比特，保证任何候选采样时间都不会读入验证段。</p><p>随后冻结抽样延迟、62.5 μA 门限和 75 μA 归一化跨度。每条路线可以有不同的传播延迟，但不能用自己的失真幅度重新归一化。<a href="measurement-contract.md">完整测量约定</a>保留定义、窗口和公式。</p></section>'''
    htmlout+='''<section id="circuits"><div class="eyebrow">03 · 电路如何工作</div><h2>A 控制阴极电压；B 把调制电流转到两个支路</h2><h3>A：受限输出摆幅的 CMOS 电压驱动</h3><p>数据先经过两级 CMOS 反相器，再共同控制输出 PMOS 和 NMOS。总计 6 只 MOS；这里只是器件数量，和早期单像素 PWM 的“六 MOS”电路没有通用拓扑含义。前置驱动的栅极信号仍为 0–3.3 V，不能把约 0.44 V 的输出电源轨差直接当作可用的 MOS 栅极摆幅。</p>'''+figure('voltage-schematic','实际 SPICE 子电路 A：标注每只 MOS 的 D/G/S/B、尺寸、输出电源和共同 LED 负载。')+'''<div class="two"><div class="card"><h3>DATA=0：低 LED 导电电流</h3><p>两次反相后 CTRL≈0。输出 PMOS 导通、NMOS 关断，OUT 被保持在较高电压。VLED 固定，因此 LED 两端电压较低，导电电流约 25 μA。这个电流从 LED 流入 OUT，再经输出 PMOS 进入 VH 电源，VH 必须具备吸收电流的能力。</p></div><div class="card"><h3>DATA=1：高 LED 导电电流</h3><p>CTRL≈3.3 V。NMOS 导通、PMOS 关断，OUT 下降，LED 两端电压上升，电流约 100 μA。低阻输出级还可提供较大的瞬态电流来改变结电容电压；这部分瞬态电流不能全部视为发光电流。</p></div></div><div class="formula">校准：VH≈1.611025 V，VL≈1.172154 V<br>OUT≈1.638636 V / 1.231990 V；Vf≈3.36134 V / 3.76791 V<br>栅极摆幅：3.3 V；LED 电压变化：约 0.40657 V</div><p>VH/VL 是理想的可吸收电流电源。本轮尚未设计实际产生这两个电压的稳压器；输出也不是被数学上严格钳在 VH 与 VL 之间。电源回灌与 MOS 压降都要保留。</p><h3>B：带直流预偏置的 NMOS 电流转向</h3><p>电路共有 9 只 MOS。RREF 与二极管连接的 MREF 产生 VBIAS；MBASE 提供约 25 μA 基线，MI 提供约 75 μA 调制尾电流；ML / MD 决定这股调制电流从 LED 还是 dummy 支路流入。这个参考支路已落实为器件，但它是电阻偏置电流镜，还不是精密基准。</p>'''+figure('steering-schematic','实际 SPICE 子电路 B：偏置、镜像、互补前驱动、转向开关、dummy 电阻及全部供电端口。')+'''<div class="two"><div class="card"><h3>DATA=0：调制电流走 dummy</h3><p>GB≈3.3 V，GP≈0；MD 导通，ML 关断。LED 只保留 MBASE 的约 25 μA。VDUMMY 经 28 kΩ 电阻、MD、MI 向地提供调制电流，功耗仍然存在。</p></div><div class="card"><h3>DATA=1：调制电流走 LED</h3><p>GB≈0，GP≈3.3 V；ML 导通，MD 关断。LED 侧为基线与调制电流之和，静态目标约 100 μA。切换期间，节点电容和尾电流源压差会改变瞬时电流，不能直接用理想 25/100 μA 方波代替仿真。</p></div></div><div class="formula">IREF≈(3.3−1.11172)/88.386 kΩ≈24.758 μA<br>MBASE：W/L=2/1 μm；MI：W/L≈5.75896/1 μm<br>I₀≈25 μA；I₁≈100 μA（仿真校准，而非只用尺寸比假定）</div><p>RREF 与 WTAIL 的小数值是仿真校准结果，并不代表制造精度；进入版图时需按 PDK 网格和实际电阻结构取整，再重新验证电流及失配。GP 比 GB 多经过一级反相器。0→1 时可能出现 ML/MD 暂时都关断；1→0 时可能暂时都导通。实际偏斜已包含在晶体管波形中。下一版应研究平衡前置驱动和交越控制，同时核算其额外功耗。</p><h3>为什么开关快，LED 电流仍然可能慢？</h3><p>转向开关首先改变阴极节点的总电流。LED 静态导电支路与并联电容共享该电流；电容电压完成变化之前，导电电流不会立刻到达新的平台。电压驱动能以较低输出阻抗推动节点，电流转向则受可用充放电电流和负载动态电阻约束。</p><div class="formula">ΔVf≈0.40657 V；ΔQ=CLED·ΔVf≈81.31 fC<br>ΔQ / 75 μA≈1.084 ns（电荷/电流尺度，不是精确的 10–90% 上升时间）</div><p>这条静态曲线在低/高工作点的局部 r<sub>d</sub>C 分别约 2.154 ns / 0.591 ns。实际的小信号时间常数还取决于 I–V 曲线斜率、MOS 输出电阻和寄生。<a href="mechanism-notes.md">解析核对笔记</a>列出插值段、动态电阻与计算条件。</p></section>'''
    htmlout+='<section id="wave"><div class="eyebrow">04 · 从比特到接收判决</div><h2>沿着同一段数据，逐级看波形变化</h2><p>每组图使用相同的输入比特。第一行看前驱动和互补信号；第二行分别看 ASIC 输出 OUT 与串联 R/L 之后的 LED 阴极 LED_K 电压；第三行单独看 LED 导电电流；第四行看封装总电流与由 KCL 算出的电容位移电流；第五行看共同接收代理。电容位移电流尖峰不直接进入光学代理。</p>'
    for rate in trace_available:htmlout+=figure(f'waveforms-{rate:g}G',f'{rate:g} Gb/s 的实际瞬态数据；同一横轴下比较驱动链和负载响应。')
    if erates:htmlout+=figure('eyes','PRBS9 接收等效电流眼图；横轴零点为训练后冻结的采样位置。绘图最多展示 96 段，数值判决使用全部 511 bit。')
    htmlout+='''<p>眼图中的轨迹来自电气仿真与共同滤波假设。没有随机噪声，不能据此推导实际 BER。正的眼开口也不自动表示固定门限合适，因此同时检查门限两侧的最小余量和时序余量。</p></section>'''
    htmlout+='''<section id="energy"><div class="eyebrow">05 · 能量算到哪里</div><h2>回灌电源的能量，不能直接记成真实节能</h2><div class="formula">p源(t)=−V源(t)·I源(t)<br>E取能=∫max(p源,0)dt；E回灌=∫max(−p源,0)dt<br>E净额=E取能−E回灌；每比特能量=E/511</div><p>所有 DC 电源在同一个 511 UI 输入时间窗口逐项积分，再求和。主表采用“各端口正向取能之和”，不预设实际稳压器能无损回收能量；同时提供回灌和净额，避免隐藏 A 的低压供电实现代价。它仍是电路端口指标，上游稳压器效率尚未计入。</p>'''+figure('energy-ports','1 Gb/s 电源端口能量：正向取能在上方，回灌在下方；DATA 独立列出。')+'''<p>A 的两个输出电源轨会吸收 LED 支路电流。B 的 dummy 支路在低状态仍耗电，参考支路也持续耗电。两版的 CMOS 前置驱动都要充放电 MOS 栅极。仅用 LED 的平均电流乘压降，会漏掉这些成本。</p><p>理想 DATA 端口能量已测量，但真实上游缓冲器会有额外损耗；本轮也未包含串行器、时钟、实际接收机和冷却。另将相同 PRBS9 连续发送两周期作复核：1 Gb/s 时，A 的两周期正向供能相差约 0.0032%，B 约 0.00018%；本条件下有限窗口影响很小。<a href="window-check.json">完整窗口检查数据</a>保留逐电源结果。对有限窗口，电容与电感的首尾储能可能不同；分析数据只保存显式 CLED / LPKG 的首尾储能变化；尚未完成含全部 MOS 内部储能的能量守恒闭合。不能把一次 511 bit 积分叫作无限长稳态或完整链路能耗。</p></section>'''
    htmlout+='''<section id="limits"><div class="eyebrow">06 · 什么限制了结论</div><h2>负载、偏置精度、器件应力与数值收敛分别检查</h2><h3>负载电容敏感性</h3><p>保持相同静态曲线和接收代理，只改变共同 CLED。该扫描显示结论对动态假设有多敏感；它不能反过来证明真实 LED 的电容等于某一个值。</p>'''+figure('capacitance','CLED=50 fF / 200 fF / 2 pF 的条件扫描。未完成的数值点不作物理速率结论。')+figure('receiver-sensitivity','只改变光学和接收假设，复用相同 1 Gb/s 电气波形；色值是门限余量，非物理 BER。')+'''<p>例如 A 在 1 GHz 接收代理下，把假设光学时间常数从 200 ps 改为 1 ns，门限余量由约 0.437 降至 0.040，虽然仍为 0/511 错位，已经不满足预设余量筛查。这说明真正的速率判断必须由实测高速 LED 模型支撑。这项独立参数扫描不意味着器件电容与载流子响应在物理上可以任意独立变化。</p><h3>工艺、电源和温度：先检查 DC 电流是否还正确</h3><p>以下只改变 MOS 模型角、MOS 温度和 VDD（DATA 高电平也随 VDD 改变）；LED 静态曲线、理想电阻、A 的 VH/VL、B 的 VDUMMY 均保持固定，所以这不是完整系统 PVT。没有失配 Monte Carlo、LED 温漂或真实电压基准误差。</p>'''+dc_table+'''<p>A 在本次供电和部分工艺扫描中的较小漂移，依赖理想且固定的 VH/VL，不能据此认定实际稳压方案更准确；温度漂移并非全部较小。例如 TT / 125°C 时，A 的高态电流为 94.519 μA（−5.48%），B 为 97.627 μA（−2.37%）。B 的 RREF 直接接 VDD，电源变化会改变参考电流；下一版需要可调、受控的参考及校准机制。</p><div class="note caution"><b>典型通过点不是工作范围保证：</b>SS、125°C、VDD=3.0 V 时，A 在 2 Gb/s 出现 64/511 错位；B 在 0.5 Gb/s 虽然仍为 0/511，最小门限余量已降至约 0.372 μA，时序余量只有 0.03125 UI，两者都未通过。A 在该角落的 0.5 与 1 Gb/s 仍通过信号筛查。需要先补足角落余量，再谈完整工作范围。</div><div class="note caution"><b>快速工艺角仍需处理：</b>FF、−40°C、VDD=3.6 V 的 6 个动态实验均超过统一 3.63 V 诊断线。A 的最大端子压差约 3.723 V，B 约 3.794 V；其中 B 出现在 dummy 开关的 VGB，涉及栅极电压约束。应分别核对各端子的可靠性规则，并通过输出钳位、前驱动摆幅或器件选择重新设计与验证。不能因信号通过就认定 PVT 与可靠性验证完成。</div><details><summary>查看全轨迹器件应力与动态角落筛查</summary><p>逐只 MOS 检查 VGS、VGD、VGB、VDS、VDB、VSB 的最大绝对值，覆盖预热、训练、验证和尾部。使用 3.63 V 作为统一诊断阈值；该值的来源是 DC gate-to-other-node 规则，不能泛化为所有端子的合格限值；具体电压、时间、温度和可靠性条件仍需分别签核。体结正向偏压另外记录，也不能按 3.63 V 判断。超过阈值意味着必须重新设计或进一步查证；低于阈值也不表示已完成可靠性验证。</p>'''+stress_table+'''</details><h3>数值失败必须和电路失真分开</h3><p>首轮梯形积分在理想数据源的边沿断点附近出现步长缩到浮点极限的失败。只改变小数表示会移动失败时间；采用 Gear2 和细步长交叉核对可以区分积分器敏感性。所有失败网表和日志保留在 build，绝不把截断的波形作为完整 PRBS9 验证。</p><p>下面比较同一物理电路的细化步长及另一积分算法；12 组典型条件对照的错误数与筛查分类均保持不变，正向供能最大变化约 0.1825%。这些对照尚未覆盖上述快速、低温、高供电角落的过冲收敛，仍需针对该角落细化步长、边沿与寄生后复核峰值。与早期成功的严格容差解的比较另见数值诊断记录。判断结果应对合理的数值设置稳定；最大电压尖峰的收敛另行查看。</p>'''+control_table+failure_table+'''<p><a href="numerical-notes.md">数值诊断记录</a> · <a href="numerical-comparison.json">逐项数值对照</a>。接收滤波和能量计算还通过 15 项独立解析正例、反例与输入检查；这些检查验证分析代码，不替代电路验证。</p></section>'''
    htmlout+='''<section id="next"><div class="eyebrow">07 · 由结果决定下一轮</div><h2>先补会改变路线判断的证据</h2>'''+table(['方向','下一轮具体工作','进入下一阶段的依据'],[
['共同负载','测量目标 LED 在 25–100 μA 的 C–V / 小信号阻抗、S21、L–I；建立偏置与温度相关模型','用独立测量验证模型，避免把静态 I–V 当高速器件证明'],
['A 电压驱动','实现可吸收电流的 VH/VL 调节或实际电流回路；计入稳压器、供电阻抗与反馈带宽','在真实供电边界下仍有信号余量，且总能量可接受'],
['B 电流转向','平衡 GB/GP 延迟，减小切换盲区；研究受控预加重、偏置稳压和较小负载电容','同一接收条件下改善眼图，并明确付出的尾电流/缓冲能量'],
['两版共同','器件尺寸扫描；故障/启动、限流、端子应力、失配和真实输入缓冲验证','不以单点 TT 结果替代稳定工作范围'],
['高速物理实现','LED 接口与输出级贴近；缩小阴极电容与完整供回流回路；差分控制线匹配；纳入 pad/ESD/封装模型','布局之后运行 DRC/LVS/PEX，再重复本套速率与能耗比较'],
['完整链路','加入 PD/TIA 噪声、光耦合、CDR 抖动、编码开销及长序列误码实验','得到可解释的 BER / 净吞吐 / Tx+Rx 能耗']])+'''<div class="note"><b>当前工程选择：</b>保留两条可运行的晶体管路线，先以相同边界做尺寸与偏置优化。要追更高单通道速率，应同时降低负载电容、改善前驱动，并检查动态光学响应；要追低能耗，必须把稳压器、dummy、参考和输入缓冲纳入预算。是否迁移到更先进 CMOS、SOI 或异质集成，应在这些数据明确后决定，不能仅靠材料名称推断速率。</div><p>本次没有把高速电路合入原有单像素 PWM 版图，也没有新增高速 GDS、DRC/LVS/PEX 或硅片证据。原项目已完成阶段的证据仍分别保留。</p></section>'''
    htmlout+=f'''<section id="sources"><div class="eyebrow">08 · 复现与研究索引</div><h2>每个结果都能回到网表、波形和假设</h2><p>正式批次：<code>{html.escape(args.work)}</code>。完整结果在该目录的 <code>analysis.json</code>；每个 case 保留网表、日志、原始波形的无损压缩文件与 SHA-256。源模型和初始脚本冻结在 <code>inputs/</code>；后处理另有版本与哈希。</p><p><a href="netlists/voltage_driver.spice">A 晶体管网表</a> · <a href="netlists/steering_driver.spice">B 晶体管网表</a> · <a href="summary.csv">下载全部实验 CSV</a> · <a href="summary.json">机器可读摘要</a> · <a href="measurement-contract.md">测量约定</a> · <a href="README.md">复现说明</a> · <a href="../highspeed-driver-routes-20261019/index.html">上一阶段：技术路线与论文索引</a></p><ol><li>静态器件曲线：Lin et al., <a href="https://doi.org/10.1038/s41467-026-74151-4">Nature Communications 2026</a>；<a href="https://doi.org/10.5281/zenodo.20034288">公开源数据 CC-BY 4.0</a>。本实验使用 I–V.xlsx 中 20 μm 黄色器件的静态数据；出处和抽取位置见原始 model-card / source-lock。</li><li>GF180 公共 PDK：<a href="https://github.com/google/gf180mcu-pdk">官方仓库</a>；<a href="https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html">可靠性规则 14.1</a>。具体模型哈希由 <code>layout/pdk-lock.json</code>及实验 manifest 锁定。</li><li>本报告所有电路图独立绘制，对应本项目网表；波形和眼图来自本轮数值实验。解析电荷估算和接收模型假设均已标明。</li></ol><p class="muted">研究目的：用可复现方法验证驱动设计，支持学习和后续工程决策。没有复制商业产品电路或协议。</p></section><footer><p class="muted">Open MicroLED Driver ASIC · single-lane NRZ study · 2026-10-19</p></footer></main></html>'''
    (OUT/'index.html').write_text(htmlout)
    print(json.dumps({'report':str(OUT/'index.html'),'rows':len(rows),'nominal':len(nom),'highest_screened_Gbps':highest,'numerical_controls':len(comparisons)},ensure_ascii=False))
if __name__=='__main__':main()
