#!/usr/bin/env python3
"""Bounded independent supply, resistor and package stress; legacy RX stays frozen."""
from pathlib import Path
import argparse, csv, datetime, hashlib, json, shutil, subprocess, sys
import numpy as np
import run as r
ROOT=r.ROOT
BASE=ROOT/'build/highspeed-nrz-pvt/final-r4'
ANALYZER_BYTES=Path(__file__).read_bytes()
ANALYZER_SHA256=hashlib.sha256(ANALYZER_BYTES).hexdigest()

def freeze(work):
    if (work/'manifest.json').exists(): return verify(work)
    work.mkdir(parents=True,exist_ok=True)
    old=json.loads((BASE/'manifest.json').read_text()); m={k:old[k] for k in ['common','route_a_rails','physical_contract']}
    m.update({'variants':{q:{'AFTER':old['variants'][q]['AFTER']} for q in 'AB'},'created':datetime.datetime.now().isoformat(),'baseline':r.rel(BASE),'baseline_manifest_sha256':r.sha(BASE/'manifest.json')})
    files=['legacy/run.py','legacy/metrics.py','legacy/analyze.py','led.spice','pdk/design.ngspice','pdk/sm141064.ngspice']
    files += [f'physical/{q}-{s}' for q in 'AB' for s in ['AFTER.spice','contract.json']]
    for f in files:
        dst=work/'inputs'/f;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BASE/'inputs'/f,dst)
    shutil.copy2(BASE/'stimulus.json',work/'stimulus.json')
    for src in Path(__file__).parent.glob('*.py'):
        dst=work/'inputs/pipeline'/src.name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    m['source_hashes']={str(p.relative_to(work/'inputs')):r.sha(p) for p in (work/'inputs').rglob('*') if p.is_file()}
    m['stimulus_sha256']=r.sha(work/'stimulus.json');m['ngspice_version']=subprocess.check_output(['ngspice','--version'],text=True)
    m['scope']={'intrinsic_LED_and_RX':'Frozen LED static fit, CLED=200fF, optical tau200ps, RX1GHz threshold62.5uA and original PRBS sampler. No optical measurement or reliability signoff.', 'stress_screen_V':3.63,'data_fixed':'fixed 3.6V high for FF disturbance; low0V, unchanged20ps edge','data_tracking':'high follows actual VDD(t), low0V, unchanged20ps bit transition; behavioral source current sensed by VDATA and energy uses actual DATA voltage','energy':'all terminal supply voltages sampled, actual v(t)*i(t); DATA included. VBIT has zero load; BTRACK terminal energy counted once via series VDATA. No upstream generation losses.','matrix':'bounded one-factor and declared combined-corner stress, not exhaustive signoff','storage_budget_GiB':4}
    r.emit(work/'manifest.json',m); return m

def verify(work):
    m=json.loads((work/'manifest.json').read_text())
    for f,h in m['source_hashes'].items():
        if r.sha(work/'inputs'/f)!=h:raise ValueError('Frozen input drift '+f)
    if r.sha(work/'stimulus.json')!=m['stimulus_sha256']:raise ValueError('Stimulus drift')
    return m

