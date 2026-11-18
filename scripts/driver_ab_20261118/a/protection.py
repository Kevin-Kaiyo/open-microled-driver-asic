"""Isolate coupling at the protection level shifter in short matched edge windows."""
import argparse
import gzip
import hashlib
import re
import shutil
import subprocess
import numpy as np
import run as a

def run_edge(edge, cap_ff, steps):
    point='SShotlow'
    codes=tuple(a.read(a.EV/f'{point}-ideal.json')['codes'])
    original=a.BUILD/f'sense-{point}'/f'fault-h{codes[0]}-l{codes[1]}'
    folder=a.BUILD/'edge-SS'/f'{edge}-c{cap_ff:g}-s{steps}'
    folder.mkdir(parents=True,exist_ok=True)
    shared=folder.parent/'inputs'
    if not shared.exists():shared.symlink_to('../sense-SShotlow/inputs',target_is_directory=True)
    a_file=original/'testbench.spice'
    deck=a_file.read_text()
    m=a.read(original/'manifest.json')
    source_shift={'assert':608e-9,'release':1248e-9}[edge]
    stop=128e-9
    for name in ['VD0','VDISABLE']:
        match=re.search(r'(?m)^('+name+r' \w+ 0 )PWL\((.+)\)$',deck)
        points=np.fromstring(match[2],sep=' ').reshape(-1,2)
        x,v=points.T
        mask=(x>source_shift)&(x<source_shift+stop)
        tkeep=np.r_[0,x[mask]-source_shift,stop]
        vkeep=np.r_[np.interp(source_shift,x,v),v[mask],np.interp(source_shift+stop,x,v)]
        deck=deck.replace(match[0],match[1]+'PWL('+' '.join(f'{u:.16g} {w:.16g}' for u,w in zip(tkeep,vkeep))+')')
    if cap_ff:
        deck=deck.replace('RGATE iso_g iso_p 100k','RGATE iso_g iso_p 100k\nCISOEDGE iso_g 0 '+f'{cap_ff:g}f')
    delta=1/1.85e9/steps
    deck=re.sub(r'(?m)^tran .+$',f'tran {delta:.16g} {stop:.16g} 0 {delta:.16g}',deck)
    if (folder/'result.json').exists():
        r=a.read(folder/'result.json')
        assert r['deck_sha256']==hashlib.sha256(deck.encode()).hexdigest()
        return r
    (folder/'testbench.spice').write_text(deck)
    shutil.copyfile(original/'route_a.spice',folder/'route_a.spice')
    m.update(source_case=str(original.relative_to(a.ROOT)),source_manifest_sha256=a.sha(original/'manifest.json'),
             source_deck_sha256=a.sha(a_file),case_name=folder.name,window_source_offset_s=source_shift,
             end_s=stop,edge=edge,edge_at_s=32e-9,cap_ff=cap_ff,local_dc_start=True,steps_per_symbol=steps,
             steps_scope='local edge only; stimulus retains original bit slice, local quiescent DC initialization; full-frame metrics inapplicable',
             deck_sha256=a.sha(folder/'testbench.spice'),route_sha256=a.sha(folder/'route_a.spice'),runner_at_execution_sha256=a.sha(__file__))
    m.pop('stimulus_sha256',None);m['case']=dict(mode='short-edge',edge=edge,steps_per_symbol=steps,cap_ff=cap_ff)
    a.emit(folder/'manifest.json',m)
    with (folder/'ngspice.log').open('w') as f:
        proc=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,stdout=f,stderr=subprocess.STDOUT)
    assert proc.returncode==0 and 'simulation(s) aborted' not in (folder/'ngspice.log').read_text()
    raw=folder/'waveform.dat'
    v=np.loadtxt(raw,skiprows=1);t=v[:,0]
    assert np.isfinite(v).all() and np.all(np.diff(t)>0) and abs(t[-1]-stop)<1e-14 and v.shape[1]==len(m['vectors'])+1
    st=a.analysis.stress(v,m,folder,False)
    currents=v[:,1]*1e6
    last=np.flatnonzero((t>=32e-9)&(abs(currents)>.1))
    ix=m['vectors'];n1=v[:,ix['iso_g']]
    r=dict(folder=str(folder.relative_to(a.ROOT)),edge=edge,cap_ff=cap_ff,steps=steps,samples=len(t),
           MOS=len(st),body_max_V=max(x['body_forward_V'] for x in st),worst_body=max(st,key=lambda s:s['body_forward_V']),
           body_pass=all(s['body_pass'] for s in st),terminal_pass=all(s['terminal_pass'] for s in st),
           iso_g_min_V=float(n1.min()),iso_g_min_time_after_edge_ns=float(t[n1.argmin()]*1e9-32),
           current_max_abs_after20ns_uA=float(np.abs(currents[t>=52e-9]).max()) if edge=='assert' else None,
           last_above_ns=(float(t[last[-1]]*1e9-32) if len(last) else 0) if edge=='assert' else None,
           end_current_uA=float(currents[-1]),deck_sha256=m['deck_sha256'],route_sha256=m['route_sha256'],
           manifest_sha256=a.sha(folder/'manifest.json'),native_sha256=a.sha(raw),log_sha256=a.sha(folder/'ngspice.log'))
    np.savez_compressed(folder/'preview.npz',time_s=t,iso_g=n1,iso_p=v[:,ix['iso_p']],iled_uA=currents)
    comp=folder/'waveform.dat.gz'
    with raw.open('rb') as fi,gzip.open(comp,'wb',compresslevel=2) as fo:shutil.copyfileobj(fi,fo)
    with gzip.open(comp,'rb') as fi:assert hashlib.file_digest(fi,'sha256').hexdigest()==r['native_sha256']
    raw.unlink();r['compressed_sha256']=a.sha(comp);a.emit(folder/'result.json',r)
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cap',type=float,required=True);p.add_argument('--steps',type=int,default=40);args=p.parse_args()
    for e in ['assert','release']:
        r=run_edge(e,args.cap,args.steps)
        print(e,args.cap,r['body_max_V'],r['current_max_abs_after20ns_uA'],r['last_above_ns'],r['terminal_pass'],flush=True)
