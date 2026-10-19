#!/usr/bin/env python3
"""Independent two-period PRBS9 energy-window check from an immutable NRZ run.

Only this process's imported stimulus generator is overridden. Source work is
read-only; all new decks, logs and traces go to a separate build directory.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse, gzip, hashlib, importlib.util, json, shutil, sys, tempfile
import numpy as np

ROOT=Path(__file__).resolve().parents[2]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rel(path):return str(path.relative_to(ROOT))
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-work',default='build/highspeed-nrz/run-0xqxvspp')
    ap.add_argument('--work',help='Recompute existing independent window-check work')
    args=ap.parse_args();source=(ROOT/args.source_work).resolve()
    srcman=json.loads((source/'manifest.json').read_text())
    for name in ['scripts/highspeed_nrz/run.py','scripts/highspeed_nrz/metrics.py']:
        assert sha(source/'inputs'/name)==srcman['inputs'][name]
    if args.work:
        work=(ROOT/args.work).resolve()
        assert source!=work and (work/'window-check-manifest.json').exists()
        assert sha(Path(__file__))==sha(work/'inputs/scripts/highspeed_nrz/window_check.py')
    else:
        work=Path(tempfile.mkdtemp(prefix='window-check-',dir=ROOT/'build/highspeed-nrz'))
        shutil.copytree(source/'inputs',work/'inputs')
        shutil.copy2(source/'manifest.json',work/'manifest.json')
        shutil.copy2(source/'ngspice-version.log',work/'ngspice-version.log')
        shutil.copy2(Path(__file__),work/'inputs/scripts/highspeed_nrz/window_check.py')
        extra={'source_work':rel(source),'source_manifest_sha256':sha(source/'manifest.json'),
               'script_sha256':sha(Path(__file__)),
               'only_stimulus_change':'PRBS9 validation period repeated twice; warmup/training/32-bit trailing guard unchanged',
               'source_work_mutated':False}
        (work/'window-check-manifest.json').write_text(json.dumps(extra,indent=2)+'\n')
    runner=module('frozen_window_runner',work/'inputs/scripts/highspeed_nrz/run.py');runner.ROOT=ROOT
    metric=module('frozen_window_metrics',work/'inputs/scripts/highspeed_nrz/metrics.py')
    original=runner.stimulus()
    assert len(original['validation_bits'])==511 and len(original['training_bits'])==254
    repeated=dict(original)
    repeated['validation_bits']=original['validation_bits']*2
    repeated['bits']=original['bits'][:286]+repeated['validation_bits']+original['bits'][-32:]
    repeated['validation_end_bit']=1308
    repeated['definition']+='; independent window test repeats same PRBS9 period twice'
    assert len(repeated['bits'])==1340 and repeated['bits'][:797]==original['bits'][:797]
    runner.stimulus=lambda:repeated
    (work/'stimulus.json').write_text(json.dumps(repeated,indent=2)+'\n')
    cases=[runner.case_spec(route,1,kind='two_period_window') for route in ['A','B']]
    print('WORK='+rel(work),flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda c:runner.run_case(work,c),cases))
    output={}
    windows={'first_period':(286e-9,797e-9,511),'second_period':(797e-9,1308e-9,511),'two_period_average':(286e-9,1308e-9,1022)}
    for result in results:
        assert result['simulation_ok'],result
        p=ROOT/result['waveform'];raw=gzip.decompress(p.read_bytes())
        assert hashlib.sha256(raw).hexdigest()==result['uncompressed_sha256']
        with gzip.open(p,'rt') as f:a=np.loadtxt(f,skiprows=1)
        t=a[:,0];vec=result['vectors'];route=result['case']['route']
        assert np.isclose(t[-1],1340e-9,rtol=0,atol=1e-18)
        perwindow={}
        for name,(start,end,nbits) in windows.items():
            rails={k:metric.energy_window(t,np.full(len(t),v['voltage_V']),a[:,vec[k.lower()+'_current']],start,end,nbits)
                   for k,v in result['rails'].items()}
            data=metric.energy_window(t,a[:,vec['data']],a[:,vec['data_current']],start,end,nbits)
            total={k:sum(e[k] for e in rails.values()) for k in ['net_J','positive_draw_J','returned_J','net_J_per_gross_bit','positive_draw_J_per_gross_bit','returned_J_per_gross_bit']}
            endpoint={k:[float(x) for x in np.interp([start,end],t,a[:,i])] for k,i in vec.items() if not k.endswith('current')}
            vk=np.interp([start,end],t,a[:,vec['led_voltage']]);ipkg=np.interp([start,end],t,a[:,vec['package_current']])
            stored=.5*200e-15*vk**2+.5*.5e-9*ipkg**2
            perwindow[name]={'start_s':start,'end_s':end,'bits':nbits,'rail_energies':rails,'data_source_energy_separate':data,
                             'supply_terminal_total':total,'endpoint_values':endpoint,
                             'explicit_CLED_Lpkg_stored_energy_J':stored.tolist(),
                             'explicit_CLED_Lpkg_stored_energy_change_J_per_bit':float((stored[1]-stored[0])/nbits),
                             'storage_boundary':'CLED and Lpkg only; not total MOS nonlinear stored energy'}
        changes={}
        for rail in list(result['rails'])+['TOTAL_SUPPLIES','DATA']:
            def entry(w):
                if rail=='TOTAL_SUPPLIES':return perwindow[w]['supply_terminal_total']
                if rail=='DATA':return perwindow[w]['data_source_energy_separate']
                return perwindow[w]['rail_energies'][rail]
            first,second,avg=[entry(w) for w in windows]
            changes[rail]={}
            for key in ['net_J_per_gross_bit','positive_draw_J_per_gross_bit','returned_J_per_gross_bit']:
                base=first[key];delta=second[key]-base
                assert np.isclose(avg[key],(first[key]+second[key])/2,rtol=1e-10,atol=1e-24)
                changes[rail][key]={'second_minus_first_fJ_per_bit':delta*1e15,
                                    'relative_to_first_percent':delta/abs(base)*100 if abs(base)>1e-21 else None}
        output[route]={'simulation':result,'windows':perwindow,'second_period_vs_first':changes,
                       'log':rel(p.parent/'ngspice.log'),'log_sha256':sha(p.parent/'ngspice.log')}
        print(route+' complete',flush=True)
    evidence={'status':'completed two-period input-window sensitivity check; not BER qualification',
              'work':rel(work),'source_work':rel(source),'source_manifest_sha256':sha(source/'manifest.json'),
              'source_inputs':srcman['inputs'],'window_definitions':windows,'conditions':srcman['common'],
              'body_geometry':srcman['body_geometry'],'script_sha256':sha(Path(__file__)),
              'frozen_script':rel(work/'inputs/scripts/highspeed_nrz/window_check.py'),
              'runner_sha256':sha(work/'inputs/scripts/highspeed_nrz/run.py'),
              'metrics_sha256':sha(work/'inputs/scripts/highspeed_nrz/metrics.py'),
              'stimulus_sha256':sha(work/'stimulus.json'),'runtime':{'python':sys.version,'numpy':np.__version__},
              'routes':output,
              'interpretation_boundary':['Common input windows with no latency shift','Training sequence unchanged; no receiver retraining is needed for this source-energy check',
                                         'Positive supply draw, returned and net energy all retained; DATA is separate',
                                         'Finite windows can retain different initial/final nonlinear-device energy; the second period diagnoses that sensitivity',
                                         'Explicit stored-energy accounting covers CLED/Lpkg only, not all MOS energy']}
    path=ROOT/'evidence/highspeed-nrz/window-check.json';path.write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'evidence':rel(path),'summary':{r:o['second_period_vs_first']['TOTAL_SUPPLIES'] for r,o in output.items()}},indent=2),flush=True)

if __name__=='__main__':main()
