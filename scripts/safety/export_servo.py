"""Export the bounded servo joint experiment without upgrading its failures."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('summary',type=Path)
    args=parser.parse_args();path=args.summary.resolve();summary=json.loads(path.read_text())
    if summary['suite']!='servo':raise ValueError('A complete dedicated servo suite is required')
    raw=ROOT/summary['raw_directory'];dest=ROOT/'evidence/safety'
    validation=raw/'independent-validation.json'
    audit=json.loads(validation.read_text())
    if not audit['data_integrity_passed'] or audit['summary_sha256']!=sha(path):raise ValueError('Independent data audit missing or mismatched')
    summary['upstream_summary_path']=str(path.relative_to(ROOT));summary['upstream_summary_sha256']=sha(path)
    summary['exporter_sha256']=sha(Path(__file__))
    summary['core_contract_passed']=all(r['passed'] for r in summary['results'] if not r['conditions'].get('reference_ramp')) and all(c['passed'] for c in summary['checks'] if 'startup' not in c['name'])
    summary['extra_startup_guard_failed']=any(not c['passed'] for r in summary['results'] if r['conditions'].get('reference_ramp') for c in r['checks'])
    summary['extra_startup_charge_convergence_failed']=any(not c['passed'] for c in summary['checks'] if 'startup Q+' in c['name'])
    summary['core_contract_scope']='Nominal TT27C, logic3.3V/LED5V, externalVSET0.5V/RSET5k, finite10ns input edges. d1 normal and one stopped-clock fault with10->2ns comparisons. Not all servo PVT, rail startup sequences or optical conditions.'
    summary['validation_path']='evidence/safety/servo-validation.json'
    for result in summary['results']:
        folder=raw/result['name'];target=dest/'servo-waveforms'/result['name'];target.mkdir(parents=True,exist_ok=True)
        with (folder/'waveform.dat').open() as f:header=f.readline().split()
        a=np.loadtxt(folder/'waveform.dat',skiprows=1);time=a[:,0]
        indices=[np.linspace(0,len(time)-1,min(4000,len(time)),dtype=int),np.flatnonzero(time<=1e-6)]
        fault=result['conditions']['fault_ns']*1e-9
        if fault>=0:indices.append(np.flatnonzero((time>=fault-200e-9)&(time<=fault+2e-6)))
        for vector in ['i(VLEDLOAD)','i(VCLAMPSUP)','i(VREFLOAD)','@d.xled.dled[capcur]']:
            i=header.index(vector);indices.append(np.array([int(np.argmax(a[:,i])),int(np.argmin(a[:,i]))]))
        selected=np.unique(np.concatenate(indices))
        csvpath=target/'waveform.csv'
        with csvpath.open('w') as f:
            writer=csv.writer(f);writer.writerow(['time_s']+header[1:]);writer.writerows(a[selected].tolist())
        rtl=target/'rtl-events.csv';shutil.copyfile(folder/'rtl-events.csv',rtl)
        result['csvpath']=str(csvpath.relative_to(ROOT));result['csv_sha256']=sha(csvpath)
        result['rtl_csvpath']=str(rtl.relative_to(ROOT));result['rtl_csv_sha256']=sha(rtl)
        (target/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    shutil.copyfile(validation,dest/'servo-validation.json')
    (dest/'servo-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'path':'evidence/safety/servo-summary.json','core_contract_passed':summary['core_contract_passed'],'extra_startup_guard_failed':summary['extra_startup_guard_failed'],'extra_startup_charge_convergence_failed':summary['extra_startup_charge_convergence_failed'],'overall_passed':summary['passed'],'results':len(summary['results'])},indent=2))

if __name__=='__main__':main()
