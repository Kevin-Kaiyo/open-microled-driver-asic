#!/usr/bin/env python3
"""Append-only 3.2 Gb/s net MicroLED layer isolation; legacy engine/RX immutable.

Run from the repository with build/layout/venv/bin/python and --phase run/analyze.
Electrical cases retain native time/current, native seven-port energy and stress.
Bypass/ideal controls are diagnostics, never replacements for the baseline screen.
"""
from pathlib import Path
import argparse, concurrent.futures, datetime, gzip, hashlib, importlib.util, json, math, shutil, subprocess, time
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'build/three-gbps-experiment-20261027/microled'
WORK = BUILD / 'run-r1'
EVIDENCE = ROOT / 'evidence/three-gbps-experiment-20261027'
LEGACY = ROOT / 'scripts/fair_driver_v1/run.py'
RXSOURCE = ROOT / 'scripts/fair_driver_v1/receiver_equal_latency_v2.py'
ORIGINAL = ROOT / 'build/fair-driver-v1/matched-r2'

def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec); spec.loader.exec_module(obj)
    return obj

e = module(LEGACY, 'microled_legacy_engine')
e.BUILD = BUILD
rx = module(RXSOURCE, 'microled_rx_reference')

def plan():
    cases = []
    for label, corner, temp, vdd in [('TT','typical',27,3.3), ('SS','ss',125,2.95), ('FF','ff',-40,3.65)]:
        for route in 'ABC':
            cases.append(dict(name=f'BASE-{label}-{route}-3p2G', route=route, corner=corner,
                              temp_C=temp, vdd_V=vdd, net_rate_Gbps=3.2, timeout_s=900,
                              group='baseline', steps_per_symbol=40))
    for route in 'ABC':
        cases.append(dict(name=f'CAP0-TT-{route}-3p2G', route=route, net_rate_Gbps=3.2,
                          led_cap_F=0., group='zero_cap_diagnostic', timeout_s=900,
                          steps_per_symbol=40))
    for capname, cap in [('CAP200', 200e-15), ('CAP0', 0.)]:
        for route in 'ABC':
            for level in range(4 if route == 'C' else 2):
                cases.append(dict(name=f'DC-{capname}-TT-{route}-L{level}', kind='dc',
                                  route=route, level=level, led_cap_F=cap,
                                  group='dc_calibration_check', timeout_s=90))
    return cases

def initialize():
    if (WORK/'manifest.json').exists():
        m=e.verify(WORK)
        assert m['legacy_engine_sha256']==e.sha(LEGACY)
        assert m['wrapper_sha256']==e.sha(Path(__file__))
        assert json.loads((WORK/'plan.json').read_text())==plan()
        return m
    old=e.verify(ORIGINAL)
    WORK.mkdir(parents=True, exist_ok=False)
    dest=WORK/'inputs'; dest.mkdir()
    for name in old['inputs']:
        src=RXSOURCE if name=='receiver.py' else ORIGINAL/'inputs'/name
        out=dest/name; out.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,out)
    stimulus=rx.make_stimulus(); original_st=json.loads((ORIGINAL/'stimulus.json').read_text())
    assert stimulus['bits']==original_st['bits'] and stimulus['eta']==32/37
    e.emit(WORK/'stimulus.json',stimulus); e.emit(WORK/'plan.json',plan())
    m={**old, 'created':datetime.datetime.now().astimezone().isoformat(),
       'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
       'inputs':{str(p.relative_to(dest)):e.sha(p) for p in dest.rglob('*') if p.is_file()},
       'stimulus_sha256':e.sha(WORK/'stimulus.json'), 'wrapper_sha256':e.sha(Path(__file__)),
       'legacy_engine_sha256':e.sha(LEGACY), 'original_manifest_sha256':e.sha(ORIGINAL/'manifest.json'),
       'purpose':'SCHEM only; fixed net3.2/line3.7Gbps; paired capacitance and independent stage controls, not retuning',
       'receiver_contract':'unchanged v2 0..8ns/5ps training-only delay; fixed 7.5uA and100ps gates',
       'ngspice_version':subprocess.check_output(['ngspice','--version'],text=True)}
    e.emit(WORK/'manifest.json',m)
    (WORK/'execution-sources').mkdir()
    shutil.copy2(Path(__file__),WORK/'execution-sources'/Path(__file__).name)
    return m