def analyze(work,result,out_name="analysis.json"):
    path=work/'cases'/result['case']['name']/'result.json';out=path.with_name(out_name)
    analyzer_snapshot=work/'execution-sources'/('analysis-'+ANALYZER_SHA256+'.py')
    analyzer_snapshot.parent.mkdir(exist_ok=True)
    if not analyzer_snapshot.exists():analyzer_snapshot.write_bytes(ANALYZER_BYTES)
    ident={'analyzer_source':r.rel(analyzer_snapshot),'result_sha256':r.sha(path),'custom_analyzer_sha256':ANALYZER_SHA256,'legacy_metrics_sha256':r.sha(work/'inputs/legacy/metrics.py'),'legacy_analyze_sha256':r.sha(work/'inputs/legacy/analyze.py')}
    if out.exists():
        old=json.loads(out.read_text())
        if old['analysis_identity']!=ident: raise ValueError('Analysis identity changed')
        return old['row']
    mm=r.module(work/'inputs/legacy/metrics.py','metrics');a=r.module(work/'inputs/legacy/analyze.py','frozen_analyze');a.ROOT=ROOT
    rec={'case':result['case'],'simulation_ok':result['simulation_ok'],'analysis_ok':False,'analysis_identity':ident}
    if result['simulation_ok']:
        trace,sources=a.load_trace(result,path); rec['sources']=sources;rec['stress']=a.stress_metrics(trace,result)
        if 'dc_bit' in result['case']:rec['dc']=a.dc_metrics(trace,result)
        else:
            st=json.loads((work/'stimulus.json').read_text());tx=a.transient_metrics(trace,result,st)
            ui=1/(result['case']['rate_Gbps']*1e9);t=trace[:,0];v=result['vectors']; rails={}
            for name in result['rails']:
                voltage=trace[:,v[name.lower()+'_voltage']]
                rails[name]=mm.energy_window(t,voltage,trace[:,v[name.lower()+'_current']],st['validation_start_bit']*ui,st['validation_end_bit']*ui,len(st['validation_bits']))
                rails[name]['voltage_min_V']=float(voltage.min());rails[name]['voltage_max_V']=float(voltage.max())
            tx['energy']['rails']=rails;tx['energy']['rail_total']=a.sum_energy(rails);tx['energy']['rail_plus_ideal_DATA_total']=a.sum_energy(rails|{'ideal_DATA':tx['energy']['ideal_DATA']})
            tx['energy']['source_voltage_method']='actual sampled v(t) for every rail and DATA'
            rec['transient']=tx
        if result['case'].get('supply_package'):
            rec['supply_package_observed']={}
            for n in ['die_vdd_voltage','die_vss_voltage','vdd_voltage']:
                values=trace[:,result['vectors'][n]];rec['supply_package_observed'][n]={'min_V':float(values.min()),'max_V':float(values.max())}
            vd=trace[:,result['vectors']['die_vdd_voltage']]-trace[:,result['vectors']['die_vss_voltage']]
            rec['supply_package_observed']['die_differential_supply']={'min_V':float(vd.min()),'max_V':float(vd.max())}
        rec['analysis_ok']=True
    row=a.compact_row(rec); row.update({k:result['case'].get(k) for k in ['res_corner','data_mode','data_high_V','rail_offsets_V','rail_profiles','supply_package','variant','resistor_errors','resistor_tc_ppm','anchor_error','anchor_tc_ppm','anchor_rout_ohm','vin_V']})
    row.update({'result_json':r.rel(path),'analysis_json':r.rel(out)})
    if rec['analysis_ok']:
        row.update({'worst_instance':rec['stress']['worst_instance'],'worst_pair':rec['stress']['worst_pair'],'terminal_screen_margin_V':3.63-row['max_abs_terminal_V']})
        gate_records=[(dev,pair,dev['terminal_differences'][pair]) for dev in rec['stress']['all_devices'] for pair in ['VGS','VGD','VGB']]
        gd,gp,gv=max(gate_records,key=lambda z:z[2]['max_abs_V'])
        row.update({'max_abs_gate_pair_V':gv['max_abs_V'],'worst_gate_instance':gd['instance'],'worst_gate_pair':gp})
        device_limits=[]
        for dev in rec['stress']['all_devices']:
            limit=6.0 if '06v0' in dev['model'] else 3.63
            device_limits.append({'instance':dev['instance'],'model':dev['model'],'limit_V':limit,'max_abs_terminal_V':dev['max_abs_terminal_V'],'margin_V':limit-dev['max_abs_terminal_V'],'passed':dev['max_abs_terminal_V']<=limit})
        rec['device_specific_screen']={'definition':'03v3 all-six-pair3.63V; 06v0 all-six-pair6.0V conservative project screen motivated by public DC gate limits; not reliability signoff','devices':device_limits,'passed':all(d['passed'] for d in device_limits)}
        row['device_specific_screen_passed']=rec['device_specific_screen']['passed']
        row['minimum_device_specific_margin_V']=min(d['margin_V'] for d in device_limits)
        row['combined_screen_passed']=row['device_specific_screen_passed'] and row.get('comparison_screen_passed',True)
        if 'iset_current' in result['vectors']:
            rec['reference_observed']={n:{'min':float(trace[:,result['vectors'][n]].min()),'max':float(trace[:,result['vectors'][n]].max()),'mean':float(trace[:,result['vectors'][n]].mean())} for n in ['iset_current','vreg_voltage','dummy_supply_voltage','vset_voltage','vin_die_voltage'] if n in result['vectors']}
            row['reference_observed']=rec['reference_observed']
    rec['row']=row;r.emit(out,rec); return row

