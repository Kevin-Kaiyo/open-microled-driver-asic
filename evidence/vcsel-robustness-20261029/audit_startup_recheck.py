#!/usr/bin/env python3
"""Independent native-waveform startup/current/rail/stress/energy audit.

This checks the stated synchronous-ramp experiment only. No data-pattern
operation, autonomous POR or asynchronous reference sequencing is inferred.
"""
from pathlib import Path
import argparse, json
import numpy as np
from audit_recheck import ROOT, EV, sha, positive_pwl


def run(case, dc_case):
    base = ROOT/'build/vcsel-robustness-20261029'
    work = base/case; dcwork = base/dc_case
    m = json.loads((work/'manifest.json').read_text())
    r = json.loads((work/'result.json').read_text())
    dm = json.loads((dcwork/'manifest.json').read_text())
    dr = json.loads((dcwork/'result.json').read_text())
    assert m['config']['mode']=='startup' and dm['config']['mode']=='dc'
    for key in ['variant','level','corner','temp','voltage','cj','vset','vregset','rscale','cc','cldo','wbase','wtail','atten']:
        assert m['config'][key]==dm['config'][key], key
    assert r['simulation_ok'] and dr['simulation_ok']
    assert r['manifest_sha256']==sha(work/'manifest.json')
    assert r['deck_sha256']==sha(work/'testbench.spice')
    assert dr['manifest_sha256']==sha(dcwork/'manifest.json')
    assert (work/'inputs/driver.spice').read_bytes()==(dcwork/'inputs/driver.spice').read_bytes()
    for man in [m,dm]:
        for path,digest in man['source_hashes'].items():
            assert sha(ROOT/path)==digest,path
    for res in [r,dr]:
        assert sha(ROOT/res['waveform']['path'])==res['waveform']['sha256']
    a = np.loadtxt(ROOT/r['waveform']['path'],skiprows=1)
    dca = np.atleast_2d(np.loadtxt(ROOT/dr['waveform']['path'],skiprows=1))
    t = a[:,0]; ix = {e:k+1 for k,e in enumerate(m['expressions'])}
    dix = {e:k+1 for k,e in enumerate(dm['expressions'])}
    assert np.all(np.diff(t)>0) and abs(t[-1]-m['end_s'])<1e-15
    channels = [('current_mA','v(jmon)',1000,.05),('laser_rail_V','v(vl)',1,.01),('buffer_rail_V','v(xdrv.dr)',1,.01)]
    metrics = {}
    for name,expr,scale,tol in channels:
        target = dca[-1,dix[expr]]*scale; v = a[:,ix[expr]]*scale
        bad = np.flatnonzero(abs(v-target)>tol*abs(target))
        entered = None if len(bad) and bad[-1]==len(v)-1 else float(t[bad[-1]+1]*1e6) if len(bad) else 0.
        metrics[name] = dict(dc_target=float(target),final=float(v[-1]),relative_band=tol,
            final_relative_error=float((v[-1]-target)/target),last_20percent_peak_to_peak=float(np.ptp(v[t>.8*t[-1]])),
            entered_and_stayed_in_dc_band_us=entered,final_in_dc_band=entered is not None)
    worst = {'V':-1}; bodymax=0.
    for dev in m['devices']:
        volts=[np.zeros(len(t)) if n=='0' else a[:,ix['v('+n+')']] for n in dev['nodes']]
        for p in range(4):
            for q in range(p+1,4):
                delta=abs(volts[p]-volts[q]); k=int(np.argmax(delta))
                if delta[k]>worst['V']:
                    worst={'V':float(delta[k]),'instance':dev['instance'],'pair':'DGSB'[p]+'DGSB'[q],'time_us':float(t[k]*1e6)}
        sign=1 if dev['model'].startswith('p') else -1
        bodymax=max(bodymax,float(np.max(sign*(volts[0]-volts[3]))),float(np.max(sign*(volts[2]-volts[3]))))
    assert abs(worst['V']-r['max_terminal_V'])<1e-12
    assert abs(bodymax-r['max_body_forward_V'])<1e-12
    energy={}
    for port,node in m['ports'].items():
        p=-a[:,ix['v('+node+')']]*a[:,ix['i('+port+')']]
        energy[port]=positive_pwl(t,p)
        for key,value in energy[port].items():
            assert abs(value-r['energy_by_port'][port][key])<1e-20
    screen=all(v['final_in_dc_band'] and v['last_20percent_peak_to_peak']<2*v['relative_band']*abs(v['dc_target']) for v in metrics.values()) and worst['V']<=3.63 and bodymax<=.3
    saved=work/'startup-review.json'
    if saved.exists():
        review=json.loads(saved.read_text())
        assert screen==review['startup_joint_screen_passed']
        for name,mine in metrics.items():
            for key,value in mine.items():
                theirs=review['metrics'][name][key]
                if value is None: assert theirs is None
                elif isinstance(value,bool): assert value==theirs
                else: assert abs(value-theirs)<1e-9,(name,key,value,theirs)
    worst['headroom_mV']=(3.63-worst['V'])*1000
    return dict(case=case,dc_case=dc_case,config=m['config'],waveform_sha256=r['waveform']['sha256'],
        dc_waveform_sha256=dr['waveform']['sha256'],metrics=metrics,stress_max=worst,body_forward_V=bodymax,
        energy_by_port_J=energy,positive_startup_J=sum(p['positive_J'] for p in energy.values()),
        max_native_timestep_ns=float(np.diff(t).max()*1e9),startup_joint_screen_passed=bool(screen),
        boundary='Constant logic level with synchronous supply, VSET and VREGSET ramps. No autonomous enable sequencing or full traffic is established by this test.')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--pair',action='append',required=True,help='startup-case:dc-case')
    ap.add_argument('--output',required=True);args=ap.parse_args()
    assert args.output.startswith('audit-') and '/' not in args.output and args.output.endswith('.json')
    rows=[]
    for pair in args.pair:
        row=run(*pair.split(':'));rows.append(row)
        print(json.dumps({k:row[k] for k in ['case','metrics','stress_max','startup_joint_screen_passed']},indent=2),flush=True)
    (EV/args.output).write_text(json.dumps({'script_sha256':sha(__file__),'helper_sha256':sha(Path(__file__).with_name('audit_recheck.py')),'rows':rows},indent=2)+'\n')
