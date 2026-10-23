#!/usr/bin/env python3
"""Read-only raw diagnosis of frozen r4 RC SS/FF cases; standalone SVG figures.

Run: build/layout/venv/bin/python scripts/highspeed_nrz_pvt_diagnosis.py
Writes only new-phase diagnosis outputs; never modifies the frozen baseline.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, fontManager

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'build/highspeed-nrz-pex/run-0m3zyewc'
RAW=ROOT/'build/highspeed-nrz-pvt/diagnosis'
EVIDENCE=ROOT/'evidence/highspeed-nrz-pvt'
FIG=ROOT/'docs/research/highspeed-nrz-pvt-20261023/figures'
BLUE='#176e86'; ORANGE='#b36631'; INK='#263944'; GRAY='#74828a'

def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
    return mod

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def relative(path):return str(path.relative_to(ROOT))
def dump(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def style():
    font=ROOT/'build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf'
    if font.exists():fontManager.addfont(font);family=FontProperties(fname=font).get_name()
    else:family='PingFang SC'
    plt.rcParams.update({'font.family':family,'font.size':11,'axes.titlesize':12,'axes.labelsize':11,
        'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#b7c2c7',
        'axes.labelcolor':INK,'text.color':INK,'xtick.color':INK,'ytick.color':INK,
        'grid.color':'#dce3e6','grid.linewidth':.7,'svg.fonttype':'none','savefig.facecolor':'white'})

def savefig(fig,name):
    files=[]
    for ext in ['svg','png']:
        p=FIG/f'{name}.{ext}';fig.savefig(p,dpi=150,bbox_inches='tight');files.append({'path':relative(p),'sha256':digest(p)})
    plt.close(fig);return files

def main():
    for p in [RAW,EVIDENCE,FIG]:p.mkdir(parents=True,exist_ok=True)
    metrics=load_module(WORK/'inputs/legacy/metrics.py','metrics')
    analyzer=load_module(WORK/'inputs/legacy/analyze.py','baseline_diagnosis_analysis');analyzer.ROOT=ROOT
    full=json.loads((WORK/'analysis.json').read_text());st=json.loads((WORK/'stimulus.json').read_text())
    selected=[];traces={}; records={}
    for z in full['cases']:
        c=z['case'];route=c['route'];rate=2 if route=='A' else .5
        if c['variant']!='RC' or c['rate_Gbps']!=rate or c['kind'] not in ['nominal','fast_cold','slow_hot']:continue
        p=WORK/'cases'/c['name']/'result.json';result=json.loads(p.read_text());a,src=analyzer.load_trace(result,p)
        t=a[:,0];v=result['vectors'];ui=1e-9/rate
        row={'case':c,'source':src};traces[route,c['kind']]=(t,a,v);records[route,c['kind']]=row
        print(c['name'],flush=True)
        if c['kind']=='fast_cold':
            stress=z['stress'];dev=next(d for d in stress['all_devices'] if d['instance']==stress['worst_instance'])
            peak=dev['terminal_differences'][stress['worst_pair']]['at_max_abs_time_s'];j=int(np.argmin(abs(t-peak)))
            boundary=int(t[j]/ui)*ui;near=['data','out']+dev['nodes']+[n for n in v if n.startswith('xdrv.vdd')]
            row['stress']={'device':dev,'peak_index':j,'peak_node_values_V':{n:float(a[j,v[n]]) for n in dict.fromkeys(near) if n!='0'},
                'input_edge_time_s':boundary,'time_into_edge_ps':float((t[j]-boundary)*1e12),
                'interpretation':'First inverter output voltage rises above VDD during the rising DATA edge; capacitive feedthrough is a mechanism inference, not isolated by this read-only waveform analysis.'}
            window=(t>=boundary-40e-12)&(t<=boundary+180e-12)
            names=['data',dev['nodes'][1],dev['nodes'][3]]
            tab=np.column_stack([(t[window]-boundary)*1e12,*[a[window,v[n]] for n in names]])
            f=RAW/(c['name']+'-feedthrough.csv');np.savetxt(f,tab,delimiter=',',header='time_after_input_edge_ps,'+','.join(names),comments='')
            row['stress']['focus_csv']={'path':relative(f),'sha256':digest(f)}
        else:
            rx=metrics.receiver_proxy(t,a[:,v['iled_cond']])['receiver_proxy_A']
            val=z['transient']['validation'];sm=z['transient']['sampler'];bits=np.array(st['validation_bits']);centers=st['validation_start_bit']*ui+np.arange(len(bits))*ui+sm['sample_delay_s']
            samples=np.interp(centers,t,rx);err=np.flatnonzero((samples>=62.5e-6)!=bits)
            row['receiver']={k:val[k] for k in ['deterministic_errors','min_one_A','max_zero_A','threshold_margin_normalized','timing_min_margin_ui']}
            row['receiver']['sample_delay_ui']=sm['sample_delay_ui']
            row['receiver']['error_bits']=[{'index':int(j),'bit':int(bits[j]),'rx_uA':float(samples[j]*1e6),'pattern_5_before_5_after':bits[max(0,j-5):j+6].tolist()}for j in err]
            groups={}
            for j in range(4,len(bits)-4):groups.setdefault(''.join(str(q) for q in bits[j-2:j+3]),[]).append(j)
            row['receiver']['patterns']={}
            for pattern in ['00100','01110','00000','11111']:
                ids=groups.get(pattern,[])
                if not ids:continue
                j=ids[int(np.argmin(samples[ids]))] if pattern[2]=='1' else ids[int(np.argmax(samples[ids]))]
                start=(st['validation_start_bit']+j)*ui;mask=(t>=start-ui)&(t<=start+4*ui)
                cols=['data','iled_cond','out']+[n for n in v if n in ['xdrv.ctrl.t1','xdrv.n1.t3','xdrv.bias.t0','xdrv.vx.t0','xdrv.gp.t0','xdrv.gb.t4']]
                tab=np.column_stack([(t[mask]-start)/ui,*[a[mask,v[n]] for n in cols],rx[mask]])
                f=RAW/(c['name']+'-'+pattern+'.csv');np.savetxt(f,tab,delimiter=',',header='relative_UI,'+','.join(cols)+',rx_A',comments='')
                peakmask=(t>=start)&(t<start+3.5*ui)
                one={'count':len(ids),'min_sample_rx_uA':float(min(samples[ids])*1e6),'max_sample_rx_uA':float(max(samples[ids])*1e6),
                    'selected_validation_bit_index':int(j),'selected_window_start_s':float(start),
                    'focus_csv':{'path':relative(f),'sha256':digest(f)},
                    'within_0_to_3p5UI_LED_peak_uA':float(np.max(a[peakmask,v['iled_cond']])*1e6),
                    'within_0_to_3p5UI_RX_peak_uA':float(np.max(rx[peakmask])*1e6)}
                if 'xdrv.bias.t0' in v:
                    bias=float(np.interp(start,t,a[:,v['xdrv.bias.t0']]))
                    one['reference_node_V_at_input_edge']=bias
                    one['estimated_RREF_current_uA_using_internal_bias_node']=(c['vdd_V']-bias)/88386.1064910889*1e6
                    one['reference_current_note']='Estimate uses the saved internal reference gate node; the small unsaved external-port-to-gate parasitic voltage drop is omitted.'
                if route=='A' and pattern=='00100':
                    ctr=a[:,v['xdrv.ctrl.t1']]
                    def crossings(level):
                        ids_cross=np.flatnonzero((ctr[:-1]-level)*(ctr[1:]-level)<0)
                        crossings=[]
                        for ii in ids_cross:
                            tc=t[ii]+(level-ctr[ii])*(t[ii+1]-t[ii])/(ctr[ii+1]-ctr[ii])
                            if start<=tc<=start+2.5*ui:crossings.append({'time_from_input_edge_ps':float((tc-start)*1e12),'direction':'rising' if ctr[ii+1]>ctr[ii] else 'falling'})
                        return crossings
                    one['CTRL_crossings_50percent_VDD']=crossings(.5*c['vdd_V'])
                    one['CTRL_crossings_90percent_VDD']=crossings(.9*c['vdd_V'])
                row['receiver']['patterns'][pattern]=one
            traces[route,c['kind']]=(t,a,v,rx)
        selected.append(row)
    style();files=[]
    fig,ax=plt.subplots(2,2,figsize=(12,7),sharex='col',gridspec_kw={'height_ratios':[1.15,1]})
    for col,route in enumerate('AB'):
        row=records[route,'fast_cold'];s=row['stress'];t,a,v=traces[route,'fast_cold'];dev=s['device'];b=s['input_edge_time_s'];sel=(t>=b-40e-12)&(t<=b+180e-12);x=(t[sel]-b)*1e12
        g=a[sel,v[dev['nodes'][1]]];body=a[sel,v[dev['nodes'][3]]]
        title='A 电压驱动 · 2 Gb/s' if route=='A' else 'B 电流转向 · 0.5 Gb/s'
        ax[0,col].set_title(title,loc='left',fontweight='bold');ax[0,col].plot(x,a[sel,v['data']],color=GRAY,ls='--',label='外部 DATA（20 ps 上升）')
        ax[0,col].plot(x,g,color=BLUE,label='第一级反相器输出 N1' if route=='A' else '第一级反相器输出 GB')
        ax[0,col].axhline(3.6,color=INK,ls=':',lw=1,label='VDD = 3.6 V');ax[0,col].set_ylim(-.2,4.05);ax[0,col].legend(loc='lower right',fontsize=9);ax[0,col].set_ylabel('节点电压 / V')
        ax[1,col].plot(x,(g-3.6)*1e3,color=BLUE,label='栅节点 − VDD')
        ax[1,col].plot(x,body*1e3,color=ORANGE,ls='--',label='体端相对地电压')
        ax[1,col].axhline(30,color=INK,ls=':',lw=1,label='30 mV：3.63 V 筛查剩余量')
        ax[1,col].set_ylim(-10,190);ax[1,col].set_ylabel('局部放大 / mV');ax[1,col].set_xlabel('相对 DATA 上升起点 / ps')
        j=s['peak_index'];p=s['time_into_edge_ps'];value=float(a[j,v[dev['nodes'][1]]]);ax[1,col].plot(p,(value-3.6)*1e3,'o',color=BLUE,ms=5)
        ax[1,col].annotate(f"VGB = {dev['max_abs_terminal_V']:.4f} V\n发生在上升开始后 {p:.2f} ps",xy=(p,(value-3.6)*1e3),xytext=(42,125),arrowprops={'arrowstyle':'->','color':GRAY},fontsize=10)
        ax[1,col].legend(loc='lower right',fontsize=8)
        for q in ax[:,col]:q.grid(True,alpha=.65);q.set_xlim(-30,150)
    fig.suptitle('快冷过冲位于前级逻辑节点：FF / −40 °C / 3.6 V',x=.07,ha='left',fontsize=16,fontweight='bold')
    fig.text(.07,.015,'证据：实际 RC 提取网表波形。主因与输入边沿的电容耦合一致；Cgd 与布线耦合的各自贡献仍需控制实验。\n3.63 V 为项目筛查值，并非晶圆厂可靠性限值。下排仅放大高电平附近，负向跃迁超出显示范围。',fontsize=9,color=GRAY)
    fig.subplots_adjust(left=.08,right=.98,top=.88,bottom=.15,hspace=.24,wspace=.2)
    files+=savefig(fig,'baseline-fast-cold-feedthrough')
    fig,ax=plt.subplots(2,2,figsize=(12,7.5),sharex='col',sharey='row')
    for col,route in enumerate('AB'):
        ax[0,col].set_title('A 电压驱动 · 2 Gb/s（1 UI = 0.5 ns）' if route=='A' else 'B 电流转向 · 0.5 Gb/s（1 UI = 2 ns）',loc='left',fontweight='bold')
        for kind,color,linestyle,label in [('nominal',BLUE,'-','TT / 27 °C / 3.3 V'),('slow_hot',ORANGE,'--','SS / 125 °C / 3.0 V')]:
            row=records[route,kind];t,a,v,rx=traces[route,kind];item=row['receiver']['patterns']['00100'];start=item['selected_window_start_s'];ui=1e-9/row['case']['rate_Gbps'];mask=(t>=start-.5*ui)&(t<=start+3.5*ui);x=(t[mask]-start)/ui
            ax[0,col].plot(x,a[mask,v['iled_cond']]*1e6,color=color,ls=linestyle,lw=1.7,label=label)
            ax[1,col].plot(x,rx[mask]*1e6,color=color,ls=linestyle,lw=1.7,label=label)
            delay=row['receiver']['sample_delay_ui'];sample=item['min_sample_rx_uA'];ax[1,col].plot(delay,sample,'o',mec=color,mfc='white',ms=6)
            if kind=='slow_hot':
                peak=item['within_0_to_3p5UI_RX_peak_uA'];ax[1,col].text(2.05,24 if route=='A' else 47,f'慢热 RX 峰值\n{peak:.3f} μA',fontsize=10,color=ORANGE)
                ax[0,col].text(1.95,91,f"慢热 LED 峰值\n{item['within_0_to_3p5UI_LED_peak_uA']:.3f} μA",fontsize=10,color=ORANGE)
        for rr in range(2):
            q=ax[rr,col];q.axvspan(0,1,facecolor='#dde7eb',alpha=.3,label='输入 DATA = 1' if rr==0 else None)
            q.axhline(62.5,color=INK,ls=':',lw=1);q.set_ylim(0,112);q.set_xlim(-.5,3.5);q.grid(True,alpha=.65)
        ax[0,col].legend(loc='lower right',fontsize=8);ax[1,col].set_xlabel('相对孤立“1”输入起点 / UI')
    ax[0,0].set_ylabel('LED 导电电流 / μA');ax[1,0].set_ylabel('固定光学 / 接收代理输出 / μA')
    fig.suptitle('慢热失败来自短脉冲幅度不足：PRBS9 验证序列第 139 位',x=.07,ha='left',fontsize=16,fontweight='bold')
    fig.text(.07,.018,'负载：同一静态 MicroLED 模型，CLED = 200 fF；光学 τ = 200 ps；接收带宽 = 1 GHz。\n灰色带表示输入“1”持续的 1 UI；虚线为固定 62.5 μA 判决阈值；空心圆为各工况经训练后冻结的采样点。\n两列速率不同，横轴按各自 UI 归一化；第 139 位对应从 0 开始的索引 138；这些是电流等效代理，并非光学测量。',fontsize=9,color=GRAY)
    fig.subplots_adjust(left=.08,right=.98,top=.88,bottom=.18,hspace=.18,wspace=.16)
    files+=savefig(fig,'baseline-slow-hot-isolated-one')
    summary={'schema_version':1,'scope':'Independent read-only diagnosis of immutable baseline RC waveform data.',
        'script':relative(Path(__file__)),'script_sha256':digest(Path(__file__)),'baseline_analysis':relative(WORK/'analysis.json'),'baseline_analysis_sha256':digest(WORK/'analysis.json'),
        'stimulus_sha256':digest(WORK/'stimulus.json'),'records':selected,'figures':files,
        'claims':{'observed':'FF peak is first-inverter output voltage above VDD, with body voltage near ground. SS isolated-one conductive-current and receiver peaks are substantially reduced.',
                  'inference':'Fast DATA-edge capacitive feedthrough is consistent with first-stage overshoot; intrinsic versus extracted coupling contributions require an intervention.',
                  'not_proved':'This diagnosis neither certifies a reliability limit nor changes the receiver/LED contract or proves a fix.'}}
    dump(EVIDENCE/'diagnosis.json',summary)
    print(json.dumps({'cases':len(selected),'figures':files,'evidence':relative(EVIDENCE/'diagnosis.json')},ensure_ascii=False))

if __name__=='__main__':main()
