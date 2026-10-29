#!/usr/bin/env python3
"""Extract a continuous startup->data run while retaining20ns filter-state warmup."""
import json,gzip,shutil
import numpy as np
from run import ROOT,BUILD,OLD,ENERGY,sha,emit

def extract(case):
 src=BUILD/case;m=json.loads((src/'manifest.json').read_text());r=json.loads((src/'result.json').read_text());c=m['config'];start=c['frame_start_ns']*1e-9;end=m['end_s'];pre=20e-9
 dest=BUILD/(case+'-frame');assert r['simulation_ok']
 if dest.exists():return dest.name
 dest.mkdir();a=np.loadtxt(ROOT/r['waveform']['path'],skiprows=1);t=a[:,0];ix={e:i+1 for i,e in enumerate(m['expressions'])}
 assert t[0]==0 and t[-1]>=end-1e-15
 cut=np.unique(np.r_[start,t[(t>start)&(t<end)],end]);dt=np.diff(cut)
 assert dt.max()<32/37/(c['rate']*1e9)/c['frame_steps']*1.0001, ('Frame native step too large',dt.max())
 power={p:-a[:,ix['v('+n+')']]*a[:,ix['i('+p+')']] for p,n in m['ports'].items()}
 ledger={port:ENERGY.signed_integrals(cut,np.interp(cut,t,values)) for port,values in power.items()}
 totals={k:sum(v[k] for v in ledger.values()) for k in ['positive_J','returned_J','net_J']};totals.update(positive_pJ_per_offered_payload_bit=totals['positive_J']/4096*1e12,net_pJ_per_offered_payload_bit=totals['net_J']/4096*1e12)
 cutpre=np.unique(np.r_[start-pre,t[(t>start-pre)&(t<end)],start,end]);wave=np.column_stack([cutpre-start]+[np.interp(cutpre,t,a[:,k]) for k in range(1,a.shape[1])]);frame=wave[wave[:,0]>=0]
 with gzip.open(dest/'waveform.dat.gz','wt',compresslevel=5) as f:np.savetxt(f,wave,header='time '+' '.join(m['expressions']),comments='',fmt='%.15e')
 c=dict(c,mode='frame',steps=c['frame_steps']);m=dict(m,case=dest.name,config=c,end_s=end-start,parent_continuous_case=case,parent_waveform_sha256=r['waveform']['sha256'],prehistory_s=pre)
 emit(dest/'manifest.json',m);shutil.copy2(src/'stimulus.json',dest/'stimulus.json');shutil.copytree(src/'inputs',dest/'inputs');shutil.copy2(__file__,dest/'inputs/extract_frame.py');shutil.copy2(src/'ngspice.log',dest/'ngspice.log')
 stress=OLD.stress(frame,ix,m['devices']);stressmax=max(max(s['max_abs_terminal_V'].values()) for s in stress);body=max(s['max_body_forward_V'] for s in stress)
 result=dict(case=dest.name,config=c,exit_code=0,simulation_ok=True,current_range_mA=[float(frame[:,1].min()*1000),float(frame[:,1].max()*1000)],stress=stress,device_screen_passed=all(s['screen_pass'] for s in stress),max_terminal_V=stressmax,max_body_forward_V=body,total_energy=totals,energy_by_port=ledger,max_timestep_ps=float(dt.max()*1e12),waveform=dict(path=str((dest/'waveform.dat.gz').relative_to(ROOT)),sha256=sha(dest/'waveform.dat.gz')),energy_method='Exact original native PWL power cropped at exact frame endpoints; startup energy excluded from per-bit result',continuous_run=dict(parent_case=case,parent_result_sha256=sha(src/'result.json'),startup_plus_frame_J=r['total_energy'],frame_start_s=start,prehistory_s=pre,startup_energy_J={k:r['total_energy'][k]-totals[k] for k in ['positive_J','returned_J','net_J']},no_operating_point_reset=True),manifest_sha256=sha(dest/'manifest.json'))
 caps={}
 for label,cap,p,n in [('Lout',10e-9,'xdrv.lcap',None),('Dout',1e-9,'xdrv.dcap',None),('rawLaser',1e-9,'laser_c',None),('rawDriver',1e-9,'vdd_c',None),('Bcomp',c['cc'],'xdrv.bn2','xdrv.bctrl'),('Tcomp',c['cc'],'xdrv.tn2','xdrv.tctrl'),('Lcomp',c['cldo'],'xdrv.lzc','xdrv.lctrl'),('Dcomp',c['cldo'],'xdrv.dzc','xdrv.dctrl')]:
  vv=frame[:,ix['v('+p+')']]-(frame[:,ix['v('+n+')']] if n else 0);ee=.5*cap*vv[[0,-1]]**2;caps[label]=dict(capacitance_F=cap,start_J=float(ee[0]),end_J=float(ee[1]),change_J=float(ee[1]-ee[0]))
 result['explicit_capacitor_energy']=dict(capacitors=caps,change_J=sum(x['change_J'] for x in caps.values()),scope='Explicit supply/compensation caps only, excluding MOSintrinsic andpackage/load storage')
 emit(dest/'result.json',result);return dest.name
if __name__=='__main__':
 import sys
 print(extract(sys.argv[1]))
