#!/usr/bin/env python3
"""Frozen before/after layout regression. Never modifies old NRZ evidence."""
from pathlib import Path
import argparse,json,shutil,datetime,subprocess
import explore as e
r=e.r;ROOT=e.ROOT;OLD=e.BASE
CONDITIONS=[('nominal','typical',27,3.3),('slow_hot','ss',125,3.0),('fast_cold','ff',-40,3.6)]

def freeze(work,physical):
    if (work/'manifest.json').exists():raise ValueError('Freeze target already exists')
    e.create(work);m=json.loads((work/'manifest.json').read_text());m['created']=datetime.datetime.now().isoformat();m['physical_work']=r.rel(physical)
    m['variants']={'A':{},'B':{}};m['physical_contract']={};m['source_hashes']={}
    for route in 'AB':
        old=json.loads((OLD/'manifest.json').read_text())['variants'][route]['RC']
        for var,src in [('BEFORE',OLD/'inputs'/old['path']),('AFTER',next((physical/route/'full-rc').glob('*_rc.spice'))),('GEOM',physical/route/'geometry-only.spice'),('C',physical/route/'capacitance-only.spice')]:
            dst=work/'inputs/physical'/f'{route}-{var}.spice';dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
            sub,ports,mos=r.parse_core(dst)
            m['variants'][route][var]={'path':str(dst.relative_to(work/'inputs')),'sha256':r.sha(dst),'subckt':sub,'ports':ports,'source':r.rel(src),'rref_source':'vdummy' if route=='B' and var!='BEFORE' else 'vdd','rref_ohm':88386.1064910889}
        src=physical/route/'physical-contract.json';dst=work/'inputs/physical'/f'{route}-contract.json';shutil.copy2(src,dst);m['physical_contract'][route]=json.loads(src.read_text())
    for src in Path(__file__).parent.glob('*.py'):
        dst=work/'inputs/pipeline'/src.name;dst.parent.mkdir(exist_ok=True);shutil.copy2(src,dst)
    m['source_hashes']={str(p.relative_to(work/'inputs')):r.sha(p) for p in (work/'inputs').rglob('*') if p.is_file()}
    m['stimulus_sha256']=r.sha(work/'stimulus.json');m['no_retune_after_pex']=True
    m['resistor_corners']='res_typical/ss/ff paired with MOS typical/ss/ff; selected joint corners, not independent exhaustive resistor corner verification'
    m['evidence_boundary']='Partial-core extracted electrical simulations with static fitted LED and assumed dynamic optical/RX proxy. No optical BER or full-chip/foundry signoff.'
    m['ngspice_version']=subprocess.check_output(['ngspice','--version'],text=True);r.emit(work/'manifest.json',m);r.emit(r.EVIDENCE/'latest-run.json',{'work':r.rel(work)})
    return work

def verify(work):
    m=json.loads((work/'manifest.json').read_text())
    for p,h in m['source_hashes'].items():
        if r.sha(work/'inputs'/p)!=h:raise ValueError('Frozen input drift '+p)
    if r.sha(work/'stimulus.json')!=m['stimulus_sha256']:raise ValueError('Stimulus drift')
    return m

def import_before(work,extra=None):
    count=0
    sources=[OLD]+[ROOT/p for p in (extra or [])]
    paths=[p for src in sources for p in sorted((src/'cases').glob('*/result.json'))]
    for path in paths:
        result=json.loads(path.read_text());case=result['case']
        if case.get('variant') not in ['RC','BEFORE'] or case['kind'] not in ['nominal','slow_hot','fast_cold']:continue
        olda=path.with_name('analysis.json');rec=json.loads(olda.read_text())
        c=case|{'variant':'BEFORE','name':case['name'].replace('RC-','BEFORE-',1)}
        folder=work/'cases'/c['name'];folder.mkdir(parents=True,exist_ok=True)
        if (folder/'result.json').exists():continue
        shutil.copy2(path.parent/'testbench.spice',folder/'testbench.spice')
        result=result|{'case':c,'reuse':{'original_result':r.rel(path),'original_result_sha256':r.sha(path),'original_analysis':r.rel(olda),'original_analysis_sha256':r.sha(olda),'rerun':False}}
        r.emit(folder/'result.json',result)
        # Numerical payload copied byte-for-byte in values from hash-pinned old
        # analysis; only labels and new evidence-path wrapper are added.
        a=e.r.module(work/'inputs/legacy/metrics.py','metrics');a=e.r.module(work/'inputs/legacy/analyze.py','legacy_analysis_reuse');a.ROOT=ROOT
        rec=rec|{'case':c,'reuse':result['reuse']};row=a.compact_row(rec)
        row.update({'variant':'BEFORE','result_json':r.rel(folder/'result.json'),'analysis_json':r.rel(folder/'analysis.json'),'combined_screen_passed':row['comparison_screen_passed'] and not row['above_3p63V_screen']})
        rec['row']=row;r.emit(folder/'analysis.json',rec);count+=1
    return count

