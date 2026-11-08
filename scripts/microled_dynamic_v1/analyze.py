#!/usr/bin/env python3
"""Append-only synthetic dynamic sensitivity on native LED conduction traces.

The circuit, electrical energy and immutable v2 RX decision contract are retained.
Only the explicitly labelled synthetic optical pole changes. No calibrated optical
model, optical energy, physical BER or topology approval is implied.
"""
from __future__ import annotations

import argparse
import ast
import csv
import datetime
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys
import traceback

import numpy as np

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'build/microled-dynamic-v1/receiver'
EVIDENCE = ROOT / 'evidence/microled-dynamic-v1'
ELECTRICAL = ROOT / 'build/microled-dynamic-v1/electrical/run-r1'
RXSOURCE = ROOT / 'scripts/fair_driver_v1/receiver_equal_latency_v2.py'
TAU_RX_S = 1 / (2 * math.pi * 1e9)
TAUS_PS = (0, 25, 75, 200)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def emit(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def scope_hash(path, functions):
    """Bind executable function ASTs, excluding unrelated orchestration/report text."""
    tree = ast.parse(Path(path).read_text())
    selected = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in functions]
    assert {node.name for node in selected} == set(functions)
    return hashlib.sha256(ast.dump(ast.Module(body=selected, type_ignores=[]), include_attributes=False).encode()).hexdigest()


STATE_FUNCTIONS = ('_ramp_gain', 'first_order_pwl', 'cascade_pwl')


def _ramp_gain(z):
    """1-(1-exp(-z))/z, with its removable singularity evaluated by series."""
    z = np.asarray(z)
    answer = 1 + np.expm1(-z) / z
    small = z < .01
    v = z[small]
    accum = np.zeros_like(v)
    for n in range(1, 11):
        accum += (-1) ** (n + 1) * v ** n / math.factorial(n + 1)
    answer[small] = accum
    return answer


def first_order_pwl(t, current, tau):
    """Exact first-order response to each native PWL interval; DC OP initial state."""
    if tau == 0:
        return current.copy()
    h = np.diff(t)
    decay = np.exp(-h / tau)
    ramp = _ramp_gain(h / tau)
    result = np.empty_like(current)
    result[0] = current[0]
    for k in range(len(h)):
        result[k + 1] = current[k] + decay[k] * (result[k] - current[k]) + (current[k + 1] - current[k]) * ramp[k]
    return result


def cascade_pwl(t_s, current_A, tau_optical_s, tau_rx_s=TAU_RX_S):
    """Exact two-pole PWL states, stable at equal poles and either bypass pole.

    Both unity-DC-gain states start at the first conduction-current sample. The
    ramp forcing uses a bivariate Taylor series for short native intervals, so
    initial femtosecond timesteps do not subtract nearly equal quantities.
    """
    t = np.asarray(t_s, dtype=float)
    current = np.asarray(current_A, dtype=float)
    if (t.ndim != 1 or current.shape != t.shape or len(t) < 2 or
            not np.isfinite(t).all() or not np.isfinite(current).all() or
            not np.all(np.diff(t) > 0)):
        raise ValueError('Finite 1D arrays and strictly increasing native time are required')
    a, b = float(tau_optical_s), float(tau_rx_s)
    if not (math.isfinite(a) and math.isfinite(b) and a >= 0 and b >= 0):
        raise ValueError('Finite nonnegative time constants are required')
    if a == 0:
        return current.copy(), first_order_pwl(t, current, b)
    if b == 0:
        first = first_order_pwl(t, current, a)
        return first, first.copy()
    h = np.diff(t)
    za, zb = h / a, h / b
    ea, eb = np.exp(-za), np.exp(-zb)
    fa = _ramp_gain(za)
    q = h * ((a - b) / (a * b))
    coupling = np.empty_like(h)
    nonzero = q != 0
    positive = q > 0
    negative = q < 0
    coupling[~nonzero] = zb[~nonzero] * eb[~nonzero]
    coupling[positive] = zb[positive] * ea[positive] * (-np.expm1(-q[positive])) / q[positive]
    coupling[negative] = zb[negative] * eb[negative] * np.expm1(q[negative]) / q[negative]
    ramp = 1 - (a + b) / h * (-np.expm1(-zb)) + a / h * coupling
    small = np.maximum(za, zb) < .5
    az, bz = za[small], zb[small]
    product, total = az * bz, az + bz
    previous = np.ones_like(az)
    current_h = total.copy()
    series = product / 6
    for n in range(3, 21):
        if n == 3:
            homogeneous = current_h
        else:
            following = total * current_h - product * previous
            previous, current_h = current_h, following
            homogeneous = current_h
        series += (-1) ** n * product * homogeneous / float(math.factorial(n + 1))
    ramp[small] = series
    first, second = np.empty_like(current), np.empty_like(current)
    first[0] = second[0] = current[0]
    for k in range(len(h)):
        u = current[k]
        du = current[k + 1] - u
        dfirst, dsecond = first[k] - u, second[k] - u
        first[k + 1] = u + ea[k] * dfirst + du * fa[k]
        second[k + 1] = u + eb[k] * dsecond + coupling[k] * dfirst + du * ramp[k]
    return first, second


