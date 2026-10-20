#!/usr/bin/env python3
"""Frozen NRZ schematic / geometry / PEX comparison; no retuning.

Only new build/highspeed-nrz-pex and evidence/highspeed-nrz-pex are written.
The historical electrical/receiver contract is imported without modification.
"""
from pathlib import Path
from datetime import datetime
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
import tempfile
import time
import traceback
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/highspeed-nrz-pex'
EVIDENCE=ROOT/'evidence/highspeed-nrz-pex'
BASE=ROOT/'build/highspeed-nrz/run-0xqxvspp'
RATES=[.1,.25,.5,1,2,4,8]
MAX_INCREMENTAL_BYTES=8*1024**3
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
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def physical_preflight(contract_path):
    raw=json.loads(contract_path.read_text())
    # Contract: {"routes":{"A":{"variants":{"GEOM":{"path":...,
    # "subckt":...,"ports":[...]}, "C":..., "RC":...}}, "B":...}}.
    for route in 'AB':
        for variant,c in raw['routes'][route]['variants'].items():
            path=(ROOT/c['path']).resolve()
            if not path.is_file():raise FileNotFoundError(path)
            if c.get('sha256') and sha(path)!=c['sha256']:raise ValueError(f'changed physical deck {path}')
            sub,ports,dev=parse_core(path)
            if sub!=c['subckt'].lower() or ports!=[x.lower() for x in c['ports']]:
                raise ValueError(f'physical contract port mismatch {route} {variant}')
            if len(dev)!=(6 if route=='A' else 9):raise ValueError(f'MOS count {route} {variant}')
    return raw

def preflight():
    old=json.loads((BASE/'manifest.json').read_text())
    files={}
    for f in ['analog/highspeed_nrz/voltage_driver.spice','analog/highspeed_nrz/steering_driver.spice',
              'analog/models/measured-led/lin2026-yellow20-dc.spice','scripts/highspeed_nrz/metrics.py']:
        h=sha(ROOT/f);files[f]={'sha256':h,'unchanged_since_baseline':h==old['inputs'][f]}
    if not all(v['unchanged_since_baseline'] for v in files.values()):raise ValueError('baseline source drift')
    out={'created':datetime.now().isoformat(),'baseline':rel(BASE),'files':files,
         'free_bytes':shutil.disk_usage(ROOT).free,'incremental_budget_bytes':MAX_INCREMENTAL_BYTES,
         'ngspice_version':subprocess.check_output(['ngspice','--version'],text=True),
         'common':old['common'],'route_a_rails':old['route_a_rails'],
         'plan':{'nominal_rates_Gbps':RATES,'threshold_A':62.5e-6,'retune_after_pex':False,
                 'baseline_waveforms':'referenced read-only, not copied or deleted',
                 'new_raw_storage':'losslessly gzipped with decompression SHA256 verification; no prior artifacts removed'}}
    emit(EVIDENCE/'preflight.json',out)
    return out

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
            if p[5].lower() not in ['nfet_03v3','pfet_03v3']:
                raise ValueError('Unsupported nested core/model: '+s)
            devices.append({'instance':p[0].lower(),'nodes':[n.lower() for n in p[1:5]],
                            'model':p[5].lower(),'sizing':' '.join(p[6:])})
    if not sub or not devices:raise ValueError('Missing core or MOS devices')
    return sub,ports,devices

