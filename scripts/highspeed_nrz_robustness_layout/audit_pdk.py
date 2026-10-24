"""Validate pinned PDK identity and independent high-R-poly process/temperature axes."""
from pathlib import Path
import argparse
import fcntl
import hashlib
import json
import math
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / 'build/layout/pdk/gf180mcuD/libs.tech/ngspice'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--lock', default='/tmp/open-microled-ngspice.lock')
    parser.add_argument('--lengths', default='A:48,B:58', help='Comma-separated route:length_um entries')
    args = parser.parse_args()
    target = ROOT / 'build/highspeed-nrz-robustness-layout' / args.run
    target.mkdir(parents=True, exist_ok=False)
    lock = json.loads((ROOT/'layout/pdk-lock.json').read_text())
    for name in ('design.ngspice', 'sm141064.ngspice'):
        assert sha(MODEL/name) == lock['files']['libs.tech/ngspice/'+name]
    model_text = (MODEL/'sm141064.ngspice').read_text()
    sheet = {}
    for corner in ('typical','ss','ff'):
        section = re.search(r'^\.LIB res_'+corner+r'\s*$(.*?)^\.ENDL\s*$',model_text,re.M|re.S).group(1)
        value = re.search(r'^\+rsh_ppolyf_u_1k_6p0=(.+)$',section,re.M).group(1)
        assert value in ('1000',"'1000+200'","'1000-200'")
        sheet[corner] = {'1000':1000,"'1000+200'":1200,"'1000-200'":800}[value]
    for term in ("r_dw='0.0148E-6*",'r_dl=3.85E-11','r_tc1=-9.39e-4','r_tc2=2.51E-6',"rsh='85.45+",'tc1=-7.92E-3','tc2=4.25E-5'):
        assert term in model_text
    result = {'schema_version':1, 'passed':True, 'method':'Full pinned PDK .op versus independently evaluated body/end resistor equations; Cartesian resistor corner and temperature sweep.',
              'pdk_source_sha256':{name:sha(MODEL/name) for name in ('design.ngspice','sm141064.ngspice')},
              'script_sha256':sha(__file__), 'sheet_resistance_ohm_per_square':sheet,
              'corner_independence':'Separate .lib res_* selector; no MOS corner is loaded or inferred in this resistor-only experiment.',
              'rows':[]}
    for item in args.lengths.split(','):
        route,length_text=item.split(':');length=float(length_text)
        assert re.fullmatch(r'[A-Za-z0-9]+',route) and length>0
        for corner,rsh in sheet.items():
            for temp in [-40,27,125]:
                name=f'{route}-{corner}-{temp}'
                path=target/(name+'.cir')
                path.write_text(f'''Independent PDK resistor corner DC calibration
.include "{MODEL/'design.ngspice'}"
.lib "{MODEL/'sm141064.ngspice'}" res_{corner}
.temp {temp}
VTEST a 0 3.6
XR a 0 0 ppolyf_u_1k_6p0 r_width=1u r_length={length}u
.control
set numdgt=15
op
print i(VTEST)
quit
.endc
.end
''')
                with open(args.lock,'w') as mutex:
                    fcntl.flock(mutex,fcntl.LOCK_EX)
                    completed=subprocess.run(['ngspice','-b',str(path)],cwd=target,capture_output=True,text=True)
                log=completed.stdout+completed.stderr
                path.with_suffix('.log').write_text(log)
                assert completed.returncode==0,log
                current=-float(re.search(r'i\(vtest\)\s*=\s*([-+\d.eE]+)',log).group(1))
                actual=3.6/current
                dt=temp-25
                effective_w=1-2*.0148
                effective_l=length-2*3.85e-5
                body=rsh*effective_l/effective_w*(1-9.39e-4*dt+2.51e-6*dt*dt)
                end=85.45/effective_w*(1-7.92e-3*dt+4.25e-5*dt*dt)
                predicted=body+2*end
                assert math.isclose(actual,predicted,rel_tol=1e-11),(actual,predicted)
                result['rows'].append(dict(route=route,length_um=length,width_um=1,resistor_corner=corner,temperature_C=temp,
                   test_voltage_V=3.6,dc_current_A=current,resistance_ohm=actual,formula_resistance_ohm=predicted,
                   relative_error=abs(actual/predicted-1),log=name+'.log',netlist=name+'.cir',exit_code=completed.returncode))
    result['row_count']=len(result['rows'])
    result['files']=[dict(path=str(p.relative_to(target)),sha256=sha(p),size=p.stat().st_size) for p in sorted(target.iterdir()) if p.is_file()]
    (target/'pdk-resistor-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'path':str(target),'passed':True,'rows':len(result['rows']),'max_formula_error':max(x['relative_error'] for x in result['rows'])}))

if __name__=='__main__':
    main()