def compact_rx(result):
    return {
        'bit_errors': result['validation']['bit_errors'],
        'bit_count': result['validation']['bit_count'],
        'symbol_errors': result['validation']['symbol_errors'],
        'min_signed_margin_uA': result['validation']['decision_distance_min_uA'],
        'mean_signed_margin_uA': result['validation']['decision_distance_mean_uA'],
        'min_time_margin_ps': result['horizontal_margin']['min_ps'],
        'delay_ps': result['sampling']['delay_s'] * 1e12,
        'training_bit_errors': result['sampling']['training_scan'][round(result['sampling']['delay_s'] * 1e12 / 5)]['bit_errors'],
        'passed': result['passed'], 'checks': result['checks'],
    }


def state_cache(t, current, raw_sha, previous=None):
    kernel_hash = scope_hash(Path(__file__), STATE_FUNCTIONS)
    key = hashlib.sha256((raw_sha + kernel_hash + repr((TAUS_PS, TAU_RX_S))).encode()).hexdigest()
    path = WORK / 'cache' / (key + '.npz')
    # A previously successful full-script cache is reusable only when its
    # archived executable kernel is identical and the recorded NPZ SHA agrees.
    if not path.exists() and previous is not None:
        old_path = ROOT / previous['state_cache']
        for archived in sorted((WORK / 'execution-sources').glob('*/analyze.py')):
            old_sha = sha(archived)
            old_key = hashlib.sha256((raw_sha + old_sha + repr((TAUS_PS, TAU_RX_S))).encode()).hexdigest()
            if (old_path.name == old_key + '.npz' and old_path.exists() and
                    scope_hash(archived, STATE_FUNCTIONS) == kernel_hash):
                assert sha(old_path) == previous['state_cache_sha256'], 'Previous state cache SHA drift'
                with np.load(old_path) as old:
                    assert np.array_equal(old['time_s'], t) and np.array_equal(old['electrical'], current)
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old_path, path)
                emit(path.with_suffix('.json'), {'raw_sha256': raw_sha, 'state_kernel_sha256': kernel_hash,
                     'cache_sha256': sha(path), 'reused_cache': str(old_path.relative_to(ROOT)),
                     'validated_previous_execution_source': str(archived.relative_to(ROOT)),
                     'validated_previous_execution_source_sha256': old_sha})
                break
    if path.exists():
        meta_path = path.with_suffix('.json')
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            assert meta['cache_sha256'] == sha(path) and meta['raw_sha256'] == raw_sha
            assert meta['state_kernel_sha256'] == kernel_hash
        with np.load(path) as data:
            states = {k: data[k].copy() for k in data.files}
            assert np.array_equal(states['time_s'], t) and np.array_equal(states['electrical'], current)
            return states, path
    states = {'time_s': t.copy(), 'electrical': current.copy(),
              'rx_only': first_order_pwl(t, current, TAU_RX_S)}
    for tau in TAUS_PS:
        optical, full = cascade_pwl(t, current, tau * 1e-12)
        states[f'optical_tau{tau}ps'] = optical
        states[f'full_tau{tau}ps'] = full
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **states)
    emit(path.with_suffix('.json'), {'raw_sha256': raw_sha, 'state_kernel_sha256': kernel_hash,
                                   'cache_sha256': sha(path), 'native_samples': len(t)})
    return states, path


