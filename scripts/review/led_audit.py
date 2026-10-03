"""Independent MicroLED model audit. Run after make setup; the working directory may be anywhere.
Raw decks/logs go to build/audit_led; compact results go to evidence/review.
These calculations and simulations are synthetic; they do not fit a real LED.
"""
from pathlib import Path
import math, json, subprocess, hashlib, re, shutil, tempfile
ROOT=Path(__file__).resolve().parents[2]
RAW=ROOT/'build/audit_led'; E=ROOT/'evidence/review'
RAW.mkdir(parents=True, exist_ok=True)
E.mkdir(parents=True, exist_ok=True)
B=Path(tempfile.mkdtemp(prefix='run-', dir=RAW))
# Each audit uses immutable copies; concurrent source edits cannot change cases.
source_files=['analog/models/microled.spice', 'analog/driver/pixel_driver.spice',
              'analog/models/pdk-lock.json', 'scripts/run_phase1.py',
              'scripts/review/led_audit.py']
source_hashes={}
for name in source_files:
    target=B/'inputs'/name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT/name, target)
    source_hashes[name]=hashlib.sha256(target.read_bytes()).hexdigest()
lock=json.loads((B/'inputs/analog/models/pdk-lock.json').read_text())
pdk_dir=B/'inputs/pdk'; pdk_dir.mkdir()
pdk_hashes={}
for upstream_name, expected in lock['files'].items():
    name=Path(upstream_name).name
    payload=(ROOT/'.cache/pdk/gf180mcu'/name).read_bytes()
    actual=hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise RuntimeError('Installed PDK source differs from lock: '+upstream_name)
    (pdk_dir/name).write_bytes(payload)
    pdk_hashes[upstream_name]=actual
Vt=1.380649e-23*300.15/1.602176634e-19
modelpath=B/'inputs/analog/models/microled.spice'
driverpath=B/'inputs/analog/driver/pixel_driver.spice'
base_model=modelpath.read_text()
for token in ['N=3', 'RS=50', 'CJO=2p', 'VJ=2.5', 'M=0.33', 'TT=1n', 'EG=2.6', 'TNOM=27']:
    if not re.search(r'(?<![A-Za-z0-9_])'+re.escape(token)+r'(?=[\s)])',base_model):
        raise RuntimeError('Baseline changed; update independent audit assumptions: '+token)
params={'N':3.0,'RS_ohm':50.,'CJO_F':2e-12,'VJ_V':2.5,'M':.33,'TT_s':1e-9,'EG_eV':2.6,'TNOM_C':27}

def run(name, deck):
    d=B/name;d.mkdir(exist_ok=True)
    (d/'test.spice').write_text(deck)
    (d/'result.dat').unlink(missing_ok=True)
    r=subprocess.run(['ngspice','-b','test.spice'],cwd=d,text=True,capture_output=True)
    (d/'ngspice.log').write_text(r.stdout+r.stderr)
    if r.returncode or not (d/'result.dat').exists(): raise RuntimeError(str(d)+r.stdout+r.stderr)
    rows=(d/'result.dat').read_text().strip().splitlines()
    values = [float(v) for v in rows[-1].split()]
    if not all(math.isfinite(v) for v in values): raise RuntimeError('nonfinite result: '+str(d))
    return values

def led_deck(current=100e-6,temp=27,n=3,rs=50,vf=2.8,extra='',mode='op',cjo=2e-12,tt=1e-9):
    Is=100e-6/math.expm1((vf-100e-6*rs)/(n*Vt))
    cmd='op\nwrdata result.dat v(a)' if mode=='op' else 'ac lin 1 1000 1000\nlet zr=real(v(a))\nlet zi=imag(v(a))\nwrdata result.dat zr zi'
    return f'''Independent synthetic LED audit
Itest 0 a DC {current:.17g} AC 1
Dled a 0 load
.model load D (IS={Is:.17g} N={n} RS={rs} CJO={cjo} VJ=2.5 M=.33 TT={tt} EG=2.6 TNOM=27)
.temp {temp}
.options reltol=1e-10 abstol=1e-18 vntol=1e-12 {extra}
.control
set wr_singlescale
set numdgt=15
{cmd}
quit
.endc
.end
'''

ngspice_version=subprocess.check_output(['ngspice','--version'],text=True)
(B/'ngspice-version.log').write_text(ngspice_version)
result={'tool':ngspice_version.splitlines()[1:4], 'ngspice_version':ngspice_version,
        'evidence_class':'Independent calculations and ngspice simulation; no measured LED data',
        'parameters':params, 'thermal_voltage_V':Vt, 'source_sha256':source_hashes,
        'source_copy_directory':str((B/'inputs').relative_to(ROOT)),
        'run_directory':str(B.relative_to(ROOT)),
        'pdk_commit':lock['commit'], 'pdk_file_sha256':pdk_hashes,
        'pdk_hashes_match_lock':True}
