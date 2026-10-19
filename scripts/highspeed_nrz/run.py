"""Frozen, common-load GF180 transistor NRZ experiments.

Raw logs/decks/losslessly compressed traces stay under build. This is not an
optical BER test: only the driver is transistor level; LED dynamics and RX are
explicit behavioral assumptions layered on a published static I(V) curve.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import argparse
import csv
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
PDK=ROOT/'build/layout/pdk/gf180mcuD/libs.tech/ngspice'
BUILD=ROOT/'build/highspeed-nrz'
EVIDENCE=ROOT/'evidence/highspeed-nrz'
INPUTS=['analog/highspeed_nrz/voltage_driver.spice','analog/highspeed_nrz/steering_driver.spice',
        'analog/models/measured-led/lin2026-yellow20-dc.spice',
        'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv',
        'analog/models/measured-led/model-card.json','analog/models/measured-led/source-lock.json',
        'layout/pdk-lock.json','scripts/highspeed_nrz/run.py','scripts/highspeed_nrz/metrics.py',
        'evidence/highspeed-nrz/voltage-prototype.json','evidence/highspeed-nrz/steering-prototype.json']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prbs(n, tap):
    state=(1<<n)-1; initial=state; result=[]
    while True:
        result.append((state>>(n-1))&1)
        feedback=((state>>(n-1))^(state>>tap))&1
        state=((state<<1)&((1<<n)-1))|feedback
        if state==initial:break
        if len(result)>2**n:raise AssertionError('PRBS does not repeat')
    assert len(result)==2**n-1 and sum(result)==2**(n-1)
    return result

def stimulus():
    training=prbs(7,5)*2
    validation=prbs(9,4)
    bits=[0,1]*16+training+validation+[0,1]*16
    return {'bits':bits,'warmup_bits':32,'training_bits':training,'validation_bits':validation,
            'training_start_bit':32,'validation_start_bit':286,'validation_end_bit':797,
            'definition':'bit k starts at k*UI; transition ramps from k*UI to k*UI+edge; no validation retuning'}

def pwl(bits,ui,vdd,edge):
    points=[(0,bits[0]*vdd)]
    for k in range(1,len(bits)):
        if bits[k]!=bits[k-1]:points.extend([(k*ui,bits[k-1]*vdd),(k*ui+edge,bits[k]*vdd)])
    points.append((len(bits)*ui,bits[-1]*vdd))
    # Decimal normalization avoids insignificant binary-multiply digits at ideal
    # source slope breakpoints. Error is <1e-18 s over this experiment's window.
    return 'PWL(\n'+'\n'.join(f'+ {t:.12g} {v:.12g}' for t,v in points)+'\n+)'

def parse_devices(path):
    lines=path.read_text().splitlines();devices=[];ports=[]
    for line in lines:
        if line.lower().startswith('.subckt'):
            ports=line.split()[2:]
            if 'params:' in [x.lower() for x in ports]:ports=ports[:[x.lower() for x in ports].index('params:')]
        if re.match(r'^X\S+\s+',line,re.I):
            fields=line.split()
            if fields[5].lower() not in ['nfet_03v3','pfet_03v3']:raise ValueError('Nested cell needs explicit node mapping')
            devices.append({'instance':fields[0].lower(),'nodes':fields[1:5],'model':fields[5].lower(),'sizing':' '.join(fields[6:])})
    return ports,devices

def freeze():
    BUILD.mkdir(parents=True,exist_ok=True);EVIDENCE.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='run-',dir=BUILD));frozen=work/'inputs'
    hashes={}
    for name in INPUTS:
        src=ROOT/name
        if not src.exists():raise FileNotFoundError(src)
        dst=frozen/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);hashes[name]=sha(dst)
    lock=json.loads((frozen/'layout/pdk-lock.json').read_text())
    for name in ['design.ngspice','sm141064.ngspice']:
        src=PDK/name
        assert sha(src)==lock['files']['libs.tech/ngspice/'+name]
        dst=frozen/'pdk'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        hashes['build/layout/pdk/gf180mcuD/libs.tech/ngspice/'+name]=sha(dst)
    version=subprocess.run(['ngspice','--version'],capture_output=True,text=True,check=True).stdout
    (work/'ngspice-version.log').write_text(version)
    (work/'stimulus.json').write_text(json.dumps(stimulus(),indent=2)+'\n')
    manifest={'created_local':datetime.now().isoformat(),'inputs':hashes,'ngspice_version':version,
              'measurement_scope':'Pre-layout GF180 transistor driver; published static LED plus assumed C/R/L; behavioral optical/current proxy and receiver',
              'runtime':{'python':sys.version,'numpy':np.__version__},
              'body_geometry':'Both routes: isolated diffusion extension 0.6 um; AD=AS=W*0.6um and PD=PS=2*(W+0.6um), not extracted',
              'common':{'vled_V':5.0,'vdd_V':3.3,'led_C_F':200e-15,'package_R_ohm':1.0,'package_L_H':.5e-9,
                        'I0_A':25e-6,'I1_A':100e-6,'edge_s':20e-12,'temperature_C':27,'corner':'typical',
                        'optical_proxy_tau_s':200e-12,'receiver_bw_Hz':1e9,'fixed_threshold_A':62.5e-6,
                        'temperature_caution':'MOS temperature changes only; measured LED DC curve has no temperature model'},
              'route_a_rails':json.loads((frozen/'evidence/highspeed-nrz/voltage-prototype.json').read_text())['rails']}
    (work/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (EVIDENCE/'latest-run.json').write_text(json.dumps({'work':str(work.relative_to(ROOT))},indent=2)+'\n')
    return work

def case_spec(route,rate=.1,**kw):
    case={'route':route,'rate_Gbps':rate,'corner':'typical','temp_C':27,'vdd_V':3.3,
          'cap_F':200e-15,'r_pkg':1.,'l_pkg':.5e-9,'edge_s':20e-12,'steps_per_ui':40,'reltol':1e-5,'chgtol':1e-16,'method':'gear','kind':'nominal'}
    case.update(kw)
    case['name']=f"{route}-{case['kind']}-{rate:g}G-{case['corner']}-{case['temp_C']}C-{case['vdd_V']:g}V-C{case['cap_F']*1e15:g}-L{case['l_pkg']*1e9:g}-e{case['edge_s']*1e12:g}-s{case['steps_per_ui']}"
    if 'dc_bit' in case:case['name']+=f"-bit{case['dc_bit']}"
    return case

def build_deck(work,case):
    frozen=work/'inputs';route=case['route'];ui=1/(case['rate_Gbps']*1e9)
    name='voltage_driver.spice' if route=='A' else 'steering_driver.spice'
    ports,devices=parse_devices(frozen/'analog/highspeed_nrz'/name)
    portmap={'data':'data','out':'out','vdd':'vdd','vh':'vh','vl':'vl','vdummy':'vdummy','vss':'0'}
    def node(n):return portmap[n] if n in portmap else 'xdrv.'+n.lower()
    nodes=sorted(set(node(n) for d in devices for n in d['nodes'])-{'0'})
    devices=[d|{'nodes':[node(n) for n in d['nodes']]} for d in devices]
    rails={'VLED':('led_a',5.0),'VDD':('vdd',case['vdd_V'])}
    calibration=json.loads((work/'manifest.json').read_text())['route_a_rails']
    if route=='A':rails.update({'VH':('vh',calibration['VH_V']),'VL':('vl',calibration['VL_V'])})
    else:rails.update({'VDUMMY':('vdummy',3.3)})
    vectors=[('data','v(data)'),('out','v(out)'),('led_k','v(led_k)'),('led_voltage','v(led_a,led_k)'),
             ('iled_cond','i(VSENSE)'),('package_current','i(LPKG)')]
    vectors += [(n,f'v({n})') for n in nodes if n not in ['data','out']]
    vectors += [(key.lower()+'_current',f'i({key})') for key in rails]
    vectors += [('data_current','i(VDATA)')]
    st=stimulus();stop=len(st['bits'])*ui
    vdata=str(case['dc_bit']*case['vdd_V']) if 'dc_bit' in case else pwl(st['bits'],ui,case['vdd_V'],case['edge_s'])
    control='op' if 'dc_bit' in case else f'tran {ui/80:.16g} {stop:.16g} 0 {ui/case["steps_per_ui"]:.16g}'
    inst='hs_voltage_driver data out vdd vh vl 0' if route=='A' else 'hs_nrz_steering data out vdd vdummy 0'
    # ngspice syntax is instance nodes followed by subcircuit name.
    inst='data out vdd vh vl 0 hs_voltage_driver' if route=='A' else 'data out vdd vdummy 0 hs_nrz_steering'
    deck=f'''Common NRZ transistor experiment {case['name']}
.include "{frozen/'pdk/design.ngspice'}"
.param sw_stat_global=0 sw_stat_mismatch=0
.lib "{frozen/'pdk/sm141064.ngspice'}" {case['corner']}
.temp {case['temp_C']}
.include "{frozen/'analog/highspeed_nrz'/name}"
.include "{frozen/'analog/models/measured-led/lin2026-yellow20-dc.spice'}"
{chr(10).join(key+' '+pin+' 0 '+str(voltage) for key,(pin,voltage) in rails.items())}
VDATA data 0 {vdata}
XDRV {inst}
XLED led_a led_dc_k lin2026_yellow20_dc
VSENSE led_dc_k led_k 0
CLED led_a led_k {case['cap_F']:.16g}
RPKG led_k pkg {case['r_pkg']:.16g}
LPKG pkg out {case['l_pkg']:.16g}
.options reltol={case['reltol']} abstol=1e-13 vntol=1e-7 chgtol={case['chgtol']} method={case['method']} maxord=2
.control
set numdgt=15
set wr_singlescale
set wr_vecnames
{control}
wrdata waveform.dat {' '.join(v for k,v in vectors)}
quit
.endc
.end
'''
    return deck,vectors,devices,rails

def run_case(work,case):
    folder=work/'cases'/case['name'];folder.mkdir(parents=True,exist_ok=True)
    cached=folder/'result.json'
    if cached.exists():return json.loads(cached.read_text())
    deck,vectors,devices,rails=build_deck(work,case)
    (folder/'testbench.spice').write_text(deck)
    (folder/'case.json').write_text(json.dumps(case,indent=2)+'\n')
    # Included model libraries reference their own filename through ngspice's cwd.
    for name in ['sm141064.ngspice','design.ngspice']:
        link=folder/name
        if not link.exists():link.symlink_to(work/'inputs/pdk'/name)
    start=time.monotonic()
    p=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,capture_output=True,text=True)
    output=p.stdout+p.stderr;(folder/'ngspice.log').write_text(output)
    if p.returncode or re.search(r'(?im)^Error:|timestep too small|simulation interrupted|fatal error',output):
        failure={'case':case,'simulation_ok':False,'exit_code':p.returncode,'log':str((folder/'ngspice.log').relative_to(ROOT))}
        cached.write_text(json.dumps(failure,indent=2)+'\n');return failure
    raw=folder/'waveform.dat';a=np.atleast_2d(np.loadtxt(raw,skiprows=1))
    assert a.shape[1]==len(vectors)+1 and np.isfinite(a).all(),case['name']
    if 'dc_bit' not in case:assert np.all(np.diff(a[:,0])>0)
    if 'dc_bit' not in case:
        assert np.isclose(a[-1,0],len(stimulus()['bits'])/(case['rate_Gbps']*1e9),rtol=1e-10,atol=1e-18),'Incomplete transient'
    raw_hash=sha(raw)
    with raw.open('rb') as src,gzip.open(folder/'waveform.dat.gz','wb',compresslevel=1) as dst:shutil.copyfileobj(src,dst)
    raw.unlink() # newly generated, losslessly preserved .gz + original-byte hash
    result={'case':case,'simulation_ok':True,'exit_code':p.returncode,'elapsed_s':time.monotonic()-start,
            'waveform':str((folder/'waveform.dat.gz').relative_to(ROOT)),'uncompressed_sha256':raw_hash,
            'waveform_sha256':sha(folder/'waveform.dat.gz'),'deck_sha256':sha(folder/'testbench.spice'),
            'vectors':dict((key,i+1) for i,(key,v) in enumerate(vectors)),
            'devices':devices,'rails':dict((key,{'node':pin,'voltage_V':v}) for key,(pin,v) in rails.items()),
            'rows':len(a),'warnings':[line for line in output.splitlines() if 'warning' in line.lower()]}
    if 'dc_bit' in case:result['dc_values']=dict((key,float(a[-1,i+1])) for i,(key,v) in enumerate(vectors))
    cached.write_text(json.dumps(result,indent=2)+'\n')
    return result

def cases_for(stage):
    if stage=='nominal':
        return [case_spec(r,f) for r in ['A','B'] for f in [.1,.25,.5,1,2,4,8]]
    if stage=='dc':
        points=[('typical',27,3.3),('ss',27,3.3),('ff',27,3.3),('fs',27,3.3),('sf',27,3.3),
                ('typical',-40,3.3),('typical',125,3.3),('typical',27,3.0),('typical',27,3.6)]
        return [case_spec(r,kind='dc',corner=c,temp_C=t,vdd_V=v,dc_bit=b) for r in ['A','B'] for c,t,v in points for b in [0,1]]
    if stage=='sensitivity':
        cases=[]
        for r in ['A','B']:
            for f in [.25,.5,1,2]:
                for cap in [50e-15,2e-12]:cases.append(case_spec(r,f,kind='capacitance',cap_F=cap))
            for f in [.5,1,2]:
                cases.append(case_spec(r,f,kind='slow_hot',corner='ss',temp_C=125,vdd_V=3.0))
                cases.append(case_spec(r,f,kind='fast_cold',corner='ff',temp_C=-40,vdd_V=3.6))
            cases.extend([case_spec(r,1,kind='edge',edge_s=100e-12),
                          case_spec(r,1,kind='package',l_pkg=2e-9),
                          case_spec(r,1,kind='zero_cap_control',cap_F=0),
                          case_spec(r,1,kind='integration_control',method='trap',steps_per_ui=200),
                          *[case_spec(r,f,kind='numerical',steps_per_ui=80) for f in [.1,.5,1,2]],
                          case_spec(r,4,kind='numerical',steps_per_ui=200)])
        return cases
    raise ValueError(stage)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work');ap.add_argument('--stage',choices=['nominal','dc','sensitivity','all'],default='nominal');ap.add_argument('--workers',type=int,default=2)
    args=ap.parse_args();work=(ROOT/args.work).resolve() if args.work else freeze()
    if args.work:
        assert sha(Path(__file__))==sha(work/'inputs/scripts/highspeed_nrz/run.py'),'Use the frozen runner or start a fresh run after code changes'
    stages=['dc','nominal','sensitivity'] if args.stage=='all' else [args.stage]
    cases=[c for stage in stages for c in cases_for(stage)]
    print('WORK='+str(work.relative_to(ROOT)),flush=True)
    results=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(lambda c:run_case(work,c),cases):
            results.append(result);print(result['case']['name']+' '+('OK' if result['simulation_ok'] else 'FAILED'),flush=True)
    (work/f'run-{args.stage}.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps({'work':str(work.relative_to(ROOT)),'completed':len(results),'failed':sum(not r['simulation_ok'] for r in results)}),flush=True)

if __name__=='__main__':main()
