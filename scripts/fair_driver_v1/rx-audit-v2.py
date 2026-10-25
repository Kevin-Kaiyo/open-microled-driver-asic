#!/usr/bin/env python3
"""Independent final v2 RX audit; no production receiver imports or EDA.

Parallel partial fractions of two first-order filters independently realize
the same two-pole transfer function as the frozen cascade receiver.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np

OPTICAL_TAU = 200e-12
RX_TAU = 1 / (2 * math.pi * 1e9)
GRAY_BITS = ((0, 0), (0, 1), (1, 1), (1, 0))
CURRENT_COMPARE_TOL_UA = 1e-6


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            digest.update(block)
    return digest.hexdigest()


def reference_filter(t, current):
    """H(s) = [a/(1+as)-b/(1+bs)]/(a-b), with both DC states equal i(0)."""
    t, current = np.asarray(t), np.asarray(current)
    if len(t) < 2 or len(t) != len(current) or not np.all(np.diff(t) > 0):
        raise ValueError('Strictly increasing equal-length arrays required')
    if not np.isfinite(t).all() or not np.isfinite(current).all():
        raise ValueError('Finite arrays required')
    states = np.array([current[0], current[0]], dtype=float)
    taus = np.array([OPTICAL_TAU, RX_TAU])
    output = np.empty(len(t))
    output[0] = current[0]
    for k, dt in enumerate(np.diff(t), start=1):
        loss = -np.expm1(-dt / taus)
        slope = (current[k] - current[k-1]) / dt
        states += (current[k-1]-states)*loss + slope*(dt-taus*loss)
        output[k] = (OPTICAL_TAU*states[0]-RX_TAU*states[1])/(OPTICAL_TAU-RX_TAU)
    return output


def margin(values, expected, thresholds):
    lower = np.array([-np.inf, *thresholds])[expected]
    upper = np.array([*thresholds, np.inf])[expected]
    return np.minimum(values-lower, upper-values)


def boundary_cache(t, y, thresholds, start, end):
    """Independent PWL zero-set method: strict crossings plus all exact zeros."""
    crossings = []
    for threshold in thresholds:
        z = y-threshold
        segment = np.flatnonzero(np.sign(z[:-1])*np.sign(z[1:]) < 0)
        points = t[segment]-(t[segment+1]-t[segment])*z[segment]/(z[segment+1]-z[segment])
        crossings.append(np.unique(np.r_[points, t[z == 0]]))
    cache = []
    for level in range(len(thresholds)+1):
        relevant = crossings[max(0,level-1):min(len(crossings),level+1)]
        points = np.concatenate(relevant)
        points = points[(points >= start) & (points <= end)]
        cache.append(np.unique(np.r_[start, points, end]))
    return cache


def minimum_time_margin(cache, times, samples, expected, thresholds):
    if np.any(margin(samples, expected, thresholds) <= 0):
        return 0.0
    worst = float('inf')
    for level in np.unique(expected):
        when = times[expected == level]
        edges = cache[int(level)]
        right = np.searchsorted(edges, when, side='right')
        left_edge = edges[np.clip(right-1,0,len(edges)-1)]
        right_edge = edges[np.clip(right,0,len(edges)-1)]
        worst = min(worst, float(np.min(np.minimum(when-left_edge,right_edge-when))))
    return max(0.,worst)*1e12


def independent_training(t, rx_uA, symbols, bits_per_symbol, bit_ui, origin=0.0):
    thresholds = np.array([37.5,62.5,87.5] if bits_per_symbol == 2 else [62.5])
    indices = np.arange(64//bits_per_symbol,512//bits_per_symbol)
    expected = np.asarray(symbols)[indices]
    ui = bits_per_symbol*bit_ui
    delays = np.arange(0,8001,5,dtype=int)/1e12
    when = origin+indices*ui
    assert when[-1]+delays[-1] < origin+576*bit_ui
    samples = np.array([np.interp(when+delay,t,rx_uA) for delay in delays])
    scores = np.array([margin(values,expected,thresholds).min() for values in samples])
    eligible = np.flatnonzero(scores >= scores.max()-1e-6)
    prefix = t < origin+576*bit_ui
    cache = boundary_cache(t[prefix],rx_uA[prefix],thresholds,
                           origin+64*bit_ui,float(t[prefix][-1]))
    time_scores = {int(i):minimum_time_margin(cache,when+delays[i],samples[i],expected,thresholds)
                   for i in eligible}
    chosen = max(time_scores,key=lambda i:(time_scores[i],-i))
    return {'delay_s':float(delays[chosen]), 'delay_symbol_UI':float(delays[chosen]/ui),
            'amplitude_scores_uA':scores, 'chosen_training_time_margin_ps':time_scores[chosen]}


def independent_decisions(samples, expected, pam4):
    thresholds = np.array([37.5, 62.5, 87.5] if pam4 else [62.5])
    decisions = np.sum(samples[:, None] >= thresholds, axis=1)
    if pam4:
        bits = np.array([GRAY_BITS[int(x)] for x in decisions]).ravel()
        wanted = np.array([GRAY_BITS[int(x)] for x in expected]).ravel()
    else:
        bits, wanted = decisions, expected
    return {'bit_errors': int(np.count_nonzero(bits != wanted)),
            'symbol_errors': int(np.count_nonzero(decisions != expected)),
            'min_signed_margin_uA': float(margin(samples, expected, thresholds).min()),
            'symbol_decisions': decisions}


def analytic_checks():
    """Independent closed-form fixtures, retained as audit calibration evidence."""
    t = np.linspace(0, 3e-9, 301)
    dc_error = float(np.max(abs(reference_filter(t, np.full(len(t), 73e-6))-73e-6)))
    # A tiny finite ramp approximates a unit step, whose two-pole closed form is known.
    t = np.r_[0., 1e-16, np.linspace(1e-12, 3e-9, 300)]
    current = np.ones(len(t)); current[0] = 0
    want = 1-(OPTICAL_TAU*np.exp(-t/OPTICAL_TAU)-RX_TAU*np.exp(-t/RX_TAU))/(OPTICAL_TAU-RX_TAU)
    step_error = float(np.max(abs(reference_filter(t, current)-want)))
    low = independent_decisions(np.array([25., 100.]), np.array([0, 1]), False)
    negative = independent_decisions(np.array([25., 25.]), np.array([0, 1]), False)
    gray = independent_decisions(np.array([75.]), np.array([0]), True)
    weak = independent_decisions(np.array([58., 67.]), np.array([0, 1]), False)
    passed = (dc_error < 1e-18 and step_error < 2e-7 and low['bit_errors'] == 0
              and negative['bit_errors'] == 1 and gray['bit_errors'] == 2
              and weak['bit_errors'] == 0 and weak['min_signed_margin_uA'] == 4.5)
    if not passed:
        raise AssertionError('Independent analytic fixtures failed')
    return {'passed': passed, 'DC_max_error_A': dc_error,
            'unit_step_max_error': step_error,
            'negative_controls': 'wrong NRZ bit=1 error; Gray00->11=2 bit errors; weak NRZ margin4.5uA despite0 errors'}


def verify_formal(work, root):
    manifest=json.loads((work/'manifest.json').read_text())
    for name,digest in manifest['files'].items():
        assert sha256(work/name)==digest, 'Frozen formal file drift: '+name
    summary=json.loads((work/'summary.json').read_text())
    assert summary['manifest_sha256']==sha256(work/'manifest.json')
    assert summary['complete'] and summary['counts']=={'baseline':45,'controls':11}
    assert not summary['unanalysed'] and not summary['no_successful_electrical']
    seen={group:set() for group in ['baseline','controls']}
    failed={group:0 for group in seen}
    for item in summary['records']:
        group,key=item['group'],item['canonical_case']
        assert key not in seen[group];seen[group].add(key)
        path=root/item['path'];assert sha256(path)==item['sha256']
        record=json.loads(path.read_text());source=root/record['source_result']
        assert sha256(source)==record['source_result_sha256']
        wanted={'analysis_version':'equal-absolute-latency-v2','group':group,'canonical_case':key,
                'v2_receiver_sha256':manifest['files']['receiver.py'],
                'v2_contract_sha256':manifest['files']['contract.md'],
                'v2_stimulus_sha256':manifest['files']['stimulus.json'],
                'analysis_execution_sha256':manifest['execution_sha256'],
                'helper_run_sha256':manifest['helper_run_sha256']}
        assert all(record[k]==v for k,v in wanted.items())
        old=json.loads(source.read_text())
        assert record['source_gzip_sha256']==old['gzip_sha256']
        assert record['communication_screen_passed']==bool(old['metrics']['device_voltage_passed'] and record['receiver']['passed'])
        failed[group]+=not record['communication_screen_passed']
    assert all(seen[g]==set(manifest['expected_canonical_cases'][g]) for g in seen)
    return manifest, {'counts':summary['counts'],'failure_counts':failed,
                      'complete':True,'unique_canonical_sets_verified':True,
                      'summary_sha256':sha256(work/'summary.json'),
                      'preserved_failed_attempts':{g:d['preserved_failed_attempts'] for g,d in summary['electrical_diagnostics'].items()}}


def audit_case(work, root, case_name):
    result_path=work/'cases/baseline'/case_name/'result.json'
    result=json.loads(result_path.read_text());original_path=root/result['source_result']
    original=json.loads(original_path.read_text());wave=original_path.with_name('waveform.dat.gz')
    assert sha256(original_path)==result['source_result_sha256']
    assert sha256(wave)==result['source_gzip_sha256']==original['gzip_sha256']
    digest=hashlib.sha256()
    with gzip.open(wave,'rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):digest.update(block)
    assert digest.hexdigest()==original['raw_sha256']==result['source_raw_sha256_recorded']
    with gzip.open(wave,'rt') as stream:data=np.loadtxt(stream,skiprows=1)
    assert original['metadata']['export_mode']=='native-led+native-energy-stress'
    assert original['metadata']['vectors']=={'iled_cond':1}
    t,current=data[:,0],data[:,1]
    assert len(t)==result['native_samples']==original['metrics']['sample_count']
    stimulus=json.loads((work/'stimulus.json').read_text());frozen=result['receiver']
    pam4=result['case']['route']=='C';bps=2 if pam4 else 1
    symbols=np.array(stimulus['symbols_C' if pam4 else 'symbols_N'])
    origin=stimulus.get('time_origin_s',0.)
    bit_ui=(4096/4736)/(result['case']['net_rate_Gbps']*1e9);ui=bps*bit_ui
    indices=np.arange(576//bps,4672//bps);expected=symbols[indices]
    filtered=reference_filter(t,current)*1e6
    sample_times=origin+indices*ui+frozen['sampling']['delay_s']
    samples=np.interp(sample_times,t,filtered)
    metrics=independent_decisions(samples,expected,pam4)
    training=independent_training(t,filtered,symbols,bps,bit_ui,origin)
    changed=current.copy();changed[t >= origin+576*bit_ui]=40e-6
    changed_symbols=symbols.copy();changed_symbols[576//bps:]=(changed_symbols[576//bps:]+1)%(4 if pam4 else 2)
    challenged=independent_training(t,reference_filter(t,changed)*1e6,changed_symbols,bps,bit_ui,origin)
    transitions=Counter(zip(expected[:-1].tolist(),expected[1:].tolist()))
    transition_map={f'{a}->{b}':transitions[(a,b)] for a in range(4 if pam4 else 2) for b in range(4 if pam4 else 2)}
    complete=all(n>0 for edge,n in transition_map.items() if edge[0]!=edge[-1])
    thresholds=np.array([37.5,62.5,87.5] if pam4 else [62.5])
    validation_cache=boundary_cache(t,filtered,thresholds,origin,origin+4736*bit_ui)
    horizontal=minimum_time_margin(validation_cache,sample_times,samples,expected,thresholds)
    sample_delta=float(np.max(abs(samples-np.array(frozen['validation']['samples_uA']))))
    margin_delta=metrics['min_signed_margin_uA']-frozen['validation']['decision_distance_min_uA']
    score_delta=float(np.max(abs(training['amplitude_scores_uA']-np.array([x['min_signed_decision_distance_uA'] for x in frozen['sampling']['training_scan']]))))
    time_delta=horizontal-frozen['horizontal_margin']['min_ps']
    checks={
      'sample_values_agree':sample_delta<=CURRENT_COMPARE_TOL_UA,
      'minimum_margin_agrees':abs(margin_delta)<=CURRENT_COMPARE_TOL_UA,
      'bit_errors_agree':metrics['bit_errors']==frozen['validation']['bit_errors'],
      'symbol_errors_agree':metrics['symbol_errors']==frozen['validation']['symbol_errors'],
      'all_decisions_agree':bool(np.array_equal(metrics['symbol_decisions'],frozen['validation']['decoded_symbols'])),
      'transition_counts_agree':transition_map==frozen['validation']['transition_counts'],
      'all_directed_transitions_present':bool(complete),
      'training_scores_agree':score_delta<=CURRENT_COMPARE_TOL_UA,
      'chosen_absolute_delay_agrees':training['delay_s']==frozen['sampling']['delay_s'],
      'validation_time_margin_agrees':abs(time_delta)<=1e-4,
      'validation_waveform_and_labels_cannot_change_training':(
          training['delay_s']==challenged['delay_s'] and
          np.array_equal(training['amplitude_scores_uA'],challenged['amplitude_scores_uA']) and
          training['chosen_training_time_margin_ps']==challenged['chosen_training_time_margin_ps'])}
    return {'case':case_name,'route':result['case']['route'],'native_samples':len(t),
      'identity':{'formal_result_sha256':sha256(result_path),'electrical_result_sha256':sha256(original_path),
                  'gzip_sha256':sha256(wave),'independently_decompressed_raw_sha256':digest.hexdigest()},
      'independent_bit_errors':metrics['bit_errors'],'independent_symbol_errors':metrics['symbol_errors'],
      'independent_min_signed_margin_uA':metrics['min_signed_margin_uA'],
      'independent_delay_s':training['delay_s'],'independent_min_time_margin_ps':horizontal,
      'max_sample_difference_uA':sample_delta,'min_margin_difference_uA':float(margin_delta),
      'max_training_score_difference_uA':score_delta,'time_margin_difference_ps':float(time_delta),
      'transition_counts':transition_map,'checks':checks,'audit_passed':all(checks.values()),
      'receiver_passed':frozen['passed'],'communication_screen_passed':result['communication_screen_passed']}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--work',type=Path,required=False)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args();fixtures=analytic_checks()
    t=np.array([0.,1.,2.,3.,5.])*1e-9;y=np.array([0.,1.,1.,2.,2.]);threshold=np.array([1.])
    cache=boundary_cache(t,y,threshold,0,5e-9)
    plateau=minimum_time_margin(cache,np.array([3e-9]),np.array([2.]),np.array([1]),threshold)
    assert abs(plateau-1000)<1e-9
    fixtures['independent_threshold_plateau_margin_ps']=plateau
    if args.self_test:print(json.dumps(fixtures,indent=2));return
    if not args.work or not args.out:parser.error('--work --out required')
    if args.out.exists():raise FileExistsError('Refuse overwrite: '+str(args.out))
    root=Path(__file__).resolve().parents[2];work=args.work.resolve()
    manifest,coverage=verify_formal(work,root)
    rows=[]
    for route in 'ABC':
        row=audit_case(work,root,f'RX-TT-{route}-0.5G');rows.append(row)
        print(json.dumps({'case':row['case'],'audit_passed':row['audit_passed'],
                          'margin_uA':row['independent_min_signed_margin_uA'],
                          'delay_ns':row['independent_delay_s']*1e9},ensure_ascii=False),flush=True)
    report={'schema_version':2,'audit_source_sha256':sha256(__file__),
       'formal_work':str(work),'formal_manifest_sha256':sha256(work/'manifest.json'),
       'formal_source_files':manifest['files'],'formal_coverage':coverage,
       'method':'Independent analytic parallel-pole partial fractions; independent PWL zero-set threshold boundaries; no production receiver import or calls.',
       'current_tolerance_uA':CURRENT_COMPARE_TOL_UA,'time_tolerance_ps':1e-4,
       'analytic_fixtures':fixtures,'rows':rows,'audit_passed':all(x['audit_passed'] for x in rows),
       'limits_zh':['审计只后处理已完成native数据，不运行SPICE、不改变原始v1/v2结果。',
                   '独立复核滤波、固定采样、训练隔离、误码、电流与时间余量；没有独立验证条件Gaussian BER。',
                   'native波形一致性仍不替代最大步长/算法对照、器件物理模型或实测光学BER。',
                   'audit_passed表示独立实现与冻结结果一致，不代表被测电路通过；C的receiver_passed=false仍保留。']}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'audit_passed':report['audit_passed'],'out':str(args.out)}))
    if not report['audit_passed']:raise SystemExit(1)


if __name__=='__main__':main()