def compact_rx(result):
    return dict(bit_errors=result['validation']['bit_errors'], bit_count=result['validation']['bit_count'],
                symbol_errors=result['validation']['symbol_errors'],
                min_signed_margin_uA=result['validation']['decision_distance_min_uA'],
                mean_signed_margin_uA=result['validation']['decision_distance_mean_uA'],
                min_time_margin_ps=result['horizontal_margin']['min_ps'],
                delay_ps=result['sampling']['delay_s']*1e12, passed=result['passed'],checks=result['checks'])

def run_one(case):
    path=WORK/'cases'/case['name']/'result.json'
    if path.exists(): return json.loads(path.read_text())
    return e.run(WORK,case)

def first_order(t,y,tau):
    """Exact first-order state update for PWL input, initialized to first sample."""
    out=np.empty(len(t)); out[0]=y[0]
    for k in range(1,len(t)):
        h=t[k]-t[k-1]; z=h/tau; a=math.exp(-z); one=-math.expm1(-z)
        out[k]=a*out[k-1]+y[k-1]*one+(y[k]-y[k-1])*(1-one/z)
    return out

def stage_analysis(t,current,route,stimulus,folder):
    optical,full=rx.filter_trace(t,current)
    rx_only=first_order(t,current,rx.TAU_RX_S)
    bypass=module(RXSOURCE,'microled_rx_bypass')
    bypass.filter_trace=lambda t,y:(np.asarray(y),np.asarray(y))
    records={}
    for name,values in [('electrical',current),('optical_only',optical),('rx_only',rx_only),('full',full)]:
        result=bypass.analyze(t,values,stimulus,route,3.2)
        result['proxy']['diagnostic_stage']=name
        result['proxy']['optical_tau_s']=rx.TAU_OPTICAL_S if name in ['optical_only','full'] else None
        result['proxy']['rx_pole_Hz']=1e9 if name in ['rx_only','full'] else None
        result['proxy']['filter']='Precomputed stage input; immutable v2 training/threshold/margin logic, no second filtering'
        result['limits'].append('Each stage trains its own delay; diagnostic isolation only. Full is the original two-pole screen.')
        e.emit(folder/(name+'.json'),result); records[name]=compact_rx(result)
    return records

def ideal_trace(route,step_ps=5):
    st=rx.make_stimulus(); symbols=np.array(st['symbols_C' if route=='C' else 'symbols_N'])
    ui=(2 if route=='C' else 1)/3.7e9; duration=4736/3.7e9
    levels=(25+symbols*(25 if route=='C' else 75))*1e-6
    t=np.unique(np.r_[np.arange(0,duration,step_ps*1e-12),np.arange(1,len(symbols))*ui,
                      np.arange(1,len(symbols))*ui+20e-12,duration])
    k=np.minimum((t/ui).astype(int),len(symbols)-1); age=t-k*ui
    old=levels[np.maximum(k-1,0)]; current=old+(levels[k]-old)*np.minimum(1,age/20e-12)
    return t,current

