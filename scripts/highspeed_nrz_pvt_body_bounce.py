#!/usr/bin/env python3
"""Compare physical-revision substrate coupling at the same frozen DATA edge.

Uses existing raw results only. Default edge: full-stimulus bit793 (falling),
route A1Gb/s FF -40C3.6V. No transient, model, or receiver mutation.
"""
from pathlib import Path
import argparse,json,hashlib,sys,importlib.util
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
FIG=ROOT/'docs/research/highspeed-nrz-pvt-20261023/figures'
E=ROOT/'evidence/highspeed-nrz-pvt'

def module(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return str(p.relative_to(ROOT))
def node_value(a,v,n):return np.zeros(len(a)) if n=='0' else a[:,v[n]]

def load(work,label,edge=793):
 name='AFTER-A-fast_cold-1G-ff--40C-3.6V-C200-L0.5-e20-s40';p=work/'cases'/name
 result=json.loads((p/'result.json').read_text());record=json.loads((p/'analysis.json').read_text())
 module(work/'inputs/legacy/metrics.py','metrics');a=module(work/'inputs/legacy/analyze.py','bounce_analyzer');a.ROOT=ROOT
 trace,source=a.load_trace(result,p/'result.json');t=trace[:,0];v=result['vectors'];ui=1e-9;boundary=edge*ui
 # Logical identity mapping is authoritative; fall back only to gate node for independent diagnostic variants.
 dev=next(d for d in result['devices'] if d.get('original_instance','').upper()=='XN2')
 # Extracted source can be the logical drain after source/drain reversal.
 ctrl=next(n for n in dev['nodes'] if 'ctrl' in n);body=dev['nodes'][3]
 core=work/'inputs'/json.loads((work/'manifest.json').read_text())['variants']['A']['AFTER']['path']
 res=None
 for line in core.read_text().splitlines():
  q=line.split()
  if len(q)>4 and q[4].lower()=='ppolyf_u_1k_6p0':res=q;break
 if res is None:raise ValueError('No poly resistor found')
 n=lambda q:'0' if q.upper()=='VSS' else 'data' if q.upper()=='DATA' else 'xdrv.'+q.lower()
 rb=n(res[3]);di=n(next(q for q in res[1:3] if q.lower().split('.')[0]=='di'));ctl=node_value(trace,v,ctrl);bodyv=node_value(trace,v,body);rbv=node_value(trace,v,rb)
 # Node names from actual transistor and resistor rather than drawing labels.
 sig={'data':trace[:,v['data']],'di':node_value(trace,v,di),'ctrl':ctl,'body':bodyv,'resbody':rbv,'stress':ctl-bodyv}
 mask=(t>=boundary-40e-12)&(t<=boundary+180e-12);local=np.flatnonzero(mask);j=int(local[np.argmax(sig['stress'][mask])]);tm=float(t[j])
 st=json.loads((work/'stimulus.json').read_text());assert st['bits'][edge-1:edge+1]==[1,0], 'Requested edge must be falling'
 out={'label':label,'work':rel(work),'source':source,'edge_full_stimulus_index':edge,'edge_validation_index':edge-st['validation_start_bit'],
      'edge_s':boundary,'pattern_5_before_5_after':st['bits'][edge-5:edge+6],
      'terminal_order_note':'The extracted transistor swaps D/S relative to the schematic; extracted VSB here corresponds to schematic drain-to-body voltage.',
      'actual_nodes':{'ctrl':ctrl,'second_inverter_body':body,'poly_substrate':rb,'DI':di},
      'window_peak':{'time_s':tm,'time_after_edge_ps':(tm-boundary)*1e12,'CTRL_V':float(ctl[j]),'NMOS_body_V':float(bodyv[j]),'resistor_substrate_V':float(rbv[j]),'VSB_V':float(sig['stress'][j])},
      'window_extrema':{'resistor_substrate_min_V':float(np.min(rbv[mask])),'second_NMOS_body_min_V':float(np.min(bodyv[mask]))},
      'global_stress':{k:record['stress'][k]for k in ['max_abs_terminal_V','worst_instance','worst_pair']},
      'model_boundary':'Substrate/body resistance and capacitance are from the public extraction deck and model. No wafer measurement or field-solver validation of this impedance is claimed.'}
 return (t[mask]-boundary)*1e12,{k:z[mask]for k,z in sig.items()},out

def main():
 p=argparse.ArgumentParser();p.add_argument('--before',default='build/highspeed-nrz-pvt/formal-poly58-r1');p.add_argument('--after');args=p.parse_args()
 style=module(ROOT/'scripts/highspeed_nrz_pvt_diagnosis.py','diagnosis_style');style.style();FIG.mkdir(parents=True,exist_ok=True);E.mkdir(parents=True,exist_ok=True)
 runs=[load(ROOT/args.before,'r1 原版图')]
 if args.after:
  runs.append(load(ROOT/args.after,'r4 修改后版图'))
  peak_ps=runs[0][2]['window_peak']['time_after_edge_ps']
  for tx,sig,info in runs:
   info['at_identical_baseline_peak_time']={'time_after_edge_ps':peak_ps,**{name:float(np.interp(peak_ps,tx,sig[name])) for name in ['data','di','ctrl','body','resbody','stress']},'method':'Linear interpolation at the baseline sampled peak timestamp; waveform peak searches remain separately reported.'}
 fig,ax=plt.subplots(2,2,figsize=(12,7.5),sharex=True);colors=['#a66b48','#176e86'] if args.after else ['#176e86']
 for (t,s,info),col in zip(runs,colors):
  lab=info['label'];ax[0,0].plot(t,s['data'],color='#74828a',ls='--',label='外部 DATA' if lab==runs[0][2]['label'] else None)
  ax[0,0].plot(t,s['di'],color=col,label=lab+' · 电阻后 DI')
  ax[0,1].plot(t,s['ctrl'],color=col,label=lab+' · CTRL')
  ax[1,0].plot(t,s['resbody'],color=col,label=lab+' · 电阻衬底')
  ax[1,0].plot(t,s['body'],color=col,ls='--',label=lab+' · 第二级 NMOS 体端')
  ax[1,1].plot(t,s['stress'],color=col,label=lab+' · CTRL − 体端')
  q=info['window_peak'];ax[1,1].plot(q['time_after_edge_ps'],q['VSB_V'],'o',color=col,ms=5)
 ax[0,0].set_title('① DATA 的 20 ps 下降沿注入电荷',loc='left');ax[0,1].set_title('② r1 应力峰值时 CTRL 仍低于 VDD',loc='left')
 ax[1,0].set_title('③ 局部衬底与 MOS 体端电位下降',loc='left');ax[1,1].set_title('④ 端电压差因此超过项目筛查值',loc='left')
 ax[0,0].set_ylim(-.15,3.85);ax[0,1].set_ylim(3.48,3.63);ax[1,0].set_ylim(-.85,.15);ax[1,1].set_ylim(3.48,3.75)
 ax[0,1].axhline(3.6,color='#263944',ls=':',label='理想 VDD = 3.6 V');ax[1,1].axhline(3.63,color='#263944',ls=':',label='项目筛查 3.63 V')
 q=runs[0][2]['window_peak'];ax[1,1].annotate(f"{q['CTRL_V']:.6f} − ({q['NMOS_body_V']:.6f})\n= {q['VSB_V']:.6f} V",(q['time_after_edge_ps'],q['VSB_V']),xytext=(52,3.695),arrowprops={'arrowstyle':'->','color':'#74828a'},fontsize=10)
 if args.after:
  old=runs[0][2]['at_identical_baseline_peak_time'];new=runs[1][2]['at_identical_baseline_peak_time']
  ax[1,0].text(46,-.31,f"同一 20.416 ps 时刻：\n电阻衬底 {old['resbody']*1e3:.3f} → {new['resbody']*1e3:.3f} mV\nNMOS 体端 {old['body']*1e3:.3f} → {new['body']*1e3:.3f} mV",fontsize=9,color='#263944')
  ax[1,1].plot(new['time_after_edge_ps'],new['stress'],'o',color='#176e86',ms=5)
  ax[1,1].annotate(f"r4 同刻：{new['stress']:.6f} V",(new['time_after_edge_ps'],new['stress']),xytext=(55,3.565),arrowprops={'arrowstyle':'->','color':'#176e86'},fontsize=10,color='#176e86')
 for q in ax.flat:q.grid(True,alpha=.65);q.set_xlim(-30,150);q.set_ylabel('电压 / V');q.legend(fontsize=8,loc='lower right')
 for q in ax[1,:]:q.set_xlabel('相对同一个 DATA 下降起点 / ps')
 fig.suptitle('布局修复前后的同一边沿：衬底电位恢复稳定' if args.after else '加入实际版图后暴露的失效：衬底耦合改变了器件端电压差',x=.07,ha='left',fontsize=16)
 fig.text(.07,.015,'条件：A 路线，1 Gb/s，FF / −40 °C / 3.6 V；全序列索引 793 的同一次下降沿。\n高阻多晶硅电阻的模型含两端到衬底的电容；提取衬底电阻网络使体端偏离理想地。\nr1 → r4 同时调整电阻尺寸、局部衬底接触与 DI 布线；这里对齐同一边沿观察体端响应。\n该衬底阻抗来自公开模型和提取规则，尚未经晶圆测量或场求解器校准；3.63 V 是项目筛查值。',fontsize=9,color='#74828a')
 fig.subplots_adjust(left=.08,right=.98,top=.88,bottom=.16,hspace=.26,wspace=.23)
 name='layout-body-bounce-before-after' if args.after else 'layout-r1-body-bounce';files=[]
 for ext in ['svg','png']:
  f=FIG/f'{name}.{ext}';fig.savefig(f,dpi=150,bbox_inches='tight');files.append({'path':rel(f),'sha256':sha(f)})
 plt.close(fig)
 (E/f'{name}.json').write_text(json.dumps({'script':rel(Path(__file__)),'script_sha256':sha(Path(__file__)),'records':[x[2]for x in runs],'figures':files},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'records':[{'peak':x[2]['window_peak'],'same_time':x[2].get('at_identical_baseline_peak_time')}for x in runs],'figures':files},ensure_ascii=False))
if __name__=='__main__':main()
