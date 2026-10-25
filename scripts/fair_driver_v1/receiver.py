"""Common current-domain optical/RX proxy for the prospective fair-driver study.

Input is LED conduction current, excluding separately connected displacement C.
No waveform, file, circuit, threshold, or validation-label fitting occurs here.
"""
from __future__ import annotations

from collections import Counter
import math
import numpy as np

GRAY = np.array([[0, 0], [0, 1], [1, 1], [1, 0]], dtype=int)
TAU_OPTICAL_S = 200e-12
TAU_RX_S = 1.0 / (2.0 * math.pi * 1e9)
PHASE_GRID = 128
AMPLITUDE_TIE_TOL_UA = 1e-6  #1pA; fixed before circuit results


def make_stimulus() -> dict:
    """Fixed PRBS15 test frame; no physical protocol, FEC or packet claim."""
    state = seed = 0x5ACE
    bits = []
    for _ in range(4736):
        bits.append((state >> 14) & 1)
        feedback = ((state >> 14) ^ (state >> 13)) & 1
        state = ((state << 1) & 0x7FFF) | feedback
    gray_to_symbol = {(0, 0): 0, (0, 1): 1, (1, 1): 2, (1, 0): 3}
    symbols = [gray_to_symbol[tuple(bits[k:k+2])] for k in range(0, len(bits), 2)]
    validation = symbols[288:2336]
    transitions = Counter(zip(validation[:-1], validation[1:]))
    assert all(transitions[(a, b)] for a in range(4) for b in range(4) if a != b)
    assert all(abs(validation.count(k) - 512) <= .05 * 512 for k in range(4))
    return {
        'schema_version': 1,
        'generator': 'PRBS15 x^15+x^14+1; output bit14, left shift, feedback bit14 XOR bit13',
        'seed': seed,
        'bits': bits,
        'symbols_N': list(bits),
        'symbols_C': symbols,
        'gray_mapping': {'00': 0, '01': 1, '11': 2, '10': 3},
        'ranges_bits': {'warmup': [0, 64], 'training': [64, 576],
                        'training_scoring': [64, 572],
                        'validation': [576, 4672], 'tail': [4672, 4736]},
        'eta': 4096 / 4736,
        'time_origin_s': 0.0,
        'validation_PAM4_symbol_counts': {str(k): validation.count(k) for k in range(4)},
        'validation_PAM4_directed_transition_counts': {
            f'{a}->{b}': transitions[(a, b)] for a in range(4) for b in range(4) if a != b},
        'boundary': 'Artificial test-frame overhead only; no implemented protocol or FEC. All512 training bits excluded from payload; last4 are common scoring guard.',
    }


def _time_and_current(t_s, i_led_A):
    t = np.asarray(t_s, dtype=float)
    current = np.asarray(i_led_A, dtype=float)
    if (t.ndim != 1 or current.ndim != 1 or len(t) != len(current) or len(t) < 2
            or not np.isfinite(t).all() or not np.isfinite(current).all()
            or not np.all(np.diff(t) > 0)):
        raise ValueError('Finite equally sized1D arrays and strictly increasing times are required')
    return t, current