def eyes(t, current, values, result, stimulus, path):
    """80 deterministic validation snippets, centred on frozen training sample."""
    route = result['route']
    bps = 2 if route == 'C' else 1
    ui = result['rates']['symbol_UI_s']
    symbols = np.asarray(stimulus['symbols_C' if bps == 2 else 'symbols_N'])
    indices = np.linspace(576 // bps + 2, 4672 // bps - 3, 80).astype(int)
    offset = np.linspace(-ui, ui, 257)
    sample = indices[:, None] * ui + result['sampling']['delay_s'] + offset[None, :]
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, offset_ps=offset * 1e12,
                        current_uA=np.interp(sample, t, current) * 1e6,
                        output_uA=np.interp(sample, t, values) * 1e6,
                        expected_symbol=symbols[indices], symbol_indices=indices,
                        sample_delay_ps=result['sampling']['delay_s'] * 1e12,
                        thresholds_uA=np.asarray(result['proxy']['thresholds_uA']))


def analyze_precomputed(t, values, stimulus, route, tau_ps, stage, output_path):
    bypass = module(RXSOURCE, 'dynamic_rx_frozen_bypass')
    bypass.filter_trace = lambda tt, yy: (np.asarray(yy), np.asarray(yy))
    result = bypass.analyze(t, values, stimulus, route, 3.2)
    result['proxy'].update(diagnostic_stage=stage,
                           optical_tau_s=tau_ps * 1e-12 if stage in ('full', 'optical_only', 'phase_delay') else None,
                           rx_pole_Hz=1e9 if stage in ('full', 'rx_only', 'phase_delay') else None,
                           filter='Explicit exact native-PWL states passed to unchanged v2 analysis with filter_trace identity; no double filtering')
    result['limits'].append('Synthetic sensitivity; each diagnostic trains delay separately under the identical unchanged contract. Energy remains native electrical energy conditional on this uncoupled optical hypothesis.')
    emit(output_path, result)
    return result


def contract():
    return {
        'schema': 'microled-dynamic-rx-v1', 'receiver_source': str(RXSOURCE.relative_to(ROOT)),
        'receiver_sha256': sha(RXSOURCE), 'analysis_sha256': sha(Path(__file__)),
        'state_kernel_sha256': scope_hash(Path(__file__), STATE_FUNCTIONS),
        'response_evidence_contract': 'evidence/microled-dynamic-20261029/response-contract.json',
        'response_evidence_contract_sha256': sha(ROOT / 'evidence/microled-dynamic-20261029/response-contract.json'),
        'runtime': {'python': sys.version, 'numpy': np.__version__,
                    'command': 'build/layout/venv/bin/python scripts/microled_dynamic_v1/analyze.py'},
        'rates': {'net_Gbps': 3.2, 'line_Gbps': 3.7, 'NRZ_Gbaud': 3.7, 'PAM4_Gbaud': 1.85, 'eta': 32 / 37},
        'optical_tau_ps': list(TAUS_PS), 'RX_pole_Hz': 1e9,
        'thresholds_uA': {'NRZ': [62.5], 'PAM4': [37.5, 62.5, 87.5]},
        'acceptance': {'minimum_signed_amplitude_uA': 7.5, 'minimum_one_sided_time_ps': 100, 'training_and_validation_errors': 0},
        'training': {'scored_bits': 448, 'guard_bits': 64, 'validation_bits': 4096, 'delay_ps': [0, 8000, 5],
                     'selection': 'Maximize minimum signed expected-class threshold distance in absoluteuA. Among candidates within1pA of maximum, maximize minimum TRAINING absolute time margin; earliest exact tie wins. Validation never participates.'},
        'boundary': ['Current-equivalent unity-DC-gain optical/RX proxy, not optical watts or measured dynamics.',
                     'C=0 and tau=0 are ideal diagnostics, not physical candidates.',
                     'Native transistor energy and stress are independent electrical evidence; changing the offline optical tau does not rerun or physically couple the emitter.',
                     'Zero finite deterministic bit errors is not physical BER qualification.',
                     'Author-normalized S21 magnitude is not used to identify a transient or remove circuit/RX poles.'],
    }


