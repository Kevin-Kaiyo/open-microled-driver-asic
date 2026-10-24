#!/usr/bin/env python3
"""PVT repair experiment engine; frozen original load/RX, actual MOS and resistor terminals.
Entry points: explore.py for immutable candidates, formal.py for selected-layout regression.
All legacy data remains read-only. Cache mismatches reject instead of overwriting.
"""
from pathlib import Path
from datetime import datetime
import argparse
import gzip
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/nrz-reference-v2'
EVIDENCE=ROOT/'evidence/nrz-reference-v2'
BASE=ROOT/'build/highspeed-nrz/run-0xqxvspp'
RATES=[.1,.25,.5,1,2,4,8]
MAX_INCREMENTAL_BYTES=int(3.5*1024**3)
RUNNER_SOURCE_BYTES=Path(__file__).read_bytes()
RUNNER_SOURCE_SHA256=hashlib.sha256(RUNNER_SOURCE_BYTES).hexdigest()

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()

def rel(path):
    try:return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:return str(Path(path).resolve())

def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
    return m

def legacy(work=None):
    path=(work/'inputs/legacy/run.py') if work else BASE/'inputs/scripts/highspeed_nrz/run.py'
    m=module(path,'nrz_legacy_runner');m.ROOT=ROOT
    return m

def emit(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,prefix=path.name+'.',suffix='.tmp',delete=False) as f:
        f.write(payload);name=f.name
    os.replace(name,path)

def parse_core(path):
    txt=re.sub(r'\n\s*\+\s*',' ',path.read_text())
    sub=None;ports=[];devices=[]
    for line in txt.splitlines():
        s=line.strip()
        if s.lower().startswith('.subckt'):
            if sub is not None:raise ValueError('Require a single flat physical core')
            p=s.split();sub=p[1].lower();ports=[n.lower() for n in p[2:]]
            if 'params:' in ports:ports=ports[:ports.index('params:')]
        elif re.match(r'^[Xx]\S+\s',s):
            p=s.split()
            if len(p)>4 and p[4].lower()=='ppolyf_u_1k_6p0':continue
            if p[5].lower() not in ['nfet_03v3','pfet_03v3','nfet_06v0','pfet_06v0']:
                raise ValueError('Unsupported nested core/model: '+s)
            devices.append({'instance':p[0].lower(),'nodes':[n.lower() for n in p[1:5]],
                            'model':p[5].lower(),'sizing':' '.join(p[6:])})
    if not sub or not devices:raise ValueError('Missing core or MOS devices')
    return sub,ports,devices

def parse_passives(path):
    text=re.sub(r'\n\s*\+\s*',' ',path.read_text());out=[]
    for line in text.splitlines():
        p=line.split()
        if len(p)>4 and p[0].lower().startswith('x') and p[4].lower()=='ppolyf_u_1k_6p0':
            out.append({'instance':p[0].lower(),'nodes':[n.lower() for n in p[1:4]],'model':p[4].lower(),'sizing':' '.join(p[5:])})
    return out

def case_spec(work,route,variant,rate=1,**kwargs):
    c=legacy(work).case_spec(route,rate,**kwargs)
    c['variant']=variant;c['name']=variant+'-'+c['name']
    return c