def freeze(contract_path):
    pf=preflight();contract=physical_preflight(contract_path)
    BUILD.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='run-',dir=BUILD))
    old=json.loads((BASE/'manifest.json').read_text())
    frozen=work/'inputs';hashes={}
    sources={
        'legacy/run.py':BASE/'inputs/scripts/highspeed_nrz/run.py',
        'legacy/metrics.py':ROOT/'scripts/highspeed_nrz/metrics.py',
        'legacy/analyze.py':ROOT/'scripts/highspeed_nrz/analyze.py',
        'schematic/A.spice':BASE/'inputs/analog/highspeed_nrz/voltage_driver.spice',
        'schematic/B.spice':BASE/'inputs/analog/highspeed_nrz/steering_driver.spice',
        'led.spice':BASE/'inputs/analog/models/measured-led/lin2026-yellow20-dc.spice',
        'pdk/design.ngspice':BASE/'inputs/pdk/design.ngspice',
        'pdk/sm141064.ngspice':BASE/'inputs/pdk/sm141064.ngspice',
        'pdk/pdk-lock.json':ROOT/'analog/models/pdk-lock.json',
        'original-manifest.json':BASE/'manifest.json',
        'original-contract.json':contract_path,
    }
    for src in Path(__file__).parent.glob('*.py'):
        if src.name not in ['report.py','diagrams.py']:sources['pipeline/'+src.name]=src
    variants={}
    for route in 'AB':
        variants[route]={'SCHEM':{'path':f'schematic/{route}.spice','source':'frozen original'}}
        for label, path in contract['routes'][route].get('metadata_files',{}).items():
            sources[f'physical/{route}-{label}.json']=ROOT/path
        for variant,definition in contract['routes'][route]['variants'].items():
            dst=f'physical/{route}-{variant}.spice';sources[dst]=ROOT/definition['path']
            variants[route][variant]=definition|{'path':dst,'source_path':definition['path']}
    # An extra B quantization control keeps old junction estimates. It is not
    # folded into the main original-vs-extracted-geometry distinction.
    variants['B']['SNAP']={'path':'schematic/B.spice','source':'original with WTAIL=5.76u only'}
    for dst,src in sources.items():
        target=frozen/dst;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
        hashes[dst]={'source':rel(src),'sha256':sha(target)}
    shutil.copy2(BASE/'stimulus.json',work/'stimulus.json')
    manifest={'created':datetime.now().isoformat(),'baseline':rel(BASE),'inputs':hashes,
              'common':old['common'],'route_a_rails':old['route_a_rails'],'variants':variants,
              'physical_contract':contract,'preflight':pf,'ngspice_version':pf['ngspice_version'],
              'no_retune_after_pex':True,'receiver_metrics':'byte-frozen original modules imported unchanged',
              'storage_budget_bytes':MAX_INCREMENTAL_BYTES,
              'evidence_boundary':'partial-core extracted electrical simulation plus assumed optical/RX proxy; no optical BER or full-chip signoff'}
    emit(work/'manifest.json',manifest);emit(EVIDENCE/'latest-run.json',{'work':rel(work)})
    return work

def case_spec(work,route,variant,rate=1,**kwargs):
    c=legacy(work).case_spec(route,rate,**kwargs)
    c['variant']=variant;c['name']=variant+'-'+c['name']
    return c

