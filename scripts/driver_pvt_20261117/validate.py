#!/usr/bin/env python3
"""Cross-check manifest, native trace provenance, and applied PVT conditions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import re

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
TAG = 'driver-pvt-20261117'
BUILD = ROOT / 'build' / TAG
EVIDENCE = ROOT / 'evidence' / TAG
MICRO_LED = '51dabe11ee4a3fbbb7bf387e422eaa4faa0203d149a3c5701ab1dfaeba9734cc'
VCSEL_LOAD = '7ed34d124b85230c15b4914407dbac0761103879ced25b1bb3794fb0e2d90beb'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def near(a, b):
    return abs(a - b) <= max(1e-14, abs(b) * 1e-10)


def energy_ledger(ledger, expected, denominator, keys):
    assert set(ledger) == set(keys)
    for port in ledger.values():
        assert port['positive_J'] >= 0 and port['returned_J'] >= 0
        assert abs(port['positive_J'] - port['returned_J'] - port['net_J']) < 1e-17
    for label in ('positive', 'returned', 'net'):
        computed = sum(port[label + '_J'] for port in ledger.values()) * 1e12 / denominator
        assert near(computed, expected[label]), label


def deck_voltage(deck, name):
    line = next(line for line in deck.splitlines() if line.startswith(name + ' '))
    return float(line.split()[3])


def check_pattern(deck, source, original_bits, ui, end, high, offset=0.0):
    body = re.search(r'(?m)^' + source + r' \w+ 0 PWL\(([^)]*)\)', deck)
    assert body, source
    flat = np.fromstring(body[1].replace('\n+', ' '), sep=' ')
    assert len(flat) >= 4 and len(flat) % 2 == 0, source
    edges = flat.reshape(-1, 2)
    assert np.all(np.diff(edges[:, 0]) >= 0), source
    indices = np.arange(len(original_bits))
    centers = (indices + 0.5) * ui - offset
    inside = (centers > 0) & (centers < end)
    assert inside.sum() > 0
    actual = np.interp(centers[inside], edges[:, 0], edges[:, 1])
    assert np.allclose(actual, high * original_bits[inside], rtol=0, atol=1e-9), source


def stimulus(lane, manifest, deck, data):
    bits = np.array(data['bits'])
    if lane == 'vcsel' and manifest['kind'] != 'dc':
        for source, pattern in [('VD', bits), ('VDB', 1 - bits)]:
            check_pattern(deck, source, pattern, manifest['UI_ps'] * 1e-12,
                          manifest['end_s'], 3.3)
    elif lane != 'vcsel' and manifest['case'].get('level') is None:
        diagnostic = manifest.get('diagnostic', {})
        bits = np.tile(bits, manifest['frames'])
        check_pattern(deck, 'VD0', bits, 4096 / 4736 / (1.6e9), manifest['end_s'],
                      deck_voltage(deck, 'VDD'), diagnostic.get('old_absolute_input_start_s', 0.0))


def conditions(lane, manifest, deck):
    cfg = manifest['pvt_config']['pvt'] if lane == 'vcsel' else manifest['pvt']
    section = cfg.get('section', cfg.get('model_section', cfg.get('corner')))
    temp = cfg.get('temp_C', cfg.get('temperature_C'))
    assert re.search(r'(?m)^\.lib [^\n]+ ' + section + r'\s*$', deck)
    assert float(re.search(r'(?m)^\.temp\s+([^\s]+)', deck)[1]) == temp
    if lane == 'vcsel':
        for supply in ('VLASER', 'VDD', 'VREF', 'VPHY'):
            assert near(deck_voltage(deck, supply), 3.3 * cfg['rail_scale']), supply
        for supply, target in [('VSET', .15), ('VREGSET', .3263157894736842)]:
            assert near(deck_voltage(deck, supply), target), supply
        assert manifest['source_sha256']['vcsel.spice'] == VCSEL_LOAD
        assert re.search(r'^XVCSEL vl vc_k jmon vcsel_research CJ=1.5e-13$', deck, re.M)
        assert re.search(r'^RPKG vc_k vc_a .5$', deck, re.M)
        assert re.search(r'^LPKG vc_a out .2n$', deck, re.M)
    else:
        supplies = manifest.get('rails_V', cfg)
        for supply in ('VIN', 'VDD', 'VREF', 'VLED'):
            key = supply if supply in supplies else supply + '_V'
            target = 2.5 if supply == 'VREF' else supplies[key]
            assert near(deck_voltage(deck, supply), target), supply
        assert manifest['inputs']['led.spice'] == MICRO_LED
        assert ' res_typical' in deck
        capacitor = re.search(r'^CLED led_a led_k ([\d.eE+-]+)', deck, re.M)
        assert capacitor and abs(float(capacitor[1]) - 200e-15) < 1e-25
    return section, temp


def check_case(path, rehash):
    folder = path.parent
    lane = folder.relative_to(BUILD).parts[0]
    result = read(path)
    manifest_path = folder / 'manifest.json'
    manifest = read(manifest_path)
    deck = folder / 'testbench.spice'
    assert sha(deck) == manifest['deck_sha256'] == result['deck_sha256']
    assert sha(manifest_path) == result['manifest_sha256']
    assert sha(folder / 'ngspice.log') == result['log_sha256']
    assert sha(folder / 'stimulus.json') == manifest['stimulus_sha256']
    expected = manifest.get('execution_source_sha256', manifest.get('execution_sha256'))
    assert sha(folder / 'execution-source.py') == expected
    correction = folder / 'execution-provenance-correction.json'
    if correction.exists():
        original = read(correction)
        assert sha(manifest_path) == original['original_manifest_sha256']
        assert sha(path) == original['original_result_sha256']
        assert expected == original['original_claimed_execution_sha256']
        actual = original['actual_execution_sha256']
        assert sha(folder / original['actual_execution_source']) == actual
        assert sha(ROOT / original['same_process_first_case'] / 'execution-source.py') == actual
    for item in manifest['execution_helpers'].values():
        name = item.get('path', 'execution-sources/' + item.get('copy', ''))
        assert sha(folder / name) == item['sha256'], name
    for name, expected in manifest.get('inputs', {}).items():
        assert sha(folder.parent / 'inputs' / name) == expected, name
    for name, expected in manifest.get('source_sha256', {}).items():
        assert sha(folder / name) == expected, name
    deck_text = deck.read_text()
    section, temp = conditions(lane, manifest, deck_text)
    stimulus(lane, manifest, deck_text, read(folder / 'stimulus.json'))

    waveform = folder / 'waveform.dat.gz'
    expected = result.get('waveform', {}).get('sha256', result.get('gzip_sha256'))
    raw_hash = result.get('waveform', {}).get('raw_sha256', result.get('raw_sha256'))
    if expected:
        assert sha(waveform) == expected
        if rehash:
            with gzip.open(waveform, 'rb') as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == raw_hash
    else:
        assert not result.get('simulation_complete'), 'Completed case lacks native trace'

    current = result.get('current_mA' if lane == 'vcsel' else 'current_uA')
    if current is not None:
        values = np.loadtxt(waveform, skiprows=1, ndmin=2, usecols=(1,))
        assert values.shape[0] == 1
        factor = 1000 if lane == 'vcsel' else 1e6
        assert near(float(values[-1, 0]) * factor, current)
        if lane == 'vcsel':
            target = 3 if manifest['pvt_config']['level'] == 0 else 7
            assert target == result['target_mA']
            assert near(100*(current/target - 1), result['error_percent'])
        else:
            target = 25 if manifest['case']['level'] == 0 else 100
            assert target == result['target_uA']
            assert near(100*(current/target - 1), result['DC_error_percent'])
    reanalysis = folder / 'reanalysis.json'
    if lane != 'vcsel':
        effective = result
        if reanalysis.exists():
            effective = read(reanalysis)
            assert effective['original_result_sha256'] == sha(path)
            assert effective['original_manifest_sha256'] == sha(manifest_path)
            assert effective['gzip_sha256'] == expected
            assert effective['raw_sha256'] == raw_hash
        for frame in effective.get('frames', []):
            energy_ledger(frame['source_energy_J'], frame['energy_pJ_per_attempted_payload_bit'],
                          4096, ['VIN', 'VREF', 'VLED', 'VDD', 'VD0', 'VD1', 'VDISABLE'])
    analysis = folder / 'analysis.json'
    if analysis.exists():
        receive = read(analysis)
        assert receive['result_sha256'] == sha(path)
        assert receive['manifest_sha256'] == sha(manifest_path)
        assert manifest['frame_bits'] == 4736 and manifest['attempted_payload_bits'] == 4096
        energy_ledger(result['energy_by_port'], result['energy_per_attempted_payload_bit_pJ'],
                      4096, ['VLASER', 'VDD', 'VREF', 'VD', 'VDB', 'VSET', 'VREGSET', 'VPHY'])
        if receive['combined_screen_pass']:
            checks = receive['pathways']['actual_graph_5GHzRX']
            assert checks['errors'] == 0 and checks['worst_signed_margin_uAeq'] >= 7.5
            assert checks['one_sided_margin_UI'] >= .37
            assert result['dynamic_screen_pass'] and receive['DC_screen_pass']
    solver_complete = bool(result.get('simulation_ok') and (result.get('simulation_complete') or reanalysis.exists()))
    return dict(case=str(folder.relative_to(ROOT)), lane=lane, corner=section, temp_C=temp,
                result_sha256=sha(path), native_sha256=expected,
                solver_complete=solver_complete, analysis_error=result.get('analysis_error'),
                execution_provenance_correction_sha256=sha(correction) if correction.exists() else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rehash-uncompressed', action='store_true')
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    lanes = ('a', 'b', 'vcsel')
    def experiment_paths(filename):
        return [p for lane in lanes for p in sorted((BUILD / lane).rglob(filename))
                if 'source-equivalence' not in p.relative_to(BUILD).parts]

    paths = experiment_paths('result.json')
    pending = [str(p.parent.relative_to(ROOT)) for p in experiment_paths('manifest.json')
               if not (p.parent / 'result.json').exists()]
    completed = []
    problems = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [(p, pool.submit(check_case, p, args.rehash_uncompressed)) for p in paths]
        for path, future in futures:
            try:
                completed.append(future.result())
            except Exception as exc:
                frame = exc.__traceback__
                while frame.tb_next:
                    frame = frame.tb_next
                problems.append({'case': str(path.parent.relative_to(ROOT)), 'error': repr(exc),
                                 'line': frame.tb_lineno})
    if args.final:
        assert all(any(c['lane'] == lane for c in completed) for lane in lanes)
    passed = not problems and (not args.final or not pending)
    receipt = {'mode': 'final' if args.final else 'interim', 'passed': passed,
               'cases_checked': len(completed), 'checked_uncompressed_sha': args.rehash_uncompressed,
               'pending': pending, 'problems': problems, 'cases': completed,
               'scope': 'Provenance and invariant input checks. Solver completeness, DC, stress, shutdown and RX pass remain per-case fields.'}
    if args.final:
        (EVIDENCE / 'validation.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'cases'}, indent=2))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
