"""A external two-level current calibration experiment. Run from the repository root."""
from pathlib import Path
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / 'build/driver-pvt-20261117/a'
PARENT = ARCH / 'trackwide4gm5buf2-fixed'
BUILD = ROOT / 'build/driver-ab-20261118/a'
EV = ROOT / 'evidence/driver-ab-20261118/a'
PVT = ROOT / 'scripts/driver_pvt_20261117/a'
sys.dont_write_bytecode = True

def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

prior = load_module(PVT/'run.py', 'a_prior')
analysis = load_module(PVT/'analyze_case.py', 'a_metrics')
sha, read, emit = prior.sha, prior.read, prior.emit
GRID = {row[0]: row for row in prior.GRID}
HOLD = {'holdTT': ('holdTT', 'typical', 45, 1.02), 'holdSS': ('holdSS', 'ss', 70, .965)}
CASES = GRID | HOLD

def netlist(point, codes, level, mode, rs=100.0, variant='sense'):
    label, section, temp, scale = CASES[point]
    template_label = label if label in GRID else 'TT'
    historical = PARENT
    if level is None and mode == 'fault':
        historical = ARCH / 'trackwide4gm5-fixed'
    base = historical / (f'{template_label}-DC-L{level}' if level is not None else
                         (f'{template_label}-fault-s40' if mode=='fault' else 'TT-continuous-f1-s40'))
    deck = (base/'testbench.spice').read_text()
    m = read(base/'manifest.json')
    if label in HOLD:
        assert level is not None
        deck = deck.replace('sm141064.ngspice" typical','sm141064.ngspice" '+section).replace('.temp 27',f'.temp {temp}')
        for source, voltage in [('VIN',5),('VDD',3.3),('VLED',5),('VD0',3.3*level)]:
            deck, count = re.subn(r'(?m)^'+source+r'( \w+ 0) [^\n]+$',lambda match: source+match[1]+f' {voltage*scale:.12g}',deck)
            assert count == 1
    route = (PARENT/'inputs/route_a.spice').read_text()
    if variant == 'sense':
        # Each external resistor-string tap is reduced to its two exact DC
        # resistance segments. The selected ideal contact is held during data.
        parts = []
        for prefix, code, sense in [('H', codes[0], 'HSENSE'), ('L', codes[1], 'LSENSE')]:
            assert 1 <= code <= 255
            parts += [f'R{prefix}DACUP VREF {prefix}TAP {(256-code)*1000}',
                      f'R{prefix}DACDN {prefix}TAP VSS {code*1000}',
                      f'R{prefix}INJ {prefix}TAP {sense} 47meg']
        route = route.replace('.ends fair_a','\n'.join(parts)+'\n.ends fair_a')
        assert 'LPKG pk out .5n' in deck
        deck = deck.replace('LPKG pk out .5n',f'LPKG pk mon .5n\nRMON mon out {rs:.12g}\nRADCDIFF mon out 10meg\nCADCDIFF mon out 50f')
        deck = re.sub(r'(?m)^(wrdata waveform.dat .+)$',r'\1 v(mon) v(xdrv.htap) v(xdrv.ltap)',deck)
        for node in ['mon','xdrv.htap','xdrv.ltap']:
            m['vectors'][node] = len(m['vectors']) + 1
        m['extra_caps'] = m.get('extra_caps',[])+[['ADC differential input',50e-15,'mon','out']]
    deck = deck.replace('../inputs/route_a.spice','route_a.spice')
    m['case'].update(corner=section, temp_C=temp,vdd_V=3.3*scale,vin_V=5*scale)
    return base, deck, route, m

