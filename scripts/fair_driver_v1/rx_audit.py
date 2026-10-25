#!/usr/bin/env python3
"""Independent RX audit of completed native/uniform exports; no receiver imports or EDA.

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


def training_time_margin(t, y, times, samples, expected, thresholds):
    """Independent threshold-event list, restricted to pre-validation waveform."""
    worst = math.inf
    for level in np.unique(expected):
        selected = np.flatnonzero(expected == level)
        if np.any(margin(samples[selected], expected[selected], thresholds) <= 0):
            return 0.0
        relevant = thresholds[max(0, level-1):min(len(thresholds), level+1)]
        events = [t[0], t[-1]]
        for threshold in relevant:
            delta = y-threshold
            crossing = np.flatnonzero(((delta[:-1] < 0) & (delta[1:] >= 0)) |
                                      ((delta[:-1] > 0) & (delta[1:] <= 0)))
            events.extend(t[crossing] + (t[crossing+1]-t[crossing]) *
                          (-delta[crossing])/(delta[crossing+1]-delta[crossing]))
        events = np.unique(events)
        for when in times[selected]:
            position = int(np.searchsorted(events, when, side='right'))
            left = events[max(0, position-1)]
            right = events[min(len(events)-1, position)]
            worst = min(worst, max(0.0, min(when-left, right-when)))
    return float(worst*1e12)


def independent_training(t, rx_uA, symbols, bits_per_symbol, bit_ui, origin=0.0):
    thresholds = np.array([37.5, 62.5, 87.5] if bits_per_symbol == 2 else [62.5])
    labels = np.arange(64//bits_per_symbol, 572//bits_per_symbol)
    expected = np.asarray(symbols)[labels]
    symbol_ui = bits_per_symbol*bit_ui
    delays = np.linspace(.5, 2., 193)
    samples = np.array([np.interp(origin+(labels+d)*symbol_ui, t, rx_uA) for d in delays])
    scores = np.min(np.array([margin(v, expected, thresholds) for v in samples]), axis=1)
    candidates = np.flatnonzero(scores >= scores.max()-1e-6)
    pre_validation = t < origin+576*bit_ui
    time_scores = {}
    for idx in candidates:
        when = origin+(labels+delays[idx])*symbol_ui
        time_scores[int(idx)] = training_time_margin(t[pre_validation], rx_uA[pre_validation],
                                                     when, samples[idx], expected, thresholds)
    best = max(time_scores, key=lambda idx: (time_scores[idx], -idx))
    return {'delay_symbol_UI': float(delays[best]), 'amplitude_scores_uA': scores,
            'chosen_training_time_margin_ps': time_scores[best]}


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


def audit_case(work, case_name):
    folder = work/'cases'/case_name
    result_path, wave = folder/'result.json', folder/'waveform.dat.gz'
    if not result_path.exists():
        raise RuntimeError('Refuse incomplete case: '+case_name)
    result = json.loads(result_path.read_text())
    if not result.get('simulation_ok') or 'receiver' not in result.get('metrics', {}):
        raise RuntimeError('Case has no completed receiver result: '+case_name)
    if sha256(wave) != result['gzip_sha256']:
        raise AssertionError('Gzip SHA mismatch')
    decompressed = hashlib.sha256()
    with gzip.open(wave, 'rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            decompressed.update(block)
    if decompressed.hexdigest() != result['raw_sha256']:
        raise AssertionError('Decompressed raw SHA mismatch')
    with gzip.open(wave, 'rt') as stream:
        values = np.loadtxt(stream, skiprows=1)
    t = values[:, 0]
    current = values[:, result['metadata']['vectors']['iled_cond']]
    stimulus = json.loads((work/'stimulus.json').read_text())
    frozen = result['metrics']['receiver']
    pam4 = result['case']['route'] == 'C'
    bps = 2 if pam4 else 1
    symbol_all = np.array(stimulus['symbols_C' if pam4 else 'symbols_N'])
    origin = stimulus.get('time_origin_s', 0.)
    bit_ui = (4096/4736)/(result['case']['net_rate_Gbps']*1e9)
    symbol_ui = bps*bit_ui
    indices = np.arange(576//bps, 4672//bps)
    expected = symbol_all[indices]
    rx_uA = reference_filter(t, current)*1e6
    times = origin+(indices+frozen['sampling']['delay_symbol_UI'])*symbol_ui
    samples = np.interp(times, t, rx_uA)
    metrics = independent_decisions(samples, expected, pam4)
    training = independent_training(t, rx_uA, symbol_all, bps, bit_ui, origin)
    # Alter validation and tail waveform, and separately their labels: training
    # must be insensitive to both. No frozen production analysis is called.
    changed = current.copy(); changed[t >= origin+576*bit_ui] = 40e-6
    changed_symbols = symbol_all.copy()
    changed_symbols[576//bps:] = (changed_symbols[576//bps:]+1) % (4 if pam4 else 2)
    challenged = independent_training(t, reference_filter(t, changed)*1e6,
                                     changed_symbols, bps, bit_ui, origin)
    transition_counts = Counter(zip(expected[:-1].tolist(), expected[1:].tolist()))
    transition_map = {f'{a}->{b}': transition_counts[(a, b)]
                      for a in range(4 if pam4 else 2) for b in range(4 if pam4 else 2)}
    all_directed = all(n > 0 for edge, n in transition_map.items() if edge[0] != edge[-1])
    sample_delta = float(np.max(abs(samples-np.array(frozen['validation']['samples_uA']))))
    margin_delta = float(metrics['min_signed_margin_uA']-frozen['validation']['decision_distance_min_uA'])
    score_delta = float(np.max(abs(training['amplitude_scores_uA']-np.array([
        row['min_signed_decision_distance_uA'] for row in frozen['sampling']['training_scan']]))))
    checks = {
        'frozen_sample_values_agree': sample_delta <= CURRENT_COMPARE_TOL_UA,
        'minimum_current_margin_agrees': abs(margin_delta) <= CURRENT_COMPARE_TOL_UA,
        'bit_error_count_agrees': metrics['bit_errors'] == frozen['validation']['bit_errors'],
        'symbol_error_count_agrees': metrics['symbol_errors'] == frozen['validation']['symbol_errors'],
        'all_symbol_decisions_agree': bool(np.array_equal(metrics['symbol_decisions'], frozen['validation']['decoded_symbols'])),
        'transition_counts_agree': transition_map == frozen['validation']['transition_counts'],
        'all_directed_transitions_present': bool(all_directed),
        'independent_training_phase_agrees': training['delay_symbol_UI'] == frozen['sampling']['delay_symbol_UI'],
        'training_scores_agree': score_delta <= CURRENT_COMPARE_TOL_UA,
        'validation_challenge_cannot_change_training': (
            challenged['delay_symbol_UI'] == training['delay_symbol_UI']
            and np.array_equal(challenged['amplitude_scores_uA'], training['amplitude_scores_uA'])
            and challenged['chosen_training_time_margin_ps'] == training['chosen_training_time_margin_ps']),
    }
    dt = np.diff(t)
    return {'case': case_name, 'route': result['case']['route'],
            'export_mode': result['metadata']['export_mode'], 'sample_count': len(t),
            'max_dt_ps': float(dt.max()*1e12),
            'uniform_dt_max_deviation_ps': float(np.max(abs(dt-np.median(dt)))*1e12),
            'identity': {'result_sha256': sha256(result_path), 'gzip_sha256': sha256(wave),
                         'raw_sha256': decompressed.hexdigest(),
                         'frozen_receiver_sha256': sha256(work/'inputs/receiver.py')},
            'independent_bit_errors': metrics['bit_errors'],
            'independent_symbol_errors': metrics['symbol_errors'],
            'independent_min_signed_margin_uA': metrics['min_signed_margin_uA'],
            'max_sample_difference_uA': sample_delta,
            'min_margin_difference_uA': margin_delta,
            'max_training_score_difference_uA': score_delta,
            'independent_delay_symbol_UI': training['delay_symbol_UI'],
            'transition_counts': transition_map, 'checks': checks,
            'audit_passed': all(checks.values()),
            'circuit_receiver_passed': frozen['passed']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path)
    parser.add_argument('--cases', nargs='+')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    fixtures = analytic_checks()
    if args.self_test:
        print(json.dumps(fixtures, indent=2))
        return
    if not args.work or not args.cases or not args.out:
        parser.error('--work --cases --out are required')
    if args.out.exists():
        raise FileExistsError('Refuse overwrite: '+str(args.out))
    work = args.work.resolve()
    manifest = json.loads((work/'manifest.json').read_text())
    for name, wanted in manifest['inputs'].items():
        if sha256(work/'inputs'/name) != wanted:
            raise AssertionError('Frozen input drift: '+name)
    if sha256(work/'stimulus.json') != manifest['stimulus_sha256']:
        raise AssertionError('Stimulus identity mismatch')
    rows = [audit_case(work, name) for name in args.cases]
    report = {'schema_version': 1, 'audit_source_sha256': sha256(__file__),
              'work': str(work), 'manifest_sha256': sha256(work/'manifest.json'),
              'stimulus_sha256': sha256(work/'stimulus.json'),
              'method': 'Independent analytic partial-fraction parallel first-order filters, DC initial states, exact PWL input integration. No receiver import or filter_trace call.',
              'transfer_function': '[a/(1+a*s)-b/(1+b*s)]/(a-b)=1/((1+a*s)*(1+b*s)); a=200ps, b=1/(2*pi*1GHz)',
              'comparison_tolerance_uA': CURRENT_COMPARE_TOL_UA,
              'analytic_fixtures': fixtures, 'rows': rows,
              'audit_passed': all(row['audit_passed'] for row in rows),
              'limits_zh': [
                  '每个结果保留 export_mode：native 使用原始自适应求解时间点；若为 uniform，则不能证明 linearize 未遗失峰值、边沿或高频细节。',
                  '两种独立算法在相同数据上吻合，只验证滤波和判决实现；即使 native 导出仍须最大步长 40/80 等细化对照，才能评估求解波形的离散误差。',
                  '原始传导电流的抽取正确性、器件模型、光学/RX 极点物理真实性、功耗与端压不属于此复核。',
                  '训练相位使用独立模型重算并与冻结结果比较，同时扰动验证/尾段数据与标签；本复核不调用原接收器分析。',
                  '有限确定性错误数不是 BER 测量或认证；audit_passed 不等于 circuit_receiver_passed。']}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'audit_passed': report['audit_passed'], 'cases': len(rows),
                      'out': str(args.out)}, ensure_ascii=False))
    if not report['audit_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
