"""Independent standard-library source, window and arithmetic audit."""
from pathlib import Path
import csv, hashlib, json, math
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'evidence/current-range'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def integrate(rows,column,left,right):
    pairs=[(float(x['time_s']),float(x[column])) for x in rows]
    assert all(math.isfinite(t) and math.isfinite(y) for t,y in pairs)
    assert all(a[0]<b[0] for a,b in zip(pairs,pairs[1:]))
    assert pairs[0][0]<=left and pairs[-1][0]>=right
    total=0
    for (t0,y0),(t1,y1) in zip(pairs,pairs[1:]):
        lo,hi=max(left,t0),min(right,t1)
        if hi<=lo:continue
        a=y0+(y1-y0)*(lo-t0)/(t1-t0);b=y0+(y1-y0)*(hi-t0)/(t1-t0)
        total+=(hi-lo)*(a+b)/2
    return total
def main():
    s=json.loads((BASE/'summary.json').read_text());checks=[]
    def check(name,ok,detail=None):
        checks.append(dict(name=name,passed=bool(ok),detail=detail))
        if not ok:raise ValueError(name)
    for p,h in s['source_hashes'].items():check('source identity '+p,sha(ROOT/p)==h)
    check('143DC and16PWM final evidence',len(s['DC'])==143 and len(s['PWM'])==16)
    for r in s['DC']:
        err=(r['current_A']/(r['units']*100e-6)-1)*100
        check('DC target and outcome '+r['name'],abs(err-r['error_pct'])<1e-10 and r['within_predeclared_5pct']==(abs(err)<=5))
    avgs={}
    for r in s['PWM']:
        path=ROOT/r['evidence_waveform'];check('waveform identity '+r['name'],sha(path)==r['waveform_sha256'])
        avg=integrate(list(csv.DictReader(path.open())),'LED_branch_A',514.5e-6,1026.5e-6)/(512e-6)
        avgs[r['name']]=avg
        check('independent adaptive integral '+r['name'],abs(avg-r['current_average_A'])<1e-12)
    for r in s['PWM']:
        full=next(x for x in s['PWM'] if x['units']==r['units'] and x['duty']==256
                  and x.get('bias_mode','ideal_current')==r.get('bias_mode','ideal_current')
                  and x.get('switch_scale',1)==r.get('switch_scale',1))
        error=(avgs[r['name']]/(avgs[full['name']]*r['duty']/256)-1)*100 if r['duty'] else None
        check('same-condition area denominator '+r['name'],error is None or abs(error-r['area_error_pct'])<1e-8)
        check('area guard not retrospectively changed '+r['name'],r['within_predeclared_2pct']==(abs(error)<=2 if error is not None else abs(avgs[r['name']])<1e-9))
    a=next(x for x in s['PWM'] if x['name']=='pwm_n70_d1_step20')
    b=next(x for x in s['PWM'] if x['name']=='pwm_n70_d1_step5')
    check('7mA minimum-code failure retained and step-insensitive',not a['within_predeclared_2pct'] and abs(a['area_error_pct']-b['area_error_pct'])<1e-4)
    data=list(csv.DictReader((ROOT/'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv').open()))
    for sample in s['dc_calibration']['independent_SPICE']:
        target=2.8
        if sample['load']=='measured_static':
            i=sample['current_A']
            for a,b in zip(data,data[1:]):
                i0,i1=float(a['current_A']),float(b['current_A'])
                if i0<=i<=i1:
                    v0,v1=float(a['voltage_V']),float(b['voltage_V']);target=v0+(v1-v0)*(i-i0)/(i1-i0);break
        check('independent LED DC calibration '+str(sample['current_A'])+sample['load'],abs(sample['VF_V']-target)<2e-6)
    result=dict(passed=True,checks=checks,threshold_failures_are_preserved=True,
                entire_current_range_qualified=False,summary_sha256=sha(BASE/'summary.json'),validator_sha256=sha(Path(__file__)))
    (BASE/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,checks=len(checks),preserved_7mA_failure=True)))
if __name__=='__main__':main()