def ideal_sink(route,cap):
    """Independent ideal driver -> same static LED+package, actual ngspice load control."""
    label='CAP0' if cap==0 else 'CAP200'; folder=WORK/'ideal-load'/f'{route}-{label}'
    result_path=folder/'result.json'
    if result_path.exists(): return json.loads(result_path.read_text())
    folder.mkdir(parents=True,exist_ok=False)
    st=rx.make_stimulus(); symbols=st['symbols_C' if route=='C' else 'symbols_N']
    levels=[(25+x*(25 if route=='C' else 75))*1e-6 for x in symbols]
    ui=(2 if route=='C' else 1)/3.7e9; duration=4736/3.7e9
    deck=f'''Ideal current sink diagnostic {route}-{label}; not a transistor driver
.include "{WORK/'inputs/led.spice'}"
VLED led_src 0 5
RLEDSRC led_src led_a .25
XLED led_a led_dc_k lin2026_yellow20_dc
VSENSE led_dc_k led_k 0
CLED led_a led_k {cap:.16g}
RPKG led_k pk 1
LPKG pk out .5n
IDRV out 0 {e.pwl(levels,ui,1.,20e-12)}
.options reltol=1e-5 abstol=1e-13 vntol=1e-7 chgtol=1e-16 method=gear maxord=2
.control
set numdgt=15
set wr_singlescale
set wr_vecnames
tran {ui/40:.16g} {duration:.16g} 0 {ui/40:.16g}
wrdata waveform.dat i(VSENSE)
quit
.endc
.end
'''
    (folder/'testbench.spice').write_text(deck); start=time.time()
    proc=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,capture_output=True,text=True,timeout=180)
    (folder/'ngspice.log').write_text(proc.stdout+proc.stderr)
    raw=folder/'waveform.dat'
    result=dict(exit_code=proc.returncode,elapsed_s=time.time()-start,route=route,capacitance_F=cap,
                deck_sha256=e.sha(folder/'testbench.spice'),level='ideal-driver load control; no transistor or energy comparison')
    assert proc.returncode==0 and raw.exists(),str(folder)
    a=np.loadtxt(raw,skiprows=1); result['stages']=stage_analysis(a[:,0],a[:,1],route,st,folder/'stages')
    result['raw_sha256']=e.sha(raw)
    with raw.open('rb') as src,gzip.open(folder/'waveform.dat.gz','wb') as dst: shutil.copyfileobj(src,dst)
    with gzip.open(folder/'waveform.dat.gz','rb') as src: assert hashlib.file_digest(src,'sha256').hexdigest()==result['raw_sha256']
    raw.unlink(); result['gzip_sha256']=e.sha(folder/'waveform.dat.gz')
    e.emit(result_path,result); return result

