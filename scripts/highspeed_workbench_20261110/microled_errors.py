#!/usr/bin/env python3
"""Localize 3.2 Gb/s MicroLED failures with fixed-frame receiver controls."""
import argparse
import json
import math
from pathlib import Path

import numpy as np

from replay import ROOT, module, sha

STAGE = Path('build/highspeed-workbench-20261110')
HISTORICAL = Path('build/microled-dynamic-v1/electrical/run-r1')
EVIDENCE = ROOT / 'evidence/highspeed-workbench-20261110'
DYNAMICS = ROOT / 'scripts/microled_dynamic_v1/analyze.py'
RECEIVER = ROOT / 'scripts/fair_driver_v1/receiver_equal_latency_v2.py'
ROUTES = ('A', 'B', 'C')


def native_trace(route, cap_fF):
    """Use fresh 200 fF traces and the frozen 10 fF sensitivity traces."""
    case_name = f'TT-{route}-C{cap_fF}fF-S40'
    if cap_fF == 200:
        base = STAGE / f'replay/tt-20261110-r2/{route}'
    else:
        base = HISTORICAL
    case_path = base / 'cases' / case_name
    waveform = ROOT / case_path / 'waveform.dat.gz'
    result_path = ROOT / case_path / 'result.json'
    result = json.loads(result_path.read_text())
    observed_hash = sha(waveform)
    if not result['simulation_ok'] or observed_hash != result['gzip_sha256']:
        raise ValueError(f'Missing or mismatched frozen native trace: {waveform}')
    time, current = np.loadtxt(waveform, skiprows=1, usecols=(0, 1)).T
    return time, current, {
        'waveform': str(case_path / waveform.name),
        'waveform_gzip_sha256': observed_hash,
        'waveform_native_sha256': result['raw_sha256'],
        'result_sha256': sha(result_path),
        'case_name': case_name,
        'sample_count': len(time),
    }


def static_threshold_train_bound(samples, truth):
    """Optimistic separability bound with free static thresholds and one delay.

    If max(min adjacent gap) < 0 over the allowed grid, even thresholds fitted
    to this training set cannot separate its classes at any permitted delay.
    A nonnegative bound is neither a validation result nor a margin guarantee.
    """
    class_samples = [samples[:, truth == level] for level in np.unique(truth)]
    gap = np.column_stack([
        upper.min(axis=1) - lower.max(axis=1)
        for lower, upper in zip(class_samples, class_samples[1:])
    ])
    best = int(gap.min(axis=1).argmax())
    return {
        'delay_index': best,
        'adjacent_class_gaps_uAeq': gap[best].tolist(),
        'best_min_gap_uAeq': float(gap[best].min()),
        'separable_training_classes_on_grid': bool(gap[best].min() > 0),
    }


