#!/usr/bin/env python3
"""Independent consistency audit of the frozen comparison, not LVS/signoff."""
from pathlib import Path
import argparse
import json
import math
import platform
import shutil
import sys
import tarfile
import numpy as np
from run import ROOT, EVIDENCE, RATES, MAX_INCREMENTAL_BYTES, sha, rel, emit, parse_core, current_bytes


def validate(work):
    validator_hash=sha(Path(__file__))
    validator_source=work/'validation-sources'/f'{validator_hash}.py'
    validator_source.parent.mkdir(parents=True,exist_ok=True)
    if not validator_source.exists():shutil.copy2(Path(__file__),validator_source)
    manifest=json.loads((work/'manifest.json').read_text())
    summary=json.loads((work/'analysis.json').read_text())
    environment={'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),
                 'ngspice':manifest['ngspice_version']}
    emit(work/'environment.json',environment)
    checks=[]
    def check(name,ok,detail=None):
        checks.append({'name':name,'passed':bool(ok),'detail':detail})
    inputs=[]
    for name,entry in manifest['inputs'].items():
        actual=sha(work/'inputs'/name)
        inputs.append({'path':name,'same':actual==entry['sha256']})
    check('frozen_input_hashes',all(x['same'] for x in inputs),inputs)
    check('same_stimulus_bytes_as_original',sha(work/'stimulus.json')==sha(ROOT/manifest['baseline']/'stimulus.json'))
    check('no_post_PEX_retune_declared',manifest['no_retune_after_pex'])
    check('legacy_metric_self_checks',summary['metrics_self_checks']['status']=='passed',summary['metrics_self_checks'])
    check('baseline_reanalysis_same',all(x['same_metrics'] for x in summary['baseline_reanalysis_checks']))
    check('declared_case_lists_complete',summary['completion']['status']=='declared_case_lists_complete',
          summary['completion'])
    check('no_extraction_hold',not summary['completion']['hold'])
    check('no_missing_or_failed_planned_cases',not summary['completion']['missing_planned_cases']
          and not summary['completion']['failed_or_unanalyzed_planned_cases'])
    place=summary['completion'].get('cap_placement_coverage',[])
    check('both_ground_capacitance_placement_controls_complete',
          len(place)==2 and {x['route'] for x in place}=={'A','B'}
          and all(x['complete'] and x['successful_rates_Gbps']==[.5,1,2] for x in place),place)
    new_count=0
    case_checks=[]
    for record in summary['cases']:
        c=record['case'];folder=work/'cases'/c['name']
        result=json.loads((folder/'result.json').read_text())
        item={'name':c['name'],'simulation_ok':result['simulation_ok'],'analysis_ok':record['analysis_ok']}
        if result.get('deck_sha256'):
            item['testbench_hash_valid']=sha(folder/'testbench.spice')==result['deck_sha256']
        if c['variant']=='SCHEM':
            original=ROOT/result['reuse']['original_result']
            item['original_result_unchanged']=sha(original)==result['reuse']['original_result_sha256']
        else:
            new_count+=1
            item['log_hash_valid']=bool(result.get('log_sha256')) and sha(ROOT/result['log'])==result['log_sha256']
            if result.get('runner_source'):
                item['executed_runner_source_hash_valid']=sha(ROOT/result['runner_source'])==result['runner_source_sha256']
            if 'waveform' in result:
                item['compressed_waveform_hash_valid']=sha(ROOT/result['waveform'])==result['waveform_sha256']
                item['roundtrip_verified']=result.get('roundtrip_verified',False)
            if result['simulation_ok']:
                core=work/'inputs'/manifest['variants'][c['route']][c['variant']]['path']
                sub,ports,devices=parse_core(core)
                def local(n):return ('0' if n=='vss' else n) if n in ports else 'xdrv.'+n
                expected=[[local(n) for n in d['nodes']] for d in devices]
                actual=[d['nodes'] for d in result['devices']]
                item['all_true_MOS_terminal_nodes_saved']=expected==actual and all(
                    n=='0' or n in result['vectors'] for group in expected for n in group)
                item['correct_MOS_count']=len(actual)==(6 if c['route']=='A' else 9)
        if record['analysis_ok']:
            item['trace_hashes_verified_by_analysis']=record['sources']['hash_checks']=='passed'
            item['all_device_stress_recorded']=len(record['stress']['all_devices'])==(6 if c['route']=='A' else 9)
            if 'transient' in record:
                t=record['transient']
                # energy_window/sum_energy perform exact signed/positive/returned
                # identity assertions. Presence of every source is checked here.
                source_data=t['energy']
                expected_rails=['VLED','VDD','VH','VL'] if c['route']=='A' else ['VLED','VDD','VDUMMY']
                item['energy_all_rails_present']=sorted(source_data['rails'])==sorted(expected_rails)
                item['energy_DATA_present']='ideal_DATA' in source_data
                total=source_data['rail_plus_ideal_DATA_total']
                item['signed_energy_identity']=math.isclose(total['net_J'],
                    total['positive_draw_J']-total['returned_J'],rel_tol=1e-10,abs_tol=1e-23)
        else:
            item['failure_explicitly_retained']=bool(record.get('simulation_failure') or record.get('analysis_error'))
        bools=[v for k,v in item.items() if isinstance(v,bool) and k not in ['simulation_ok','analysis_ok']]
        item['audit_passed']=all(bools)
        case_checks.append(item)
    check('case_hash_terminal_failure_audits',all(x['audit_passed'] for x in case_checks),case_checks)
    coverage=[]
    for route in 'AB':
        for variant in ['SCHEM','GEOM','C','RC']:
            found=[r['rate_Gbps'] for r in summary['rows'] if r['route']==route and r['variant']==variant and r['kind']=='nominal' and r['analysis_ok']]
            coverage.append({'route':route,'variant':variant,'rates':sorted(found),'complete':sorted(found)==RATES})
    check('nominal_seven_rate_coverage',all(x['complete'] for x in coverage),coverage)
    size=sum(p.stat().st_size for p in work.rglob('*') if p.is_file() and not p.is_symlink())
    all_size=current_bytes()
    check('incremental_storage_budget',all_size<MAX_INCREMENTAL_BYTES,
          {'current_run_bytes':size,'all_new_runs_bytes_including_diagnostics':all_size,'budget':MAX_INCREMENTAL_BYTES})
    archive=work/'frozen-inputs.tar.gz'
    if not archive.exists():
        with tarfile.open(archive,'w:gz',compresslevel=6) as tar:
            for name in ['inputs','manifest.json','stimulus.json','baseline-import.json',
                         'execution-sources','analysis-sources','validation-sources','reused-cases.json']:
                if (work/name).exists():tar.add(work/name,arcname=name,recursive=True)
            tar.add(work/'environment.json',arcname='environment.json')
    result={'work':rel(work),'passed':all(c['passed'] for c in checks),'new_case_count':new_count,
            'validator_source':rel(validator_source),'validator_source_sha256':validator_hash,
            'environment':environment,
            'all_case_count':len(case_checks),'checks':checks,
            'frozen_source_archive':{'path':rel(archive),'sha256':sha(archive),'bytes':archive.stat().st_size},
            'prior_diagnostic_run':{'status':'excluded from final completion and failure counts',
                'hold_record':'evidence/highspeed-nrz-pex/r3-hold.json',
                'scope':'deliberately interrupted r3 C cases retained; no r3 RC transient was run'},
            'scope':'hash/provenance, coverage, actual terminal-vector and outcome consistency; not LVS, extraction validation, BER or signoff'}
    emit(EVIDENCE/'validation.json',result)
    print(json.dumps({'passed':result['passed'],'cases':len(case_checks),
                      'failed_checks':[x['name'] for x in checks if not x['passed']]},indent=2))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work');args=p.parse_args()
    work=(ROOT/(args.work or json.loads((EVIDENCE/'latest-run.json').read_text())['work'])).resolve()
    validate(work)
