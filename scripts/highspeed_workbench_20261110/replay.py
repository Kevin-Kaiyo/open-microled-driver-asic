#!/usr/bin/env python3
"""Replay one immutable, historical high-speed transistor case into a fresh work directory."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'build/highspeed-workbench-20261110/replay'
MICRO_ORIGINAL = ROOT / 'build/microled-dynamic-v1/electrical/run-r1'
VCSEL_ORIGINAL = ROOT / 'build/vcsel-robustness-20261029/frame-TT-r10'
VCSEL_ANALYSIS = 'fixed-v3-r2'
HISTORICAL_CACHE = '__pycache__/receiver.cpython-312.pyc'


def read_json(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def relative(path):
    return str(path.relative_to(ROOT))


def microled(work, route, portable=False):
    for name in ('inputs', 'execution-sources'):
        shutil.copytree(MICRO_ORIGINAL / name, work / name)
    for name in ('manifest.json', 'stimulus.json', 'plan.json'):
        shutil.copy2(MICRO_ORIGINAL / name, work / name)
    # Old manifests pinned one accidental host-specific cache. Keep the
    # historical manifest intact and relax only its missing copy in this run.
    if portable and not (work / 'inputs' / HISTORICAL_CACHE).exists():
        manifest_path = work / 'manifest.json'
        manifest = read_json(manifest_path)
        historical_sha = sha(manifest_path)
        removed_hash = manifest['inputs'].pop(HISTORICAL_CACHE, None)
        if removed_hash:
            manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
            (work / 'portable-inputs.json').write_text(json.dumps({
                'historical_manifest_sha256': historical_sha,
                'omitted_cache': HISTORICAL_CACHE,
                'omitted_sha256': removed_hash,
                'working_manifest_sha256': sha(manifest_path),
            }, indent=2) + '\n')
    name = f'TT-{route}-C200fF-S40'
    case = next(entry for entry in read_json(work / 'plan.json') if entry['name'] == name)
    case_dir = work / 'cases' / name
    old_dir = MICRO_ORIGINAL / 'cases' / name
    previous = read_json(old_dir / 'result.json')
    assert previous['case'] == case
    source = work / (previous.get('runner_source_path') or 'execution-sources/wrapper.py')
    assert sha(source) == previous['runner_sha256']
    runner = module(source, 'microled_frozen_runner')
    runner.ROOT = ROOT
    runner.verify(work)
    text, _ = runner.deck(work, case)
    assert hashlib.sha256(text.encode()).hexdigest() == previous['deck_sha256']
    print(f'ngspice replay {name} into {relative(case_dir)}', flush=True)
    result = runner.run_one(work, case)
    return case_dir, old_dir, previous, result, None


def normalized_vcsel_deck(path):
    lines = path.read_text().splitlines()
    for index, line in enumerate(lines):
        if line.startswith(('.include ', '.lib ')):
            prefix, reference, suffix = line.split('"')
            lines[index] = prefix + '"' + Path(reference).name + '"' + suffix
    return lines


def vcsel(work):
    script_dir = ROOT / 'scripts/vcsel_robustness_20261029'
    runner = module(script_dir / 'run_r10.py', 'vcsel_r10_runner')
    runner.BUILD = work
    frozen = read_json(VCSEL_ORIGINAL / 'manifest.json')
    source_paths = {
        'driver.spice': VCSEL_ORIGINAL / 'inputs/driver.spice',
        'runner.py': script_dir / 'run_r10.py',
        'design.ngspice': ROOT / '.cache/pdk/gf180mcu/design.ngspice',
        'sm141064.ngspice': ROOT / '.cache/pdk/gf180mcu/sm141064.ngspice',
        'vcsel.spice': ROOT / 'analog/models/vcsel_research_20261027/vcsel_research.spice',
    }
    for path, expected in frozen['source_hashes'].items():
        assert sha(source_paths[Path(path).name]) == expected, path
    assert runner.circuit(frozen['config']['variant']) == source_paths['driver.spice'].read_text()
    previous = read_json(VCSEL_ORIGINAL / 'result.json')
    name = frozen['case']
    case_dir = work / name
    print(f'ngspice replay {name} into {relative(case_dir)}', flush=True)
    result = runner.run(name, **frozen['config'])
    assert normalized_vcsel_deck(case_dir / 'testbench.spice') == normalized_vcsel_deck(
        VCSEL_ORIGINAL / 'testbench.spice'
    )
    assert sha(case_dir / 'stimulus.json') == frozen['stimulus_sha256']
    analysis = None
    if result['simulation_ok']:
        previous_analysis = read_json(VCSEL_ORIGINAL / f'analysis-{VCSEL_ANALYSIS}' / 'plan.json')
        for path, expected in previous_analysis['sources'].items():
            assert sha(ROOT / path) == expected, path
        sys.path.insert(0, str(script_dir))
        receiver = module(script_dir / 'analyze.py', 'vcsel_fixed_v3')
        receiver.BUILD = work
        analysis = receiver.analyze(name, grid_ps=previous_analysis['grid_ps'], label=VCSEL_ANALYSIS)
    return case_dir, VCSEL_ORIGINAL, previous, result, analysis


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('route', choices=('A', 'B', 'C', 'VCSEL'))
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--portable', action='store_true',
                        help='Allow the missing historical MicroLED Python cache on restore')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*', args.run_id):
        parser.error('--run-id must be a simple name')
    work = BUILD / args.run_id / args.route
    work.mkdir(parents=True, exist_ok=False)
    if args.route == 'VCSEL':
        case_dir, old_dir, previous, result, analysis = vcsel(work)
        old_raw = previous.get('waveform', {}).get('raw_sha256')
        new_raw = result.get('waveform', {}).get('raw_sha256')
    else:
        case_dir, old_dir, previous, result, analysis = microled(work, args.route, args.portable)
        old_raw = previous.get('raw_sha256')
        new_raw = result.get('raw_sha256')
    receipt = {
        'route': args.route,
        'run_id': args.run_id,
        'dispatch_script_sha256': sha(Path(__file__)),
        'old_case': relative(old_dir),
        'new_case': relative(case_dir),
        'solver_command': ['ngspice', '-b', 'testbench.spice'],
        'solver_version': subprocess.check_output(['ngspice', '--version'], text=True),
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'exit_code': result['exit_code'],
        'simulation_ok': result['simulation_ok'],
        'analysis_error': result.get('analysis_error'),
        'simulation_elapsed_s': result.get('simulation_elapsed_s', result['elapsed_s']),
        'old_result_sha256': sha(old_dir / 'result.json'),
        'new_result_sha256': sha(case_dir / 'result.json'),
        'old_deck_sha256': previous['deck_sha256'],
        'new_deck_sha256': result['deck_sha256'],
        'exact_deck_sha256_match': previous['deck_sha256'] == result['deck_sha256'],
        'normalized_deck_match': True,
        'old_native_raw_sha256': old_raw,
        'new_native_raw_sha256': new_raw,
        'exact_native_raw_sha256_match': new_raw is not None and new_raw == old_raw,
        'analysis_path': relative(case_dir / f'analysis-{VCSEL_ANALYSIS}' / 'result.json') if analysis else None,
    }
    (work / 'replay-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, ensure_ascii=False), flush=True)
    if not result['simulation_ok'] or result.get('analysis_error'):
        raise SystemExit('Replay simulation or analysis failed. Retained case logs.')


if __name__ == '__main__':
    main()
