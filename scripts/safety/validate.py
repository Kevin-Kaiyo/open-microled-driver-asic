"""Independent numerical/source audit; never imports the experiment runner.

This verifies the arithmetic and classification of an experiment, including
honestly failed guards. Data integrity PASS does not make a failed experiment
PASS. Full-resolution waveforms stay in the recorded build directory.
"""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def bounded(time,value,left,right):
    middle=(time>left)&(time<right)
    return np.concatenate(([left],time[middle],[right])),np.concatenate(([np.interp(left,time,value)],value[middle],[np.interp(right,time,value)]))

def charges(time,value,left,right):
    x,y=bounded(time,value,left,right)
    positive=negative=0.0
    for t0,t1,y0,y1 in zip(x[:-1],x[1:],y[:-1],y[1:]):
        if y0*y1<0:
            zero=t0+(t1-t0)*abs(y0)/(abs(y0)+abs(y1))
            segments=[(.5*y0*(zero-t0)),(.5*y1*(t1-zero))]
        else:segments=[.5*(y0+y1)*(t1-t0)]
        for q in segments:
            if q>0:positive+=q
            else:negative+=q
    return {'signed_c':positive+negative,'positive_c':positive,'negative_c':negative}

def close(a,b):return abs(a-b)<=max(1e-22,abs(a)*1e-9)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('summary',type=Path,nargs='?',default=ROOT/'evidence/safety/summary.json')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    summary_path=args.summary.resolve();summary=json.loads(summary_path.read_text())
    raw=ROOT/summary['raw_directory'];checks=[]
    def check(label,passed,**extra):checks.append(dict(name=label,passed=bool(passed),**extra))
    limits=json.loads((raw/'inputs/evidence/safety/contract.json').read_text())['thresholds']
    for name,expected in summary['source_sha256'].items():
        frozen=raw/'inputs'/name
        check('Frozen source '+name,digest(frozen)==expected)
        check('Current source unchanged '+name,digest(ROOT/name)==expected)
    check('Summary classification matches all listed checks',summary['passed']==all(c['passed'] for c in summary['checks']))
    for result in summary['results']:
        folder=raw/result['name'];prefix=result['name']+' / '
        for filename,key in [('waveform.dat','raw_waveform_sha256'),('waveform.csv','compact_waveform_sha256'),('testbench.spice','deck_sha256'),('rtl-events.csv','rtl_events_sha256')]:
            check(prefix+filename+' hash',digest(folder/filename)==result[key])
        with (folder/'waveform.dat').open() as f:columns=f.readline().split()
        data=np.loadtxt(folder/'waveform.dat',skiprows=1);time=data[:,0]
        vector={name:data[:,i] for i,name in enumerate(columns)}
        check(prefix+'finite monotonic full-resolution data',np.isfinite(data).all() and np.all(np.diff(time)>0))
        current=vector['i(VLEDLOAD)'];conditions=result['conditions'];fault=conditions['fault_ns']*1e-9
        if conditions['fault_ns']<0 and not conditions.get('reference_ramp'):
            q=charges(time,current,514.5e-6,1026.5e-6)['signed_c']
            check(prefix+'independent normal charge',close(q,result['charge_c']))
            average=q/512e-6
            check(prefix+'independent average',close(average,result['average_current_a']))
            duty=conditions['duty'];error=None if not duty else (average/(result['dc_full_a']*duty/256)-1)*100
            if duty:check(prefix+'area arithmetic',abs(error-result['area_error_pct'])<1e-7)
        elif conditions['fault_ns']>=0:
            q=charges(time,current,fault,fault+1e-6)
            for key,value in q.items():check(prefix+'tail '+key,close(value,result['tail_charge'][key]))
            x,y=bounded(time,current,fault+1e-6,fault+2e-6)
            offmax=float(np.max(np.abs(y)))
            check(prefix+'held-fault current arithmetic',close(offmax,result['post_deadline_max_abs_current_a']))
            check(prefix+'signed tail is not used to cancel positive guard',any(c['name']=='Positive fault tail <=10pC' for c in result['checks']) or bool(conditions.get('negative')))
            if conditions.get('negative'):
                check(prefix+'actual negative control stays bright',offmax>=.95*result['dc_full_a'] and result.get('expected_negative_control_failure'))
            total=vector['@d.xled.dled[id]'];capacitive=vector['@d.xled.dled[capcur]']
            for field,value in [('model_LED_total_charge',total),('model_LED_capacitive_charge',capacitive),('model_LED_conduction_charge',total-capacitive)]:
                recomputed=charges(time,value,fault,fault+1e-6)
                for key,qvalue in recomputed.items():check(prefix+field+' '+key,close(qvalue,result[field][key]))
            # Internal @D[id] is a diagnostic, while the independent zero-V
            # series meter defines every branch-current guard. Compare device
            # diagnostic closure only over the claimed post-fault tail window;
            # report the entire waveform residual separately, including recovery.
            x,residual=bounded(time,total-current,fault,fault+1e-6)
            check(prefix+'LED device diagnostic closes in fault-tail window',np.max(np.abs(residual))<1e-10,
                  max_residual_a=float(np.max(np.abs(residual))),full_waveform_max_residual_a=float(np.max(np.abs(total-current))))
        if conditions.get('reference_ramp'):
            stop=conditions['initial_fault_clear_ns']*1e-9
            x,y=bounded(time,current,0,stop);peak=float(np.max(np.abs(y)))
            check(prefix+'startup peak arithmetic',close(peak,result['startup']['LED_max_abs_current_a']))
            guard=[c for c in result['checks'] if c['name']=='External asserted fault blocks reference-startup LED current'][0]
            check(prefix+'startup guard classification is honest',guard['passed']==(peak<limits['fault_safe_current_abs_a']))
            for key,value in charges(time,current,0,stop).items():check(prefix+'startup '+key,close(value,result['startup']['LED_charge'][key]))
        with (folder/'rtl-events.csv').open() as f:rows=list(csv.DictReader(f))
        rows=list({r['time_ns']:r for r in rows}.values())
        truth=True;recovery=True;previous=None;stop_negative_seen=False
        for row in rows:
            keys=['raw_pwm','protected_pwm','permit','fault','recover_request','clk_run','sync_only_pwm']
            if not all(row[k] in ['0','1'] for k in keys):continue
            values={k:int(row[k]) for k in keys}
            truth &= values['protected_pwm']==(values['raw_pwm'] and values['permit'] and not values['fault'])
            if previous and not previous['permit'] and values['permit']:
                recovery &= not values['fault'] and values['recover_request'] and not previous['raw_pwm']
            if not values['clk_run'] and values['fault'] and values['raw_pwm'] and values['sync_only_pwm'] and not values['protected_pwm']:stop_negative_seen=True
            previous=values
        check(prefix+'actual RTL combinational priority',truth)
        check(prefix+'actual RTL qualified recovery',recovery)
        if conditions['stop_ns']>=0:check(prefix+'synchronous-only stopped-clock negative observed',stop_negative_seen)
        check(prefix+'scope names declared D/S orientation', 'D/S may be swapped' in result['stress_scope'])
        deck=(folder/'testbench.spice').read_text()
        logic=float(re.search(r'^VSUPSAFE safety_vdd 0 ([0-9.]+)',deck,re.M)[1])
        zero=np.zeros(len(time))
        gate_nodes={'vss':zero,'vdd':np.full(len(time),logic),'raw':vector['v(raw_pwm)'],
                    'fault':vector['v(fault_pin)'],'permit':vector['v(permit)'],'out':vector['v(unused_safe)']}
        for name in ['fault_b','nand_n','stack1','stack2']:gate_nodes[name]=vector['v(xsafe.'+name+')']
        clamp_nodes={'vss':zero,'anode':vector['v(clamp_anode)'],'cathode':vector['v(led_k)'],
                     'fault':zero if conditions.get('negative') else vector['v(fault_pin)'],
                     'fault_hb':vector['v(xclamp.fault_hb)']}
        for filename,nodes in [('fault_gate.spice',gate_nodes),('fault_led_clamp.spice',clamp_nodes)]:
            for line in (raw/'inputs/analog/safety'/filename).read_text().splitlines():
                if not line.startswith('X'):continue
                name,d,g,s,b,*rest=line.split()
                for label,y in [('VGS',nodes[g]-nodes[s]),('VGD',nodes[g]-nodes[d]),('VDS',nodes[d]-nodes[s]),
                                ('VSB',nodes[s]-nodes[b]),('VDB',nodes[d]-nodes[b])]:
                    values={'min_v':float(np.min(y)),'max_v':float(np.max(y)),'max_abs_v':float(np.max(np.abs(y)))}
                    check(prefix+name+' '+label+' terminal arithmetic',all(abs(v-result['terminal_stress'][name][label][k])<1e-9 for k,v in values.items()))
    passed=all(c['passed'] for c in checks)
    report={'schema_version':1,'validator_sha256':digest(Path(__file__)),
            'data_integrity_passed':passed,'experiment_passed':summary['passed'],
            'summary_path':str(summary_path.relative_to(ROOT)),'summary_sha256':digest(summary_path),
            'raw_directory':summary['raw_directory'],'check_count':len(checks),'checks':checks,
            'boundary':'Independent arithmetic and hashes only. A data-integrity PASS preserves the original guard failures; it does not confer circuit qualification, POR, layout, full-PG, silicon or optical evidence.'}
    destination=args.output.resolve() if args.output else raw/'independent-validation.json'
    destination.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'data_integrity_passed':passed,'experiment_passed':summary['passed'],'checks':len(checks),'output':str(destination.relative_to(ROOT)),'failed_checks':[c for c in checks if not c['passed']]},indent=2))
    if not passed:raise SystemExit(1)

if __name__=='__main__':main()
