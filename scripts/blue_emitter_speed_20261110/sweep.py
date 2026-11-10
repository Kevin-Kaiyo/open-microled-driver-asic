#!/usr/bin/env python3
"""Real frozen-schematic rate sweep, preserving native traces and source hashes.

No waveform rescaling is used. Each new rate executes ngspice afresh. The
historical model remains a yellow 20 um static I-V plus hypothetical dynamics.
"""
import argparse
import concurrent.futures
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/highspeed_workbench_20261110'))
from replay import module, read_json, sha
import vcsel_x10_run as vc

BUILD = ROOT / 'build/blue-emitter-speed-review-20261110'
MICRO = BUILD / 'microled'
OLD = ROOT / 'build/microled-dynamic-v1/electrical/run-r1'


def emit(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def initialize():
    if (MICRO / 'manifest.json').exists():
        return
    MICRO.mkdir(parents=True, exist_ok=False)
    for name in ('inputs', 'execution-sources'):
        shutil.copytree(OLD / name, MICRO / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(OLD / 'stimulus.json', MICRO / 'stimulus.json')
    manifest = read_json(OLD / 'manifest.json')
    manifest['inputs'] = {k: v for k,v in manifest['inputs'].items()
                          if '__pycache__' not in k}
    manifest['rate_sweep_origin'] = {'manifest': str((OLD/'manifest.json').relative_to(ROOT)),
                                   'sha256': sha(OLD/'manifest.json'),
                                   'omitted_only': 'Host-specific Python bytecode cache'}
    emit(MICRO / 'plan.json', [])
    manifest['plan_sha256'] = sha(MICRO / 'plan.json')
    emit(MICRO / 'manifest.json', manifest)


def micro_case(route, rate, cap, steps):
    return dict(name=f'TT-{route}-net{rate:g}-C{cap:g}fF-S{steps}', route=route,
                corner='typical', temp_C=27, vdd_V=3.3, led_cap_F=cap*1e-15,
                net_rate_Gbps=rate, steps_per_symbol=steps, timeout_s=900,
                group='actual_transistor_rate_sweep')


def run_micro(case):
    runner = module(MICRO / 'execution-sources/wrapper.py', 'frozen_microled_sweep')
    runner.ROOT = ROOT
    runner.verify(MICRO)
    print('START '+case['name'], flush=True)
    result = runner.run_one(MICRO, case)
    print(json.dumps({'case': case['name'], 'simulation_ok': result['simulation_ok'],
                      'elapsed_s': result['elapsed_s'], 'analysis_error': result.get('analysis_error')},
                     ensure_ascii=False), flush=True)
    return result


def run_vcsel(rate, steps):
    folder = BUILD / 'vcsel' / f'net{rate:g}-edge20-s{steps}'
    if (folder/'result.json').exists():
        return read_json(folder/'result.json')
    folder.mkdir(parents=True, exist_ok=False)
    identity = vc.make_deck(folder, rate, 20, steps)
    identity['sweep_dispatch_sha256'] = sha(Path(__file__))
    emit(folder/'manifest.json', identity)
    vc.solve(folder, identity)
    return read_json(folder/'result.json')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=['microled','vcsel'])
    ap.add_argument('--rates', nargs='+', type=float, required=True)
    ap.add_argument('--routes', default='ABC')
    ap.add_argument('--cap-fF', type=float, default=200)
    ap.add_argument('--steps', type=int, default=40)
    args = ap.parse_args()
    assert all(0 < r <=32 for r in args.rates) and args.steps>=40
    if args.mode=='microled':
        if any(r>3.2 for r in args.rates):
            ap.error('This MicroLED wrapper retains the historical receiver export; currently supported sweep rates are 0 < rate <= 3.2 Gb/s. Higher-rate work requires a separately versioned evaluator.')
        if not args.routes or set(args.routes)-set('ABC') or args.cap_fF<0:
            ap.error('MicroLED routes must be A/B/C and capacitance must be nonnegative.')
        initialize()
        cases = [micro_case(route, rate, args.cap_fF, args.steps)
                 for rate in args.rates for route in args.routes]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for result in pool.map(run_micro, cases):
                if not result['simulation_ok'] or result.get('analysis_error'):
                    raise RuntimeError('Failed simulation; retained logs')
    else:
        for rate in args.rates:
            run_vcsel(rate, args.steps)


if __name__ == '__main__':
    main()