def build_deck(work,case):
    m=json.loads((work/'manifest.json').read_text());frozen=work/'inputs'
    definition=m['variants'][case['route']][case['variant']]
    core=frozen/definition['path']
    if definition.get('sha256') and sha(core)!=definition['sha256']:raise ValueError('core hash drift')
    sub,ports,devices=parse_core(core)
    supply_pkg=case.get('supply_package')
    portmap={n:(('diegnd' if supply_pkg else '0') if n=='vss' else n) for n in ports}
    def node(n):return portmap.get(n,'xdrv.'+n)
    passives=parse_passives(core)
    nodes=sorted(set(node(n) for d in devices+passives for n in d['nodes'])-{'0'})
    devices=[d|{'nodes':[node(n) for n in d['nodes']]} for d in devices]
    mapping_file=frozen/'physical'/f'{case["route"]}-contract.json'
    if case['variant'] in ['GEOM','C','RC','AFTER'] and mapping_file.exists():
        mapping={d['extracted_instance'].lower():d for d in json.loads(mapping_file.read_text()).get('extracted_device_mapping',[])}
        devices=[d|({'original_instance':mapping[d['instance']]['original_instance'],
                     'extracted_D_S_swapped_from_original':mapping[d['instance']]['drain_source_swapped']}
                    if d['instance'] in mapping else {}) for d in devices]
    rails={'VLED':('led_a',5.),'VDD':('vdd',case['vdd_V'])}
    if case['route']=='A':
        rails.update({'VH':('vh',definition.get('rails',m['route_a_rails'])['VH_V']),'VL':('vl',definition.get('rails',m['route_a_rails'])['VL_V'])})
    else:
        if definition.get('reference_v2'):
            rails['VRAW']=('vin_source',case.get('vin_V',5.))
            anchor=2.5*(1+case.get('anchor_error',0))*(1+case.get('anchor_tc_ppm',0)*1e-6*(case['temp_C']-27))
            rails['VREF']=('ref_source',anchor)
            if definition.get('disable_clamp'):rails['VDISABLE']=('disable_source',case.get('disable_V',0.))
        else:rails['VDUMMY']=('vdummy',3.3)
    supply_package_lines=''
    if supply_pkg:
        rails['VDD']=('vdd_source',case['vdd_V'])
        supply_package_lines=f"RVDDPKG vdd_source pvdd {supply_pkg['r_vdd_ohm']}\nLVDDPKG pvdd vdd {supply_pkg['l_vdd_H']}\nRVSSPKG diegnd pvss {supply_pkg['r_vss_ohm']}\nLVSSPKG pvss 0 {supply_pkg['l_vss_H']}"
    for key, val in case.get('rail_offsets_V', {}).items():
        n, v = rails[key]; rails[key] = (n, v + val)
    vectors=[('data','v(data)'),('out','v(out)'),('led_k','v(led_k)'),('led_voltage','v(led_a,led_k)'),
             ('iled_cond','i(VSENSE)'),('package_current','i(LPKG)')]
    if supply_pkg:vectors += [('die_vdd_voltage','v(vdd)'),('die_vss_voltage','v(diegnd)'),('supply_package_vdd_current','i(LVDDPKG)'),('supply_package_vss_current','i(LVSSPKG)')]
    vectors += [(n,f'v({n})') for n in nodes if n not in ['data','out']]
    vectors += [(k.lower()+'_voltage',f'v({n})') for k,(n,v) in rails.items()]
    vectors += [(k.lower()+'_current',f'i({k})') for k in rails]+[('data_current','i(VDATA)')]
    lg=legacy(work);st=lg.stimulus();ui=1/(case['rate_Gbps']*1e9);stop=len(st['bits'])*ui
    mode=case.get('data_mode','tracking')
    if mode not in ['fixed','tracking']: raise ValueError('unknown DATA mode')
    high=case.get('data_high_V',case['vdd_V'])
    vdata=str(case['dc_bit']*high) if 'dc_bit' in case else lg.pwl(st['bits'],ui,high,case['edge_s'])
    data_source='VDATA data 0 '+vdata
    if mode=='tracking' and case.get('rail_profiles',{}).get('VDD'):
        bit=str(case['dc_bit']) if 'dc_bit' in case else lg.pwl(st['bits'],ui,1.,case['edge_s'])
        data_source='VBIT bit 0 '+bit+'\nBTRACK data_track 0 V=v(bit)*v(vdd)\nVDATA data data_track 0'
    rail_lines=[]
    for key,(n,v) in rails.items():
        profile=case.get('rail_profiles',{}).get(key)
        expr=str(v) if not profile else supply_expression(v,profile,ui)
        rail_lines.append(key+' '+n+' 0 '+expr)
    control='op' if 'dc_bit' in case else f'tran {ui/80:.16g} {stop:.16g} 0 {ui/case["steps_per_ui"]:.16g}'
    if case.get('startup'):
        startup=case['startup']; stop=startup.get('stop_s',100e-6); step=startup.get('maxstep_s',10e-9)
        ramp=startup.get('ramp_s',1e-6); delay=startup.get('anchor_delay_s',0)
        if startup.get('kind','ramp')=='loadstep':
            data_source=f'VDATA data 0 PULSE(0 {high} 20u 20p 20p 20u 40u)'
            control=f'tran {step} {stop} 0 {step}'
        else:
            rail_lines=[]
            for key,(n,value) in rails.items():
                if key in startup.get('rail_pwl',{}):
                    points=' '.join(f'{t:.16g} {vv:.16g}' for t,vv in startup['rail_pwl'][key])
                    rail_lines.append(key+' '+n+' 0 PWL('+points+')')
                    continue
                if key=='VDISABLE':
                    release=startup.get('disable_release_s',20e-6); edge=startup.get('disable_edge_s',100e-9)
                    rail_lines.append(f'VDISABLE disable_source 0 PWL(0 3.3 {release} 3.3 {release+edge} 0)')
                    continue
                d=delay if key=='VREF' else 0
                points=f'0 0 {d} 0 {d+ramp} {value}' if d else f'0 0 {ramp} {value}'
                rail_lines.append(key+' '+n+' 0 PWL('+points+')')
            data_source=f'VDATA data 0 PWL(0 0 {ramp} {case.get("dc_bit",1)*high})'
            if startup.get('initial_op'):
                data_source=f'VDATA data 0 {case.get("dc_bit",1)*high}'
            control=f'tran {step} {stop} 0 {step}'+('' if startup.get('initial_op') else ' uic')
    paras=' WTAIL=5.76u' if case['variant']=='SNAP' else ''
    def resistance(name,nom):
        return nom*(1+case.get('resistor_errors',{}).get(name,0))*(1+case.get('resistor_tc_ppm',{}).get(name,0)*1e-6*(case['temp_C']-27))
    if definition.get('reference_v2'):
        external=f'''RVIN vin_source pvin {case.get('r_vin_ohm',.25)}
LVIN pvin vin {case.get('l_vin_H',.5e-9)}
RANCHOR ref_source vref {case.get('anchor_rout_ohm',.2)}
RDIVH vref vset {resistance('RDIVH',200000)}
RDIVL vset 0 {resistance('RDIVL',50000)}
RIBIAS ipb 0 {resistance('RIBIAS',100000)}
RLBIAS lpb 0 {resistance('RLBIAS',100000)}
CICOMP in2 ictrl {case.get('ccomp_F',3e-12)}
CLCOMP ln2 lctrl {case.get('ldo_ccomp_F',case.get('ccomp_F',3e-12))}
RSET sense rsetmon {resistance('RSET',20000)}
VRSETMON rsetmon 0 0
RFBH vreg regfb {resistance('RFBH',56000)}
RFBL regfb 0 {resistance('RFBL',10000)}
RCAP vreg vcap {case.get('cout_esr_ohm',.2)}
COUT vcap 0 {case.get('cout_F',1e-8)}
RDUMMY_EXT vreg dummy {resistance('RDUMMY',28000)}'''
        if definition.get('direct_raw'):
            external=f'''RVIN vin_source pvin {case.get('r_vin_ohm',.25)}
LVIN pvin vin {case.get('l_vin_H',.5e-9)}
RANCHOR ref_source vref {case.get('anchor_rout_ohm',.2)}
RDIVH vref vset {resistance('RDIVH',200000)}
RDIVL vset 0 {resistance('RDIVL',50000)}
RIBIAS ipb 0 {resistance('RIBIAS',100000)}
CICOMP in2 {('0' if case.get('compensation','shunt')=='shunt' else 'ictrl')} {case.get('vi_comp_F',15e-12)}
RSET sense rsetmon {resistance('RSET',20000)}
VRSETMON rsetmon 0 0
RCAP vin vcap {case.get('cout_esr_ohm',.2)}
CIN vcap 0 {case.get('cout_F',100e-9)}
RDUMMY_EXT vin dummy {resistance('RDUMMY',definition.get('rdummy_ohm',50000))}'''
            if case.get('comp_package'):
                package=case['comp_package']
                external=external.replace('CICOMP in2 ','CICOMP comp_cap ')
                external+=f'\nRCOMPPIN in2 comp_pin {package["r_ohm"]}\nLCOMPPIN comp_pin comp_esr {package["l_H"]}\nRCOMPESR comp_esr comp_cap {package["esr_ohm"]}'
        if definition.get('disable_clamp'):
            external += f'\nRGPIO disable_source disable {case.get("gpio_rout_ohm",100)}\nRKEEP out {"kret" if definition.get("switched_keeper") else "0"} {resistance("RKEEP",case.get("keeper_ohm",definition.get("keeper_ohm",1e7)))}'
        vectors += [('iset_current','i(VRSETMON)'),(('dummy_supply_voltage' if definition.get('direct_raw') else 'vreg_voltage'),('v(vin)' if definition.get('direct_raw') else 'v(vreg)')),('vset_voltage','v(vset)'),('vin_die_voltage','v(vin)')]
    else:
        external=('RREF_EXT '+definition.get('rref_source','vdd')+' bias '+str(resistance('RREF',definition.get('rref_ohm',88386.1064910889)))+'\nRDUMMY_EXT vdummy dummy '+str(resistance('RDUMMY',28000))) if 'bias' in ports and 'dummy' in ports else ''
    # Only observed MOS-terminal and source vectors are saved; no signal/PG/body
    # projection or de-duplication of electrically distinct nodes is performed.
    deck=f'''Frozen NRZ PEX comparison {case['name']}
.include "{frozen/'pdk/design.ngspice'}"
.param sw_stat_global=0 sw_stat_mismatch=0
.lib "{frozen/'pdk/sm141064.ngspice'}" {case['corner']}
.lib "{frozen/'pdk/sm141064.ngspice'}" res_{case.get('res_corner',case['corner'] if case['corner'] in ['ss','ff'] else 'typical')}
.temp {case['temp_C']}
.include "{core}"
.include "{frozen/'led.spice'}"
{chr(10).join(rail_lines)}
{data_source}
{supply_package_lines}
XDRV {' '.join(portmap[n] for n in ports)} {sub}{paras}
{external}
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
wrdata waveform.dat {' '.join(v for _,v in vectors)}
quit
.endc
.end
'''
    return deck,vectors,devices,rails

