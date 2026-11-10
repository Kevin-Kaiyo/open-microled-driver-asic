"""Controlled MicroLED B experiment with ideal complementary gate excitation."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np

from replay import ROOT, module, read_json, relative, sha

SOURCE = ROOT / 'build/microled-dynamic-v1/electrical/run-r1'
EVIDENCE = ROOT / 'evidence/highspeed-workbench-20261110'
DROPPED = {'XRIN', 'XINV1N', 'XINV1P', 'XINV2N', 'XINV2P'}


def case_id(cap):
    return f'TT-B-C{cap}fF-S40'


def modify(work, cap):
    case = case_id(cap)
    original = SOURCE / 'cases' / case
    folder = work / 'cases' / case
    folder.mkdir(parents=True)
    deck_source = original / 'testbench.spice'
    if sha(deck_source) != read_json(original / 'result.json')['deck_sha256']:
        raise ValueError('Original deck does not match the frozen result')
    deck = deck_source.read_text()
    stimulus = re.search(r'^VD0 data0_src 0 PWL\((.+)\)$', deck, re.M)[1]
    tokens = stimulus.split()
    assert len(tokens) % 2 == 0 and set(map(float, tokens[1::2])) == {0., 3.3}
    original_net = SOURCE / 'inputs/route_b.spice'
    lines = original_net.read_text().splitlines()
    assert {line.split()[0] for line in lines if line.split() and line.split()[0] in DROPPED} == DROPPED
    gate_net = [line for line in lines if not line.split() or line.split()[0] not in DROPPED]
    end = gate_net.index('.ends fair_b')
    gate_net[end:end] = [
        'EGP GP VSS D0 VSS 1',
        'BGB GB VSS V={3.3-v(D0,VSS)}',
    ]
    (folder / 'route_b_gate_bypass.spice').write_text('\n'.join(gate_net) + '\n')
    deck = deck.replace('.include "../../inputs/route_b.spice"',
                        '.include "route_b_gate_bypass.spice"')
    # Reuse one PWL source. The ideal controlled sources bypass the input
    # resistor as well as the on-chip inverter pair.
    assert deck.count('XDRV d0 d1 ') == 1
    deck = deck.replace('XDRV d0 d1 ', 'XDRV data0_src d1 ')
    before, control = deck.split('.control\n', 1)
    setup = '\n'.join(control.splitlines()[:4])
    deck = (before + '.control\n' + setup +
            '\nwrdata waveform.dat i(VSENSE) v(led_a) v(led_k) v(out) '
            'v(xdrv.gp) v(xdrv.gb) v(xdrv.vx) v(xdrv.dummy)\nquit\n.endc\n.end\n')
    assert setup.splitlines()[-1].startswith('tran ')
    (folder / 'testbench.spice').write_text(deck)
    return folder


def receiver_cases(rx_path, stim, t, current):
    rx = module(rx_path, 'microled_gate_bypass_rx')
    rows = {}
    for tau in (200, 25):
        rx.TAU_OPTICAL_S = tau * 1e-12
        r = rx.analyze(t, current, stim, 'B', 3.2)
        rows[f'opt{tau}ps_rx1GHz'] = {
            'bit_errors': r['validation']['bit_errors'],
            'training_error_free': r['checks']['training_error_free'],
            'compared_bits': r['validation']['bit_count'],
            'signed_margin_uAeq': r['validation']['decision_distance_min_uA'],
            'time_margin_ps': r['horizontal_margin']['min_ps'],
            'delay_ps': r['sampling']['delay_s'] * 1e12,
            'pass': r['passed'],
        }
    return rows


def run_case(work, cap, analyze_only=False):
    folder = work / 'cases' / case_id(cap)
    if not analyze_only:
        folder = modify(work, cap)
        with (folder / 'ngspice.log').open('w') as log:
            subprocess.run(['ngspice', '-b', 'testbench.spice'], cwd=folder, stdout=log,
                           stderr=subprocess.STDOUT, timeout=600, check=True)
    raw = folder / 'waveform.dat'
    compressed = folder / 'waveform.dat.gz'
    native = raw if raw.exists() else compressed
    data = np.loadtxt(native, skiprows=1)
    t, current = data[:, :2].T
    if not np.isfinite(data).all() or not np.all(np.diff(t) > 0) or not math.isclose(t[-1], 1.28e-6):
        raise ValueError('Incomplete or invalid SPICE waveform')
    assert np.max(np.abs(data[:, 5] + data[:, 6] - 3.3)) < 1e-6
    if not compressed.exists():
        with raw.open('rb') as src, gzip.open(compressed, 'wb', compresslevel=5) as dst:
            shutil.copyfileobj(src, dst)
    with gzip.open(compressed, 'rb') as stream:
        native_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    if raw.exists() and native_hash != sha(raw):
        raise ValueError('Compressed waveform bytes differ from simulator output')
    row = {
        'cap_fF': cap,
        'rows': len(data),
        'original_deck_sha256': sha(SOURCE / 'cases' / case_id(cap) / 'testbench.spice'),
        'native_sha256': native_hash,
        'current_min_uA': float(current.min() * 1e6),
        'current_max_uA': float(current.max() * 1e6),
        'artifacts': {relative(f): sha(f) for f in sorted(folder.iterdir()) if f != raw},
        'receiver_cases': receiver_cases(work/'inputs/receiver.py', read_json(work/'stimulus.json'), t, current),
    }
    (folder/'result.json').write_text(json.dumps(row, indent=2) + '\n')
    raw.unlink(missing_ok=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--analyze-only', action='store_true', help='Post-process existing solver output')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', args.run_id):
        parser.error('Expected an alphanumeric run ID, with optional hyphens')
    work = ROOT / 'build/highspeed-workbench-20261110/b-gate-bypass' / args.run_id
    if not args.analyze_only:
        work.mkdir(parents=True)
    frozen = read_json(SOURCE/'manifest.json')
    for name, expected in frozen['inputs'].items():
        if name.startswith('__pycache__/'):
            continue
        src = SOURCE/'inputs'/name
        if sha(src) != expected:
            raise ValueError(f'Frozen input changed: {name}')
        dest = work/'inputs'/name
        if not args.analyze_only:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        assert sha(dest) == expected
    assert sha(SOURCE/'stimulus.json') == frozen['stimulus_sha256']
    if not args.analyze_only:
        shutil.copy2(SOURCE/'stimulus.json', work/'stimulus.json')
    assert sha(work/'stimulus.json') == frozen['stimulus_sha256']
    with ThreadPoolExecutor(max_workers=2) as executor:
        rows = list(executor.map(lambda cap: run_case(work, cap, args.analyze_only), (200, 10)))
    out = {
        'run': relative(work),
        'scope': 'TT 27C, net 3.2 Gb/s. Replace five R/MOS input devices with complementary ideal 0/3.3V, 20ps controlled gate sources. Output MOS, LED, package, supplies, reference and fixed v2 RX are unchanged within each capacitance pair.',
        'prior_attempt': 'pair-r1 timed out in both cases at 300 s with repeated PWL sources. pair-r2 reuses the original data PWL through ideal controlled sources and uses a 600 s cap.',
        'limit': 'The ideal source supplies gate charge. This is a controlled upper-bound experiment, not a buildable replacement. No energy or reliability ranking.',
        'ngspice': subprocess.check_output(['ngspice', '--version'], text=True).strip(),
        'script_sha256': sha(Path(__file__)),
        'inputs_sha256': {relative(f): sha(f) for f in sorted((work/'inputs').rglob('*')) if f.is_file()},
        'stimulus_sha256': frozen['stimulus_sha256'],
        'cases': rows,
    }
    (EVIDENCE/'b-gate-bypass.json').write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps([row['receiver_cases'] for row in rows], indent=2))


if __name__ == '__main__':
    main()
