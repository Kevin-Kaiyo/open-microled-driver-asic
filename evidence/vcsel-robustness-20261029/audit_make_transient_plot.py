#!/usr/bin/env python3
"""Compact visualization-only native envelopes; never recompute pass/fail metrics."""
from pathlib import Path
import argparse,json
import numpy as np
from audit_recheck import ROOT,EV,sha


def run(case,filename):
    work=ROOT/'build/vcsel-robustness-20261029'/case
    m=json.loads((work/'manifest.json').read_text());r=json.loads((work/'result.json').read_text())
    assert r['simulation_ok'] and sha(ROOT/r['waveform']['path'])==r['waveform']['sha256']
    a=np.loadtxt(ROOT/r['waveform']['path'],skiprows=1);t=a[:,0]
    assert np.all(np.diff(t)>0)
    ix={n:k+1 for k,n in enumerate(m['expressions'])}
    wanted={'rawlaser_V':'v(laser_src)','rawref_V':'v(ref_src)','rawvdd_V':'v(vdd_src)',
            'VL_V':'v(vl)','DR_V':'v(xdrv.dr)','SBASE_V':'v(xdrv.sbase)',
            'STAIL_V':'v(xdrv.stail)','JMON_A':'v(jmon)','Lctrl_V':'v(xdrv.lctrl)',
            'BCTRL_V':'v(xdrv.bctrl)','TCTRL_V':'v(xdrv.tctrl)'}
    signals={name:a[:,ix[expr]] for name,expr in wanted.items() if expr in ix}
    # Every 0.5 ns bin retains both native extrema of every requested channel.
    bins=int(np.ceil((t[-1]-t[0])/0.5e-9));edges=np.linspace(t[0],t[-1],bins+1)
    pos=np.searchsorted(t,edges);pos[-1]=len(t)
    keep={0,len(t)-1};extrema={};envelopes={}
    for name,v in signals.items():
        lo=int(np.argmin(v));hi=int(np.argmax(v));keep.update([lo,hi])
        extrema[name]={'min':{'time_s':float(t[lo]),'value':float(v[lo]),'native_index':lo},
                       'max':{'time_s':float(t[hi]),'value':float(v[hi]),'native_index':hi}}
        mins=[];maxs=[];centers=[]
        for k in range(bins):
            l,u=int(pos[k]),int(pos[k+1])
            if l==u:continue
            i=l+int(np.argmin(v[l:u]));j=l+int(np.argmax(v[l:u]));keep.update([i,j])
            mins.append(v[i]);maxs.append(v[j]);centers.append((edges[k]+edges[k+1])/2)
        envelopes[name+'_bin_min']=np.array(mins);envelopes[name+'_bin_max']=np.array(maxs)
        envelopes[name+'_bin_center_s']=np.array(centers)
    c=m['config'];end=m['end_s'];turns=[]
    if c.get('disturb'):
        turns=[end*f for f in [.42,.46,.70,.74]]
    for point in turns:
        k=int(np.searchsorted(t,point));keep.update(j for j in [k-1,k,k+1] if 0<=j<len(t))
    selected=np.array(sorted(keep),dtype=int)
    # Explicitly include exact source knees as interpolated points, retaining native neighbors.
    compact_t=np.unique(np.r_[t[selected],turns])
    arrays={'time_s':compact_t,**{name:np.interp(compact_t,t,v) for name,v in signals.items()},**envelopes}
    target=EV/filename;np.savez_compressed(target,**arrays)
    for e in extrema.values():
        for which in ['min','max']:assert np.any(compact_t==e[which]['time_s'])
    meta={'case':case,'script_sha256':sha(__file__),'source_waveform_sha256':r['waveform']['sha256'],
          'source_manifest_sha256':sha(work/'manifest.json'),'npz_file':target.name,'npz_sha256':sha(target),
          'native_rows':len(t),'compact_rows':len(compact_t),'bin_width_max_ns':float(np.diff(edges).max()*1e9),
          'channels':{name:wanted[name] for name in signals},'source_turns_s':turns,
          'global_native_extrema':extrema,'scope':'Visualization only. Retains native min and max per channel per 0.5 ns bin, all global extrema, original source-knee neighbors and exact interpolated knees. No averaging, no metric/eye/energy recomputation. Per-bin ranges expose unresolved NRZ switching without aliasing a uniformly decimated trace.'}
    target.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps({'file':target.name,'rows':len(compact_t),'bytes':target.stat().st_size,'sha256':meta['npz_sha256']},indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--case',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    assert a.output.startswith('audit-') and '/' not in a.output and a.output.endswith('.npz')
    run(a.case,a.output)
