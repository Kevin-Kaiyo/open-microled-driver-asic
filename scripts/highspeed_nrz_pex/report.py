#!/usr/bin/env python3
"""Traceable figures and Chinese report for the single-channel physical experiment."""
from pathlib import Path
import argparse, csv, gzip, hashlib, html, importlib.util, json, math, re, sys
import xml.etree.ElementTree as ET
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'docs/research/highspeed-nrz-pex-20261020';FIG=OUT/'figures'
sys.path.insert(0,str(ROOT/'scripts/highspeed_nrz'))
from metrics import receiver_proxy, eye_segments
from analyze import load_trace
FONT=ROOT/'build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf'
font_manager.fontManager.addfont(str(FONT));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(FONT)).get_name()
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.labelcolor':'#233d4b','text.color':'#233d4b','axes.edgecolor':'#b5c6cc','grid.color':'#dce5e8','axes.grid':True,'grid.alpha':.6,'figure.facecolor':'white','svg.fonttype':'none'})
COLORS={'SCHEM':'#70818e','SNAP':'#aaa45e','GEOM':'#957aa2','C':'#c58a45','RC':'#177f8d'}
LABELS={'SCHEM':'原理图','SNAP':'网格量化','GEOM':'实际器件几何','C':'几何 + C','RC':'几何 + RC'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(fig,name):
    fig.savefig(FIG/(name+'.svg'),bbox_inches='tight');fig.savefig(FIG/(name+'.png'),dpi=170,bbox_inches='tight');plt.close(fig)
def f(v,n=3):return '—' if v is None else f'{v:.{n}f}'
def table(head,rows):return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+str(x)+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in r)+'</tr>' for r in rows)+'</tbody></table></div>'
def figure(name,caption):return f'<figure><a href="figures/{name}.svg" target="_blank"><img src="figures/{name}.svg" alt="{html.escape(caption)}" loading="lazy"></a><figcaption>{caption} · 点击查看原尺寸矢量图</figcaption></figure>'
def plots(s,analysis,work):
    rows=[r for r in s['rows'] if r['analysis_ok']];nom=[r for r in rows if r['kind']=='nominal'];recmap={r['case']['name']:r for r in analysis['cases']}
    def row(route,variant,rate):return next(r for r in nom if r['route']==route and r['variant']==variant and r['rate_Gbps']==rate)
    def trace(r):
        p=ROOT/r['result_json'];res=json.loads(p.read_text());a,_=load_trace(res,p);return a,res['vectors']
    fig,axs=plt.subplots(2,3,figsize=(15,9),layout='constrained')
    for i,route in enumerate('AB'):
        for var in ['SCHEM','GEOM','C','RC']:
            rr=sorted([r for r in nom if r['route']==route and r['variant']==var],key=lambda r:r['rate_Gbps']);x=[r['rate_Gbps'] for r in rr]
            for ax,key in zip(axs[i],['threshold_margin_normalized','timing_min_margin_ui','rail_plus_DATA_positive_draw_fJ_per_gross_bit']):
                ax.plot(x,[r[key] for r in rr],color=COLORS[var],label=LABELS[var],lw=1.4)
                for r in rr:ax.scatter(r['rate_Gbps'],r[key],color=COLORS[var],marker='o' if r['comparison_screen_passed'] else 'x',s=35,zorder=3)
        for ax in axs[i]:
            ax.set_xscale('log',base=2);ax.set_xticks([.1,.25,.5,1,2,4,8],['0.1','0.25','0.5','1','2','4','8']);ax.set_xlabel('输入毛速率 (Gb/s)');ax.legend(fontsize=8)
        axs[i,0].axhline(.1,color='#a44b43',ls='--',lw=1);axs[i,1].axhline(.1,color='#a44b43',ls='--',lw=1)
        axs[i,0].set_ylabel('固定门限最小余量 / 75 µA');axs[i,1].set_ylabel('最小左右时序余量 / UI');axs[i,2].set_ylabel('全部电源 + DATA 正向取能 (fJ/毛bit)');axs[i,2].set_yscale('log')
        for ax,title in zip(axs[i],['幅度余量','时序余量','包含失败点的能耗']):ax.set_title(f'{route} · {title}')
    save(fig,'rate-energy')
    fig,axs=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
    for ax,route in zip(axs,'AB'):
        for var in ['SCHEM','GEOM','C','RC']:
            rr=[row(route,var,x) for x in [.5,1,2]];ax.plot([r['rate_Gbps'] for r in rr],[r['max_abs_terminal_V'] for r in rr],marker='o',label=LABELS[var],color=COLORS[var])
        ax.axhline(3.63,color='#a44b43',ls='--',label='项目端差筛查 3.63 V');ax.set(xlabel='输入毛速率 (Gb/s)',ylabel='全窗口最大 MOS 端差 (V)',title=f'{route} · 实际 D/G/S/B 局部端子');ax.legend(fontsize=8)
    save(fig,'stress')
    st=json.loads((work/'stimulus.json').read_text())
    for rate in [.5,1,2]:
        fig,axs=plt.subplots(3,2,figsize=(14,8.7),sharex='col',layout='constrained')
        for j,route in enumerate('AB'):
            for var in ['SCHEM','GEOM','RC']:
                r=row(route,var,rate);a,v=trace(r);ui=1/(rate*1e9);start=(st['validation_start_bit']+30)*ui;mask=(a[:,0]>=start)&(a[:,0]<=start+12*ui);x=(a[mask,0]-start)*1e9
                p=receiver_proxy(a[:,0],a[:,v['iled_cond']]);col=COLORS[var]
                axs[0,j].plot(x,a[mask,v['out']],label=LABELS[var],color=col,lw=1)
                axs[1,j].plot(x,a[mask,v['iled_cond']]*1e6,label=LABELS[var],color=col,lw=1)
                axs[2,j].plot(x,p['receiver_proxy_A'][mask]*1e6,label=LABELS[var],color=col,lw=1)
            axs[0,j].set_title(f'{route} · {rate:g} Gb/s，同一验证数据片段');axs[0,j].set_ylabel('芯片 OUT 电压 (V)');axs[1,j].set_ylabel('LED 导电电流 (µA)');axs[2,j].set_ylabel('接收代理 (µA)');axs[2,j].set_xlabel('相对输入时间 (ns)');axs[2,j].axhline(62.5,color='#a44b43',ls='--',lw=1)
        handles,labels=axs[0,0].get_legend_handles_labels()
        fig.legend(handles,labels,loc='outside upper center',ncol=3,fontsize=10)
        save(fig,f'waveforms-{rate:g}G')
    fig,axs=plt.subplots(2,3,figsize=(14,8),layout='constrained')
    for i,route in enumerate('AB'):
        for j,rate in enumerate([.5,1,2]):
            r=row(route,'RC',rate);rec=recmap[r['name']];a,v=trace(r);ui=1/rate/1e9;p=receiver_proxy(a[:,0],a[:,v['iled_cond']]);e=eye_segments(a[:,0],p['receiver_proxy_A'],st['validation_bits'],st['validation_start_bit']*ui,ui,rec['transient']['sampler'])
            for y in e['signal_A']:axs[i,j].plot(e['phase_from_frozen_sample_ui'],np.asarray(y)*1e6,color=COLORS['RC'],alpha=.13,lw=.7)
            axs[i,j].axhline(62.5,color='#a44b43',ls='--');axs[i,j].axvline(0,color='#70818e',ls=':');axs[i,j].set(xlabel='相对冻结抽样点 (UI)',ylabel='接收代理 (µA)',ylim=(10,115),title=f'{route} · RC · {rate:g} Gb/s · {r["errors"]}/511 比特错误')
    save(fig,'eyes-rc')
    fig,axs=plt.subplots(1,2,figsize=(12,4.7),layout='constrained')
    for ax,route in zip(axs,'AB'):
        r=row(route,'RC',1);en=recmap[r['name']]['transient']['energy'];ports=en['rails']|{'DATA':en['ideal_DATA']};ax.bar(list(ports),[x['positive_draw_J_per_gross_bit']*1e15 for x in ports.values()],color=COLORS['RC'],label='正向取能');ax.bar(list(ports),[-x['returned_J_per_gross_bit']*1e15 for x in ports.values()],color='#b4c6cc',label='返回理想源');ax.axhline(0,color='#233d4b',lw=.8);ax.set(title=f'{route} · RC · 1 Gb/s',ylabel='每输入毛bit能量 (fJ)');ax.legend()
    save(fig,'energy-ports-rc')
    return {'rows':rows,'nominal':nom}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--summary',default='evidence/highspeed-nrz-pex/summary.json');ap.add_argument('--plots-only',action='store_true');ap.add_argument('--text-only',action='store_true');args=ap.parse_args()
    s=json.loads((ROOT/args.summary).read_text())
    assert not s['counts'].get('missing_planned_cases',1), 'Report requires the declared case list'
    assert not s['counts'].get('failed_or_unanalyzed_planned_cases',1), 'Incomplete or failed cases require explicit investigation'
    assert not s.get('completion',{}).get('hold'), 'Do not publish a held diagnostic run'
    work=ROOT/s['work'];p=ROOT/s['analysis_json'];assert sha(p)==s['analysis_sha256'];a=json.loads(p.read_text());FIG.mkdir(parents=True,exist_ok=True)
    data=({'rows':[r for r in s['rows'] if r['analysis_ok']],
           'nominal':[r for r in s['rows'] if r['analysis_ok'] and r['kind']=='nominal']}
          if args.text_only else plots(s,a,work))
    if not args.plots_only:
        template=OUT/'report-template.html';assert template.exists(),'Write report-template.html with evidence tokens before final generation'
        (OUT/'index.html').write_text(render_text(template.read_text(),s,data))
    print('Figures written to '+str(FIG))

