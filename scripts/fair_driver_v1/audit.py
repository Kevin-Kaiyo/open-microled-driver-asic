#!/usr/bin/env python3
"""Read-only, memory-bounded fair-driver audit. Never imports the runner or RX.

Full-native controls permit independent seven-port integration and every MOS
terminal-pair extremum. Native-LED exports permit independent current integration,
identity/contract checks and scalar/receipt consistency, NOT independent recovery
of unsaved port or internal-node traces. No simulation is launched by this tool.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import sys

import numpy as np

EXECUTION_SOURCE = Path(__file__).read_text()
EXECUTION_SHA = hashlib.sha256(EXECUTION_SOURCE.encode()).hexdigest()
ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'evidence/fair-driver-v1/independent-audit.json'
PORTS = ('VIN', 'VDD', 'VREF', 'VLED', 'VD0', 'VD1', 'VDISABLE')
PAIR_INDICES = tuple(itertools.combinations(range(4), 2))
PAIR_NAMES = tuple('DGSB'[i] + 'DGSB'[j] for i, j in PAIR_INDICES)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(2**20), b''):
            h.update(chunk)
    return h.hexdigest()


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT))


def load(path):
    return json.loads(Path(path).read_text())


def near(a, b, abs_tol=1e-20, rel_tol=2e-10):
    return math.isclose(float(a), float(b), abs_tol=abs_tol, rel_tol=rel_tol)


def split_energy(t, p):
    """Integrate PWL sample POWER, splitting sign-changing segments analytically.

    This is not the exact integral of the product of PWL voltage and current.
    It matches the experiment's sampled-power trapezoidal convention.
    """
    step = np.diff(t)
    left, right = p[:-1], p[1:]
    clipped_positive = np.sum(step * (np.maximum(left, 0) + np.maximum(right, 0)) / 2)
    clipped_returned = np.sum(step * (np.maximum(-left, 0) + np.maximum(-right, 0)) / 2)
    crossing = ((left > 0) & (right < 0)) | ((left < 0) & (right > 0))
    # Algebraically equivalent to dt*abs(p0*p1)/(2*(abs(p0)+abs(p1))),
    # arranged to avoid unnecessary multiplication under/overflow.
    a, b = np.abs(left[crossing]), np.abs(right[crossing])
    correction = np.sum(step[crossing] * (a / (a + b)) * b / 2)
    return np.array([clipped_positive - correction, clipped_returned - correction,
                     np.sum(step * (left + right) / 2), correction,
                     clipped_positive, clipped_returned, np.count_nonzero(crossing)], float)


def source_inventory(inputs, route, ground):
    """Independently flatten frozen electrical sources; no runner import."""
    definitions = {}
    for path in sorted(inputs.glob('*.spice')):
        sub = None
        for line in re.sub(r'\n\s*\+\s*', ' ', path.read_text()).splitlines():
            words = line.lower().split()
            if not words or words[0].startswith('*'):
                continue
            if words[0] == '.subckt':
                stop = words.index('params:') if 'params:' in words else len(words)
                sub = words[1]
                definitions[sub] = (words[2:stop], [])
            elif words[0] == '.ends':
                sub = None
            elif sub:
                definitions[sub][1].append(words)
    devices = []

    def walk(name, actual, prefix):
        formal, elements = definitions[name]
        assert len(formal) == len(actual), 'subcircuit port count'
        mapping = dict(zip(formal, actual))
        node = lambda n: '0' if n == '0' else mapping.get(n, prefix + '.' + n)
        for words in elements:
            if not words[0].startswith('x'):
                continue
            if len(words) > 5 and re.fullmatch(r'[np]fet_0[36]v[03]', words[5]):
                devices.append({'instance': prefix + '.' + words[0],
                                'nodes': [node(n) for n in words[1:5]], 'model': words[5]})
            else:
                nested = next((n for n in words[1:] if n in definitions), None)
                if nested:
                    n = len(definitions[nested][0])
                    walk(nested, [node(x) for x in words[1:1+n]], prefix + '.' + words[0])
                else:
                    assert len(words) > 4 and words[4] == 'ppolyf_u_1k_6p0', words
    walk('fair_' + route.lower(), ['d0', 'd1', 'out', 'vin', 'vdd', 'vref', ground, 'disable'], 'xdrv')
    return devices


def identity(folder, result):
    work = folder.parent.parent
    manifest = load(work / 'manifest.json')
    stimulus = load(work / 'stimulus.json')
    case, meta = result['case'], result['metadata']
    checks, warnings = {}, []
    checks['case_receipt'] = case == load(folder / 'case.json')
    checks['deck_hash'] = digest(folder / 'testbench.spice') == result['deck_sha256']
    frozen_hashes = {name: digest(work / 'inputs' / name) for name in manifest['inputs']}
    checks['all_frozen_inputs'] = frozen_hashes == manifest['inputs']
    stimulus_hash = digest(work / 'stimulus.json')
    if 'stimulus_sha256' in manifest:
        checks['frozen_stimulus'] = stimulus_hash == manifest['stimulus_sha256']
    else:
        warnings.append('Legacy native control has no pre-run stimulus SHA in manifest; current stimulus is hashed here, but its prior immutability cannot be established by this audit.')
    snapshot = work / 'execution-sources' / ('run-' + result['runner_sha256'] + '.py')
    checks['runner_snapshot'] = snapshot.exists() and digest(snapshot) == result['runner_sha256']
    parameters = {**manifest['parameters'][case['route']], **case.get('parameters', {})}
    checks['parameters'] = parameters == meta['parameters']
    calibration_path = ROOT / 'build/fair-driver-v1/dc-calibration-r1/calibration.json'
    calibration = load(calibration_path)
    checks['selected_TT_calibration'] = parameters == {**calibration['parameters'][case['route']], **case.get('parameters', {})}
    deck = (folder / 'testbench.spice').read_text()
    line = next(x for x in deck.splitlines() if x.startswith('XDRV '))
    ground = 'diegnd' if case.get('ground_package') else '0'
    checks['top_ports'] = line.split()[1:10] == ['d0', 'd1', 'out', 'vin', 'vdd', 'vref', ground, 'disable', 'fair_' + case['route'].lower()]
    checks['deck_parameters'] = all(near(float(dict(x.split('=', 1) for x in line.split()[10:])[k]), v) for k, v in parameters.items())
    checks['device_inventory'] = source_inventory(work / 'inputs', case['route'], ground) == meta['devices']
    checks['seven_ports'] = tuple(meta['sources']) == PORTS
    checks['payload_is_4096'] = stimulus['ranges_bits']['validation'][1] - stimulus['ranges_bits']['validation'][0] == 4096
    checks['full_frame_is_4736'] = len(stimulus['bits']) == 4736
    checks['eta'] = stimulus['eta'] == 4096 / 4736
    expected_duration = 4096 / (case['net_rate_Gbps'] * 1e9)
    checks['full_frame_duration'] = near(meta['frame_duration_s'], expected_duration, abs_tol=1e-18)
    tran = next(x.split() for x in deck.splitlines() if x.startswith('tran '))
    checks['tran_OP_not_uic'] = len(tran) == 5 and tran[3] == '0' and near(float(tran[2]), expected_duration, abs_tol=1e-18)
    required = ['XLED led_a led_dc_k lin2026_yellow20_dc', 'VSENSE led_dc_k led_k 0',
                'RPKG led_k pk 1', 'LPKG pk out .5n', 'RLEDSRC led_src led_a .25',
                'RVIN vin_src vin_p 0.25', 'LVIN vin_p vin 5e-10',
                'RVDD vdd_src vdd_p 1.0', 'LVDD vdd_p vdd 2e-09',
                'RREF vref_src vref .2', 'RD0 data0_src d0 100', 'RD1 data1_src d1 100']
    checks['load_and_source_impedance'] = all(x in deck.splitlines() for x in required)
    cled = next(float(x.split()[3]) for x in deck.splitlines() if x.startswith('CLED '))
    checks['LED_capacitance'] = near(cled, case.get('led_cap_F', 200e-15), abs_tol=1e-27)
    checks['port_ground_reference'] = all(any(x.startswith(f'{name} {node} 0 ') for x in deck.splitlines()) for name, node in meta['sources'].items())
    return {'checks': checks, 'warnings': warnings, 'work': relative(work),
            'manifest_sha256': digest(work / 'manifest.json'), 'source_commit': manifest['source_commit'],
            'frozen_input_sha256': frozen_hashes, 'stimulus_sha256_current': stimulus_hash,
            'runner_snapshot': relative(snapshot), 'runner_sha256': result['runner_sha256'],
            'deck_sha256': result['deck_sha256'], 'result_sha256': digest(folder / 'result.json'),
            'ngspice_log_sha256': digest(folder / 'ngspice.log'), 'parameters': parameters,
            'calibration_path': relative(calibration_path), 'calibration_sha256': digest(calibration_path),
            'target_levels_uA': [25, 50, 75, 100] if case['route'] == 'C' else [25, 100],
            'payload_bits': 4096, 'full_frame_bits': len(stimulus['bits']),
            'frame_duration_s': expected_duration, 'power_boundary': manifest['common']['power_boundary'],
            'physical_level': manifest['common']['physical_level']}


def stream_waveform(folder, result, block_rows=8192):
    """Hash raw bytes and parse at most block_rows (+ one carry) rows at once."""
    meta = result['metadata']; vectors = meta['vectors']; devices = meta['devices']
    full = all(name + '_current' in vectors for name in PORTS)
    energy = np.zeros((len(PORTS), 7)); maxima = np.full((len(devices), 8), -np.inf)
    times = np.zeros_like(maxima); count = 0; previous = None; first_t = None; led_area = 0.
    h = hashlib.sha256(); led_hash = hashlib.sha256(); columns = len(vectors) + 1
    with gzip.open(folder / 'waveform.dat.gz', 'rb') as stream:
        header = stream.readline(); h.update(header); names = header.decode().split()
        assert len(names) == columns and names[0] == 'time', 'waveform column header'
        expected = {'iled_cond': 'i(vsense)'}
        for name, node in meta['sources'].items():
            expected[name + '_voltage'] = f'v({node})'; expected[name + '_current'] = f'i({name.lower()})'
        for key, index in vectors.items():
            assert names[index].lower() == expected.get(key, f'v({key})'), ('vector mapping', key)
        while True:
            lines = list(itertools.islice(stream, block_rows))
            if not lines:
                break
            blob = b''.join(lines); h.update(blob)
            a = np.fromstring(blob.decode('ascii'), sep=' ')
            assert a.size == len(lines) * columns, 'waveform row parse'
            a = a.reshape(-1, columns); assert np.isfinite(a).all(), 'nonfinite waveform'
            led_hash.update(np.ascontiguousarray(a[:, [0, vectors['iled_cond']]], dtype='<f8').tobytes())
            count += len(a)
            if first_t is None:
                first_t = float(a[0, 0])
            if previous is not None:
                a = np.vstack((previous, a))
            t = a[:, 0]; assert np.all(np.diff(t) > 0), 'non-monotonic time'
            led = a[:, vectors['iled_cond']]
            led_area += float(np.sum(np.diff(t) * (led[:-1] + led[1:]) / 2))
            if full:
                for k, name in enumerate(PORTS):
                    p = -a[:, vectors[name + '_voltage']] * a[:, vectors[name + '_current']]
                    energy[k] += split_energy(t, p)
                node = lambda n: np.zeros(len(t)) if n == '0' else a[:, vectors[n]]
                for k, device in enumerate(devices):
                    voltage = [node(n) for n in device['nodes']]
                    sign = 1 if device['model'].startswith('nfet') else -1
                    waves = [np.abs(voltage[i] - voltage[j]) for i, j in PAIR_INDICES]
                    waves += [sign * (voltage[3] - voltage[i]) for i in (0, 2)]
                    for j, wave in enumerate(waves):
                        ix = int(np.argmax(wave))
                        if wave[ix] > maxima[k, j]:
                            maxima[k, j] = wave[ix]; times[k, j] = t[ix]
            previous = a[-1:].copy()
    assert count >= 2
    last_t = float(previous[0, 0]); duration = last_t - first_t
    return {'raw_sha256': h.hexdigest(), 'sample_count': count, 'first_time_s': first_t,
            'last_time_s': last_t, 'mean_LED_current_A': led_area / duration,
            'full_native_available': full, 'energy': energy, 'maxima': maxima,
            'maxima_times': times, 'header': names, 'block_rows': block_rows,
            'native_time_LED_float64_le_sha256': led_hash.hexdigest()}


def audit_case(folder):
    folder = Path(folder).resolve(); result = load(folder / 'result.json')
    assert result['case'].get('kind', 'transient') == 'transient', 'transient audit only'
    ident = identity(folder, result); meta = result['metadata']; metrics = result['metrics']
    raw = stream_waveform(folder, result); checks = dict(ident['checks'])
    checks.update(gzip_hash=digest(folder / 'waveform.dat.gz') == result['gzip_sha256'],
                  raw_hash=raw['raw_sha256'] == result['raw_sha256'],
                  sample_count=raw['sample_count'] == metrics['sample_count'],
                  start_at_zero=raw['first_time_s'] == 0,
                  end_at_full_frame=near(raw['last_time_s'], ident['frame_duration_s'], abs_tol=1e-18),
                  mean_LED_current=near(raw['mean_LED_current_A'], metrics['mean_LED_current_A'], abs_tol=1e-17))
    scalar = {k: float(v) for k, v in re.findall(r'^([a-z][a-z0-9]*)\s*=\s*([-+0-9.eE]+)\s*$', (folder / 'ngspice.log').read_text(), re.M)}
    energies, stresses = {}, []
    for k, name in enumerate(PORTS):
        if raw['full_native_available']:
            p, r, net, correction, cp, cr, crosses = raw['energy'][k]
            item = dict(positive_J=float(p), returned_J=float(r), net_J=float(net),
                        clipping_bias_each_sign_J=float(correction), clipped_positive_J=float(cp),
                        clipped_returned_J=float(cr), crossing_segments=int(crosses))
        else:
            p, r, correction = (scalar[f'fe{k}{s}'] for s in 'prc')
            item = dict(positive_J=p, returned_J=r, net_J=p-r,
                        clipping_bias_each_sign_J=correction)
        checks['energy_' + name] = all(near(item[key], metrics['energy'][name][key]) for key in ('positive_J', 'returned_J', 'net_J'))
        checks['energy_balance_' + name] = near(item['positive_J'] - item['returned_J'], item['net_J'])
        energies[name] = item
    for k, device in enumerate(meta['devices']):
        values = raw['maxima'][k] if raw['full_native_available'] else [scalar[f'fs{k}x{j}'] for j in range(6)] + [scalar[f'fb{k}x{j}'] for j in (0, 2)]
        item = {**device, 'pair_max_V': dict(zip(PAIR_NAMES, map(float, values[:6]))),
                'body_forward_D_S_V': list(map(float, values[6:])),
                'max_pair_V': float(max(values[:6])), 'max_body_forward_V': float(max(values[6:])),
                'limit_V': 3.63 if '03v3' in device['model'] else 6.0}
        item['device_screen_passed'] = item['max_pair_V'] <= item['limit_V']
        if raw['full_native_available']:
            item['pair_max_time_s'] = dict(zip(PAIR_NAMES, map(float, raw['maxima_times'][k, :6])))
        reported = metrics['stress'][k]
        checks['stress_' + device['instance']] = (reported['instance'] == device['instance'] and
            near(item['max_pair_V'], reported['max_pair_V'], abs_tol=1e-12) and
            near(item['max_body_forward_V'], reported['max_body_forward_V'], abs_tol=1e-12) and
            item['device_screen_passed'] == reported['passed'] and item['limit_V'] == reported['limit_V'])
        stresses.append(item)
    totals = {key: math.fsum(v[key] for v in energies.values()) for key in ('positive_J', 'returned_J', 'net_J')}
    totals.update({key.replace('_J', '_pJ_per_payload_bit'): value / 4096 * 1e12 for key, value in list(totals.items())})
    checks['total_and_4096_normalization'] = all(near(value, metrics['total_energy'][key], abs_tol=1e-20) for key, value in totals.items())
    checks['device_pass_aggregate'] = all(s['device_screen_passed'] for s in stresses) == metrics['device_voltage_passed']
    return {'case_folder': relative(folder), 'case': result['case'], 'identity': ident,
            'audit_scope': 'Independent full-native seven-port PWL-power integration and all MOS six-pair/body extrema.' if raw['full_native_available'] else 'Independent native LED integration and hash/contract checks; port energies and MOS extrema cross-checked between native SPICE stdout and result.json only. Unsaved source/internal waveforms cannot be independently reconstructed.',
            'full_native_energy_stress_recomputed': raw['full_native_available'],
            'checks': checks, 'audit_passed': all(checks.values()),
            'circuit_passed_as_reported': metrics['passed'], 'receiver_as_reported': metrics['receiver'],
            'raw': {k: v for k, v in raw.items() if k not in ('energy', 'maxima', 'maxima_times')},
            'energy': energies, 'total_energy': totals, 'stress': stresses,
            'clipping_bias_each_sign_pJ_per_payload_bit': math.fsum(v['clipping_bias_each_sign_J'] for v in energies.values()) / 4096 * 1e12}


def compare_control(native, compact):
    """Require identical solve inputs, while allowing different export/RX code."""
    a, b = native['identity'], compact['identity']
    folders = [ROOT / x['case_folder'] for x in (native, compact)]
    def solve_text(folder):
        text = (folder / 'testbench.spice').read_text().split('.control')[0]
        # Absolute frozen include paths and title are not circuit differences.
        text = '\n'.join(text.splitlines()[1:])
        return re.sub(r'"[^"\n]*/inputs/', '"<inputs>/', text)
    tran_commands = [next(line for line in (folder / 'testbench.spice').read_text().splitlines() if line.startswith('tran ')) for folder in folders]
    checks = {'native_control_available': native['full_native_energy_stress_recomputed'],
              'circuit_and_solver_deck': solve_text(folders[0]) == solve_text(folders[1]),
              'tran_command': tran_commands[0] == tran_commands[1],
              'stimulus_content': a['stimulus_sha256_current'] == b['stimulus_sha256_current'],
              'parameters': a['parameters'] == b['parameters'],
              'circuit_model_inputs': {k: v for k, v in a['frozen_input_sha256'].items() if k != 'receiver.py'} == {k: v for k, v in b['frozen_input_sha256'].items() if k != 'receiver.py'}}
    differences = {}
    for name in PORTS:
        differences[name] = {key: compact['energy'][name][key] - native['energy'][name][key] for key in ('positive_J', 'returned_J', 'net_J', 'clipping_bias_each_sign_J')}
        checks['energy_' + name] = all(near(native['energy'][name][key], compact['energy'][name][key], abs_tol=1e-21) for key in differences[name])
    checks['all_MOS_pairs_and_body'] = len(native['stress']) == len(compact['stress']) and all(
        x['instance'] == y['instance'] and all(near(x['pair_max_V'][p], y['pair_max_V'][p], abs_tol=1e-11) for p in PAIR_NAMES)
        and all(near(u, v, abs_tol=1e-11) for u, v in zip(x['body_forward_D_S_V'], y['body_forward_D_S_V']))
        for x, y in zip(native['stress'], compact['stress']))
    if compact['raw']['sample_count'] == native['raw']['sample_count']:
        checks['mean_LED_current'] = near(compact['raw']['mean_LED_current_A'], native['raw']['mean_LED_current_A'], abs_tol=1e-16)
        if 'native_time_LED_float64_le_sha256' in native['raw']:
            checks['identical_native_time_and_LED_samples'] = compact['raw']['native_time_LED_float64_le_sha256'] == native['raw']['native_time_LED_float64_le_sha256']
    return {'native_case': native['case_folder'], 'compact_case': compact['case_folder'],
            'checks': checks, 'passed': all(checks.values()), 'energy_delta_J': differences,
            'boundary': 'Validates native scalar/export implementation against one preserved B solve. Does not independently validate all unsaved waveforms in other routes or cases; receiver code may differ and is not compared here.'}


def self_test():
    cases = [(np.array([0., 2.]), np.array([2., -2.]), [1., 1., 0., 1.]),
             (np.array([0., 3.]), np.array([-2., 1.]), [.5, 2., -1.5, 1.]),
             (np.array([0., 1., 3.]), np.array([0., 2., 0.]), [3., 0., 3., 0.])]
    for t, p, expected in cases:
        assert np.allclose(split_energy(t, p)[:4], expected, rtol=0, atol=1e-14)
    rng = np.random.default_rng(250102)
    t = np.r_[0., np.cumsum(rng.random(1000))]; p = rng.normal(size=len(t))
    whole = split_energy(t, p)
    chunks = sum((split_energy(t[k:min(k+38, len(t))], p[k:min(k+38, len(t))]) for k in range(0, len(t)-1, 37)), np.zeros(7))
    assert np.allclose(whole, chunks, rtol=2e-14, atol=1e-14), 'chunk-boundary integration'
    # Separate scalar triangle oracle avoids testing only one vectorized formula.
    positive = returned = 0.
    for x, y, h in zip(p[:-1], p[1:], np.diff(t)):
        if x * y < 0:
            split = h * abs(x) / (abs(x) + abs(y))
            parts = [.5*x*split, .5*y*(h-split)]
        else:
            parts = [.5*(x+y)*h]
        positive += sum(max(v, 0) for v in parts); returned += sum(max(-v, 0) for v in parts)
    assert near(whole[0], positive) and near(whole[1], returned)
    return {'passed': True, 'checks': ['symmetric crossing', 'asymmetric crossing', 'zero endpoints', 'chunk carry', 'independent scalar triangle oracle']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', action='append', type=Path, default=[])
    parser.add_argument('--compare', nargs=2, action='append', metavar=('NATIVE_CASE', 'COMPACT_CASE'), default=[])
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args(); tests = self_test()
    if args.self_test and not args.case and not args.compare:
        print(json.dumps(tests)); return
    assert args.case, 'At least one explicit completed --case is required'
    receipt = load(OUTPUT) if OUTPUT.exists() else {'schema_version': 1, 'runs': []}
    cases = [audit_case(p) for p in args.case]
    index = {relative(p): c for p, c in zip(args.case, cases)}
    # Previously audited cases are usable only if their result and raw hashes still match.
    for oldrun in receipt['runs']:
        for c in oldrun['cases']:
            if c['case_folder'] not in index:
                folder = ROOT / c['case_folder']
                if digest(folder / 'result.json') == c['identity']['result_sha256'] and digest(folder / 'waveform.dat.gz') == load(folder / 'result.json')['gzip_sha256']:
                    index[c['case_folder']] = c
    comparisons = [compare_control(index[relative(a)], index[relative(b)]) for a, b in args.compare]
    record = {'created': dt.datetime.now().astimezone().isoformat(), 'script_sha256': EXECUTION_SHA,
              'script_source': EXECUTION_SOURCE,
              'command': [sys.executable, *sys.argv], 'self_tests': tests, 'cases': cases,
              'comparisons': comparisons, 'passed': all(c['audit_passed'] for c in cases) and all(c['passed'] for c in comparisons),
              'limits': ['Sampled-power quadrature is exact only for piecewise-linear interpolation of sampled power; it does not prove continuous-time numerical convergence.',
                         'MOS six-pair limits are project screens, not oxide lifetime, junction-injection, silicon or optical qualification.',
                         'Formal RX may use native LED samples; this auditor does not refit or rerun receiver training. Zero observed errors is not a BER bound.']}
    receipt['runs'].append(record)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'output': relative(OUTPUT), 'passed': record['passed'],
                      'cases': [{'name': c['case']['name'], 'audit_passed': c['audit_passed'], 'failed_checks': [k for k,v in c['checks'].items() if not v], 'energy': c['total_energy']} for c in cases],
                      'comparisons': comparisons}, ensure_ascii=False, indent=2))
    if not record['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
