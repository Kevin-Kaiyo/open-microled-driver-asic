"""Small reproducible frozen-PDK SPICE engine; used by run.py and early probes."""
from pathlib import Path
import hashlib, json, math, re, subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
PDK=ROOT/'build/layout/pdk/gf180mcuD/libs.tech/ngspice'
REF=ROOT/'analog/reference/beta_multiplier.spice'
PIXEL=ROOT/'evidence/layout/pixel_driver_rc.spice'
LED=ROOT/'analog/models/microled.spice'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command(args,folder,log):
    p=subprocess.run(list(map(str,args)),cwd=folder,capture_output=True,text=True)
    out=p.stdout+p.stderr;(folder/log).write_text(out)
    if p.returncode or re.search(r'(?im)^Error:|fatal|timestep too small|simulation interrupted',out):
        raise RuntimeError(str(folder/log))
    return out
def run(folder,body,control,corner='typical',res='res_typical',temp=27):
    folder.mkdir(parents=True,exist_ok=True)
    for name in ['design.ngspice','sm141064.ngspice']:
        p=folder/name
        if not p.exists():p.symlink_to(PDK/name)
    deck=f'''GF180 actual transistor beta multiplier candidate
.include design.ngspice
.param sw_stat_global=0 sw_stat_mismatch=0
.lib sm141064.ngspice {corner}
.lib sm141064.ngspice {res}
.include "{REF}"
.temp {temp}
{body}
.options reltol=1e-7 abstol=1e-15 vntol=1e-9
.control
set noaskquit
set numdgt=15
set wr_vecnames
set wr_singlescale
{control}
quit
.endc
.end
'''
    (folder/'case.spice').write_text(deck)
    command(['ngspice','-b','case.spice'],folder,'ngspice.log')
    data=np.loadtxt(folder/'data.dat',skiprows=1,ndmin=2)
    if not np.isfinite(data).all():raise RuntimeError('Nonfinite '+str(folder))
    return data
def op(folder,rl=12e-6,logic=3.3,load=1.4,corner='typical',res='res_typical',temp=27,pixel=False,ledv=5,start=1,pwm=1):
    led_is=100e-6/math.expm1((2.8-100e-6*50)/(3*8.617333262145e-5*300.15))
    body=f'VDD vdd 0 {logic}\nXREF vdd 0 out beta_reference RL={rl:.15g} START={start}\n'
    if pixel:
        body+=f'''.include "{PIXEL}"
.include "{LED}"
.param LED_IS={led_is:.17g}
VSENSE out bias 0
VLED led_a 0 {ledv}
VPWM pwm 0 {logic*pwm}
XLED led_a led_k microled
XPIXEL 0 bias gate pwm pwm_b led_k vdd pixel_driver_layout
'''
        iexpr='-i(vled)';bias='v(bias)'
    else:body+=f'VLOAD out 0 {load}\n';iexpr='i(vload)';bias='v(out)'
    control=f'''op
let iout={iexpr}
let ivdd=-i(vdd)
let iref={'i(vsense)' if pixel else 'i(vload)'}
let branch=@m.xref.xn1.m0[id]
let kick=@m.xref.xnkick.m0[id]
let startup=@m.xref.xpup.m0[id]
wrdata data.dat iout ivdd iref v(xref.pg) v(xref.nb) v(xref.rs) v(xref.su) branch kick startup {bias}
'''
    a=run(folder,body,control,corner,res,temp)[0,1:]
    names=['iout_a','supply_a','iref_a','pg_v','nb_v','rs_v','su_v','branch_a','kick_a','startup_a','bias_v']
    return dict(zip(names,map(float,a)))
if __name__=='__main__':
    import tempfile
    w=ROOT/'build/reference';w.mkdir(exist_ok=True)
    d=Path(tempfile.mkdtemp(prefix='probe-',dir=w))
    for rl in [8e-6,12e-6,16e-6]:
        print(rl,op(d/str(rl),rl=rl))
    print(d)
