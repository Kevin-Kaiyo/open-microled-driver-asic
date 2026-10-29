#!/usr/bin/env python3
"""Independent DC calibration/current-sense and source-power audit."""
from pathlib import Path
import argparse,json
import numpy as np
from audit_recheck import ROOT,EV,sha


def run(case):
    work=ROOT/'build/vcsel-robustness-20261029'/case
    m=json.loads((work/'manifest.json').read_text());r=json.loads((work/'result.json').read_text());c=m['config']
    assert c['mode']=='dc' and c['variant']!='baseline' and r['simulation_ok']
    assert r['manifest_sha256']==sha(work/'manifest.json') and r['deck_sha256']==sha(work/'testbench.spice')
    for p,h in m['source_hashes'].items():assert sha(ROOT/p)==h
    assert sha(ROOT/r['waveform']['path'])==r['waveform']['sha256']
    a=np.atleast_2d(np.loadtxt(ROOT/r['waveform']['path'],skiprows=1));assert len(a)==1
    x={e:float(a[0,k+1]) for k,e in enumerate(m['expressions'])}
    current=x['v(jmon)'];base=x['i(v.xdrv.vibase)'];tail=x['i(v.xdrv.vitail)']
    for key,value in [('current_mA',current*1000),('base_current_mA',base*1000),('tail_current_mA',tail*1000)]:assert abs(value-r[key])<1e-12
    ib_sense=x['v(xdrv.sbase)']/(50*c['rscale']);it_sense=x['v(xdrv.stail)']/(37.5*c['rscale'])
    assert abs(base-ib_sense)<1e-9 and abs(tail-it_sense)<1e-9
    powers={p:-x['v('+n+')']*x['i('+p+')'] for p,n in m['ports'].items()}
    for p,v in powers.items():assert abs(v-r['source_power_W'][p])<1e-14
    target=c['vset']/(50*c['rscale'])+c['level']*c['vset']/(37.5*c['rscale'])
    return dict(case=case,config=c,waveform_sha256=r['waveform']['sha256'],circuit_sha256=sha(work/'inputs/driver.spice'),
        current_mA=current*1000,target_from_external_VSET_mA=target*1000,relative_target_error=(current-target)/target,
        current_vs_nominal_3_or_7mA_error_percent=(current/(.003+.004*c['level'])-1)*100,
        base_mA=base*1000,tail_mA=tail*1000,sense_base_minus_branch_nA=(ib_sense-base)*1e9,sense_tail_minus_branch_nA=(it_sense-tail)*1e9,
        source_power_W=powers,total_source_power_W=sum(powers.values()),rail_V={n:x['v('+n+')'] for n in ['vl','xdrv.dr','vref','vset','vregset'] if 'v('+n+')' in x},
        boundary='Ideal external precision VSET and nominal ideal sense resistors; mismatch/statistical models disabled. Small DC errors are model loop errors, not fabricated current-source accuracy.')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--case',required=True,action='append');ap.add_argument('--output',required=True);a=ap.parse_args()
    assert a.output.startswith('audit-') and '/' not in a.output and a.output.endswith('.json')
    rows=[run(c) for c in a.case]
    (EV/a.output).write_text(json.dumps({'script_sha256':sha(__file__),'rows':rows},indent=2)+'\n')
    print(json.dumps([{'case':r['case'],'current_mA':r['current_mA'],'error_percent':r['current_vs_nominal_3_or_7mA_error_percent']} for r in rows],indent=2))
