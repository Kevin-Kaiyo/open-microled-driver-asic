#!/usr/bin/env python3
"""Run the frozen r10 VCSEL transistor circuit on accelerated NRZ frames."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

import numpy as np

from replay import ROOT, VCSEL_ORIGINAL, module, read_json, sha

BUILD = ROOT / 'build/highspeed-workbench-20261110/vcsel-x10'
PINNED = ROOT / '.cache/pdk/gf180mcu'
R10 = ROOT / 'analog/circuits/vcsel_robustness_20261029/regulated-r10.spice'
LOAD = ROOT / 'analog/models/vcsel_research_20261027/vcsel_research.spice'
LEGACY = ROOT / 'scripts/three_gbps_experiment/vcsel_driver_run.py'
ENERGY = ROOT / 'scripts/fair_driver_v1/run.py'
RUNNER = ROOT / 'scripts/vcsel_robustness_20261029/run_r10.py'
SAVED = ROOT / 'build/vcsel-robustness-20261029/frame-TT-r10'
FRAME = 4736
PAYLOAD = 4096


def emit(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def make_deck(directory, net_rate, edge_ps, steps):
    frozen = read_json(SAVED / 'manifest.json')
    configs = frozen['config']
    assert configs['nbits'] == FRAME and configs['variant'] == 'regulated'
    sources = {'design.ngspice': PINNED / 'design.ngspice',
               'sm141064.ngspice': PINNED / 'sm141064.ngspice',
               'vcsel.spice': LOAD, 'driver.spice': R10, 'runner.py': RUNNER}
    expected = {Path(path).name: digest for path, digest in frozen['source_hashes'].items()}
    for name, source in sources.items():
        assert sha(source) == expected[name], f'Frozen input mismatch: {name}'
        if name != 'runner.py':
            shutil.copy2(source, directory / name)
    stimulus = SAVED / 'stimulus.json'
    assert sha(stimulus) == frozen['stimulus_sha256']
    shutil.copy2(stimulus, directory / 'stimulus.json')
    bits = read_json(stimulus)['bits']
    assert len(bits) == FRAME
    ui = PAYLOAD / FRAME / (net_rate * 1e9)
    end = FRAME * ui
    edge = edge_ps * 1e-12
    if not 0 < edge < ui:
        raise ValueError('PWL edge must fit in one line UI')
    base_path = SAVED / 'testbench.spice'
    assert sha(base_path) == read_json(SAVED / 'result.json')['deck_sha256']
    base_deck = base_path.read_text()
    deck = re.sub(r'(?m)^(\.include|\.lib) "[^"]+/([^/"]+)"', r'\1 "\2"', base_deck)
    legacy = module(LEGACY, 'vcsel_x10_stimulus')
    for name, node, symbols in [('VD', 'd_src', bits), ('VDB', 'db_src', [1-b for b in bits])]:
        pwl = legacy.pwl(symbols, ui, configs['voltage'], edge)
        deck, count = re.subn(rf'(?m)^{name} {node} 0 PWL\([^)]*\)',
                              f'{name} {node} 0 {pwl}', deck)
        assert count == 1
    deck, count = re.subn(r'(?m)^tran .+$', f'tran {ui/steps} {end} 0 {ui/steps}', deck)
    assert count == 1
    deck = f'VCSEL r10 NRZ net {net_rate:g} Gb/s, {edge_ps:g} ps edges\n' + deck.split('\n', 1)[1]
    path = directory / 'testbench.spice'
    path.write_text(deck)
    identity = {
        'case': directory.name, 'net_Gbps': net_rate, 'line_GBd': 1e-9/ui,
        'UI_ps': ui*1e12, 'source_edge_ps_0_to_100': edge_ps, 'steps_per_UI': steps,
        'frame_bits': FRAME, 'attempted_payload_bits': PAYLOAD, 'end_s': end,
        'scope': 'Frozen r10 transistor schematic and 850 nm model; original 150 fF CJ, 0.5 ohm/0.2 nH, 25 C TT; only PWL timing, simulation time and output path change.',
        'original_deck_sha256': sha(base_path), 'deck_sha256': sha(path),
        'baseline_result_sha256': sha(SAVED / 'result.json'), 'source_sha256': expected,
        'stimulus_sha256': frozen['stimulus_sha256'], 'expressions': frozen['expressions'],
        'ports': frozen['ports'], 'devices': frozen['devices'],
        'ngspice': subprocess.check_output(['ngspice','--version'], text=True),
        'run_script_sha256': sha(Path(__file__)),
    }
    emit(directory / 'manifest.json', identity)
    return identity


def run(rate, edge, steps):
    folder = BUILD / f'net{rate:g}-edge{edge:g}-s{steps}'
    folder.mkdir(parents=True, exist_ok=False)
    identity = make_deck(folder, rate, edge, steps)
    solve(folder, identity)


def solve(folder, identity):
    print(f'r10: {folder.name}, {identity["line_GBd"]:.3f} GBd', flush=True)
    start = time.monotonic()
    log = folder / 'ngspice.log'
    code = None
    with log.open('w') as handle:
        try:
            code = subprocess.run(['ngspice', '-b', 'testbench.spice'], cwd=folder,
                                  stdout=handle, stderr=subprocess.STDOUT, timeout=480).returncode
        except subprocess.TimeoutExpired:
            pass
    result = {'exit_code': code, 'solve_s': time.monotonic()-start,
              'log_sha256': sha(log), 'simulation_ok': False}
    wave = folder / 'waveform.dat'
    if code == 0 and wave.is_file():
        raw = np.loadtxt(wave, skiprows=1)
        t = raw[:,0]
        end = identity['end_s']
        assert np.isfinite(raw).all() and np.all(np.diff(t)>0) and abs(t[-1]-end) < 1e-16
        ix = {expr: k+1 for k, expr in enumerate(identity['expressions'])}
        assert raw.shape[1] == len(ix)+1
        legacy = module(LEGACY, 'vcsel_x10_stress')
        stress = legacy.stress(raw, ix, identity['devices'])
        energy = module(ENERGY, 'vcsel_x10_energy')
        ledger = {p: energy.signed_integrals(t, -raw[:,ix[f'v({n})']]*raw[:,ix[f'i({p})']])
                  for p, n in identity['ports'].items()}
        total = {k: sum(row[k] for row in ledger.values()) for k in ['positive_J','returned_J','net_J']}
        assert np.isclose(total['positive_J']-total['returned_J'], total['net_J'], atol=1e-22, rtol=1e-9)
        max_pair = max((abs(value), row['instance'], pair) for row in stress
                       for pair,value in row['max_abs_terminal_V'].items())
        result.update(simulation_ok=True, sample_count=len(t), max_native_step_ps=float(np.diff(t).max()*1e12),
                      current_min_mA=float(raw[:,1].min()*1e3), current_max_mA=float(raw[:,1].max()*1e3),
                      stress=stress, terminal_peak=dict(value_V=max_pair[0], instance=max_pair[1], pair=max_pair[2]),
                      max_body_forward_V=max(row['max_body_forward_V'] for row in stress),
                      terminal_screen_pass=all(row['screen_pass'] for row in stress),
                      energy_by_port=ledger, total_energy=total,
                      energy_per_attempted_payload_bit_pJ={k.replace('_J',''): v*1e12/PAYLOAD for k,v in total.items()},
                      waveform=legacy.compress(wave))
    emit(folder / 'result.json', result)
    if not result['simulation_ok']:
        raise RuntimeError(f'Incomplete solve: {folder}')
    print(f'completed {folder.name}: {result["sample_count"]} points, {result["solve_s"]:.2f} s', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--net', type=float, required=True)
    parser.add_argument('--edge-ps', type=float, default=20)
    parser.add_argument('--steps', type=int, default=40)
    args = parser.parse_args()
    if not (args.net>0 and args.steps>=20):
        parser.error('positive net rate and >=20 steps per UI required')
    run(args.net, args.edge_ps, args.steps)