def build_deck(work,case):
    m=json.loads((work/'manifest.json').read_text());frozen=work/'inputs'
    definition=m['variants'][case['route']][case['variant']]
    core=frozen/definition['path'];sub,ports,devices=parse_core(core)
    portmap={n:('0' if n=='vss' else n) for n in ports}
    def node(n):return portmap.get(n,'xdrv.'+n)
    nodes=sorted(set(node(n) for d in devices for n in d['nodes'])-{'0'})
    devices=[d|{'nodes':[node(n) for n in d['nodes']]} for d in devices]
    mapping_file=frozen/'physical'/f'{case["route"]}-contract.json'
    if case['variant'] in ['GEOM','C','RC'] and mapping_file.exists():
        mapping={d['extracted_instance'].lower():d for d in json.loads(mapping_file.read_text()).get('extracted_device_mapping',[])}
        devices=[d|({'original_instance':mapping[d['instance']]['original_instance'],
                     'extracted_D_S_swapped_from_original':mapping[d['instance']]['drain_source_swapped']}
                    if d['instance'] in mapping else {}) for d in devices]
    rails={'VLED':('led_a',5.),'VDD':('vdd',case['vdd_V'])}
    if case['route']=='A':
        rails.update({'VH':('vh',m['route_a_rails']['VH_V']),'VL':('vl',m['route_a_rails']['VL_V'])})
    else:rails['VDUMMY']=('vdummy',3.3)
    vectors=[('data','v(data)'),('out','v(out)'),('led_k','v(led_k)'),('led_voltage','v(led_a,led_k)'),
             ('iled_cond','i(VSENSE)'),('package_current','i(LPKG)')]
    vectors += [(n,f'v({n})') for n in nodes if n not in ['data','out']]
    vectors += [(k.lower()+'_current',f'i({k})') for k in rails]+[('data_current','i(VDATA)')]
    lg=legacy(work);st=lg.stimulus();ui=1/(case['rate_Gbps']*1e9);stop=len(st['bits'])*ui
    vdata=str(case['dc_bit']*case['vdd_V']) if 'dc_bit' in case else lg.pwl(st['bits'],ui,case['vdd_V'],case['edge_s'])
    control='op' if 'dc_bit' in case else f'tran {ui/80:.16g} {stop:.16g} 0 {ui/case["steps_per_ui"]:.16g}'
    paras=' WTAIL=5.76u' if case['variant']=='SNAP' else ''
    external='RREF_EXT vdd bias 88386.1064910889\nRDUMMY_EXT vdummy dummy 28k' if 'bias' in ports and 'dummy' in ports else ''
    # Only observed MOS-terminal and source vectors are saved; no signal/PG/body
    # projection or de-duplication of electrically distinct nodes is performed.
    deck=f'''Frozen NRZ PEX comparison {case['name']}
.include "{frozen/'pdk/design.ngspice'}"
.param sw_stat_global=0 sw_stat_mismatch=0
.lib "{frozen/'pdk/sm141064.ngspice'}" {case['corner']}
.temp {case['temp_C']}
.include "{core}"
.include "{frozen/'led.spice'}"
{chr(10).join(k+' '+n+' 0 '+str(v) for k,(n,v) in rails.items())}
VDATA data 0 {vdata}
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

def compress_new(raw):
    """Archive this newly generated trace, verify original bytes before unlink."""
    initial=sha(raw);gz=raw.with_suffix(raw.suffix+'.gz')
    with raw.open('rb') as src,gzip.open(gz,'wb',compresslevel=1) as dst:shutil.copyfileobj(src,dst)
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
    if cached.exists():return json.loads(cached.read_text())
    source_hash=RUNNER_SOURCE_SHA256
    source_copy=work/'execution-sources'/f'{source_hash}.py'
    if not source_copy.exists():
        source_copy.parent.mkdir(parents=True,exist_ok=True);source_copy.write_bytes(RUNNER_SOURCE_BYTES)
    start=time.monotonic();result={'case':case,'simulation_ok':False,'exit_code':None,
                                  'runner_source':rel(source_copy),'runner_source_sha256':source_hash}
    raw=folder/'waveform.dat'
    try:
        used=current_bytes()
        if used>MAX_INCREMENTAL_BYTES or shutil.disk_usage(ROOT).free<4*1024**3:
            raise RuntimeError('storage budget guard: no simulation started')
        deck,vectors,devices,rails=build_deck(work,case)
        (folder/'testbench.spice').write_text(deck);emit(folder/'case.json',case)
        for name in ['design.ngspice','sm141064.ngspice']:
            link=folder/name
            if not link.exists():link.symlink_to(work/'inputs/pdk'/name)
        with (folder/'ngspice.log').open('w') as log:
            proc=subprocess.Popen(['ngspice','-b','testbench.spice'],cwd=folder,stdout=log,stderr=subprocess.STDOUT)
            reason=None
            while proc.poll() is None:
                if time.monotonic()-start>timeout:reason='runtime budget timeout'
                if raw.exists() and raw.stat().st_size>1200*1024**2:reason='single raw trace storage guard'
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
        if 'dc_bit' not in case:
            if not np.all(np.diff(a[:,0])>0):raise ValueError('non-increasing time; no silent repair')
            stop=len(legacy(work).stimulus()['bits'])/(case['rate_Gbps']*1e9)
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

def import_baseline(work):
    imported=[]
    for path in sorted((BASE/'cases').glob('*/result.json')):
        original=json.loads(path.read_text());c=original['case']
        if c['kind'] not in ['dc','nominal','numerical','integration_control','slow_hot','fast_cold']:continue
        result=original.copy();c=c.copy();c['variant']='SCHEM';c['name']='SCHEM-'+c['name'];result['case']=c
        result['reuse']={'original_result':rel(path),'original_result_sha256':sha(path),'rerun':False}
        folder=work/'cases'/c['name'];folder.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path.parent/'testbench.spice',folder/'testbench.spice')
        emit(folder/'result.json',result);imported.append(c['name'])
    emit(work/'baseline-import.json',{'cases':imported,'raw_bytes_copied':0,'original_artifacts_modified':False})
    return imported

def case_list(work,stage,variants=None,routes='AB'):
    manifest=json.loads((work/'manifest.json').read_text());cases=[]
    if variants and 'RCLUMP' in variants:
        raise ValueError('RCLUMP is a cap_placement_control; use scripts/highspeed_nrz_pex/controls.py')
    for r in routes:
        modes=[v for v in manifest['variants'][r] if v not in ['SCHEM','RCLUMP'] and (variants is None or v in variants)]
        for v in modes:
            if v=='SNAP':
                if stage in ['smoke','dc']:cases += [case_spec(work,r,v,kind='dc',dc_bit=b) for b in [0,1]]
                elif stage=='nominal':cases += [case_spec(work,r,v,f) for f in RATES]
                continue
            if stage=='smoke':
                cases += [case_spec(work,r,v,kind='dc',dc_bit=b) for b in [0,1]]
                cases += [case_spec(work,r,v,1)]
            elif stage=='dc':
                for corner,temp,vdd in [('typical',27,3.3),('ss',27,3.3),('ff',27,3.3),('fs',27,3.3),('sf',27,3.3),
                                         ('typical',-40,3.3),('typical',125,3.3),('typical',27,3.0),('typical',27,3.6)]:
                    cases += [case_spec(work,r,v,kind='dc',dc_bit=b,corner=corner,temp_C=temp,vdd_V=vdd) for b in [0,1]]
            elif stage=='nominal':cases += [case_spec(work,r,v,f) for f in RATES]
            elif stage=='convergence':
                cases += [case_spec(work,r,v,f,kind='numerical',steps_per_ui=80) for f in [.5,1,2]]
                cases += [case_spec(work,r,v,1,kind='integration_control',method='trap',steps_per_ui=200)]
            elif stage=='pvt':
                for f in [.5,1,2]:
                    cases += [case_spec(work,r,v,f,kind='slow_hot',corner='ss',temp_C=125,vdd_V=3.0),
                              case_spec(work,r,v,f,kind='fast_cold',corner='ff',temp_C=-40,vdd_V=3.6)]
    return cases

def main():
    p=argparse.ArgumentParser();p.add_argument('--preflight',action='store_true');p.add_argument('--contract');p.add_argument('--work')
    p.add_argument('--stage',choices=['smoke','dc','nominal','convergence','pvt'],default='smoke')
    p.add_argument('--variants');p.add_argument('--routes',default='AB');p.add_argument('--timeout',type=float,default=240)
    args=p.parse_args()
    if args.preflight:print(json.dumps(preflight(),ensure_ascii=False,indent=2));return
    work=(ROOT/args.work).resolve() if args.work else freeze((ROOT/args.contract).resolve())
    if not args.work:import_baseline(work)
    print('WORK='+rel(work),flush=True)
    cases=case_list(work,args.stage,args.variants.split(',') if args.variants else None,args.routes)
    emit(work/f'planned-{args.stage}-{args.variants or "all"}-{args.routes}.json',{'cases':cases})
    results=[]
    for case in cases:
        hold_file=work/'hold-variants.json'
        if hold_file.exists() and case['variant'] in json.loads(hold_file.read_text()).get('variants',[]):
            print('HELD '+case['name']+' pending extraction review; no simulation started',flush=True)
            break
        result=run_case(work,case,args.timeout);results.append(result)
        print(case['name']+' '+('OK' if result['simulation_ok'] else 'FAILED '+result.get('error','')),flush=True)
    emit(work/f'run-{args.stage}-{args.variants or "all"}-{args.routes}.json',results)
    print(json.dumps({'completed':len(results),'failed':sum(not r['simulation_ok'] for r in results),'bytes':current_bytes()}),flush=True)

if __name__=='__main__':main()
