"""Drive the final buffer at the existing 3ns input-transition upper budget.

The frozen, successful joint-link testbench changes only full ramp time from
1ns to 7.5ns (=3ns at the actual Liberty 30–70% thresholds). These are declared
endpoint stimuli, not recovered preceding-register transistor waveforms.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import re
import shutil
import tempfile

import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    summary=json.loads((ROOT/'evidence/interface/summary.json').read_text())
    if not summary['passed'] or not summary['joint_link_sha256']:
        raise RuntimeError('Successful actual joint-link base run required')
    original=ROOT/summary['run_directory']
    work=Path(tempfile.mkdtemp(prefix='slew-budget-',dir=ROOT/'build/interface'))
    frozen=work/'inputs';frozen.mkdir()
    shutil.copyfile(Path(__file__),frozen/'stress.py')
    shutil.copyfile(ROOT/'scripts/interface/run.py',frozen/'run.py')
    shutil.copyfile(ROOT/'evidence/interface/summary.json',frozen/'base-summary.json')
    spec=importlib.util.spec_from_file_location('frozen_interface_common',frozen/'run.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    def case(base):
        folder=work/base['name'];folder.mkdir()
        original_deck=original/base['name']/'testbench.spice'
        text=original_deck.read_text()
        match=re.search(r'VIN input 0 PWL\(\n(.*?)\n\+\)',text,re.S)
        if not match:raise RuntimeError('Actual buffer input PWL not found')
        points=[list(map(float,row[2:].split())) for row in match[1].splitlines()]
        moved=0
        for n in range(1,len(points)):
            if points[n][1]!=points[n-1][1]:
                if abs(points[n][0]-points[n-1][0]-1e-9)>1e-14:
                    raise RuntimeError('Old input full ramp not 1ns')
                points[n][0]=points[n-1][0]+7.5e-9;moved+=1
        values='\n'.join(f'+ {t:.15g} {v:.15g}' for t,v in points)
        text=text[:match.start(1)]+values+text[match.end(1):]
        (folder/'testbench.spice').write_text(text)
        for name in ['design.ngspice','sm141064.ngspice']:
            (folder/name).symlink_to((original/base['name']/name).resolve())
        module.run(['ngspice','-b','testbench.spice'],folder,'ngspice.log')
        data=np.loadtxt(folder/'waveform.dat',skiprows=1);t=data[:,0]
        current=-module.integral(t,data[:,1])/(module.RIGHT-module.LEFT)*1e6
        full=next(r for r in summary['transient_results'] if r['envelope']==base['envelope'] and
                  r['driver']=='buffer_joint' and r['led']=='synthetic' and r['duty']==256)
        area=(current/(full['average_led_current_uA']*base['duty']/256)-1)*100
        edge=module.edges(t,data[:,4],base['logic_v'])
        return dict(name=base['name'],envelope=base['envelope'],duty=base['duty'],logic_v=base['logic_v'],
                    actual_input_full_ramp_ns=7.5,actual_input_30_70_ns=3,changed_ramp_endpoints=moved,
                    average_led_current_uA=current,area_error_pct=area,
                    base_current_uA=base['average_led_current_uA'],delta_from_1ns_ramp_uA=current-base['average_led_current_uA'],
                    average_buffer_power_uW=-module.integral(t,data[:,3])/(module.RIGHT-module.LEFT)*base['logic_v']*1e6,
                    source_deck_sha256=sha(original_deck),**edge)
    selected=[r for r in summary['transient_results'] if r['driver']=='buffer_joint' and r['duty'] in [1,255]
              and not r['name'].endswith('_fine')]
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(case,selected))
    checks=[]
    for r in results:
        checks += [dict(name=r['name']+'_slew_3ns',passed=r['rise_30_70_ns']<=3 and r['fall_70_30_ns']<=3),
                   dict(name=r['name']+'_pulse_950ns',passed=r['high_pulse_min_ns']>=950 and r['low_pulse_min_ns']>=950)]
        if r['duty']==1:checks.append(dict(name=r['name']+'_area_2pct',passed=abs(r['area_error_pct'])<=2))
    output=dict(passed=all(r['passed'] for r in checks),run_directory=str(work.relative_to(ROOT)),transient_runs=len(results),
                conditions=dict(input_full_ramp_ns=7.5,input_30_70_ns=3,slew_limit_ns=3,
                                stimulus='declared worst allowed input slew; preceding FF transistor waveform not simulated',
                                unchanged='frozen joint-link buffer transistor and analog RC, PDK, rail/temperature/model; only VIN ramp endpoints moved'),
                base_summary_sha256=sha(ROOT/'evidence/interface/summary.json'),
                sources_sha256={'scripts/interface/stress.py':sha(Path(__file__)),'scripts/interface/run.py':sha(ROOT/'scripts/interface/run.py')},
                frozen_input_hashes={p.name:sha(p) for p in frozen.iterdir() if p.is_file()},
                raw_artifacts_sha256={str(p.relative_to(work)):sha(p) for p in work.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix in ['.dat','.spice','.log']},
                results=results,checks=checks)
    (work/'summary.json').write_text(json.dumps(output,indent=2)+'\n')
    dest=ROOT/'evidence/interface';(dest/'slew-budget-summary.json').write_bytes((work/'summary.json').read_bytes())
    with (dest/'slew-budget.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(results[0]));writer.writeheader();writer.writerows(results)
    print(json.dumps({k:v for k,v in output.items() if k not in ['raw_artifacts_sha256','frozen_input_hashes','sources_sha256']},indent=2))
    if not output['passed']:raise RuntimeError('Slew budget failed; retain evidence')


if __name__=='__main__':main()
