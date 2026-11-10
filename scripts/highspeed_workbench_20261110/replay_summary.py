#!/usr/bin/env python3
"""Summarize replay receipts and extract short teaching traces from native waveforms."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np

from replay import BUILD, ROOT, VCSEL_ANALYSIS, module, read_json, relative, sha


EVIDENCE = ROOT / 'evidence/highspeed-workbench-20261110'
ROUTES = ('A', 'B', 'C', 'VCSEL')
TRACE_FIELDS = ('route', 'relative_time_ns', 'expected_symbol', 'emitter_current_mA',
                'optical_proxy', 'receiver_proxy', 'proxy_unit')
BITS_PER_FRAME = 4736
PAYLOAD_BITS = 4096
BIT_UI_S = 1 / 3.7e9
TRACE_START_BIT = 576
TRACE_SAMPLES_PER_SYMBOL = 48
TRACE_SYMBOLS = 12


def compact_receiver(receiver, unit, thresholds):
    return {
        'errors': receiver['validation']['bit_errors'],
        'symbol_errors': receiver['validation']['symbol_errors'],
        'compared_bits': receiver['validation']['bit_count'],
        'signed_amplitude_margin': receiver['validation']['decision_distance_min_uA'],
        'signed_amplitude_margin_unit': unit,
        'minimum_one_sided_time_margin_ps': receiver['horizontal_margin']['min_ps'],
        'sampling_delay_ps': receiver['sampling']['delay_s'] * 1e12,
        'thresholds_uAeq': thresholds,
        'checks': receiver['checks'],
        'passed': receiver['passed'],
    }


def positive_energy_by_source(port_ledger):
    return {port: energy['positive_J'] * 1e12 / PAYLOAD_BITS
            for port, energy in port_ledger.items()}


def micro_metrics(result):
    metrics = result['metrics']
    receiver = metrics['receiver']
    energy = metrics['total_energy']
    current = result['observables']['iled_cond']
    return {
        'modulation': 'PAM4' if result['case']['route'] == 'C' else 'NRZ',
        'symbol_rate_Gbaud': receiver['rates']['symbol_Gbaud'],
        'source_port_positive_pJ_per_offered_payload_bit': positive_energy_by_source(metrics['energy']),
        'positive_pJ_per_offered_payload_bit': energy['positive_pJ_per_payload_bit'],
        'returned_pJ_per_offered_payload_bit': energy['returned_pJ_per_payload_bit'],
        'net_pJ_per_offered_payload_bit': energy['net_pJ_per_payload_bit'],
        'current_min_mA': current['min'] * 1e3,
        'current_max_mA': current['max'] * 1e3,
        'max_native_step_ps': result['native_time']['max_step_ps'],
        'native_samples': result['native_time']['rows'],
        'device_voltage_screen_passed': metrics['device_voltage_passed'],
        'receiver': compact_receiver(receiver, 'µAeq (MicroLED v2)', receiver['proxy']['thresholds_uA']),
    }


def laser_metrics(result, analysis, normalization):
    energy = result['total_energy']
    receiver = compact_receiver(analysis['receiver'], 'µAeq (VCSEL v3)', [62.5])
    receiver['thresholds_mW'] = [500 * (normalization['low_W'] + normalization['high_W'])]
    return {
        'modulation': 'NRZ',
        'symbol_rate_Gbaud': 3.7,
        'source_port_positive_pJ_per_offered_payload_bit': positive_energy_by_source(result['energy_by_port']),
        'positive_pJ_per_offered_payload_bit': energy['positive_pJ_per_offered_payload_bit'],
        'returned_pJ_per_offered_payload_bit': energy['returned_J'] * 1e12 / PAYLOAD_BITS,
        'net_pJ_per_offered_payload_bit': energy['net_pJ_per_offered_payload_bit'],
        'current_min_mA': result['current_range_mA'][0],
        'current_max_mA': result['current_range_mA'][1],
        'max_native_step_ps': result['max_timestep_ps'],
        'native_samples': result['sample_count'],
        'device_voltage_screen_passed': result['device_screen_passed'],
        'receiver': receiver,
        'optical_margin_min_mW': analysis['optical_margin_min_mW'],
        'combined_screen_passed': analysis['combined_screen_passed'],
    }


def trace_grid(stimulus, symbol_width_bits):
    symbol_ui = BIT_UI_S * symbol_width_bits
    indices = np.arange(TRACE_SYMBOLS * TRACE_SAMPLES_PER_SYMBOL)
    symbol_start = TRACE_START_BIT // symbol_width_bits
    symbols = stimulus['symbols_C' if symbol_width_bits == 2 else 'symbols_N']
    relative_t = indices * (symbol_ui / TRACE_SAMPLES_PER_SYMBOL)
    expected = np.asarray(symbols)[symbol_start + indices // TRACE_SAMPLES_PER_SYMBOL]
    return relative_t, TRACE_START_BIT * BIT_UI_S + relative_t, expected


def transition_errors(stimulus, receiver, route):
    width = 2 if route == 'C' else 1
    symbols = stimulus['symbols_C' if width == 2 else 'symbols_N']
    start, end = [index // width for index in stimulus['ranges_bits']['validation']]
    transitions = [(symbols[index - 1], symbols[index]) for index in range(start, end)]
    occurrences = Counter(transitions)
    errors = Counter(transitions[index] for index in receiver['validation']['error_symbol_offsets'])
    return {
        f'{source}->{target}': {'symbol_errors': errors[source, target], 'opportunities': count}
        for (source, target), count in sorted(occurrences.items())
    }


def micro_wave(stimulus, route, native_t, current, optical, received):
    rel_t, query, expected = trace_grid(stimulus, 2 if route == 'C' else 1)
    for time, symbol, led, light, out in zip(
        rel_t, expected,
        np.interp(query, native_t, current) * 1e3,
        np.interp(query, native_t, optical) * 1e6,
        np.interp(query, native_t, received) * 1e6,
        strict=True,
    ):
        yield route, time * 1e9, symbol, led, light, out, 'uAeq_microled_v2'


def micro_analysis(work, case_dir, route):
    stimulus = read_json(work / 'stimulus.json')
    native_t, current = np.loadtxt(case_dir / 'waveform.dat.gz', skiprows=1, usecols=(0, 1)).T
    rx = module(work / 'inputs/receiver.py', 'microled_frozen_rx_trace')
    optical, received = rx.filter_trace(native_t, current)
    rx.filter_trace = lambda _, samples: (samples, samples)
    bypass = rx.analyze(native_t, current, stimulus, route, 3.2)
    diagnostic = compact_receiver(bypass, 'µA (conduction-current diagnostic)',
                                  bypass['proxy']['thresholds_uA'])
    waveform = micro_wave(stimulus, route, native_t, current, optical, received)
    return diagnostic, waveform


def laser_wave(case_dir, analysis_dir):
    stimulus = read_json(case_dir / 'stimulus.json')
    rel_t, query, expected = trace_grid(stimulus, 1)
    with np.load(analysis_dir / 'plot-data.npz') as trace:
        plot_time = trace['trace_t_s']
        for time, symbol, led, light, out in zip(
            rel_t, expected,
            np.interp(query, plot_time, trace['trace_current_A']) * 1e3,
            np.interp(query, plot_time, trace['trace_optical_W']) * 1e3,
            np.interp(query, plot_time, trace['trace_rx_W']) * 1e3,
            strict=True,
        ):
            yield 'VCSEL', time * 1e9, symbol, led, light, out, 'mW_vcsel_graph_proxy'


def case_summary(work, route):
    receipt = read_json(work / 'replay-receipt.json')
    previous_dir = ROOT / receipt['old_case']
    case_dir = ROOT / receipt['new_case']
    old_result = read_json(previous_dir / 'result.json')
    new_result = read_json(case_dir / 'result.json')
    assert receipt['simulation_ok'] and not receipt['analysis_error'], route
    assert sha(case_dir / 'result.json') == receipt['new_result_sha256'], route
    assert sha(previous_dir / 'result.json') == receipt['old_result_sha256'], route
    electrical_only = None
    if route == 'VCSEL':
        analysis_dir = case_dir / f'analysis-{VCSEL_ANALYSIS}'
        analysis = read_json(analysis_dir / 'result.json')
        old_analysis = read_json(previous_dir / f'analysis-{VCSEL_ANALYSIS}' / 'result.json')
        plan = read_json(analysis_dir / 'plan.json')
        old_plan = read_json(previous_dir / f'analysis-{VCSEL_ANALYSIS}' / 'plan.json')
        metrics = laser_metrics(new_result, analysis, plan['normalization'])
        previous = laser_metrics(old_result, old_analysis, old_plan['normalization'])
        receiver = analysis['receiver']
        stimulus = read_json(case_dir / 'stimulus.json')
        waveform = laser_wave(case_dir, analysis_dir)
        manifest = read_json(case_dir / 'manifest.json')
        identities = {
            'inputs': {Path(path).name: hash_value for path, hash_value in manifest['source_hashes'].items()},
            'stimulus': manifest['stimulus_sha256'],
            'receiver_analysis': plan['sources'],
            'result': sha(analysis_dir / 'result.json'),
        }
    else:
        metrics = micro_metrics(new_result)
        previous = micro_metrics(old_result)
        receiver = new_result['metrics']['receiver']
        stimulus = read_json(work / 'stimulus.json')
        electrical_only, waveform = micro_analysis(work, case_dir, route)
        manifest = read_json(work / 'manifest.json')
        identities = {
            'inputs': manifest['inputs'],
            'frozen_sources': manifest['source_snapshots'],
            'stimulus': manifest['stimulus_sha256'],
            'executed_runner': new_result['runner_sha256'],
        }
    assert metrics['receiver']['compared_bits'] == PAYLOAD_BITS, route
    replay_waveform = case_dir / 'waveform.dat.gz'
    return {
        'replay': receipt,
        'metrics': metrics,
        'historical_metrics': previous,
        'exact_reported_metrics_match': metrics == previous,
        'electrical_only_retrained_delay': electrical_only,
        'receiver_symbol_errors_by_expected_transition': transition_errors(stimulus, receiver, route),
        'identities_sha256': identities,
        'compressed_native_waveforms': {
            'historical_bytes': old_result['waveform']['bytes'] if route == 'VCSEL' else old_result['gzip_bytes'],
            'replay_bytes': replay_waveform.stat().st_size,
            'historical_sha256': old_result['waveform']['sha256'] if route == 'VCSEL' else old_result['gzip_sha256'],
            'replay_sha256': new_result['waveform']['sha256'] if route == 'VCSEL' else new_result['gzip_sha256'],
        },
    }, waveform


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    stage = BUILD / args.run_id
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    rows = {}
    trace_path = EVIDENCE / 'replay-waves.csv'
    trace_tmp = trace_path.with_suffix('.tmp')
    with trace_tmp.open('w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(TRACE_FIELDS)
        for route in ROUTES:
            rows[route], waveform = case_summary(stage / route, route)
            for name, time, symbol, current, optical, received, unit in waveform:
                writer.writerow((name, f'{time:.8f}', symbol, f'{current:.9f}',
                                 f'{optical:.8f}', f'{received:.8f}', unit))
    trace_tmp.replace(trace_path)
    summary = {
        'schema': 'highspeed-driver-transistor-replay-v1',
        'run_id': args.run_id,
        'level': 'Schematic transistor + frozen electrical load and deterministic optical/RX proxy',
        'net_Gbps': 3.2,
        'line_Gbps': 3.7,
        'line_bits': BITS_PER_FRAME,
        'offered_payload_bits': PAYLOAD_BITS,
        'acceptance_thresholds': {'min_amplitude_uAeq_within_each_proxy': 7.5,
                                  'min_one_sided_time_ps': 100,
                                  'training_and_validation_bit_errors': 0},
        'runtime': {'python': sys.version, 'numpy': np.__version__, 'platform': platform.platform()},
        'commands': [
            *[f'build/layout/venv/bin/python scripts/highspeed_workbench_20261110/replay.py {route} --run-id {args.run_id}'
              for route in ROUTES],
            f'build/layout/venv/bin/python scripts/highspeed_workbench_20261110/replay_summary.py --run-id {args.run_id}',
        ],
        'MicroLED_conditions': {
            'corner': 'typical', 'temperature_C': 27, 'supply_V': 3.3,
            'emitter_model': '20 µm published static I-V fit + assumed 200 fF parallel C',
            'electrical_package_assumption': '1 Ω / 0.5 nH',
            'receiver': 'v2: fixed 200 ps synthetic optical pole and 1 GHz RX pole',
        },
        'VCSEL_conditions': {
            'corner': 'typical', 'temperature_C': 25, 'supply_V': 3.3,
            'emitter_model': '850 nm 25 °C graph-constrained VCSEL + assumed 150 fF parallel C',
            'electrical_package_assumption': '0.5 Ω / 0.2 nH',
            'receiver': 'v3: fixed graph-constrained 3 mA optical response proxy and 5 GHz RX pole',
        },
        'energy_scope': 'For each source port use P=-V×I from native points. Split each linear power interval at zero. Positive E+, returned magnitude E− and net E+−E− are each summed across seven ports over 1.28 µs and divided by 4096 offered payload bits. This remains an input energy metric when a receiver screen fails. Upstream host, clock/SerDes, RX and internal power of ideal sources are outside this ledger.',
        'receiver_diagnosis': 'Negative expected-class signed decision margin means at least one validation sample is on the wrong side of its threshold. A zero minimum one-sided time margin means at least one expected class has no valid time window at the selected delay. The electrical-only diagnostic evaluates the freshly replayed native LED conduction current with both optical and receiver poles bypassed. The v2 delay is trained independently under the same declared contract and thresholds, so differences in error count are diagnostic and do not partition additive errors. VCSEL v3 maps graph-constrained optical power at 3/7 mA to 25/100 µAeq, so the positive signed distance is a normalization within that proxy.',
        'interpretation': 'MicroLED A/B/C share a stimulus, load, supply convention and v2 receiver. VCSEL retains its own frozen optical/RX contract and temperature. Cross-family measured optical power, system BER, end-to-end energy and route ranking require additional evidence.',
        'compressed_native_waveform_total_bytes': sum(
            row['compressed_native_waveforms']['replay_bytes'] for row in rows.values()
        ),
        'waveform_extract': {
            'path': relative(trace_path),
            'sha256': sha(trace_path),
            'time_origin': 'First validation bit launch (frame bit index 576); no RX delay shift.',
            'symbols_per_route': TRACE_SYMBOLS,
            'samples_per_symbol': TRACE_SAMPLES_PER_SYMBOL,
            'scope': 'Electrical current in mA. MicroLED optical and RX proxies in µAeq. VCSEL graph-derived optical and RX proxies in mW. Compare amplitudes within each family.',
        },
        'routes': rows,
        'replay_script_sha256': sha(Path(__file__).with_name('replay.py')),
        'generator_sha256': sha(Path(__file__)),
    }
    summary_path = EVIDENCE / 'replay-summary.json'
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    print(json.dumps({route: {
        'native_exact': entry['replay']['exact_native_raw_sha256_match'],
        'metrics_exact': entry['exact_reported_metrics_match'],
        'errors': entry['metrics']['receiver']['errors'],
        'positive_pJ_per_offered_payload_bit': entry['metrics']['positive_pJ_per_offered_payload_bit'],
    } for route, entry in rows.items()}, indent=2))


if __name__ == '__main__':
    main()