def case(work,route,label,corner='ff',temp=-40,vdd=3.6,**kw):
    c=r.case_spec(work,route,kw.pop('variant','AFTER'),1 if route=='A' else .5,kind=label,corner=corner,temp_C=temp,vdd_V=vdd,**kw)
    c.setdefault('res_corner','typical' if corner=='typical' else corner); c.setdefault('data_mode','tracking'); c.setdefault('data_high_V',vdd)
    return c

def plan(work,stage,routes):
    cs=[]
    for q in routes:
        if stage=='minimal':
            for mode in ['tracking','fixed']:cs.append(case(work,q,'FFplus50_'+mode,vdd=3.65,data_mode=mode,data_high_V=3.6 if mode=='fixed' else 3.65))
        elif stage=='baseline':
            for label,corner,temp,vdd in [('TT','typical',27,3.3),('SS','ss',125,3.),('FF','ff',-40,3.6)]:cs.append(case(work,q,label,corner,temp,vdd))
        elif stage=='resistor':
            for label,corner,temp,vdd in [('SS','ss',125,3.),('FF','ff',-40,3.6)]:
                for rc in ['typical','ss','ff']:
                    if rc==corner:continue
                    cs.append(case(work,q,label+'_res_'+rc,corner,temp,vdd,res_corner=rc))
        elif stage=='supply':
            for offset in [-.05,-.025,.025]:cs.append(case(work,q,'FFvdd_'+str(offset),vdd=3.6+offset))
            for offset in [-.05,.05]:cs.append(case(work,q,'VLED_'+str(offset),rail_offsets_V={'VLED':offset}))
            for offset in [-.05,.05]:
                rails={'VH':offset,'VL':offset} if q=='A' else {'VDUMMY':offset}
                cs.append(case(work,q,'aux_'+str(offset),rail_offsets_V=rails))
        elif stage=='dynamic':
            pulse={'kind':'pulse','amplitude_V':.05,'delay_ui':300,'edge_ui':1,'width_ui':32,'period_ui':127}
            sine={'kind':'sine','amplitude_V':.05,'frequency_Hz':10e6}
            for mode in ['fixed','tracking']:cs.append(case(work,q,'VDDpulse_'+mode,rail_profiles={'VDD':pulse},data_mode=mode,data_high_V=3.6))
            cs.append(case(work,q,'aux_ripple',rail_profiles={k:sine for k in (['VLED','VH','VL'] if q=='A' else ['VLED','VDUMMY'])}))
        elif stage=='package':
            for resistance,inductance in [(.25,.1),(1.,2.),(4.,.5),(4.,2.)]:cs.append(case(work,q,f'pkg_R{resistance:g}_L{inductance:g}',r_pkg=resistance,l_pkg=inductance*1e-9))
        else:raise ValueError('unknown stage')
    return cs