def numerical_validation():
    """Independent analytic controls; numerical tolerances are not fit parameters."""
    t = np.r_[0., np.geomspace(20e-12, 4e-9, 3000)]
    u = np.r_[0., np.ones(len(t) - 1)]
    errors = []
    for a, b in [(0., TAU_RX_S), (25e-12, TAU_RX_S), (200e-12, 200e-12),
                 (200e-12, 200.000000001e-12)]:
        _, observed = cascade_pwl(t, u, a, b)
        def integral_step(q):
            q = np.maximum(q, 0.)
            if a == 0:
                return q - b * (-np.expm1(-q / b))
            if abs(a - b) < 1e-18:
                return q - 2 * a + (q + 2 * a) * np.exp(-q / a)
            return q - a - b + (a * a * np.exp(-q / a) - b * b * np.exp(-q / b)) / (a - b)
        expected = (integral_step(t) - integral_step(t - t[1])) / t[1]
        error = float(np.max(abs(expected - observed)))
        assert error < 1e-10
        errors.append({'tau_optical_ps': a * 1e12, 'tau_rx_ps': b * 1e12,
                       'analytic_ramp_max_absolute_error_unit_gain': error})
        for dc in (25e-6, 100e-6):
            x, y = cascade_pwl(t, np.full(len(t), dc), a, b)
            assert np.max(abs(x - dc)) == 0 and np.max(abs(y - dc)) == 0
    rng = np.random.default_rng(20261108)
    t = np.r_[0., np.cumsum(10 ** rng.uniform(-17, -10, 5000))]
    u = rng.uniform(20e-6, 105e-6, len(t))
    finer_t = np.sort(np.r_[t, (t[:-1] + t[1:]) / 2])
    finer_u = np.interp(finer_t, t, u)
    refinements = []
    for a, b in [(0., TAU_RX_S), (25e-12, TAU_RX_S), (75e-12, TAU_RX_S),
                 (200e-12, TAU_RX_S), (200e-12, 200e-12)]:
        x, y = cascade_pwl(t, u, a, b)
        fine_x, fine_y = cascade_pwl(finer_t, finer_u, a, b)
        error = float(max(np.max(abs(fine_x[::2] - x)), np.max(abs(fine_y[::2] - y))))
        assert error < 1e-15
        refinements.append({'tau_optical_ps': a * 1e12, 'tau_rx_ps': b * 1e12,
                            'exact_PWL_half_interval_max_error_A': error})
    frozen = module(RXSOURCE, 'dynamic_rx_numerical_reference')
    old_x, old_y = frozen.filter_trace(t, u)
    x, y = cascade_pwl(t, u, 200e-12)
    old_difference = float(max(np.max(abs(old_x - x)), np.max(abs(old_y - y))))
    assert old_difference < 1e-15
    return {'passed': True, 'analytic_fixtures': errors, 'PWL_subdivision': refinements,
            'old_200ps_filter_nonuniform_max_error_A': old_difference,
            'tolerances': {'analytic_unit_gain': 1e-10, 'PWL_subdivision_A': 1e-15,
                           'old_filter_A': 1e-15},
            'limits': 'Analytic/subdivision tests verify numerical state propagation only; circuit halfstep and native baseline metrics are separate checks.'}


def _record_base(source):
    case, metrics = source['case'], source['metrics']
    energy = metrics['total_energy']
    return {
        'case_name': case['name'], 'route': case['route'], 'group': case['group'],
        'corner': case.get('corner', 'typical'), 'temp_C': case.get('temp_C', 27),
        'vdd_V': case.get('vdd_V', 3.3), 'capacitance_fF': case['led_cap_F'] * 1e15,
        'steps_per_symbol': case['steps_per_symbol'],
        'device_voltage_pass': metrics['device_voltage_passed'],
        'max_body_forward_V': metrics['max_body_forward_V'],
        'device_pair_stress': metrics['stress'],
        'energy_positive_pJ_per_attempted_payload_bit': energy['positive_pJ_per_payload_bit'],
        'energy_returned_pJ_per_attempted_payload_bit': energy['returned_pJ_per_payload_bit'],
        'energy_net_pJ_per_attempted_payload_bit': energy['net_pJ_per_payload_bit'],
        'energy_ports_positive_pJ_per_attempted_payload_bit': {
            name: item['positive_J'] * 1e12 / 4096 for name, item in metrics['energy'].items()},
        'mean_LED_conduction_uA': metrics['mean_LED_current_A'] * 1e6,
        'result_path': source['result_path'], 'result_sha256': source['result_sha256'],
        'waveform_path': source['waveform_path'], 'raw_sha256': source['raw_sha256'],
        'gzip_sha256': source['gzip_sha256'], 'native_time': source['native_time'],
        'observables': source['observables'],
    }