def alternative_selection(time, received, stimulus, route, receiver):
    """Train a single delay on both margins; never train on validation data."""
    pam4 = route == 'C'
    width = 2 if pam4 else 1
    thresholds = np.array([37.5, 62.5, 87.5] if pam4 else [62.5])
    ranges = stimulus['ranges_bits']
    symbols = np.asarray(stimulus['symbols_C' if pam4 else 'symbols_N'])
    train_idx = np.arange(*[bit // width for bit in ranges['training_scoring']])
    val_idx = np.arange(*[bit // width for bit in ranges['validation']])
    expected_train, expected = symbols[train_idx], symbols[val_idx]
    bit_ui = 1 / 3.7e9
    ui = width * bit_ui
    delays_ps = np.arange(0, receiver.DELAY_BUDGET_PS + 1, receiver.DELAY_GRID_PS)
    train_start = ranges['training_scoring'][0] * bit_ui
    train_stop = ranges['validation'][0] * bit_ui
    prefix = time < train_stop
    train_t, train_y = time[prefix], received[prefix] * 1e6
    when = train_idx * ui + delays_ps[:, None] * 1e-12
    if when.max() >= train_t[-1]:
        raise ValueError('Training or its margin search touches validation')
    samples = np.interp(when, train_t, train_y)
    amplitude = receiver._signed_margin(samples, expected_train, thresholds)
    train_amp = amplitude.min(axis=1)
    min_time = np.full(len(delays_ps), np.inf)
    train_end = float(train_t[-1])
    events_by_level = receiver._crossing_events(train_t, train_y, thresholds)
    for level, events in enumerate(events_by_level):
        columns = expected_train == level
        timestamps = when[:, columns]
        if len(events):
            pos = np.searchsorted(events, timestamps, side='right')
            previous = np.where(pos > 0, events[np.maximum(pos - 1, 0)], train_start)
            following = np.where(pos < len(events), events[np.minimum(pos, len(events) - 1)],
                                 train_end)
        else:
            previous, following = train_start, train_end
        left = timestamps - np.maximum(previous, train_start)
        right = np.minimum(following, train_end) - timestamps
        distances = np.where(amplitude[:, columns] > 0, np.minimum(left, right), 0)
        min_time = np.minimum(min_time, distances.min(axis=1) * 1e12)
    min_time = np.maximum(min_time, 0)
    training_joint = np.minimum(train_amp / 7.5, min_time / 100)
    chosen = int(training_joint.argmax())
    delay_ps = int(delays_ps[chosen])
    train_horizontal = receiver._horizontal(
        train_t, train_y, when[chosen], samples[chosen], expected_train, thresholds,
        train_start, train_end, ui, bit_ui, events_by_level=events_by_level)
    if abs(train_horizontal['min_ps'] - min_time[chosen]) > 1e-8:
        raise AssertionError('Vectorized timing margin disagrees with frozen v2')
    train_decisions = receiver._decode(samples[chosen], thresholds)
    train_errors = int(np.count_nonzero(
        receiver._bits(train_decisions, pam4) != receiver._bits(expected_train, pam4)))
    values_uA = received * 1e6
    sample_t = val_idx * ui + delay_ps * 1e-12
    validation = np.interp(sample_t, time, values_uA)
    decoded = receiver._decode(validation, thresholds)
    bit_errors = int(np.count_nonzero(
        receiver._bits(decoded, pam4) != receiver._bits(expected, pam4)))
    min_amp = float(receiver._signed_margin(validation, expected, thresholds).min())
    min_ps = receiver._horizontal(
        time, values_uA, sample_t, validation, expected, thresholds,
        0, len(stimulus['bits']) * bit_ui, ui, bit_ui)['min_ps']
    bound = static_threshold_train_bound(samples, expected_train)
    bound['delay_ps'] = int(delays_ps[bound.pop('delay_index')])
    return bound, {
        'delay_ps': delay_ps,
        'training_grid_points_meeting_both_margins': int(np.count_nonzero(training_joint >= 1)),
        'training_bit_errors': train_errors,
        'training_min_signed_margin_uAeq': float(train_amp[chosen]),
        'training_min_time_margin_ps': float(min_time[chosen]),
        'validation_bit_errors': bit_errors,
        'validation_min_signed_margin_uAeq': min_amp,
        'validation_min_time_margin_ps': min_ps,
        'joint_screen': bool(train_errors == 0 and bit_errors == 0
                             and min_amp >= 7.5 and min_ps >= 100),
    }


def evaluate(time, current, stimulus, route, tau_ps, rx_GHz, dynamics, receiver):
    _, received = dynamics.cascade_pwl(
        time, current, tau_ps * 1e-12, 1 / (2 * math.pi * rx_GHz * 1e9))
    result = receiver.analyze(time, received, stimulus, route, 3.2)
    separation, alternate = alternative_selection(time, received, stimulus, route, receiver)
    return {
        'optical_tau_ps': tau_ps,
        'rx_GHz': rx_GHz,
        **dynamics.compact_rx(result),
        'static_threshold_train_bound': separation,
        'joint_margin_training_diagnostic': alternate,
    }


def charge_budget():
    # Read the audited DC I–V interpolation rather than transcribing its numbers.
    source = ROOT / 'evidence/fair-driver-v1/load-dynamics.json'
    data = json.loads(source.read_text())
    voltage = data['step_100to25']['VF_delta_V']
    half_ui_s = 0.5 / 3.7e9
    return {
        'basis': str(source.relative_to(ROOT)), 'sha256': sha(source),
        'nominal_levels_uA': [25, 100], 'vf_swing_V': voltage,
        'hypothetical_full_swing_budget_ps': half_ui_s * 1e12,
        'controls': [
            {'capacitance_fF': cap, 'delta_charge_fC': cap * voltage,
             'mean_absolute_displacement_current_uA': cap * 1e-9 * voltage / half_ui_s}
            for cap in (200, 10)],
        'scope': 'Q=C*dV over a hypothetical half-NRZ-UI full-swing budget. '
                 'This estimates only the average magnitude of capacitive current.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=EVIDENCE / 'microled-errors-controls.json')
    args = parser.parse_args()
    dynamics = module(DYNAMICS, 'microled_error_dynamics')
    receiver = module(RECEIVER, 'microled_error_receiver')
    receiver.filter_trace = lambda _, samples: (samples, samples)
    stimulus_path = ROOT / HISTORICAL / 'stimulus.json'
    stimulus = json.loads(stimulus_path.read_text())
    rows = []
    for route in ROUTES:
        for cap_fF, variants in (
            (200, [(200, 1), (200, 5), (25, 5)]),
            (10, [(25, 1), (25, 5)]),
        ):
            time, current, source = native_trace(route, cap_fF)
            for tau_ps, rx_GHz in variants:
                row = {'route': route, 'input': 'native', 'capacitance_fF': cap_fF,
                       'source': source, **evaluate(time, current, stimulus, route,
                                                   tau_ps, rx_GHz, dynamics, receiver)}
                rows.append(row)
                print(route, cap_fF, tau_ps, rx_GHz, row['bit_errors'], row['passed'], flush=True)
    for route in ('A', 'C'):
        time, current = dynamics.ideal_waveform(route, stimulus)
        for tau_ps, rx_GHz in [(200, 1), (200, 5), (75, 1), (25, 5)]:
            row = {'route': 'NRZ' if route == 'A' else 'PAM4',
                   'input': 'ideal_20ps_conduction', 'capacitance_fF': None,
                   **evaluate(time, current, stimulus, route, tau_ps, rx_GHz, dynamics, receiver)}
            rows.append(row)
            print(row['route'], 'ideal', tau_ps, rx_GHz, row['bit_errors'], row['passed'], flush=True)
    # An independent record pins the initial 3-way result before the new controls.
    summary_path = EVIDENCE / 'replay-summary.json'
    baseline = json.loads(summary_path.read_text())['routes']
    for row in rows:
        if (row['capacitance_fF'], row['optical_tau_ps'], row['rx_GHz']) == (200, 200, 1):
            old = baseline[row['route']]['metrics']['receiver']
            if (row['bit_errors'] != old['errors']
                    or abs(row['min_signed_margin_uA'] - old['signed_amplitude_margin']) > 1e-4):
                raise AssertionError('Baseline receiver did not reproduce')
    payload = {
        'schema': 'microled-nrz-pam4-failure-controls-v1',
        'scope': 'Native conduction waveform reuse and explicit diagnostic pole/ideal input changes, '
                 'not a circuit change, fabricated device, measured optical RX, FEC, or BER.',
        'sources_sha256': {str(p.relative_to(ROOT)): sha(p) for p in (
            Path(__file__), DYNAMICS, RECEIVER, stimulus_path, summary_path)},
        'conditions': {'rate_net_Gbps': 3.2, 'rate_line_Gbps': 3.7,
                       'scored_training_bits': 448, 'scored_validation_bits': 4096,
                       'training_only_fixed_delay_scan_ps': [0, 8000, 5],
                       'alternative_delay_selection': 'Maximize the smaller of training amplitude/7.5uAeq '
                                                      'and training time/100ps, earliest exact tie. '
                                                      'Fixed thresholds and a common disjoint validation segment.',
                       'min_signed_margin_uAeq': 7.5, 'min_time_margin_ps': 100,
                       'thresholds_uAeq': {'NRZ': [62.5], 'PAM4': [37.5, 62.5, 87.5]},
                       'ideal_edges_ps': 20},
        'charge_budget': charge_budget(),
        'rows': rows,
    }
    dynamics.emit(args.output, payload)


if __name__ == '__main__':
    main()
