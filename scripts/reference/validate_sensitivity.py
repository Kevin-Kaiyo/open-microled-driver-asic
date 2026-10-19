"""Independent consistency checks for finite junction geometry and VSET boundaries."""
from pathlib import Path
import json,re,math
import numpy as np
from validate import integral,sha
ROOT=Path(__file__).resolve().parents[2];E=ROOT/'evidence/reference'
def main():
    s=json.loads((E/'junction-sensitivity.json').read_text());checks=[]
    for name,h in s['source_hashes'].items():
        path=ROOT/s['workdir']/'inputs'/'pdk'/name.removeprefix('PDK/') if name.startswith('PDK/') else ROOT/name
        assert sha(path)==h,name
    source=(ROOT/'analog/reference/vset_servo_with_junctions.spice').read_text()
    devices=[]
    for row in source.splitlines():
        if 'fet_06v0 w=' not in row:continue
        fields=dict(re.findall(r'\b(w|l|ad|as|pd|ps)=([^\s]+)',row));width=float(fields['w'][:-1])*1e-6
        for name,target in [('ad',width*.44e-6),('as',width*.44e-6),('pd',2*(width+.44e-6)),('ps',2*(width+.44e-6))]:assert math.isclose(float(fields[name]),target,rel_tol=1e-12)
        devices.append(row.split()[0])
    assert len(devices)==10;checks.append('Ten reference MOS AD/AS/PD/PS obey the declared geometric hypothesis; all paired sources retain hashes')
    pwm=[]
    for r in s['pwm']:
        a=np.loadtxt(ROOT/r['raw_waveform'],skiprows=1);q=[integral(a[:,0],a[:,1],514.5e-6+k*256e-6,514.5e-6+(k+1)*256e-6) for k in range(2)]
        for x,y in zip(q,r['frame_charge_c']):assert math.isclose(x,y,rel_tol=2e-9)
        err=[100*(x/(r['dc_full_a']*1e-6)-1) for x in q]
        for x,y in zip(err,r['charge_error_pct']):assert abs(x-y)<1e-7
        pwm.append(dict(envelope=r['envelope'],maxstep_s=r['maxstep_s'],charge_error_pct=err))
    checks.append('Six paired duty1 traces independently integrated; both frame charge and same-geometry DC denominator agree')
    for name,key in [('junction-sensitivity.json','startup'),('junction-zero-controls.json','results')]:
        summary=json.loads((E/name).read_text())
        for r in summary[key]:
            a=np.loadtxt(ROOT/r['raw_waveform'],skiprows=1);js=a[:,-20:]
            for k,dev in enumerate(['pbias','ptail','pd1','pd2','nd1','nd2','nstage','pload','preg','pout']):
                for q,j in enumerate(['ibd','ibs']):
                    result=r['model_reported_junction_currents'][dev][j]
                    assert math.isclose(float(js[:,k*2+q].min()),result['min_a'],rel_tol=1e-12,abs_tol=1e-30)
                    assert math.isclose(float(js[:,k*2+q].max()),result['max_a'],rel_tol=1e-12,abs_tol=1e-30)
    checks.append('All 10 reference MOS signed drain/source junction-current extrema match raw saved model vectors for 6 geometry and 4 zero-area controls')
    boundaries=json.loads((E/'servo-boundaries.json').read_text())
    for r in boundaries['vset_cases']:
        a=np.loadtxt(ROOT/r['raw_waveform'],skiprows=1)
        final=integral(a[:,0],a[:,1],50e-6,60e-6)/10e-6
        assert math.isclose(final,r['final_current_a'],rel_tol=2e-9)
        if r['vset_zero_2_to_19us_mean_current_a'] is not None:
            early=integral(a[:,0],a[:,1],2e-6,19e-6)/17e-6
            assert math.isclose(early,r['vset_zero_2_to_19us_mean_current_a'],rel_tol=2e-9)
    checks.append('Three VSET power-sequence cases: final and zero-VSET mean currents independently integrated')
    out=dict(status='validation_pass',script_sha256=sha(Path(__file__)),checks=checks,pwm=pwm,
             evidence_sha256={n:sha(E/n) for n in ['junction-sensitivity.json','junction-zero-controls.json','servo-boundaries.json']})
    (E/'sensitivity-validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
