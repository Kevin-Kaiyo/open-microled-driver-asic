#!/usr/bin/env python3
"""Synthetic counterfactual controls for receiver training and time scaling.

These controls exercise the receiver with known signals. They do not execute
SPICE, modify native circuit data, validate a physical optical model, or
establish BER. Only the fixed-frame decision methodology is checked.
"""
from pathlib import Path
import sys

import numpy as np

sys.dont_write_bytecode = True
import analyze as analysis


def synthetic_trace(stimulus, route, rate_Gbps):
    """Construct independently prescribed levels and a 0.04-bit-UI ramp."""
    width = 2 if route == 'C' else 1
    symbols = np.asarray(stimulus['symbols_C' if width == 2 else 'symbols_N'])
    bit_ui = analysis.ETA / (rate_Gbps * 1e9)
    symbol_ui = width * bit_ui
    time = np.arange(4736 * 64 + 1) * bit_ui / 64
    index = np.minimum((time / symbol_ui).astype(int), len(symbols) - 1)
    previous = symbols[np.maximum(index - 1, 0)]
    fraction = np.clip((time - index * symbol_ui) / (0.04 * bit_ui), 0, 1)
    signal = 25 + (25 if width == 2 else 75) * (
        previous + fraction * (symbols[index] - previous))
    return time, signal, bit_ui


def selected_metrics(result):
    return {key: result[key] for key in (
        'train_errors', 'errors', 'delay_bit_UI', 'delay_ps',
        'worst_signed_margin_uAeq', 'one_sided_margin_bit_UI',
        'one_sided_margin_symbol_UI', 'one_sided_margin_ps',
        'research_margin_pass')}


def main():
    rx = analysis.module(analysis.RXPATH, 'receiver_controls_frozen_helpers')
    stimulus = rx.make_stimulus()
    rows = []
    for route in ('A', 'C'):
        for rate in (0.4, 3.2):
            time, original, bit_ui = synthetic_trace(stimulus, route, rate)
            baseline = analysis.receive(time, original, stimulus, route, rate, rx)
            damaged = original.copy()
            validation_and_tail = time >= 576 * bit_ui
            damaged[validation_and_tail] = (
                62.5 + 300 * np.sin(time[validation_and_tail] / bit_ui))
            counterfactual = analysis.receive(time, damaged, stimulus, route, rate, rx)
            checks = {
                'known_signal_zero_training_and_validation_errors':
                    baseline['train_errors'] == baseline['errors'] == 0,
                'known_signal_passes_research_receiver_margin':
                    baseline['research_margin_pass'],
                'all_prevalidation_samples_bitwise_unchanged':
                    bool(np.array_equal(original[~validation_and_tail],
                                        damaged[~validation_and_tail])),
                'counterfactual_changes_validation_errors':
                    counterfactual['errors'] > baseline['errors'],
                'selected_training_phase_unchanged':
                    counterfactual['delay_bit_UI'] == baseline['delay_bit_UI'],
                'training_errors_unchanged':
                    counterfactual['train_errors'] == baseline['train_errors'],
            }
            rows.append({'modulation': 'PAM4' if route == 'C' else 'NRZ',
                         'synthetic_rate_Gbps': rate,
                         'baseline': selected_metrics(baseline),
                         'validation_only_counterfactual': selected_metrics(counterfactual),
                         'checks': checks, 'passed': all(checks.values())})

    scaling = []
    for modulation in ('NRZ', 'PAM4'):
        low, high = [row for row in rows if row['modulation'] == modulation]
        low_m, high_m = low['baseline'], high['baseline']
        checks = {
            'same_training_phase_in_line_bit_UI':
                low_m['delay_bit_UI'] == high_m['delay_bit_UI'],
            'same_normalized_line_bit_time_margin': bool(np.isclose(
                low_m['one_sided_margin_bit_UI'], high_m['one_sided_margin_bit_UI'],
                rtol=0, atol=1e-10)),
            'same_normalized_symbol_time_margin': bool(np.isclose(
                low_m['one_sided_margin_symbol_UI'], high_m['one_sided_margin_symbol_UI'],
                rtol=0, atol=1e-10)),
            'absolute_time_margin_scales_by_inverse_rate': bool(np.isclose(
                low_m['one_sided_margin_ps'] / high_m['one_sided_margin_ps'],
                3.2 / 0.4, rtol=0, atol=1e-9)),
        }
        scaling.append({'modulation': modulation, 'checks': checks,
                        'passed': all(checks.values())})

    passed = all(row['passed'] for row in rows + scaling)
    out = {
        'schema': 'receiver-counterfactual-controls-v1',
        'scope': 'Synthetic prescribed waveforms only. No new SPICE, device, '
                 'noise, BER, startup, or energy validation.',
        'signal': {'NRZ_levels_uAeq': [25, 100],
                   'PAM4_levels_uAeq': [25, 50, 75, 100],
                   'ramp_line_bit_UI': 0.04,
                   'grid_per_line_bit_UI': 64,
                   'note': 'Ramp scales with UI only in this mathematical '
                           'receiver control. Actual transistor sweep retains '
                           '20 ps input edges and solves each rate anew.'},
        'counterfactual': 'Replace samples at or after 576 line-bit UI by '
                          '62.5 + 300*sin(t/bit_UI) uAeq. All earlier samples '
                          'and all labels remain unchanged.',
        'rates_Gbps': [0.4, 3.2],
        'numpy_version': np.__version__,
        'source_hashes': {str(p.relative_to(analysis.ROOT)): analysis.sha(p)
                          for p in (Path(__file__).resolve(),
                                    Path(analysis.__file__).resolve(), analysis.RXPATH)},
        'counterfactual_checks': rows,
        'scale_checks': scaling,
        'all_passed': passed,
        'limits': 'The controls detect validation-waveform leakage and '
                  'normalization inconsistency for these signals. They do '
                  'not prove all receiver software correct or characterize '
                  'the simulated drivers.',
    }
    output = analysis.EV / 'receiver-controls.json'
    analysis.emit(output, out)
    print(f'{output.relative_to(analysis.ROOT)}: all_passed={passed}')
    if not passed:
        raise SystemExit('Receiver counterfactual control failed')


if __name__ == '__main__':
    main()