result['options']={'isolated_led':'reltol=1e-10 abstol=1e-18 vntol=1e-12, default GMIN unless explicitly recorded', 'gmin_driver':'reltol=1e-7 abstol=1e-16 vntol=1e-9', 'driver_model':'original phase1 pre-layout GF180 model subset', 'working_temperature_C':27}
result['calibration']=[]
for vf in [2.4,2.8,3.2]:
    Is=100e-6/math.expm1((vf-.005)/(3*Vt))
    got=run(f'cal_{vf}',led_deck(vf=vf))[-1]
    result['calibration'].append({'target_V':vf,'IS_A':Is,'spice_V':got,'error_uV':(got-vf)*1e6})
result['same_anchor_iv']=[]
for n in [2.2,3.,4.]:
    # Lower epsmin explicitly for N2.2; measured current range is hypothetical.
    Is=100e-6/math.expm1((2.8-.005)/(n*Vt))
    for current in [1e-9,1e-6,10e-6,100e-6,1e-3]:
        actual=run(f'iv_n{n}_i{current}',led_deck(current=current,n=n,extra='epsmin=1e-50'))[-1]
        analytic=n*Vt*math.log1p(current/Is)+current*50
        result['same_anchor_iv'].append({'N':n,'I_A':current,'IS_A':Is,'calculated_V':analytic,'simulated_V':actual})
result['temperature']=[]
for temp in [0,27,85]:
    actual=run(f'temp_{temp}',led_deck(temp=temp))[-1]
    result['temperature'].append({'temp_C':temp,'I_A':100e-6,'simulated_V':actual})
result['epsmin']=[]
for extra in ['', 'epsmin=1e-50']:
    actual=run('floor_default' if not extra else 'floor_lowered',led_deck(vf=3.2,n=2.2,extra=extra))[-1]
    result['epsmin'].append({'N':2.2,'Vf_target_V':3.2,'requested_IS_A':100e-6/math.expm1((3.2-.005)/(2.2*Vt)),'option':extra or 'default','simulated_V':actual})
result['gmin_off']=[]
for gmin in [1e-9,1e-12,1e-15,1e-18]:
    prefix=f"""Independent pre-layout six-MOS off-current audit
.include design.ngspice
.param sw_stat_global=0 sw_stat_mismatch=0
.lib sm141064.ngspice typical
.param LED_IS={100e-6/math.expm1((2.8-.005)/(3*Vt)):.17g}
.include \"{modelpath}\"
.include \"{driverpath}\"
.temp 27
VDD vdd 0 5
VLOGIC vlogic 0 3.3
IREF vlogic bias DC 100u
VSENSE vdd led_a 0
VPWM pwm 0 0
XLED led_a led_k microled
XPIXEL led_k pwm vlogic bias gate pwm_b pixel_driver
.options reltol=1e-7 abstol=1e-16 vntol=1e-9 gmin={gmin}
"""
    name=f'gmin_tighter_{gmin}'; d=B/name;d.mkdir(exist_ok=True)
    for filename in ['design.ngspice','sm141064.ngspice']:
        link=d/filename
        if not link.exists():link.symlink_to(pdk_dir/filename)
    vals=run(name,prefix+'''.control
set wr_singlescale
set numdgt=15
op
wrdata result.dat i(VSENSE) v(led_k) v(gate) v(bias)
quit
.endc
.end
''')
    result['gmin_off'].append({'gmin_S':gmin,'current_A':vals[1],'V_cathode_V':vals[2],'V_gate_V':vals[3],'V_bias_V':vals[4]})
result['capacitance']=[]
for cjo in [0,2e-12,20e-12]:
    for tt in [0,1e-9,10e-9]:
        vals=run(f'cap_{cjo}_{tt}',led_deck(mode='ac',cjo=cjo,tt=tt))
        z=complex(vals[1],vals[2]); y=1/(z-50)
        result['capacitance'].append({'CJO_F':cjo,'TT_s':tt,'frequency_Hz':1000,'dc_I_A':100e-6,'terminal_Z_real_ohm':z.real,'terminal_Z_imag_ohm':z.imag,'junction_C_F':y.imag/(2*math.pi*1000),'junction_G_S':y.real})
result['current_density_examples']=[{'square_side_um':s,'I_A':100e-6,'J_A_per_cm2':100e-6/(s*1e-4)**2} for s in [5,10,20,50,100]]
result['successful_simulations']=sum(len(result[k]) for k in ['calibration','same_anchor_iv','temperature','epsmin','gmin_off','capacitance'])
result['analytic_dVdT_at_27_mV_per_C']=((2.8-100e-6*50-2.6)/300.15-3*(1.380649e-23/1.602176634e-19))*1e3
result['rs_drop_at_100uA_mV']=100e-6*50*1e3
result['differential_resistance_at_100uA_ohm']=3*Vt/100e-6+50
(E/'led-independent-checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