def supply_expression(base, profile, ui):
    kind=profile['kind']; amplitude=profile['amplitude_V']
    if kind=='sine':
        return f"SIN({base:.16g} {amplitude:.16g} {profile['frequency_Hz']:.16g} 0 0 {profile.get('phase_deg',0)})"
    if kind=='pulse':
        return f"PULSE({base:.16g} {base+amplitude:.16g} {profile.get('delay_ui',300)*ui:.16g} {profile.get('edge_ui',1)*ui:.16g} {profile.get('edge_ui',1)*ui:.16g} {profile.get('width_ui',32)*ui:.16g} {profile.get('period_ui',127)*ui:.16g})"
    raise ValueError('unsupported supply profile')

def compress_new(raw):
    """Archive this newly generated trace, verify original bytes before unlink."""
    initial=sha(raw);gz=raw.with_suffix(raw.suffix+'.gz')
    with raw.open('rb') as src,gzip.open(gz,'wb',compresslevel=6) as dst:shutil.copyfileobj(src,dst)
    h=hashlib.sha256()
    with gzip.open(gz,'rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    if initial!=h.hexdigest():raise AssertionError('gzip round trip differs')
    before=raw.stat().st_size;raw.unlink()
    return {'waveform':rel(gz),'waveform_sha256':sha(gz),'uncompressed_sha256':initial,
            'uncompressed_bytes':before,'compressed_bytes':gz.stat().st_size,'roundtrip_verified':True}

def current_bytes():
    return sum(p.stat().st_size for p in BUILD.rglob('*') if p.is_file() and not p.is_symlink())

def run_case(work,case,timeout=240):
    folder=work/'cases'/case['name'];folder.mkdir(parents=True,exist_ok=True);cached=folder/'result.json'
    if cached.exists():
        old=json.loads(cached.read_text())
        if not old.get('input_identity'):raise ValueError('Legacy cached result lacks original input identity; use read-only audit or a new run')
        for source,expected in old['input_identity'].items():
            if sha(work/'inputs'/source)!=expected:raise ValueError('Cached included input changed: '+source)
        if old.get('stimulus_sha256')!=sha(work/'stimulus.json'):raise ValueError('Cached stimulus changed')
        definition=json.loads((work/'manifest.json').read_text())['variants'][case['route']][case['variant']]
        dh=hashlib.sha256(json.dumps(definition,sort_keys=True).encode()).hexdigest()
        if old.get('candidate_definition_sha256') and old['candidate_definition_sha256']!=dh:raise ValueError('Cached candidate definition identity changed')
        proposed=build_deck(work,case)[0]
        if old['case']!=case or old.get('deck_sha256')!=hashlib.sha256(proposed.encode()).hexdigest():
            raise ValueError('Cached case identity changed; use a new immutable run/label')
        return old
    source_hash=RUNNER_SOURCE_SHA256
    source_copy=work/'execution-sources'/f'{source_hash}.py'
    if not source_copy.exists():
        source_copy.parent.mkdir(parents=True,exist_ok=True);source_copy.write_bytes(RUNNER_SOURCE_BYTES)
    start=time.monotonic();result={'case':case,'simulation_ok':False,'exit_code':None,
                                  'runner_source':rel(source_copy),'runner_source_sha256':source_hash}
    raw=folder/'waveform.dat'
    try:
        used=current_bytes()
        if used>MAX_INCREMENTAL_BYTES or shutil.disk_usage(ROOT).free<5*1024**3:
            raise RuntimeError('storage budget guard: no simulation started')
        deck,vectors,devices,rails=build_deck(work,case)
        m=json.loads((work/'manifest.json').read_text());definition=m['variants'][case['route']][case['variant']]
        core=work/'inputs'/definition['path'];ports=parse_core(core)[1]
        result['passives']=[p|{'nodes':[(('diegnd' if case.get('supply_package') else '0') if n=='vss' else n) if n in ports else 'xdrv.'+n for n in p['nodes']]} for p in parse_passives(core)]
        result['candidate_definition']=definition
        result['candidate_definition_sha256']=hashlib.sha256(json.dumps(definition,sort_keys=True).encode()).hexdigest()
        result['input_identity']={k:sha(work/'inputs'/k) for k in ['legacy/run.py','legacy/metrics.py','legacy/analyze.py','led.spice','pdk/design.ngspice','pdk/sm141064.ngspice']}
        result['stimulus_sha256']=sha(work/'stimulus.json')
        (folder/'testbench.spice').write_text(deck);emit(folder/'case.json',case)
        for name in ['design.ngspice','sm141064.ngspice']:
            link=folder/name
            if not link.exists():link.symlink_to(work/'inputs/pdk'/name)
        with open('/tmp/open-microled-nrz-ngspice.lock','a') as lock, (folder/'ngspice.log').open('w') as log:
            fcntl.flock(lock,fcntl.LOCK_EX)
            start=time.monotonic()
            proc=subprocess.Popen(['ngspice','-b','testbench.spice'],cwd=folder,stdout=log,stderr=subprocess.STDOUT)
            reason=None
            while proc.poll() is None:
                if time.monotonic()-start>timeout:reason='runtime budget timeout'
                if raw.exists() and raw.stat().st_size>1600*1024**2:reason='single raw trace storage guard'
                if reason:
                    proc.terminate()
                    try:proc.wait(5)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()
                    break
                time.sleep(.25)
        output=(folder/'ngspice.log').read_text();result['exit_code']=proc.returncode
        result.update({'deck_sha256':sha(folder/'testbench.spice'),'log':rel(folder/'ngspice.log'),
                       'log_sha256':sha(folder/'ngspice.log'),'vectors':{k:i+1 for i,(k,v) in enumerate(vectors)},
                       'devices':devices,'rails':{k:{'node':n,'voltage_V':v} for k,(n,v) in rails.items()}})
        if reason:raise RuntimeError(reason)
        if proc.returncode or re.search(r'(?im)^Error:|timestep too small|simulation interrupted|fatal error',output):
            raise RuntimeError('ngspice failure (see retained log)')
        a=np.atleast_2d(np.loadtxt(raw,skiprows=1))
        if a.shape[1]!=len(vectors)+1 or not np.isfinite(a).all():raise ValueError('invalid or nonfinite trace')
        if 'dc_bit' not in case or case.get('startup'):
            if not np.all(np.diff(a[:,0])>0):raise ValueError('non-increasing time; no silent repair')
            stop=case['startup'].get('stop_s',100e-6) if case.get('startup') else len(legacy(work).stimulus()['bits'])/(case['rate_Gbps']*1e9)
            if not np.isclose(a[-1,0],stop,rtol=1e-10,atol=1e-18):raise ValueError('incomplete transient')
        result.update({'simulation_ok':True,'rows':len(a),
                       'warnings':[s for s in output.splitlines() if 'warning' in s.lower()]})
        if 'dc_bit' in case:result['dc_values']={k:float(a[-1,i+1]) for i,(k,v) in enumerate(vectors)}
        del a
    except Exception as exc:
        result['error']=f'{type(exc).__name__}: {exc}'
        (folder/'pipeline-error.log').write_text(traceback.format_exc())
    finally:
        if raw.exists() and raw.stat().st_size:
            try:result.update(compress_new(raw))
            except Exception as exc:
                result['simulation_ok']=False;result['archive_error']=str(exc)
        result['elapsed_s']=time.monotonic()-start;emit(cached,result)
    return result