def run(point, codes=(128,128), level=None, mode='dc', rs=100., variant='sense'):
    variant_tag = variant if rs==100 else f'{variant}-r{rs:g}'
    experiment = variant_tag + '-' + point
    ident = (f'dc{level}' if level is not None else mode) + f'-h{codes[0]}-l{codes[1]}'
    folder = BUILD/experiment/ident
    folder.mkdir(exist_ok=True, parents=True)
    inlink = folder.parent/'inputs'
    if not os.path.lexists(inlink):
        try:
            inlink.symlink_to(os.path.relpath(PARENT/'inputs',inlink.parent),target_is_directory=True)
        except FileExistsError:
            pass
    base, deck, route, m = netlist(point, codes, level, mode, rs, variant)
    result_file = folder/'result.json'
    if result_file.exists():
        r = read(result_file)
        assert r['deck_sha256']==hashlib.sha256(deck.encode()).hexdigest()
        assert r['route_sha256']==hashlib.sha256(route.encode()).hexdigest()
        return r
    (folder/'testbench.spice').write_text(deck)
    (folder/'route_a.spice').write_text(route)
    shutil.copyfile(base/'stimulus.json', folder/'stimulus.json')
    m.update(pvt=CASES[point], source_case=str(base.relative_to(ROOT)),
             case_name=ident, codes=list(codes), variant=variant, rs_ohm=rs,
             inputs={f.name:sha(f) for f in (PARENT/'inputs').rglob('*') if f.is_file() and f.name!='route_a.spice'},
             source_manifest_sha256=sha(base/'manifest.json'),
             source_deck_sha256=sha(base/'testbench.spice'), parent_route_sha256=sha(PARENT/'inputs/route_a.spice'),
             deck_sha256=sha(folder/'testbench.spice'),route_sha256=sha(folder/'route_a.spice'),
             stimulus_sha256=sha(folder/'stimulus.json'), runner_at_execution_sha256=sha(__file__),
             analysis_path=str((PVT/'analyze_case.py').relative_to(ROOT)),analysis_sha256=sha(PVT/'analyze_case.py'))
    emit(folder/'manifest.json',m)
    start=time.monotonic()
    with (folder/'ngspice.log').open('w') as log:
        proc=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,stdout=log,stderr=subprocess.STDOUT)
    log=(folder/'ngspice.log').read_text()
    assert proc.returncode==0 and 'simulation(s) aborted' not in log and 'Timestep too small' not in log
    raw=folder/'waveform.dat'
    a=np.loadtxt(raw,skiprows=1,ndmin=2)
    assert np.isfinite(a).all() and a.shape[1]==len(m['vectors'])+1
    if level is None:
        assert np.all(np.diff(a[:,0])>0) and abs(a[-1,0]-m['end_s']) < 1e-14
    r=analysis.summarize_case(folder,m,a)
    if level is not None and variant=='sense':
        ix=m['vectors']
        r['shunt_V']=float(a[-1,ix['mon']]-a[-1,ix['out']])
    del a
    r.update(case_path=str(folder.relative_to(ROOT)),codes=list(codes),pvt=CASES[point],
             deck_sha256=m['deck_sha256'],route_sha256=m['route_sha256'],
             manifest_sha256=sha(folder/'manifest.json'),native_sha256=sha(raw),log_sha256=sha(folder/'ngspice.log'))
    zipped=folder/'waveform.dat.gz'
    with gzip.open(zipped,'wb',compresslevel=2) as out,raw.open('rb') as src:
        shutil.copyfileobj(src,out)
    with gzip.open(zipped,'rb') as native:
        assert hashlib.file_digest(native,'sha256').hexdigest()==r['native_sha256']
    raw.unlink()
    r.update(compressed_sha256=sha(zipped),runtime_s=time.monotonic()-start)
    emit(result_file,r)
    return r

def calibrate(point, *, res=100., offset_uV=0.,gain=1.,tag='ideal'):
    # First hold D0=0, adjust H (higher cathode=25uA); then hold D0=1, adjust L.
    # ADC observes only the differential terminal voltage. Nominal Rs=100 ohm
    # enters the target, even when actual Rs has an injected error.
    codes=[128,128]
    history=[]
    for level,target_uA in enumerate([25.,100.]):
        lo,hi=1,255
        observations=[]
        while lo<=hi:
            code=(lo+hi)//2
            codes[level]=code
            r=run(point,tuple(codes),level,rs=res)
            adc_lsb=round((r['shunt_V']*gain+offset_uV*1e-6)/5e-6)
            err=adc_lsb*5e-6-target_uA*1e-6*100
            observations.append((abs(err),code))
            history.append(dict(level=level,code=code,observed_adc=adc_lsb,path=r['case_path']))
            if adc_lsb==round(target_uA*1e-6*100/5e-6):
                break
            if err<0:lo=code+1
            else:hi=code-1
        codes[level]=min(observations)[1]
    final=[run(point,tuple(codes),lev,rs=res) for lev in [0,1]]
    row=dict(point=point,codes=codes,history=history,res=res,offset_uV=offset_uV,gain=gain,
             final=[{k:r[k] for k in ['case_path','current_uA','DC_error_percent','DC_pass','shunt_V']} for r in final])
    emit(EV/f'{point}-{tag}.json',row)
    return row

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['cal','wave','hold','errors','controls'])
    p.add_argument('--point',default='all')
    p.add_argument('--mode',choices=['continuous','fault'],default='fault')
    p.add_argument('--baseline',action='store_true')
    args=p.parse_args()
    if args.action=='cal':
        for point in (GRID if args.point=='all' else [args.point]):
            print(point,calibrate(point)['codes'],flush=True)
    elif args.action=='wave':
        c=tuple(read(EV/f'{args.point}-ideal.json')['codes'])
        run(args.point,c,None,args.mode,variant='baseline' if args.baseline else 'sense')
    elif args.action=='hold':
        for point,old_point in [('holdTT','TT'),('holdSS','SShotlow')]:
            codes=tuple(read(EV/f'{old_point}-ideal.json')['codes'])
            for level in [0,1]:
                run(point,codes,level)
            calibrate(point)
    elif args.action=='errors':
        for tag,res,offset,gain in [('up',100.1,10.,1.001),('down',99.9,-10.,.999)]:
            calibrate('SShotlow',res=res,offset_uV=offset,gain=gain,tag=tag)
    elif args.action=='controls':
        for point in GRID:
            for level in [0,1]:
                run(point,(128,128),level)
