"""Independently recompute the six declared upper-input-slew stress cases."""
from pathlib import Path
import csv
import hashlib
import json
import re

import numpy as np
import validate as independent

ROOT=Path(__file__).resolve().parents[2]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    s=json.loads((ROOT/'evidence/interface/slew-budget-summary.json').read_text())
    base=json.loads((ROOT/'evidence/interface/summary.json').read_text());work=ROOT/s['run_directory']
    left,right=base['conditions']['measurement_window_s'];duration=right-left
    checks=[]
    def check(name,passed):checks.append(dict(name=name,passed=bool(passed)))
    check('base_summary_identity',sha(ROOT/'evidence/interface/summary.json')==s['base_summary_sha256'])
    for name,h in s['sources_sha256'].items():check('source_'+name,sha(ROOT/name)==h)
    for name,h in s['frozen_input_hashes'].items():check('frozen_'+name,sha(work/'inputs'/name)==h)
    for name,h in s['raw_artifacts_sha256'].items():check('raw_'+name,sha(work/name)==h)
    for r in s['results']:
        data=np.loadtxt(work/r['name']/'waveform.dat',skiprows=1);t=data[:,0]
        current=-independent.integrate(t,data[:,1],left,right)/duration*1e6
        power=-independent.integrate(t,data[:,3],left,right)/duration*r['logic_v']*1e6
        check(r['name']+'_independent_current',abs(current-r['average_led_current_uA'])<1e-7)
        check(r['name']+'_independent_buffer_power',abs(power-r['average_buffer_power_uW'])<1e-7)
        full=next(x for x in base['transient_results'] if x['envelope']==r['envelope'] and x['driver']=='buffer_joint' and x['duty']==256)
        area=(current/(full['average_led_current_uA']*r['duty']/256)-1)*100
        check(r['name']+'_independent_area',abs(area-r['area_error_pct'])<1e-5 and (r['duty']!=1 or abs(area)<=2))
        voltage=data[:,4];vdd=r['logic_v']
        for name,rising in [('rise',True),('fall',False)]:
            a=independent.crossing_times(t,voltage,(.3 if rising else .7)*vdd,rising)
            b=independent.crossing_times(t,voltage,(.7 if rising else .3)*vdd,rising)
            spans=[]
            for x in a[(a>left)&(a<right)]:
                later=b[b>x]
                if len(later):spans.append((later[0]-x)*1e9)
            slew=max(spans)
            recorded=r['rise_30_70_ns' if rising else 'fall_70_30_ns']
            check(r['name']+'_independent_'+name+'_slew',abs(slew-recorded)<1e-4 and slew<=3)
        deck=(work/r['name']/'testbench.spice').read_text()
        match=re.search(r'VIN input 0 PWL\(\n(.*?)\n\+\)',deck,re.S)
        points=np.array([list(map(float,line[2:].split())) for line in match[1].splitlines()])
        steps=np.diff(points[:,1]);ramps=np.diff(points[:,0])[steps!=0]
        check(r['name']+'_actual_7p5ns_ramp_endpoints',np.all(abs(ramps-7.5e-9)<1e-14))
    with (ROOT/'evidence/interface/slew-budget.csv').open() as f:rows=list(csv.DictReader(f))
    check('CSV_record_count',len(rows)==len(s['results']))
    for i,(actual,expected) in enumerate(zip(rows,s['results'])):
        for k,v in expected.items():
            check(f'CSV_{i}_{k}',independent.math_isclose(float(actual[k]),float(v)) if isinstance(v,(int,float)) else actual[k]==str(v))
    output=dict(passed=all(x['passed'] for x in checks),checks=len(checks),failures=[x for x in checks if not x['passed']],
                stress_summary_sha256=sha(ROOT/'evidence/interface/slew-budget-summary.json'),
                independent_helper_sha256=sha(ROOT/'scripts/interface/validate.py'),verifier_sha256=sha(Path(__file__)))
    (ROOT/'evidence/interface/slew-budget-validation.json').write_text(json.dumps(output,indent=2)+'\n')
    manifest={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'evidence/interface').rglob('*'))
              if p.is_file() and p.name!='manifest.json'}
    (ROOT/'evidence/interface/manifest.json').write_text(json.dumps(dict(files_sha256=manifest),indent=2)+'\n')
    print(json.dumps(output,indent=2))
    if not output['passed']:raise RuntimeError('Independent stress validation failed')


if __name__=='__main__':main()