def render_text(template,s,data):
    rows=data['rows'];nom=data['nominal']
    def pick(route,var,rate):return next(r for r in nom if r['route']==route and r['variant']==var and r['rate_Gbps']==rate)
    def high(route,var):return max((r['rate_Gbps'] for r in nom if r['route']==route and r['variant']==var and r['comparison_screen_passed']),default=0)
    content=OUT/'report-content.json'
    v=json.loads(content.read_text()) if content.exists() else {}
    v['RESULT_TABLE']=table(['路线','原理图最高筛查点','RC 最高筛查点','0.5 Gb/s 原理图能耗','0.5 Gb/s RC 能耗','变化'],[[rt,f(high(rt,'SCHEM'),2)+' Gb/s',f(high(rt,'RC'),2)+' Gb/s',f(pick(rt,'SCHEM',.5)['rail_plus_DATA_positive_draw_fJ_per_gross_bit'],1)+' fJ/bit',f(pick(rt,'RC',.5)['rail_plus_DATA_positive_draw_fJ_per_gross_bit'],1)+' fJ/bit',f(100*(pick(rt,'RC',.5)['rail_plus_DATA_positive_draw_fJ_per_gross_bit']/pick(rt,'SCHEM',.5)['rail_plus_DATA_positive_draw_fJ_per_gross_bit']-1),2)+'%']for rt in 'AB'])
    v['NOMINAL_TABLE']=table(['路线','模型','Gb/s','错误比特 / 511','幅度余量 / 75 µA','时序余量 / UI','正向取能 fJ/bit','通过筛查'],[[r['route'],r['variant'],r['rate_Gbps'],r['errors'],f(r['threshold_margin_normalized']),f(r['timing_min_margin_ui']),f(r['rail_plus_DATA_positive_draw_fJ_per_gross_bit'],1),'是' if r['comparison_screen_passed'] else '否'] for r in nom])
    dc=[r for r in rows if 'dc_bit' in r and r['corner']=='typical' and r['temp_C']==27 and r['vdd_V']==3.3]
    v['DC_TABLE']=table(['路线','模型','数据位','LED DC µA','相对目标误差'],[[r['route'],r['variant'],r['dc_bit'],f(r['LED_current_A']*1e6,6),f(r['LED_current_error_percent'],4)+'%'] for r in dc])
    v['PVT_TABLE']=table(['路线','模型','MOS / 温度 / VDD','Gb/s','比特错误','幅度余量','时序余量','接收筛查'],[[r['route'],r['variant'],f"{r['corner']} / {r['temp_C']}°C / {r['vdd_V']} V",r['rate_Gbps'],r['errors'],f(r['threshold_margin_normalized']),f(r['timing_min_margin_ui']),'是' if r['comparison_screen_passed'] else '否'] for r in rows if r['kind'] in ['slow_hot','fast_cold'] and r['variant'] in ['SCHEM','RC']])
    v['CONVERGENCE_TABLE']=table(['路线','模型','Gb/s','控制','能耗变化','幅度余量变化','比特错误数改变','筛查改变'],[[r['route'],r['variant'],r['rate_Gbps'],r['control'],f(r.get('energy_change_percent'),4)+'%',f(r.get('threshold_margin_change'),6),str(r.get('errors_changed')),str(r.get('screen_changed'))] for r in s['numerical_controls']])
    c=s['counts']; reused=sum(r['variant']=='SCHEM' for r in rows)
    v['RUN_COUNTS']=f"共 {c['case_results_found']} 条记录：{c['analyzed_DC']} 条 DC、{c['analyzed_transient']} 条瞬态。其中 {reused} 条 SCHEM 基线只读复用，还含 GEOM/SNAP 控制复用；不能称为同等数量的新仿真。预先声明的 {c['planned_cases']} 项计划完整覆盖，仿真和分析执行失败均为 0；这不代表所有电气与接收判据通过"
    v['RUN_PATH']=s['work'];v['ANALYSIS_SHA']=s['analysis_sha256']
    for name in ['rate-energy','stress','waveforms-0.5G','waveforms-1G','waveforms-2G','eyes-rc','energy-ports-rc','layout-A','layout-B','wire-to-rc','comparison-boundary']:
        v['FIG:'+name]=figure(name,{'rate-energy':'相同负载、接收与评判条件；圆点通过，叉号未通过。失败点能耗不能视为可用链路能效。','eyes-rc':'由 LED 导电电流经过假设光学与接收响应得到的无噪声眼图，非实测光学眼图。','energy-ports-rc':'同一个 511 输入 UI 窗口积分；负向柱是被理想电源吸收的能量。','stress':'全热身、训练和验证窗口，采样提取后局部 D/G/S/B；3.63 V 是项目筛查线。','layout-A':'A 核心真实 GDS，器件标注 W/L 单位 µm。图中不含 pad、ESD 或稳压器。','layout-B':'B 核心真实 GDS，RREF 与 RDUMMY 为外部元件。','wire-to-rc':'局部等效电路的原理示意；R、C 符号没有冒用实际提取数值。','comparison-boundary':'本次物理实现与外部测试台的边界。'}.get(name,'相同输入片段的真实 SPICE 波形；原理图、实际几何和 RC 结果直接叠加，不做幅度归一化。'))
    for key,value in v.items():template=template.replace('{{'+key+'}}',value)
    assert '{{' not in template,'Unresolved report tokens'
    # Reserve the SVG aspect ratio before lazy loading, so section links remain stable.
    def dimensions(match):
        tag=match.group(0);src=re.search(r'src="([^"]+)"',tag).group(1)
        if not src.endswith('.svg'):return tag
        box=ET.parse(OUT/src).getroot().attrib['viewBox'].split()
        return tag[:-1]+f' width="{float(box[2]):g}" height="{float(box[3]):g}">'
    template=re.sub(r'<img\b[^>]*>',dimensions,template)
    return template
if __name__=='__main__':main()