def filter_trace(t_s: np.ndarray, i_led_A: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Exact cascade state evolution for a piecewise-linear conduction input.

    Both states start at i_led_A[0] (existing DC OP). Optical output and RX
    output are returned in equivalent-current A; they are not optical watts.
    """
    t, current = _time_and_current(t_s, i_led_A)
    optical = np.empty(len(t))
    rx = np.empty(len(t))
    first = second = float(current[0])
    optical[0] = rx[0] = first
    a, b = TAU_OPTICAL_S, TAU_RX_S
    for k in range(1, len(t)):
        h = float(t[k] - t[k-1])
        u = float(current[k-1])
        slope = float((current[k] - current[k-1]) / h)
        ea, eb = math.exp(-h/a), math.exp(-h/b)
        one_a, one_b = -math.expm1(-h/a), -math.expm1(-h/b)
        # exp difference avoids cancellation for very short PWL intervals.
        de = eb * math.expm1(h * (1/b - 1/a)) if h < 20*a else ea - eb
        forcing = first - u + slope*a
        next_second = (eb*second + (u-slope*a)*one_b
                       + slope*(h-b*one_b) + forcing*a/(a-b)*de)
        first = ea*first + u*one_a + slope*(h-a*one_a)
        second = next_second
        optical[k], rx[k] = first, second
    return optical, rx


def _signed_margin(samples_uA, symbols, thresholds_uA):
    bounds = np.r_[-np.inf, thresholds_uA, np.inf]
    return np.minimum(samples_uA - bounds[symbols], bounds[symbols+1] - samples_uA)


def _decode(samples_uA, thresholds_uA):
    return np.searchsorted(thresholds_uA, samples_uA, side='right').astype(int)


def _bits(symbols, pam4):
    return GRAY[symbols].reshape(-1) if pam4 else symbols


def _crossings(t, y, threshold):
    lo, hi = y[:-1] - threshold, y[1:] - threshold
    ix = np.flatnonzero(((lo < 0) & (hi >= 0)) | ((lo > 0) & (hi <= 0)))
    return t[ix] + (t[ix+1] - t[ix]) * (-lo[ix]) / (hi[ix] - lo[ix])


def _horizontal(t, y_uA, sample_t, samples_uA, expected, thresholds, origin, end, ui, bit_ui):
    """Nearest decision-region boundary, interpolated in the original time grid."""
    crossings = [_crossings(t, y_uA, x) for x in thresholds]
    left = np.zeros(len(expected))
    right = np.zeros(len(expected))
    correct_margin = _signed_margin(samples_uA, expected, thresholds)
    for level in range(len(thresholds)+1):
        ix = np.flatnonzero((expected == level) & (correct_margin > 0))
        if not len(ix):
            continue
        edges = []
        if level:
            edges.append(crossings[level-1])
        if level < len(thresholds):
            edges.append(crossings[level])
        events = np.unique(np.concatenate(edges))
        if len(events):
            pos = np.searchsorted(events, sample_t[ix], side='right')
            previous = np.where(pos > 0, events[np.maximum(pos-1, 0)], origin)
            following = np.where(pos < len(events), events[np.minimum(pos, len(events)-1)], end)
        else:
            previous = np.full(len(ix), origin)
            following = np.full(len(ix), end)
        left[ix] = sample_t[ix] - np.maximum(previous, origin)
        right[ix] = np.minimum(following, end) - sample_t[ix]
    margins = np.maximum(0.0, np.minimum(left, right))
    smallest = float(margins.min())
    return {
        'left_min_ps': float(max(0.0, left.min()) * 1e12),
        'right_min_ps': float(max(0.0, right.min()) * 1e12),
        'min_ps': smallest * 1e12,
        'min_symbol_UI': smallest / ui,
        'min_bit_UI': smallest / bit_ui,
        'worst_symbol_offset': int(margins.argmin()),
        'definition': 'Minimum one-sided shift from frozen training sample to either correct decision-region threshold crossing across validation. Linear interpolation on original RX time grid; wrong/on-threshold samples have0 margin. No refit and no UI normalization for100ps acceptance.',
    }


def _noise_ber(samples_uA, expected, thresholds, pam4):
    results = []
    labels = GRAY if pam4 else np.array([[0], [1]])
    for sigma in [.5, 1.0, 2.0, 4.0]:
        # Evaluate tails directly: 1-CDF would round small error probabilities to0.
        q = lambda z: .5 * math.erfc(float(z) / math.sqrt(2))
        rows = []
        for y in samples_uA:
            z = (thresholds-float(y))/sigma
            row = [q(-z[0])]
            for lower, upper in zip(z[:-1], z[1:]):
                row.append(max(0.0, q(lower)-q(upper) if lower >= 0
                               else q(-upper)-q(-lower)))
            row.append(q(z[-1]))
            rows.append(row)
        probabilities = np.array(rows)
        hamming = np.count_nonzero(labels[expected, None, :] != labels[None, :, :], axis=2)
        ber = float(np.mean(np.sum(probabilities * hamming, axis=1)) / labels.shape[1])
        ser = float(np.mean(np.sum(probabilities * (np.arange(len(thresholds)+1)[None, :] != expected[:, None]), axis=1)))
        results.append({'sigma_uA': sigma, 'conditional_BER': max(0.0, ber),
                        'conditional_SER': max(0.0, ser),
                        'assumption': 'Independent additive zero-mean Gaussian equivalent-current noise at frozen RX samples; fixed thresholds; deterministic waveform ISI retained. Conditional analytic estimate, not measuredBER or a noise qualification.'})
    return results


def analyze(t_s: np.ndarray, i_led_A: np.ndarray, stimulus: dict,
            route: str, net_rate_Gbps: float) -> dict:
    """Train only on the declared guard-trimmed training segment; then freeze."""
    name = str(route).upper()
    if name not in {'A', 'B', 'N', 'NRZ', 'C', 'PAM4'}:
        raise ValueError('route must be A/B/N/NRZ or C/PAM4')
    if not math.isfinite(net_rate_Gbps) or net_rate_Gbps <= 0:
        raise ValueError('net_rate_Gbps must be finite and positive')
    pam4 = name in {'C', 'PAM4'}
    bits_per_symbol = 2 if pam4 else 1
    bits = np.asarray(stimulus['bits'], dtype=int)
    expected_all = np.asarray(stimulus['symbols_C' if pam4 else 'symbols_N'], dtype=int)
    ranges = stimulus['ranges_bits']
    if (len(bits) != 4736 or not np.isin(bits, [0, 1]).all()
            or len(expected_all) != 4736 // bits_per_symbol
            or not np.isin(expected_all, range(4 if pam4 else 2)).all()
            or not np.array_equal(_bits(expected_all, pam4), bits)
            or ranges.get('warmup') != [0, 64]
            or ranges.get('tail') != [4672, 4736]
            or ranges.get('training') != [64, 576]
            or ranges.get('training_scoring') != [64, 572]
            or ranges.get('validation') != [576, 4672]
            or not math.isclose(stimulus['eta'], 4096/4736, rel_tol=0, abs_tol=1e-15)):
        raise ValueError('Stimulus does not match the fixed bit/frame/Gray contract')
    t, current = _time_and_current(t_s, i_led_A)
    origin = float(stimulus.get('time_origin_s', 0.0))
    if not math.isfinite(origin):
        raise ValueError('time_origin_s must be finite')
    eta = 4096/4736
    line = float(net_rate_Gbps) / eta
    bit_ui = 1 / (line*1e9)
    ui = bits_per_symbol * bit_ui
    frame_duration = len(bits) * bit_ui
    end = origin + frame_duration
    tolerance = max(1e-16, frame_duration*1e-12)
    if t[0] > origin+tolerance or t[-1] < end-tolerance:
        raise ValueError('Waveform must cover the complete frame including warmup/training/tail')
    _, filtered = filter_trace(t, current)
    filtered_uA = filtered * 1e6
    thresholds = np.array([37.5, 62.5, 87.5] if pam4 else [62.5])
    train_idx = np.arange(64//bits_per_symbol, 572//bits_per_symbol)
    val_idx = np.arange(576//bits_per_symbol, 4672//bits_per_symbol)
    expected_train, expected = expected_all[train_idx], expected_all[val_idx]
    delays = np.arange(64, 257, dtype=float) / PHASE_GRID
    training_scan = []
    training_scores = []
    for delay in delays:
        when = origin + (train_idx + delay) * ui
        assert when.max() < origin + 576*bit_ui
        values = np.interp(when, t, filtered_uA)
        margins = _signed_margin(values, expected_train, thresholds)
        decisions = _decode(values, thresholds)
        score = float(margins.min())
        training_scores.append(score)
        training_scan.append({
            'delay_symbol_UI': float(delay), 'delay_s': float(delay*ui),
            'min_signed_decision_distance_uA': score,
            'mean_signed_decision_distance_uA': float(margins.mean()),
            'symbol_errors': int(np.count_nonzero(decisions != expected_train)),
            'bit_errors': int(np.count_nonzero(_bits(decisions, pam4) != _bits(expected_train, pam4))),
        })
    # Almost settled amplitude plateaus must not be decided by roundoff. Within
    #1pA of the best amplitude score, maximize TRAINING-only time margin.
    # The prefix is strictly before validation; even a changed boundary sample
    # cannot influence this tie-break. The common four-bit guard remains overhead.
    best_score = max(training_scores)
    eligible = np.flatnonzero(np.asarray(training_scores) >= best_score-AMPLITUDE_TIE_TOL_UA)
    prefix = t < origin+576*bit_ui
    train_t, train_y = t[prefix], filtered_uA[prefix]
    best_time = -1.0
    chosen = int(eligible[0])
    for j, record in enumerate(training_scan):
        record['amplitude_plateau_eligible'] = bool(j in eligible)
        record['training_time_margin_ps'] = None
    for j in eligible:
        when = origin+(train_idx+delays[j])*ui
        values = np.interp(when,t,filtered_uA)
        hm = _horizontal(train_t,train_y,when,values,expected_train,thresholds,
                         origin,float(train_t[-1]),ui,bit_ui)
        score = hm['min_ps']
        training_scan[j]['training_time_margin_ps'] = score
        if score > best_time:
            chosen, best_time = int(j), score
    delay = float(delays[chosen])
    sample_t = origin + (val_idx + delay) * ui
    values = np.interp(sample_t, t, filtered_uA)
    margins = _signed_margin(values, expected, thresholds)
    distances = np.min(abs(values[:, None]-thresholds[None, :]), axis=1)
    decisions = _decode(values, thresholds)
    actual_bits, target_bits = _bits(decisions, pam4), _bits(expected, pam4)
    bad_bits = np.flatnonzero(actual_bits != target_bits)
    bad_symbols = np.flatnonzero(decisions != expected)
    transitions = Counter(zip(expected[:-1].tolist(), expected[1:].tolist()))
    transition_counts = {f'{a}->{b}': int(transitions[(a,b)])
                         for a in range(4 if pam4 else 2) for b in range(4 if pam4 else 2)}
    directed_complete = all(transitions[(a,b)] > 0 for a in range(4 if pam4 else 2)
                            for b in range(4 if pam4 else 2) if a != b)
    horizontal = _horizontal(t, filtered_uA, sample_t, values, expected,
                             thresholds, origin, end, ui, bit_ui)
    checks = {
        'training_error_free': training_scan[chosen]['bit_errors'] == 0,
        'validation_error_free': len(bad_bits) == 0,
        'decision_distance_7p5uA': float(margins.min()) >= 7.5,
        'time_margin_100ps': horizontal['min_ps'] >= 100,
        'all_directed_transitions_present': bool(directed_complete),
    }
    return {
        'schema_version': 1, 'route': name, 'modulation': 'PAM4' if pam4 else 'NRZ',
        'rates': {'net_Gbps': float(net_rate_Gbps), 'line_Gbps': line,
                  'symbol_Gbaud': line/bits_per_symbol, 'eta': eta,
                  'frame_duration_s': frame_duration, 'payload_bits': 4096,
                  'transmitted_bits': 4736, 'bit_UI_s': bit_ui, 'symbol_UI_s': ui},
        'ranges_bits': {k:list(v) for k,v in ranges.items()},
        'proxy': {'input': 'LED conduction current only; displacement excluded by harness',
                  'optical_tau_s': TAU_OPTICAL_S, 'rx_pole_Hz': 1e9,
                  'initial_equivalent_current_A': float(current[0]),
                  'thresholds_uA': thresholds.tolist(),
                  'filter': 'exact cascade state evolution for piecewise-linear input; sample/threshold crossing linearly interpolated on output time grid',
                  'max_input_step_ps': float(np.diff(t).max()*1e12)},
        'sampling': {'delay_symbol_UI': delay, 'delay_s': delay*ui,
                     'phase_symbol_UI': delay % 1.0, 'integer_symbol_delay': int(delay),
                     'phase_grid_per_symbol': PHASE_GRID,
                     'search_delay_symbol_UI': [.5, 2.0],
                     'training_scored_bits': 508, 'training_guard_bits': 4,
                     'training_scored_symbols': int(len(train_idx)),
                     'amplitude_plateau_tolerance_uA': AMPLITUDE_TIE_TOL_UA,
                     'training_selection': 'Maximize minimum signed expected-class threshold distance in absoluteuA. Among candidates within1pA of maximum, maximize minimum TRAINING absolute time margin; earliest exact tie wins. Validation never participates.',
                     'training_scan': training_scan},
        'validation': {'bit_count': int(len(target_bits)), 'bit_errors': int(len(bad_bits)),
                       'raw_errors': int(len(bad_bits)), 'raw_BER': float(len(bad_bits)/len(target_bits)),
                       'symbol_count': int(len(expected)), 'symbol_errors': int(len(bad_symbols)),
                       'SER': float(len(bad_symbols)/len(expected)),
                       'decision_distance_min_uA': float(margins.min()),
                       'decision_distance_mean_uA': float(margins.mean()),
                       'absolute_threshold_distance_min_uA': float(distances.min()),
                       'absolute_threshold_distance_mean_uA': float(distances.mean()),
                       'error_bit_offsets': bad_bits.tolist(), 'error_symbol_offsets': bad_symbols.tolist(),
                       'decoded_symbols': decisions.tolist(), 'samples_uA': values.tolist(),
                       'symbol_counts': {str(k): int(np.count_nonzero(expected==k)) for k in range(4 if pam4 else 2)},
                       'transition_counts': transition_counts,
                       'all12_PAM4_directed_transitions': bool(directed_complete) if pam4 else None},
        'horizontal_margin': horizontal,
        'conditional_noise_BER': _noise_ber(values, expected, thresholds, pam4),
        'checks': checks, 'passed': bool(all(checks.values())),
        'limits': ['Training is not payload; artificial frame overhead is not an implemented protocol.',
                   'Validation never changes thresholds, delay, phase or symbol labels.',
                   'Zero observed errors is a finite deterministic result, not BER certification.',
                   'Optical/RX poles and Gaussian noise are shared assumptions, not measured LED/RX models.',
                   'Phase-grid optimum and interpolated time margin must be checked with waveform step refinement.'],
    }
