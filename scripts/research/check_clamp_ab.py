"""Matched 10ns clamp-enable control; keep the source hardware and load fixed."""
from pathlib import Path
import csv, hashlib, json, os, re, shutil, subprocess, tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'evidence/safety-clamp-ab'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def integ(t,y,lo,hi):
    m=(t>lo)&(t<hi);x=np.r_[lo,t[m],hi];v=np.r_[np.interp(lo,t,y),y[m],np.interp(hi,t,y)]
    return float(np.sum(np.diff(x)*(v[:-1]+v[1:])/2))
def directional(t,y,lo,hi,positive):
    m=(t>lo)&(t<hi);x=np.r_[lo,t[m],hi];v=np.r_[np.interp(lo,t,y),y[m],np.interp(hi,t,y)]
    crosses=np.flatnonzero(v[:-1]*v[1:]<0)
    extra=x[crosses]-v[crosses]*(x[crosses+1]-x[crosses])/(v[crosses+1]-v[crosses])
    refined=np.unique(np.r_[x,extra]);values=np.interp(refined,x,v)
    return integ(refined,np.maximum(values,0) if positive else np.minimum(values,0),lo,hi)
def main():
    core=json.loads((ROOT/'evidence/safety/summary.json').read_text())
    old=ROOT/core['raw_directory']/'stop_high';deck=(old/'testbench.spice').read_text()
    needle='XCLAMP fault_pin clamp_anode led_k 0 fault_led_clamp'
    if deck.count(needle)!=1:raise ValueError('Unexpected original clamp interface')
    OUT.mkdir(parents=True,exist_ok=True);parent=ROOT/'build/research-reference-safety-20261013';parent.mkdir(exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='clamp-ab-',dir=parent));results=[];t0=20125e-9
    for enabled in [False,True]:
      for step in [10,2]:
        name=f'clamp{int(enabled)}_step{step}';folder=work/name;folder.mkdir()
        for file in ['design.ngspice','sm141064.ngspice']:(folder/file).symlink_to((old/file).resolve())
        modified=deck if enabled else deck.replace(needle,'XCLAMP 0 clamp_anode led_k 0 fault_led_clamp')
        modified=modified.replace('tran 10n 36125n 0 10n',f'tran 10n 36125n 0 {step}n')
        (folder/'testbench.spice').write_text(modified)
        p=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,text=True,capture_output=True)
        (folder/'ngspice.log').write_text(p.stdout+p.stderr)
        if p.returncode or re.search(r'(?im)^Error:|timestep too small',p.stdout+p.stderr):raise RuntimeError(str(folder))
        a=np.loadtxt(folder/'waveform.dat',skiprows=1);header=(folder/'waveform.dat').open().readline().split()
        vectors={k:a[:,i] for i,k in enumerate(header)};t=a[:,0];i=vectors['i(VLEDLOAD)']
        before=integ(t,i,t0-1e-6,t0-1e-8)/(.99e-6)
        mask=(t>=t0+1e-6)&(t<=t0+2e-6);maximum=float(np.max(np.abs(i[mask])))
        window=(t>=t0)&(t<=t0+3e-6);tw=t[window];iw=np.abs(i[window])
        bad=np.flatnonzero(iw>1e-9)
        if len(bad) and bad[-1]+1<len(tw):
            n=bad[-1];settle=tw[n]+(1e-9-iw[n])*(tw[n+1]-tw[n])/(iw[n+1]-iw[n])-t0
        else:settle=0 if not len(bad) else None
        result=dict(name=name,clamp_action_enabled=enabled,maxstep_ns=step,input_slew_ns=10,
                    pre_fault_current_A=before,fault_to_stable_1nA_s=float(settle) if settle is not None else None,
                    after_deadline_max_abs_current_A=maximum,original_fault_contract_passed=bool(maximum<1e-9 and settle is not None and settle<=1e-6),
                    Qpositive_first_us_C=directional(t,i,t0,t0+1e-6,True),
                    Qnegative_first_us_C=directional(t,i,t0,t0+1e-6,False),
                    source_deck_sha256=sha(folder/'testbench.spice'))
        path=OUT/(name+'.csv')
        with path.open('w') as f:
            w=csv.writer(f);w.writerow(['time_s','LED_branch_A','LED_K_V','gate_V','fault_V'])
            w.writerows(zip(t,i,vectors['v(led_k)'],vectors['v(gate)'],vectors['v(fault_pin)']))
        result['waveform_path']=str(path.relative_to(ROOT));result['waveform_sha256']=sha(path);results.append(result)
    if not all(r['original_fault_contract_passed']==r['clamp_action_enabled'] for r in results):raise ValueError('Control outcome differs')
    for enabled in [False,True]:
        rows=[r for r in results if r['clamp_action_enabled']==enabled]
        assert abs(rows[0]['pre_fault_current_A']-rows[1]['pre_fault_current_A'])<1e-10
        assert abs(rows[0]['fault_to_stable_1nA_s']-rows[1]['fault_to_stable_1nA_s'])<2e-9
    source_hashes={'evidence/safety/summary.json':sha(ROOT/'evidence/safety/summary.json'),
                   'scripts/research/check_clamp_ab.py':sha(Path(__file__)),'source_deck':sha(old/'testbench.spice')}
    s=dict(study_date='2026-10-14',completed=True,scope='Matched10ns source fixture, only clamp control input changes; new modules remain pre-layout.',
           source_core=core['raw_directory'],raw_directory=str(work.relative_to(ROOT)),source_hashes=source_hashes,
           fault_origin='RTL event/PWL start t0=20125ns',results=results,
           qualification='Control correctness plus step sensitivity; not optical/SOA/full-chip validation.')
    (OUT/'summary.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(results))
if __name__=='__main__':main()