def summarize(work):
    m=verify(work); paths=sorted((work/'cases').glob('*/analysis.json'));paths=[p.with_name('analysis-verified.json') if p.with_name('analysis-verified.json').exists() else p for p in paths];rows=[json.loads(p.read_text())['row'] for p in paths]
    amendment=json.loads((work/'selection-amendment.json').read_text()) if (work/'selection-amendment.json').exists() else {}
    superseded=amendment.get('superseded_plan_files',[])
    plans=[c for p in work.glob('plan-*.json') if p.name not in superseded for c in json.loads(p.read_text())['cases']];done={x['name'] for x in rows}
    administrative=[json.loads(p.read_text())['case']['name'] for p in (work/'cases').glob('*/result.json') if (lambda z:z.get('exit_code') is None and not z.get('error'))(json.loads(p.read_text()))]
    summary={'work':r.rel(work),'manifest_sha256':r.sha(work/'manifest.json'),'scope':m['scope'],'rows':rows,'count':len(rows),'missing':sorted({c['name'] for c in plans if c['name'] not in done and c['name'] not in administrative}),'superseded_plan_files':superseded,'administrative_interrupted_cases':administrative,'failed_simulations':[x['name'] for x in rows if not x['analysis_ok'] and x['name'] not in administrative],'screen_failures':[x['name'] for x in rows if x.get('combined_screen_passed') is False]}
    results=[json.loads(p.read_text()) for p in (work/'cases').glob('*/result.json')]
    effective_names={c['name'] for c in plans}-set(administrative)
    successful_names={x['case']['name'] for x in results if x.get('simulation_ok')}
    analysis_failed=sorted(n for n in successful_names if n not in done or not next((x['analysis_ok'] for x in rows if x['name']==n),False))
    sim_failed=sorted(x['case']['name'] for x in results if not x.get('simulation_ok') and x['case']['name'] not in administrative)
    summary['failed_simulations']=sim_failed
    summary['coverage']={'effective_planned_cases':len(effective_names),'effective_analyzed_cases':len(effective_names & done),'missing':sorted(effective_names-done),'excluded_administrative_cases':len(administrative),'superseded_plan_files':superseded}
    summary['validation_counts']={'successful_simulations':len(successful_names),'simulation_failures':len(sim_failed),'analysis_failures':len(analysis_failed),'functional_screen_failures':sum(x.get('comparison_screen_passed') is False for x in rows),'device_screen_failures':sum(x.get('device_specific_screen_passed') is False for x in rows),'combined_screen_failures':sum(x.get('combined_screen_passed') is False for x in rows),'administrative_interruptions':len(administrative)}
    summary['analysis_failures']=analysis_failed
    summary['scope_clarifications']={'identity_audit':'An all_checks_passed identity audit does not assert functional/device pass.', 'legacy_stress_screen_V':'Manifest inherited3.63V is historical03v3 uniform metric; read actual analysis.device_specific_screen per MOS:03v3 3.63V and06v0 conservative6.0V. Gate-specific limits remain distinguished from full reliability.', 'DATA':'Use actual case.data_mode/data_high_V/rail_profiles and sampled waveform; inheritedfixed3.6V description describes initialbaselineFF control, not everyfinalcase.', 'DC':'combined_screen_passed onDC is device voltage screening only; compare current to threshold separately, not transientRX pass.', 'resistor_corners':'Only PDKpolyRIN corner changes; ideal externalB RREF88.386106k and RDUMMY28k tolerances not covered.'}
    r.emit(work/'summary.json',summary);r.emit(r.EVIDENCE/(work.name+'-summary.json'),summary)
    return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',default='build/highspeed-nrz-robustness/baseline-r1');p.add_argument('--stage',choices=['minimal','baseline','resistor','supply','dynamic','package','summary'],default='minimal');p.add_argument('--routes',default='AB');p.add_argument('--freeze',action='store_true');args=p.parse_args();work=ROOT/args.work
    if args.freeze:freeze(work)
    verify(work)
    if args.stage!='summary':
        cs=plan(work,args.stage,args.routes);r.emit(work/f'plan-{args.stage}-{args.routes}.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs})
        for c in cs:
            row=analyze(work,r.run_case(work,c));print(json.dumps(row),flush=True)
    print(json.dumps({k:v for k,v in summarize(work).items() if k not in ['rows','scope']}),flush=True)
if __name__=='__main__':main()