def analyze():
    initialize(); stimulus=rx.make_stimulus(); records=[]; dc=[]; missing=[]; failures=[]
    for case in plan():
        path=WORK/'cases'/case['name']/'result.json'
        if not path.exists(): missing.append(case['name']); continue
        r=json.loads(path.read_text())
        if not r.get('simulation_ok') or 'analysis_error' in r:
            failures.append(dict(name=case['name'],result=str(path.relative_to(ROOT)),exit_code=r['exit_code'],analysis_error=r.get('analysis_error')));continue
        m=r['metrics']
        if case.get('kind')=='dc':
            dc.append(dict(name=case['name'],route=case['route'],level=case['level'],cap_F=case['led_cap_F'],
                           current_uA=m['i_led_A']*1e6,error_percent=m['current_error_percent'],
                           voltage_pass=m['device_voltage_passed'],result_sha256=e.sha(path)));continue
        raw=path.with_name('waveform.dat.gz'); assert e.sha(raw)==r['gzip_sha256']
        a=np.loadtxt(raw,skiprows=1); folder=WORK/'layer-analysis'/case['name']
        stages=stage_analysis(a[:,0],a[:,1],case['route'],stimulus,folder)
        assert stages['full']==compact_rx(m['receiver']), 'Full-stage analysis must match unchanged receiver'
        records.append(dict(name=case['name'],route=case['route'],group=case['group'],corner=case.get('corner','typical'),
                            native_samples=len(a),max_step_ps=float(np.diff(a[:,0]).max()*1e12),
                            stages=stages,energy_pJ_netbit=m['total_energy']['positive_pJ_per_payload_bit'],
                            returned_energy_pJ_netbit=m['total_energy']['returned_pJ_per_payload_bit'],
                            energy_ports_pJ_netbit={k:v['positive_J']*1e12/4096 for k,v in m['energy'].items()},
                            mean_LED_current_uA=m['mean_LED_current_A']*1e6,
                            device_voltage_pass=m['device_voltage_passed'],max_body_forward_V=m['max_body_forward_V'],
                            source_result=str(path.relative_to(ROOT)),source_result_sha256=e.sha(path),
                            raw_sha256=r['raw_sha256'],gzip_sha256=r['gzip_sha256'],deck_sha256=r['deck_sha256'],
                            elapsed_s=r['elapsed_s']))
    ideal=[]
    for route in ['A','C']:
        t,y=ideal_trace(route)
        ideal.append(dict(route='NRZ' if route=='A' else 'PAM4',kind='ideal_conduction_waveform',
                          stages=stage_analysis(t,y,route,stimulus,WORK/'ideal-receiver'/route)))
        for cap in [200e-15,0.]: ideal.append(dict(kind='ngspice_ideal_sink',**ideal_sink(route,cap)))
    checks=[]
    for route in 'ABC':
        for level in range(4 if route=='C' else 2):
            values=[x for x in dc if x['route']==route and x['level']==level]
            if len(values)==2: checks.append(dict(route=route,level=level,capacitance_DC_delta_uA=values[0]['current_uA']-values[1]['current_uA']))
    report=dict(created=datetime.datetime.now().astimezone().isoformat(),schema='microled-layer-isolation-v1',
                rates=dict(net_Gbps=3.2,line_Gbps=3.7,eta=32/37,NRZ_GBd=3.7,PAM4_GBd=1.85,payload_bits=4096),
                manifest_sha256=e.sha(WORK/'manifest.json'),wrapper_sha256=e.sha(Path(__file__)),
                legacy_engine_sha256=e.sha(LEGACY),receiver_v2_sha256=e.sha(RXSOURCE),
                records=records,dc=dc,dc_capacitance_checks=checks,ideal_controls=ideal,missing=missing,failures=failures,
                limits=['New SCHEM ngspice simulation only; no new layout/DRC/LVS/PEX/silicon/optical measurement.',
                        'Static LED PWL and200fF are frozen assumptions; no measured capacitance, carrier lifetime or optical calibration.',
                        'Stage bypasses each choose training-only delay independently; diagnostic separation, not a physical receiver claim.',
                        'Ideal sink has no driver MOS, energy or stress qualification and is excluded from topology ranking.',
                        'No error-free finite deterministic trace can certify BER. All existing7.5uA/100ps screen gates retained.',
                        'Positive energy includes VIN,VDD,VREF,VLED,VD0,VD1,VDISABLE; excludes source IC overhead, RX, clock and host.'])
    e.emit(EVIDENCE/'microled-summary.json',report)
    print(json.dumps({'records':len(records),'dc':len(dc),'missing':missing,'failures':failures},ensure_ascii=False),flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['run','analyze'],required=True)
    ap.add_argument('--jobs',type=int,default=2);ap.add_argument('--only',default='');a=ap.parse_args()
    initialize()
    if a.phase=='analyze':analyze();return
    selected=[c for c in plan() if a.only in c['name']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        for r in pool.map(run_one,selected):
            m=r.get('metrics',{});result={'name':r['case']['name'],'ok':r['simulation_ok'],'seconds':round(r['elapsed_s'],2),'analysis_error':r.get('analysis_error')}
            if 'receiver' in m:result.update(compact_rx(m['receiver']),energy_pJ_netbit=m['total_energy']['positive_pJ_per_payload_bit'])
            else:result.update(current_uA=m.get('i_led_A',0)*1e6)
            print(json.dumps(result),flush=True)

if __name__=='__main__':main()
