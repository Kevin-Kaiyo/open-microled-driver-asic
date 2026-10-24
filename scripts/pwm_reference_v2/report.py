#!/usr/bin/env python3
"""Chinese evidence report/figures; consumes immutable cases, never runs SPICE."""
from pathlib import Path
import gzip,hashlib,json,re,shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2];W=ROOT/'build/pwm-reference-v2/20261024';E=ROOT/'evidence/pwm-reference-v2/20261024';D=ROOT/'docs/research/pwm-reference-startup-20261024';F=D/'electrical-figures';P=E/'plot-data'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def raw(name):
 p=W/name/'waveform.dat.gz'
 if p.exists():return np.atleast_2d(np.loadtxt(gzip.open(p),skiprows=1))
 return np.atleast_2d(np.loadtxt(W/name/'waveform.dat',skiprows=1))
def main():
 network=json.loads((ROOT/'analog/pwm_reference_v2/final-network.json').read_text());selected_prefix=network.get('selected_prefix','c15');prefix=selected_prefix+'_';selected_cf=network.get('selected_filter_c_nf',15)
 F.mkdir(parents=True,exist_ok=True);P.mkdir(parents=True,exist_ok=True)
 fp=W/'inputs/report-font';fp.mkdir(parents=True,exist_ok=True)
 for n in ['NotoSansCJKsc-Regular.otf','LICENSE.txt']:
  src=ROOT/'build/blender-pwm-animation/fonts'/n;dst=fp/n
  if not dst.exists():shutil.copy2(src,dst)
 font_manager.fontManager.addfont(str(fp/'NotoSansCJKsc-Regular.otf'));plt.rcParams.update({'font.family':'Noto Sans CJK SC','axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'path','figure.facecolor':'#fcfcfa','axes.facecolor':'#fcfcfa','axes.grid':True,'grid.alpha':.18})
 data=[json.loads(p.read_text()) for p in sorted(W.glob('*/result.json'))];rows={x['case']['name']:x for x in data if 'case' in x};loops=[x for x in data if 'crossings' in x];selected=[x for n,x in rows.items() if n.startswith(prefix)];dc=[x for n,x in rows.items() if n.startswith('n2rl_dc_') and 'extref' not in n];dynamic=[x for n,x in rows.items() if n.startswith(prefix+'dyn_')];valid=json.loads((E/'validation.json').read_text()) if (E/'validation.json').exists() else {}
 figrecords=[]
 def export(fig,name,sources):
  fig.tight_layout();paths=[]
  for ext in ['png','svg']:
   p=F/(name+'.'+ext);fig.savefig(p,dpi=180,bbox_inches='tight');paths.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p)})
  plt.close(fig);figrecords.append(dict(name=name,outputs=paths,sources=sources))
 def series(name):
  a=raw(name);ix=set(np.linspace(0,len(a)-1,min(2500,len(a)),dtype=int));ix.update([int(a[:,1].argmin()),int(a[:,1].argmax())]);held=np.flatnonzero(a[:,0]<=20e-6);ix.update([int(held[a[held,1].argmin()]),int(held[a[held,1].argmax()])]) if len(held) else None;b=a[sorted(ix)];p=P/(name+'.csv');np.savetxt(p,b[:,[0,1,2,4,5,11,18,19]],delimiter=',',header='time_s,total_current_a,reference_rail_v,control_v,sense_v,die_ground_v,diode_total_a,diode_displacement_a',comments='',fmt='%.15e');return a,{'case':name,'raw_sha256':rows[name].get('raw_sha256'),'plot_data':str(p.relative_to(ROOT)),'plot_data_sha256':sha(p)}
 if prefix+'step' in rows and rows[prefix+'step']['completed']:
  fig,ax=plt.subplots(2,1,figsize=(10,6),sharex=True);sources=[]
  for n,label,color in [('pilot_step_cff0_obs2','原 Miller 补偿，未加供电 RC','#a34736'),('comp_n2_150p_step','150 pF 局部补偿诊断，未加 RC','#9b8600'),(prefix+'step','最终 PCB 补偿＋供电 RC＋N2 引脚 R/L','#147d83')]:
   a,meta=series(n);sources.append(meta);ax[0].plot(a[:,0]*1e6,a[:,1]*1e6,label=label,c=color,lw=1.2);ax[1].plot(a[:,0]*1e6,a[:,2],label=label,c=color,lw=1.2)
  ax[0].set(ylabel='LED总支路电流（µA）',title='相同10% / 10ns供电阶跃：改补偿连接后减少电流扰动');ax[0].legend(fontsize=8);ax[1].set(xlabel='时间（µs）',ylabel='芯片参考电源（V）',xlim=(5,60));export(fig,'供电阶跃与恢复',sources)
 final_start=prefix+'startup_fullmesh_trap' if rows.get(prefix+'startup_fullmesh_trap',{}).get('completed') else prefix+'startup_fullmesh'
 if rows.get(final_start,{}).get('completed'):
  a,meta=series(final_start);fig,ax=plt.subplots(3,1,figsize=(10,7));held=a[:,0]<=20e-6;ax[0].plot(a[:,0]*1e6,a[:,2],label='参考电源',c='#147d83');ax[0].plot(a[:,0]*1e6,a[:,5],label='SENSE',c='#274861');ax[0].set(ylabel='电压（V）',title='受控启动：PCB被动充电，外部FAULT保持20µs');ax[0].legend(fontsize=8)
  ax[1].plot(a[held,0]*1e6,a[held,1]*1e12,label='总支路电流',c='#147d83');ax[1].plot(a[held,0]*1e6,(a[held,18]-a[held,19])*1e12,label='导电分量',c='#a34736');ax[1].set(ylabel='保持窗电流（pA）',xlim=(0,20));ax[1].legend(fontsize=8)
  ax[2].plot(a[:,0]*1e6,a[:,1]*1e6,c='#147d83');ax[2].axvline(20,c='#888',ls='--',label='FAULT释放');ax[2].axvline(21.5,c='#444',ls=':',label='PERMIT许可');ax[2].set(xlabel='时间（µs）',ylabel='总支路电流（µA）',xlim=(19.5,40));ax[2].legend(fontsize=8);export(fig,'启动保持与许可', [meta])
 if dc:
  fig,ax=plt.subplots(figsize=(9,4));x=np.arange(3);labels=['0°C','27°C','85°C'];sources=[]
  for off,co,label,color in [(-.18,'ss','SS / 2.97V','#a34736'),(0,'typical','TT / 3.3V','#147d83'),(.18,'ff','FF / 3.63V','#274861')]:
   vals=[[r['error_pct'] for r in dc if r['case']['corner']==co and r['case']['temp_c']==t] for t in [0,27,85]]
   if not all(vals):continue
   lo=np.array([min(v) for v in vals]);hi=np.array([max(v) for v in vals]);mid=(lo+hi)/2;ax.errorbar(x+off,mid,yerr=np.vstack([mid-lo,hi-mid]),fmt='o',capsize=5,label=label,c=color)
  ax.axhline(5,c='#777',ls='--');ax.axhline(-5,c='#777',ls='--');ax.set(xticks=x,xticklabels=labels,ylabel='相对100µA误差（%）',ylim=(-5.6,5.6),title='DC开路等效基线：9组PVT，每组16个独立电阻顶点');ax.legend();export(fig,'直流PVT与独立电阻角落',[{'case':r['case']['name'],'raw_sha256':r['raw_sha256']} for r in dc])
 if dynamic:
  fig,ax=plt.subplots(figsize=(10,4));groups=[(co,[x for x in dynamic if x['case']['corner']==co]) for co in ['typical','ss','ff']];labs=[];vals=[]
  for co,items in groups:
   if items:labs.append({'typical':'TT / 27°C','ss':'SS / 85°C','ff':'FF / 0°C'}[co]);vals.append(max(x['excursion_pct'] for x in items if x['completed']))
  ax.bar(labs,vals,color=['#147d83','#a34736','#274861'][:len(vals)],width=.45);ax.axhline(20,c='#777',ls='--',label='20%研究预算');ax.set(ylabel='最大相对电流偏差（%）',title='TT含8个独立R/C顶点；SS、FF各验证快/慢两端点');ax.legend();export(fig,'供电动态容差',[{'case':r['case']['name'],'raw_sha256':r.get('raw_sha256')} for r in dynamic])
 final_loops=[x for x in loops if x.get('n2_pin_package') and x.get('comp_damp_ohm')==10 and selected_cf*.89<=x.get('filter_c_nf',100)<=selected_cf*1.11 and x.get('complete_source_identity')]
 if final_loops:
  fig,ax=plt.subplots(2,1,figsize=(10,6),sharex=True);sources=[]
  names=['loop_cff0_cc30_cs30_typical_27','loop_cff1000_cc30_cs30_typical_27']+[x['name'] for x in final_loops]
  for name in names:
   p=E/(name+'.csv');a=np.loadtxt(p,delimiter=',',skiprows=1);label='原Miller' if name==names[0] else '被拒绝：1000pF前馈' if name==names[1] else '最终网络 '+{'typical':'TT','ss':'SS','ff':'FF'}[next(x['corner'] for x in final_loops if x['name']==name)];ax[0].semilogx(a[:,0],a[:,1],label=label);ax[1].semilogx(a[:,0],180+a[:,2],label=label);sources.append({'loop':name,'csv_sha256':sha(p)})
  ax[0].axhline(0,c='#777',ls='--');ax[0].set(ylabel='局部返回比幅度（dB）',title='两次独立注入的局部返回比估计；不代表全多环路签核');ax[0].legend(fontsize=8);ax[1].set(xlabel='频率（Hz）',ylabel='180°＋相位（°）',xlim=(1e2,1e7));export(fig,'局部环路对照',sources)
 summary=dict(baseline_commit='112ba95969ac6a2141c305324ea694e7b96c0765',selected_prefix=selected_prefix,selected_filter_c_nf=selected_cf,selected_network=network,selected_acceptance=valid.get('selected_acceptance',False),selected_case_count=len(selected),selected_completed=sum(r['completed'] for r in selected),selected_passed=sum(r.get('passed',False) for r in selected),dc_matrix=dict(basis='144-point N2-package baseline with100nF and no added damping; capacitor branch is open atDC. Final capacitor/damping values leave the DC network identical; nominal/global extrema were separately replayed.',count=len(dc),passed=sum(r.get('passed',False) for r in dc),min_error_pct=min((r['error_pct'] for r in dc),default=None),max_error_pct=max((r['error_pct'] for r in dc),default=None)),dynamic_matrix=dict(count=len(dynamic),passed=sum(r.get('passed',False) for r in dynamic),max_excursion_pct=max((r.get('excursion_pct',0) for r in dynamic),default=None),max_restore_s=max((r.get('settle_s') or 0 for r in dynamic),default=None)),key_results={n:rows[n] for n in [prefix+'dc',prefix+'step',prefix+'step_fine',prefix+'startup_fullmesh',prefix+'startup_fullmesh_trap',prefix+'fault',prefix+'pwm'] if n in rows},startup_corners={n:rows[n] for n in [prefix+'startup_ss_slow',prefix+'startup_ff_fast'] if n in rows},dc_equivalence_spots=[{'case':n,'baseline':r['case']['equivalence_baseline_case'],'current_delta_a':r['current_a']-rows[r['case']['equivalence_baseline_case']]['current_a']} for n,r in rows.items() if n.startswith(prefix+'dc_equiv_')],external_reference_spots=[r for n,r in rows.items() if n.startswith(prefix+'dc_extref_')],historical_candidates={n:rows[n] for n in ['damped_startup_ss_slow','c47_startup_ss_slow','c47_dyn_ss_mmm','c47_dyn_ss_ppp'] if n in rows},final_local_loops=final_loops,numerical_validation=valid.get('numerical_comparisons',[]),identity_exceptions=valid.get('identity_exceptions',[]),figures=figrecords,boundaries=['外部0.5V基准边界，未验证片内带隙','外部FAULT/RTL许可，非自主POR','原合成LED，电流/电荷不是实测光功率','N2及原供电引脚R/L/ESR为工程应力，不含完整pad/ESD/互感','原39MOS真实PEX未修改；外部补偿改变不产生新GDS','局部两注入估计，不升级为全多环路/硅/可靠性签核'])
 save(E/'final-summary.json',summary);save(E/'figure-manifest.json',dict(script_sha256=sha(Path(__file__)),font_sha256=sha(fp/'NotoSansCJKsc-Regular.otf'),font_license_sha256=sha(fp/'LICENSE.txt'),figures=figrecords));save(E/'summary.json',dict(count=len(rows),completed_count=sum(x['completed'] for x in rows.values()),results=list(rows.values()),loops=loops))
 print(json.dumps({k:summary[k] for k in ['selected_case_count','selected_completed','selected_passed','dc_matrix','dynamic_matrix']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
