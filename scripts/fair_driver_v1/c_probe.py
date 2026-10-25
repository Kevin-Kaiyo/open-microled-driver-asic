#!/usr/bin/env python3
"""Bounded schematic C DC probe. Never modifies old sources or existing runs."""
from pathlib import Path
import argparse, datetime, fcntl, gzip, hashlib, json, shutil, subprocess
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GRAY = [(0, 0), (0, 1), (1, 1), (1, 0)]  # (D1,D0), ascending analog level


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def emit(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def mos_nodes(route, reference):
    top = {'D0': 'd0', 'D1': 'd1', 'OUT': 'out', 'VIN': 'vin',
           'VDD': 'vdd', 'VREF': 'vref', 'VSS': '0', 'DISABLE': 'disable'}
    resolve = lambda n: top.get(n.upper(), 'xdrv.' + n.lower())
    devices = []
    for line in route.splitlines():
        w = line.split()
        if len(w) >= 6 and w[0].startswith('X') and w[5] in ('nfet_03v3', 'nfet_06v0', 'pfet_06v0'):
            devices.append({'instance': w[0], 'model': w[5], 'nodes': [resolve(n) for n in w[1:5]]})
    refpins = ['VIN', 'VSS', 'VSET', 'SENSE', 'IOUT', 'IPB', 'IN2', 'ICTRL', 'DISABLE', 'KRET']
    refnets = ['VIN', 'VSS', 'VSET', 'SENSE', 'BIAS', 'IPB', 'IN2', 'ICTRL', 'DISABLE', 'KRET']
    refmap = dict(zip(refpins, map(resolve, refnets)))
    for line in reference.splitlines():
        w = line.split()
        if len(w) >= 6 and w[0].startswith('X') and w[5] in ('nfet_03v3', 'nfet_06v0', 'pfet_06v0'):
            ns = [refmap.get(n.upper(), 'xdrv.xrefmod.' + n.lower()) for n in w[1:5]]
            devices.append({'instance': 'XREFMOD.' + w[0], 'model': w[5], 'nodes': ns})
    assert len(devices) == 49
    return devices


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='build/fair-driver-v1-c-probe/dc-r1')
    ap.add_argument('--rset', type=float, default=20000)
    ap.add_argument('--wunit', type=float, default=1.92e-6)
    ap.add_argument('--pvt', nargs='+', choices=['TT','SS','FF'], default=['TT','SS','FF'])
    ap.add_argument('--levels', nargs='+', type=int, choices=range(4), default=[0,1,2,3])
    args = ap.parse_args()
    work = (ROOT / args.work).resolve()
    assert work.is_relative_to(ROOT / 'build/fair-driver-v1-c-probe')
    assert not work.exists(), 'Existing runs are immutable; choose another --work'
    assert shutil.disk_usage(ROOT).free >= 5 * 1024**3
    inp = work / 'inputs'; inp.mkdir(parents=True)
    old = ROOT / 'build/highspeed-nrz-robustness/selected-a8-b58-r4/inputs'
    sources = {'route_c.spice': ROOT/'analog/fair_driver_v1/route_c.spice',
               'reference.spice': ROOT/'analog/nrz_reference_v2/vi_reference_switched_keeper.spice',
               'led.spice': old/'led.spice', 'design.ngspice': old/'pdk/design.ngspice',
               'sm141064.ngspice': old/'pdk/sm141064.ngspice', 'c_probe.py': Path(__file__)}
    for name, src in sources.items(): shutil.copy2(src, inp/name)
    devices = mos_nodes((inp/'route_c.spice').read_text(), (inp/'reference.spice').read_text())
    nodes = sorted({n for d in devices for n in d['nodes']} - {'0'})
    rails = ['VLED', 'VIN', 'VDD', 'VREF', 'VD0', 'VD1', 'VDISABLE']
    exprs = ['i(VSENSE)'] + ['v('+n+')' for n in nodes] + ['i('+n+')' for n in rails]
    index = {e: i+1 for i, e in enumerate(exprs)}
    cases = [dict(label=lab, corner=co, temp_C=t, vdd_V=v, level=k, D1=d1, D0=d0)
             for lab,co,t,v in [('TT','typical',27,3.3),('SS','ss',125,2.95),('FF','ff',-40,3.65)]
             for k,(d1,d0) in enumerate(GRAY) if lab in args.pvt and k in args.levels]
    plan = {'declared_before_execution': datetime.datetime.now().isoformat(), 'scope': 'Schematic DC only, no PEX/NRZ/PAM4 eye or BER claim',
            'cases': cases, 'fixed_parameters': {'RSET_ohm': args.rset, 'WUNIT_m': args.wunit},
            'source_sha256': {k: sha(inp/k) for k in sources}, 'devices': devices,
            'all_12_directed_transitions_planned_not_run': [{'from_level':a,'to_level':b,'from_D1D0':GRAY[a],'to_D1D0':GRAY[b]}
                for a in range(4) for b in range(4) if a != b],
            'resource_limit_bytes': 200*1024**2, 'lock': '/tmp/open-microled-nrz-ngspice.lock'}
    emit(work/'plan.json', plan)
    rows=[]
    for c in cases:
        f=work/(c['label']+'-L'+str(c['level'])); f.mkdir()
        deck=f'''Fair C schematic DC, not extracted
.include "{inp/'design.ngspice'}"
.param sw_stat_global=0 sw_stat_mismatch=0
.lib "{inp/'sm141064.ngspice'}" {c['corner']}
.lib "{inp/'sm141064.ngspice'}" res_{c['corner']}
.temp {c['temp_C']}
.include "{inp/'reference.spice'}"
.include "{inp/'route_c.spice'}"
.include "{inp/'led.spice'}"
VLED led_a 0 5
VIN vin 0 5
VDD vdd 0 {c['vdd_V']}
VREF refsrc 0 2.5
RREFOUT refsrc vref .2
VD0 d0 0 {c['D0']*c['vdd_V']}
VD1 d1 0 {c['D1']*c['vdd_V']}
VDISABLE disablesrc 0 0
RGPIO disablesrc disable 100
XDRV d0 d1 out vin vdd vref 0 disable fair_c RSET={args.rset} WUNIT={args.wunit}
XLED led_a led_dc_k lin2026_yellow20_dc
VSENSE led_dc_k led_k 0
CLED led_a led_k 200f
RPKG led_k pkg 1
LPKG pkg out .5n
.options reltol=1e-7 abstol=1e-14 vntol=1e-9 chgtol=1e-17
.control
set numdgt=15
set wr_singlescale
set wr_vecnames
op
wrdata waveform.dat {' '.join(exprs)}
quit
.endc
.end
'''
        (f/'testbench.spice').write_text(deck)
        with open('/tmp/open-microled-nrz-ngspice.lock','a') as lock, (f/'ngspice.log').open('w') as log:
            fcntl.flock(lock,fcntl.LOCK_EX)
            run=subprocess.run(['ngspice','-b','testbench.spice'],cwd=f,stdout=log,stderr=subprocess.STDOUT,timeout=30)
        result={'case':c,'exit_code':run.returncode,'deck_sha256':sha(f/'testbench.spice'),'log_sha256':sha(f/'ngspice.log')}
        assert run.returncode == 0, str(f/'ngspice.log')
        data=np.atleast_2d(np.loadtxt(f/'waveform.dat',skiprows=1))[-1]
        def voltage(n): return 0. if n=='0' else float(data[index['v('+n+')']])
        stress=[]
        for d in devices:
            vals=list(map(voltage,d['nodes'])); pairs={}
            for label,i,j in [('VDS',0,2),('VGS',1,2),('VGD',1,0),('VGB',1,3),('VDB',0,3),('VSB',2,3)]:pairs[label]=vals[i]-vals[j]
            limit=3.63 if d['model']=='nfet_03v3' else 6.
            stress.append(dict(d, voltages_DGSB_V=vals, differences_V=pairs, maximum_abs_V=max(map(abs,pairs.values())), limit_V=limit))
        decoder=[voltage('xdrv.t1'),voltage('d1'),voltage('xdrv.t3')]
        truth=[int(z>c['vdd_V']/2) for z in decoder]
        expected=[int(c['D1'] or c['D0']),c['D1'],int(c['D1'] and not c['D0'])]
        assert truth==expected, (c,truth,expected)
        current=float(data[index['i(VSENSE)']])
        currents={rail:float(data[index['i('+rail+')']]) for rail in rails}
        volts={'VLED':5.,'VIN':5.,'VDD':c['vdd_V'],'VREF':2.5,'VD0':c['D0']*c['vdd_V'],'VD1':c['D1']*c['vdd_V'],'VDISABLE':0.}
        powers={rail:-volts[rail]*currents[rail] for rail in rails}
        result.update(LED_current_A=current, target_A=(c['level']+1)*25e-6, target_error_percent=100*(current/((c['level']+1)*25e-6)-1),
                      nodes_V={n:voltage(n) for n in nodes}, decoder_T1_T2_T3_V=decoder, decoder_truth_passed=True,
                      stress=stress, device_screen_passed=all(d['maximum_abs_V']<=d['limit_V'] for d in stress),
                      source_currents_A=currents, source_delivered_power_W=powers,
                      source_total_positive_power_W=sum(max(p,0) for p in powers.values()), source_total_net_power_W=sum(powers.values()))
        raw=f/'waveform.dat'; original=sha(raw); gz=f/'waveform.dat.gz'
        with raw.open('rb') as fi,gzip.open(gz,'wb',compresslevel=6) as fo:shutil.copyfileobj(fi,fo)
        assert hashlib.sha256(gzip.open(gz,'rb').read()).hexdigest()==original
        raw.unlink()  # Only this newly generated, losslessly verified scratch file.
        result.update(waveform_sha256=sha(gz),uncompressed_sha256=original,roundtrip_verified=True)
        emit(f/'result.json',result); rows.append(result)
        print(c['label'],c['level'],current*1e6,'uA','device',result['device_screen_passed'],flush=True)
    linearity=[]
    for label in ['TT','SS','FF']:
        pts=[r['LED_current_A'] for r in rows if r['case']['label']==label]
        if len(pts)!=4: continue
        endpoint_step=(pts[-1]-pts[0])/3
        linearity.append({'PVT':label,'currents_uA':[v*1e6 for v in pts], 'endpoint_step_uA':endpoint_step*1e6,
                          'DNL_endpoint_LSB':[(pts[i+1]-pts[i])/endpoint_step-1 for i in range(3)],
                          'INL_endpoint_LSB':[(pts[i]-(pts[0]+i*endpoint_step))/endpoint_step for i in range(4)],
                          'absolute_error_25uA_LSB':[(pts[i]-(i+1)*25e-6)/25e-6 for i in range(4)]})
    emit(work/'summary.json',{'scope':'Schematic four-level DC. Endpoint INL/DNL remove offset/gain; absolute error retained separately.',
         'plan_sha256':sha(work/'plan.json'),'rows':[{'path':str(Path(r['case']['label']+'-L'+str(r['case']['level']))/'result.json'),
         'LED_current_A':r['LED_current_A'],'device_screen_passed':r['device_screen_passed']} for r in rows], 'linearity':linearity,
         'sources':plan['source_sha256'],'all_devices_count':len(devices),'MOS_by_model':{m:sum(d['model']==m for d in devices) for m in ['nfet_03v3','nfet_06v0','pfet_06v0']}})
    assert sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) < 200*1024**2


if __name__=='__main__': main()
