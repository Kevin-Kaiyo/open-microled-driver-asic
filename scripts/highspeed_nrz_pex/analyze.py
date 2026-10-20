#!/usr/bin/env python3
"""Apply the byte-frozen original NRZ metrics to actual local PEX MOS terminals."""
from pathlib import Path
import argparse
import csv
import json
import math
import shutil
import sys
import numpy as np
from run import ROOT,EVIDENCE,BASE,RATES,sha,rel,emit,module

def load_metrics(work):
    module(work/'inputs/legacy/metrics.py','metrics')
    a=module(work/'inputs/legacy/analyze.py','frozen_nrz_analysis')
    a.ROOT=ROOT
    return a

def analyze(work):
    m=json.loads((work/'manifest.json').read_text())
    st=json.loads((work/'stimulus.json').read_text());a=load_metrics(work)
    wrapper_hash=sha(Path(__file__))
    wrapper_source=work/'analysis-sources'/f'{wrapper_hash}.py'
    if not wrapper_source.exists():
        wrapper_source.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(Path(__file__),wrapper_source)
    identity={'analyzer_sha256':wrapper_hash,'analyzer_source':rel(wrapper_source),'frozen_analyzer_sha256':sha(work/'inputs/legacy/analyze.py'),
              'frozen_metrics_sha256':sha(work/'inputs/legacy/metrics.py'),
              'manifest_sha256':sha(work/'manifest.json'),'stimulus_sha256':sha(work/'stimulus.json')}
    records=[]
    for path in sorted((work/'cases').glob('*/result.json')):
        result=json.loads(path.read_text());cache=path.with_name('analysis.json');rh=sha(path)
        rec=None
        if cache.exists():
            old=json.loads(cache.read_text())
            # Per-case numbers are computed exclusively by these byte-frozen
            # modules from result.json + trace + stimulus. Report/coverage/link
            # changes do not require recalculating the same numerical record.
            engine_keys=['frozen_analyzer_sha256','frozen_metrics_sha256','stimulus_sha256']
            old_identity=old.get('analysis_identity',{})
            if old.get('result_sha256')==rh and all(old_identity.get(k)==identity[k] for k in engine_keys):
                rec=old
        if rec is None:
            rec={'case':result['case'],'simulation_ok':result['simulation_ok'],'analysis_ok':False,
                 'result_sha256':rh,'analysis_identity':identity,'simulation_warnings':result.get('warnings',[])}
            if not result['simulation_ok']:rec['simulation_failure']=result
            else:
                try:
                    trace,sources=a.load_trace(result,path)
                    rec['sources']=sources;rec['stress']=a.stress_metrics(trace,result)
                    if 'dc_bit' in result['case']:rec['dc']=a.dc_metrics(trace,result)
                    else:rec['transient']=a.transient_metrics(trace,result,st)
                    rec['analysis_ok']=True
                    del trace
                except Exception as exc:rec['analysis_error']=f'{type(exc).__name__}: {exc}'
            emit(cache,rec)
        records.append(rec)
        print(rec['case']['name']+' '+('ANALYZED' if rec['analysis_ok'] else 'FAILED'),flush=True)
    rows=[]
    for rec in records:
        r=a.compact_row(rec)
        r['variant']=rec['case']['variant']
        r['result_json']=rel(work/'cases'/rec['case']['name']/'result.json')
        r['analysis_json']=rel(work/'cases'/rec['case']['name']/'analysis.json')
        r['waveform']=rec.get('sources',{}).get('waveform')
        # Reused traces keep their original immutable log location.
        r['log']=json.loads((ROOT/r['result_json']).read_text()).get('log')
        rows.append(r)
    counts={'case_results_found':len(records),'simulation_failures':sum(not r['simulation_ok'] for r in records),
            'analysis_failures':sum(r['simulation_ok'] and not r['analysis_ok'] for r in records),
            'analyzed_DC':sum(r['analysis_ok'] and 'dc' in r for r in records),
            'analyzed_transient':sum(r['analysis_ok'] and 'transient' in r for r in records)}
    planned={}
    for path in sorted(work.glob('planned-*.json')):
        for case in json.loads(path.read_text()).get('cases',[]):planned[case['name']]=case
    found={r['case']['name']:r for r in records}
    missing_planned=sorted(set(planned)-set(found))
    incomplete_planned=sorted(n for n in planned if n in found and not found[n]['analysis_ok'])
    nominal_coverage=[]
    for route in 'AB':
        for variant in m['variants'][route]:
            if variant=='RCLUMP':continue
            successes=sorted(r['rate_Gbps'] for r in rows if r['route']==route and r['variant']==variant
                and r['kind']=='nominal' and r['analysis_ok'])
            nominal_coverage.append({'route':route,'variant':variant,'expected_rates_Gbps':RATES,
                'successful_rates_Gbps':successes,'missing_rates_Gbps':sorted(set(RATES)-set(successes)),
                'complete':successes==RATES})
    placement_coverage=[]
    for route in 'AB':
        if 'RCLUMP' not in m['variants'][route]:continue
        got=sorted(r['rate_Gbps'] for r in rows if r['route']==route and r['variant']=='RCLUMP'
            and r['kind']=='cap_placement_control' and r['analysis_ok'])
        placement_coverage.append({'route':route,'expected_rates_Gbps':[.5,1,2],
                                  'successful_rates_Gbps':got,'complete':got==[.5,1,2]})
    hold=json.loads((work/'hold-variants.json').read_text()) if (work/'hold-variants.json').exists() else None
    completion={'status':'held_pending_review' if hold else 'incomplete' if missing_planned or incomplete_planned or
                not all(c['complete'] for c in nominal_coverage+placement_coverage) else 'declared_case_lists_complete',
                'scope':'declared simulation case lists and nominal grid only; not physical/optical/product qualification',
                'planned_cases':len(planned),'missing_planned_cases':missing_planned,
                'failed_or_unanalyzed_planned_cases':incomplete_planned,'nominal_coverage':nominal_coverage,
                'cap_placement_coverage':placement_coverage,'hold':hold}
    counts.update({'planned_cases':len(planned),'missing_planned_cases':len(missing_planned),
                   'failed_or_unanalyzed_planned_cases':len(incomplete_planned),
                   'nominal_grid_complete':all(c['complete'] for c in nominal_coverage)})
    groups={}
    for r in rows:
        g=groups.setdefault(r['route']+'/'+r['variant'],{'DC_ok':0,'transient_ok':0,'failed':0})
        g['DC_ok' if r['analysis_ok'] and 'dc_bit' in r else 'transient_ok' if r['analysis_ok'] else 'failed']+=1
    original=json.loads((ROOT/'evidence/highspeed-nrz/summary.json').read_text())
    orig={r['name']:r for r in original['rows']}
    reuse_checks=[]
    for r in rows:
        if r['variant']!='SCHEM' or not r['analysis_ok']:continue
        prior=orig[r['name'][6:]]
        keys=['LED_current_A','max_abs_terminal_V','errors','threshold_margin_normalized',
              'rail_plus_DATA_positive_draw_fJ_per_gross_bit','timing_min_margin_ui']
        deltas={k:r[k]-prior[k] for k in keys if k in r and k in prior}
        reuse_checks.append({'name':r['name'],'absolute_deltas':deltas,
                             'same_metrics':all(abs(v)<1e-10 for v in deltas.values())})
    # Unretuned nominal deltas from both the historical circuit and the
    # extracted-geometry control are kept; failed cases never become zero.
    comparisons=[]
    for r in rows:
        if r['kind'] not in ['nominal','cap_placement_control'] or r['variant']=='SCHEM':continue
        entry={'route':r['route'],'variant':r['variant'],'rate_Gbps':r['rate_Gbps'],
               'kind':r['kind'],'available':r['analysis_ok'],'deltas':{}}
        for reference in ['SCHEM','GEOM','RC']:
            candidates=[b for b in rows if b['route']==r['route'] and b['variant']==reference and
                        b['kind']=='nominal' and b['rate_Gbps']==r['rate_Gbps'] and b['analysis_ok']]
            if not r['analysis_ok'] or not candidates:continue
            b=candidates[0];delta={}
            for k in ['errors','eye_normalized','threshold_margin_normalized','timing_min_margin_ui',
                      'sample_delay_ui','max_abs_terminal_V','rail_plus_DATA_positive_draw_fJ_per_gross_bit',
                      'rail_net_fJ_per_gross_bit','rail_returned_fJ_per_gross_bit','LED_mean_current_A']:
                if k in b and k in r:delta[k]=r[k]-b[k]
            energy='rail_plus_DATA_positive_draw_fJ_per_gross_bit'
            delta['all_source_positive_energy_change_percent']=100*(r[energy]-b[energy])/b[energy]
            delta['screen_changed']=r['comparison_screen_passed']!=b['comparison_screen_passed']
            entry['deltas'][reference]=delta
        comparisons.append(entry)
    convergence=[]
    for r in rows:
        if r['kind'] not in ['numerical','integration_control']:continue
        b=next((x for x in rows if x['route']==r['route'] and x['variant']==r['variant'] and
                x['kind']=='nominal' and x['rate_Gbps']==r['rate_Gbps'] and x['analysis_ok']),None)
        e={'route':r['route'],'variant':r['variant'],'rate_Gbps':r['rate_Gbps'],
           'control':r['kind'],'available':bool(b and r['analysis_ok'])}
        if e['available']:
            k='rail_plus_DATA_positive_draw_fJ_per_gross_bit'
            e.update({'energy_change_percent':100*(r[k]-b[k])/b[k],
                      'eye_normalized_change':r['eye_normalized']-b['eye_normalized'],
                      'threshold_margin_change':r['threshold_margin_normalized']-b['threshold_margin_normalized'],
                      'errors_changed':r['errors']!=b['errors'],
                      'screen_changed':r['comparison_screen_passed']!=b['comparison_screen_passed'],
                      'max_terminal_change_V':r['max_abs_terminal_V']-b['max_abs_terminal_V']})
        else:e['failure']=r.get('failure','matching nominal missing')
        convergence.append(e)
    full={'schema_version':1,'identity':identity,'work':rel(work),'counts':counts,'groups':groups,'completion':completion,
          'common':m['common'],'metrics_self_checks':a.self_checks(),'comparison_screen':a.SCREEN,
          'physical_contract':m['physical_contract'],'variants':m['variants'],'rows':rows,
          'evidence_boundary':m['evidence_boundary'],'no_retune_after_pex':True,
          'baseline_reanalysis_checks':reuse_checks,'nominal_comparisons':comparisons,
          'numerical_controls':convergence,
          'simulation_failures':[r for r in records if not r['simulation_ok']],
          'analysis_failures':[r for r in records if r['simulation_ok'] and not r['analysis_ok']]}
    emit(work/'analysis.json',full|{'cases':records})
    full['analysis_json']=rel(work/'analysis.json');full['analysis_sha256']=sha(work/'analysis.json')
    emit(EVIDENCE/'summary.json',full);emit(EVIDENCE/'comparisons.json',comparisons)
    emit(EVIDENCE/'convergence.json',convergence)
    with (EVIDENCE/'summary.csv').open('w',newline='') as f:
        fields=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fields)
        w.writeheader();w.writerows(rows)
    print(json.dumps({'counts':counts,'groups':groups,'baseline_metrics_same':all(x['same_metrics'] for x in reuse_checks)},indent=2))
    return full

def main():
    p=argparse.ArgumentParser();p.add_argument('--work');args=p.parse_args()
    work=(ROOT/(args.work or json.loads((EVIDENCE/'latest-run.json').read_text())['work'])).resolve()
    analyze(work)

if __name__=='__main__':main()