def planned(work,stage,routes,variants):
    cases=[]
    for route in routes:
        for var in variants:
            if stage=='targets':
                rate=1 if route=='A' else .5
                for kind,corner,temp,vdd in CONDITIONS:
                    cases.append(r.case_spec(work,route,var,rate,kind=kind,corner=corner,temp_C=temp,vdd_V=vdd))
            elif stage=='grid':
                for kind,corner,temp,vdd in CONDITIONS:
                    for rate in r.RATES:cases.append(r.case_spec(work,route,var,rate,kind=kind,corner=corner,temp_C=temp,vdd_V=vdd))
            elif stage=='dc':
                for _,corner,temp,vdd in CONDITIONS:
                    for bit in [0,1]:cases.append(r.case_spec(work,route,var,1,kind='dc',corner=corner,temp_C=temp,vdd_V=vdd,dc_bit=bit))
            elif stage=='numerical':
                for kind,corner,temp,vdd in CONDITIONS:
                    rate=1 if route=='A' else .5
                    cases.append(r.case_spec(work,route,var,rate,kind='numerical_'+kind,corner=corner,temp_C=temp,vdd_V=vdd,steps_per_ui=80))
            elif stage=='integration':
                rate=1 if route=='A' else .5
                for _,corner,temp,vdd in [CONDITIONS[0],CONDITIONS[2]]:
                    cases.append(r.case_spec(work,route,var,rate,kind='integration_control',corner=corner,temp_C=temp,vdd_V=vdd,method='trap',steps_per_ui=200))
    return cases

def summarize(work):
    m=verify(work);records=[json.loads(p.read_text()) for p in sorted((work/'cases').glob('*/analysis.json'))];rows=[a['row'] for a in records]
    plans={c['name']:c for p in work.glob('planned-*.json') for c in json.loads(p.read_text())['cases']};found={r['name']:r for r in rows}
    missing=sorted(set(plans)-set(found));failed=[k for k,v in found.items() if not v['analysis_ok']]
    result={'schema_version':1,'work':r.rel(work),'manifest_sha256':r.sha(work/'manifest.json'),'common':m['common'],'variants':m['variants'],'physical_work':m['physical_work'],'physical_contract':m['physical_contract'],'evidence_boundary':m['evidence_boundary'],'rows':rows,'counts':{'total':len(rows),'DC':sum('dc_bit' in x for x in rows),'transient':sum('errors' in x for x in rows),'reused':sum('reuse' in x for x in records),'fresh':sum('reuse' not in x for x in records)},'completion':{'missing':missing,'failed':failed,'planned_count':len(plans),'all_planned_analyzed':not missing and not failed}}
    r.emit(work/'analysis.json',result|{'cases':records});result['analysis_json']=r.rel(work/'analysis.json');result['analysis_sha256']=r.sha(work/'analysis.json')
    r.emit(r.EVIDENCE/'summary.json',result)
    import csv
    with (r.EVIDENCE/'summary.csv').open('w',newline='') as f:
        fields=list(dict.fromkeys(k for row in rows for k in row));writer=csv.DictWriter(f,fields);writer.writeheader();writer.writerows(rows)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',default='build/highspeed-nrz-pvt/formal-poly58-r1');p.add_argument('--freeze');p.add_argument('--baseline-extension',action='append');p.add_argument('--stage',choices=['targets','grid','dc','numerical','integration','summary'],default='targets');p.add_argument('--routes',default='AB');p.add_argument('--variants',default='BEFORE,AFTER');a=p.parse_args();w=ROOT/a.work
    if a.freeze:freeze(w,ROOT/a.freeze);print('IMPORTED',import_before(w,a.baseline_extension),flush=True)
    verify(w)
    if a.stage!='summary':
        cases=planned(w,a.stage,a.routes,a.variants.split(','));r.emit(w/f'planned-{a.stage}-{a.routes}-{a.variants}.json',{'cases':cases})
        for c in cases:
            rp=w/'cases'/c['name']/'result.json'
            if rp.exists() and json.loads(rp.read_text()).get('reuse'):
                print(c['name']+' REUSED',flush=True);continue
            row=e.metrics(w,r.run_case(w,c));print(json.dumps({k:row.get(k) for k in ['name','simulation_ok','errors','threshold_margin_normalized','timing_min_margin_ui','max_abs_terminal_V','combined_screen_passed','LED_current_A','rail_plus_DATA_positive_draw_fJ_per_gross_bit']}),flush=True)
    print(json.dumps(summarize(w)['completion']),flush=True)
if __name__=='__main__':main()