def process_case(source, stimulus):
    base = _record_base(source)
    name = base['case_name']
    folder = WORK / 'cases' / name
    folder.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256((source['raw_sha256'] + source['result_sha256'] +
                                 sha(Path(__file__)) + sha(RXSOURCE)).encode()).hexdigest()
    summary_path = folder / 'summary.json'
    previous = None
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        if summary.get('fingerprint') == fingerprint:
            return summary
        if summary.get('records'):
            previous = summary['records'][0]
    assert sha(ROOT / source['result_path']) == source['result_sha256'], 'Electrical result hash drift'
    waveform = ROOT / source['waveform_path']
    assert sha(waveform) == source['gzip_sha256'], 'Electrical gzip hash drift'
    with gzip.open(waveform, 'rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == source['raw_sha256'], 'Native waveform hash drift'
    vectors = source['metadata']['vectors']
    trace = np.loadtxt(waveform, skiprows=1, usecols=(0, vectors['iled_cond']))
    t, current = trace[:, 0], trace[:, 1]
    states, cache_path = state_cache(t, current, source['raw_sha256'], previous=previous)
    selected = (base['corner'] == 'typical' and base['steps_per_symbol'] == 40 and
                any(abs(base['capacitance_fF'] - c) < 1e-8 for c in (10, 200)))
    requests = [('full', tau, t, states[f'full_tau{tau}ps']) for tau in TAUS_PS]
    if selected:
        requests += [('electrical', 0, t, current), ('rx_only', 0, t, states['rx_only'])]
        requests += [('optical_only', tau, t, states[f'optical_tau{tau}ps']) for tau in TAUS_PS]
        # A true time shift preserves the complete PWL curve and thresholds;
        # reinterpolating on the original grid would introduce artificial loss.
        requests += [('phase_delay', 75, np.r_[0., t + 100e-12],
                      np.r_[states['full_tau75ps'][0], states['full_tau75ps']])]
    records = []
    full_results = {}
    for stage, tau, local_t, values in requests:
        label = f'{stage}-tau{tau}ps'
        path = folder / (label + '.json')
        result = analyze_precomputed(local_t, values, stimulus, base['route'], tau, stage, path)
        if stage == 'full':
            full_results[tau] = result
        record = {**base, 'stage': stage, 'optical_tau_ps': tau,
                  'extra_pure_delay_ps': 100 if stage == 'phase_delay' else 0,
                  **compact_rx(result), 'analysis_path': str(path.relative_to(ROOT)),
                  'analysis_sha256': sha(path), 'state_cache': str(cache_path.relative_to(ROOT)),
                  'state_cache_sha256': sha(cache_path)}
        record['combined_electrical_and_RX_screen_pass'] = bool(record['passed'] and record['device_voltage_pass'])
        record['ideal_limit_diagnostic'] = bool(base['capacitance_fF'] == 0 or tau == 0)
        if base['corner'] == 'typical' and base['steps_per_symbol'] == 40:
            eye_path = WORK / 'eyes' / name / (label + '.npz')
            eyes(local_t, current if stage != 'phase_delay' else np.r_[current[0], current],
                 values, result, stimulus, eye_path)
            record['eye_path'] = str(eye_path.relative_to(ROOT))
            record['eye_sha256'] = sha(eye_path)
        records.append(record)
    old = source['metrics']['receiver']
    old_compact, new_compact = compact_rx(old), compact_rx(full_results[200])
    for field in ('bit_errors', 'bit_count', 'symbol_errors', 'passed', 'checks', 'delay_ps', 'training_bit_errors'):
        assert old_compact[field] == new_compact[field], ('Frozen 200ps receiver reproduction', name, field)
    for field in ('min_signed_margin_uA', 'mean_signed_margin_uA', 'min_time_margin_ps'):
        assert abs(old_compact[field] - new_compact[field]) < 1e-7, ('Frozen baseline numerical tolerance', name, field)
    phase = None
    if selected:
        normal = next(r for r in records if r['stage'] == 'full' and r['optical_tau_ps'] == 75)
        delayed = next(r for r in records if r['stage'] == 'phase_delay')
        phase = {'case_name': name, 'pure_delay_ps': 100,
                 'training_delay_shift_ps': delayed['delay_ps'] - normal['delay_ps'],
                 'signed_margin_delta_uA': delayed['min_signed_margin_uA'] - normal['min_signed_margin_uA'],
                 'time_margin_delta_ps': delayed['min_time_margin_ps'] - normal['min_time_margin_ps'],
                 'bit_error_delta': delayed['bit_errors'] - normal['bit_errors'],
                 'pass_unchanged': delayed['passed'] == normal['passed'],
                 'interpretation': 'A uniform100ps pure delay is absorbed by the shared0..8ns training search when its optimum remains inside the budget. This does not identify missing dispersive phase or a physical transient.'}
        assert abs(phase['training_delay_shift_ps'] - 100) < 1e-8
        assert abs(phase['signed_margin_delta_uA']) < 1e-7
        assert abs(phase['time_margin_delta_ps']) < 1e-6
        assert phase['bit_error_delta'] == 0 and phase['pass_unchanged']
    summary = {'fingerprint': fingerprint, 'records': records,
               'baseline_200ps_reproduction': {'case_name': name, 'passed': True,
                                             'legacy': old_compact, 'new': new_compact},
               'pure_delay_sensitivity': phase}
    emit(summary_path, summary)
    return summary


def halfstep_checks(records):
    out = []
    for fine in records:
        if fine['stage'] != 'full' or fine['steps_per_symbol'] != 80:
            continue
        coarse = next((r for r in records if r['route'] == fine['route'] and
                       r['stage'] == 'full' and r['steps_per_symbol'] == 40 and
                       r['corner'] == fine['corner'] and
                       abs(r['capacitance_fF'] - fine['capacitance_fF']) < 1e-8 and
                       r['optical_tau_ps'] == fine['optical_tau_ps']), None)
        if coarse is None:
            continue
        tau = fine['optical_tau_ps']
        with np.load(ROOT / coarse['state_cache']) as cd, np.load(ROOT / fine['state_cache']) as fd:
            ct, ft = cd['time_s'], fd['time_s']
            full_delta = fd[f'full_tau{tau}ps'] - np.interp(ft, ct, cd[f'full_tau{tau}ps'])
            optical_delta = fd[f'optical_tau{tau}ps'] - np.interp(ft, ct, cd[f'optical_tau{tau}ps'])
            state_delta = {'full_max_abs_uA': float(np.max(abs(full_delta)) * 1e6),
                           'full_rms_uA': float(np.sqrt(np.mean(full_delta ** 2)) * 1e6),
                           'optical_max_abs_uA': float(np.max(abs(optical_delta)) * 1e6),
                           'comparison': 'S40 state linearly interpolated onto S80 native grid; full-frame max and native-sample RMS, not a time-weighted error norm.'}
        out.append({'coarse_case': coarse['case_name'], 'fine_case': fine['case_name'],
                    'route': fine['route'], 'capacitance_fF': fine['capacitance_fF'],
                    'optical_tau_ps': fine['optical_tau_ps'],
                    'amplitude_delta_uA': fine['min_signed_margin_uA'] - coarse['min_signed_margin_uA'],
                    'time_delta_ps': fine['min_time_margin_ps'] - coarse['min_time_margin_ps'],
                    'delay_delta_ps': fine['delay_ps'] - coarse['delay_ps'],
                    'bit_error_delta': fine['bit_errors'] - coarse['bit_errors'],
                    'pass_unchanged': fine['passed'] == coarse['passed'],
                    'native_state_difference': state_delta,
                    'energy_positive_delta_percent': 100 * (fine['energy_positive_pJ_per_attempted_payload_bit'] /
                                                           coarse['energy_positive_pJ_per_attempted_payload_bit'] - 1),
                    'scope': 'Native ngspice maximum-step refinement; same circuit and fixed RX training/threshold contract. Deltas remain visible even when both screens fail.'})
    return out


def family_data():
    frequency = np.geomspace(1e6, 20e9, 180)
    data = []
    for tau in TAUS_PS:
        optical = 1 / (1 + 2j * math.pi * frequency * tau * 1e-12)
        full = optical / (1 + 1j * frequency / 1e9)
        data.append({'tau_ps': tau, 'frequency_Hz': frequency.tolist(),
                     'optical_magnitude_dB': (20 * np.log10(abs(optical))).tolist(),
                     'optical_phase_deg': np.angle(optical, deg=True).tolist(),
                     'optical_plus_RX_magnitude_dB': (20 * np.log10(abs(full))).tolist(),
                     'optical_plus_RX_phase_deg': np.angle(full, deg=True).tolist()})
    return {'schema': 'microled-dynamic-synthetic-family-v1', 'members': data,
            'boundary': 'Analytic unity-gain first-order optical sensitivity family with fixed1GHz RX. Not a fit to S21; electrical RC remains native in each circuit conduction trace.'}


def source_is_transient(source):
    """DC and failed circuit records remain electrical evidence, outside RX frames."""
    return bool(source['case'].get('kind', 'transient') == 'transient' and
                source.get('simulation_ok') and not source.get('analysis_error'))


def ideal_waveform(route, stimulus, step_ps=5.):
    """Complete fixed frame with ideal25..100uA conduction and20ps linear edges."""
    pam4 = route == 'C'
    symbols = np.asarray(stimulus['symbols_C' if pam4 else 'symbols_N'])
    ui = (2 if pam4 else 1) / 3.7e9
    duration = 4736 / 3.7e9
    levels = (25 + symbols * (25 if pam4 else 75)) * 1e-6
    boundaries = np.arange(1, len(symbols)) * ui
    t = np.unique(np.r_[np.arange(0, duration, step_ps * 1e-12), boundaries,
                        boundaries + 20e-12, duration])
    index = np.minimum(np.floor(t / ui).astype(int), len(symbols) - 1)
    age = t - index * ui
    previous = levels[np.maximum(index - 1, 0)]
    current = previous + (levels[index] - previous) * np.clip(age / 20e-12, 0., 1.)
    return t, current


def ideal_controls(stimulus):
    folder = WORK / 'ideal-conduction-controls'
    fingerprint = hashlib.sha256((sha(Path(__file__)) + sha(RXSOURCE) +
                                 repr((TAUS_PS, TAU_RX_S))).encode()).hexdigest()
    summary_path = folder / 'summary.json'
    if summary_path.exists():
        prior = json.loads(summary_path.read_text())
        if prior.get('fingerprint') == fingerprint:
            return prior
    records = []
    for route, modulation in [('A', 'NRZ'), ('C', 'PAM4')]:
        grid_results = {}
        for step_ps in (5., 2.5):
            t, current = ideal_waveform(route, stimulus, step_ps)
            raw_sha = hashlib.sha256(t.tobytes() + current.tobytes()).hexdigest()
            states, _ = state_cache(t, current, raw_sha)
            for tau in TAUS_PS:
                path = folder / modulation / f'step{step_ps:g}ps-tau{tau}ps.json'
                result = analyze_precomputed(t, states[f'full_tau{tau}ps'], stimulus, route,
                                             tau, 'full', path)
                result['limits'].append('Ideal conduction waveform with20ps edges, no transistor/load/energy. Diagnostic feasibility control only.')
                emit(path, result)
                grid_results[(step_ps, tau)] = result
                if step_ps == 5.:
                    eye_path = folder / modulation / f'tau{tau}ps-eye.npz'
                    eyes(t, current, states[f'full_tau{tau}ps'], result, stimulus, eye_path)
                    records.append({'control': 'ideal_conduction_20ps_edge', 'modulation': modulation,
                                    'optical_tau_ps': tau, **compact_rx(result),
                                    'energy_pJ_per_bit': None, 'candidate': False,
                                    'analysis_path': str(path.relative_to(ROOT)), 'analysis_sha256': sha(path),
                                    'eye_path': str(eye_path.relative_to(ROOT)), 'eye_sha256': sha(eye_path),
                                    'boundary': 'Ideal conduction current25/100uA NRZ or25/50/75/100uA Gray PAM4, fixed20ps linear edges, same complete4736bit frame and same1GHz RX/threshold/training contract. Excludes circuit and optical evidence and all energy ranking.'})
        for record in records:
            if record['modulation'] != modulation:
                continue
            tau = record['optical_tau_ps']
            coarse, fine = compact_rx(grid_results[(5., tau)]), compact_rx(grid_results[(2.5, tau)])
            record['PWL_grid_halfstep'] = {
                'coarse_step_ps': 5., 'fine_step_ps': 2.5,
                'amplitude_delta_uA': fine['min_signed_margin_uA'] - coarse['min_signed_margin_uA'],
                'time_delta_ps': fine['min_time_margin_ps'] - coarse['min_time_margin_ps'],
                'delay_delta_ps': fine['delay_ps'] - coarse['delay_ps'],
                'bit_error_delta': fine['bit_errors'] - coarse['bit_errors'],
                'pass_unchanged': fine['passed'] == coarse['passed']}
    summary = {'fingerprint': fingerprint, 'records': records,
               'analysis_source_sha256': sha(Path(__file__)), 'receiver_sha256': sha(RXSOURCE)}
    emit(summary_path, summary)
    return summary


def run(only=''):
    WORK.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    archive = WORK / 'execution-sources' / sha(Path(__file__))
    archive.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), archive / 'analyze.py')
    registry_path = EVIDENCE / 'electrical-registry.json'
    registry = json.loads(registry_path.read_text())
    stimulus_path = ELECTRICAL / 'stimulus.json'
    stimulus = json.loads(stimulus_path.read_text())
    assert sha(ELECTRICAL / 'inputs/receiver.py') == sha(RXSOURCE), 'Frozen receiver source mismatch'
    assert stimulus == module(RXSOURCE, 'dynamic_rx_stimulus_reference').make_stimulus()
    summaries, failures = [], []
    for source in registry['records']:
        if not source_is_transient(source):
            continue
        if only and only not in source['case']['name']:
            continue
        try:
            summary = process_case(source, stimulus)
            summaries.append(summary)
            print(json.dumps({'case': source['case']['name'], 'records': len(summary['records'])}), flush=True)
        except Exception as error:
            path = WORK / 'failed-analysis' / (source['case']['name'] + '-' +
                   datetime.datetime.now().strftime('%Y%m%dT%H%M%S') + '.log')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(traceback.format_exc())
            failures.append({'case': source['case']['name'], 'error': repr(error),
                             'log': str(path.relative_to(ROOT)), 'log_sha256': sha(path)})
            print(json.dumps(failures[-1]), file=sys.stderr, flush=True)
    records = [record for summary in summaries for record in summary['records']]
    numerical = numerical_validation()
    ideal = ideal_controls(stimulus)
    plan = json.loads((ELECTRICAL / 'plan.json').read_text())
    planned_transients = {case['name'] for case in plan if case.get('kind', 'transient') == 'transient'}
    report = {'created': datetime.datetime.now().astimezone().isoformat(), 'contract': contract(),
              'electrical_registry_sha256': sha(registry_path), 'stimulus_sha256': sha(stimulus_path),
              'records': records, 'electrical_dc': registry['dc'],
              'ideal_conduction_controls': ideal['records'],
              'input_scope': {'registry_records': len(registry['records']),
                              'successful_transient_records': sum(source_is_transient(s) for s in registry['records']),
                              'DC_records_excluded_from_RX': sum(s['case'].get('kind') == 'dc' for s in registry['records']),
                              'planned_transient_records': len(planned_transients),
                              'DC_table_retained': True},
              'electrical_dc_capacitance_checks': registry['dc_capacitance_checks'],
              'missing_electrical': registry['missing'], 'electrical_failures': registry['failures'],
              'missing_transients': [name for name in registry['missing'] if name in planned_transients],
              'missing_DC': [name for name in registry['missing'] if name not in planned_transients],
              'analysis_failures': failures, 'numerical_validation': numerical,
              'baseline_200ps_reproduction': [s['baseline_200ps_reproduction'] for s in summaries],
              'pure_delay_sensitivity': [s['pure_delay_sensitivity'] for s in summaries if s['pure_delay_sensitivity']],
              'halfstep_checks': halfstep_checks(records),
              'stage_status': 'complete' if not registry['missing'] and not failures and not registry['failures'] and not only else 'partial',
              'selection_filter': only or None}
    suffix = '-selected' if only else ''
    emit(EVIDENCE / ('rx-summary' + suffix + '.json'), report)
    emit(EVIDENCE / 'rx-contract.json', contract())
    emit(EVIDENCE / 'rx-family.json', family_data())
    emit(EVIDENCE / ('rx-validation' + suffix + '.json'), {k: report[k] for k in
         ('numerical_validation', 'baseline_200ps_reproduction', 'pure_delay_sensitivity',
          'halfstep_checks', 'analysis_failures', 'electrical_failures', 'missing_electrical',
          'missing_transients', 'missing_DC', 'input_scope', 'ideal_conduction_controls', 'stage_status')})
    columns = ['case_name', 'route', 'corner', 'temp_C', 'vdd_V', 'capacitance_fF',
               'steps_per_symbol', 'stage', 'optical_tau_ps', 'extra_pure_delay_ps',
               'min_signed_margin_uA', 'min_time_margin_ps', 'delay_ps', 'bit_errors',
               'training_bit_errors', 'symbol_errors', 'passed', 'device_voltage_pass',
               'combined_electrical_and_RX_screen_pass', 'ideal_limit_diagnostic',
               'energy_positive_pJ_per_attempted_payload_bit',
               'energy_returned_pJ_per_attempted_payload_bit',
               'energy_net_pJ_per_attempted_payload_bit', 'mean_LED_conduction_uA']
    with (EVIDENCE / ('rx-matrix' + suffix + '.csv')).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(records)
    print(json.dumps({'records': len(records), 'case_count': len(summaries),
                      'analysis_failures': failures, 'missing_electrical': len(registry['missing']),
                      'stage_status': report['stage_status']}), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', default='')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(numerical_validation(), indent=2))
    else:
        report = run(args.only)
        if report['analysis_failures']:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
