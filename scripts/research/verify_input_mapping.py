"""Preserve the actual pre-TRACE_REALTIME TB and verify default RTL equivalence.

This bridges a documented testbench-only revision without replacing historical
run hashes or rerunning their SPICE simulations. The public source snapshot is
the exact old TB; current source bytes and RTL are frozen only in build/.
"""
from pathlib import Path
import argparse
import csv
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OLD_SHA = 'ce23d247156ea1e28a0abaefa84ad018eade72c18f4c6d1e1093f4d5ca4ed9ea'
CURRENT_SHA = 'f0fc5b991974b79a7a229567ece574da0a052367ccee9ebce69f6e4c41bf2dbe'
RTL_SHA = '690e4f6f08d58485dcbe0bf42eb00cfae4810a813f993b4ae6fe8af8a6d05de6'
TB_PATH = 'sim/rtl/tb_pixel_pwm.v'
CASES = [(0, 1), (1, 1), (64, 1), (128, 1), (192, 1), (255, 1),
         (256, 1), (257, 1), (511, 1), (256, 0)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(arguments, directory, log):
    run = subprocess.run([str(a) for a in arguments], cwd=directory,
                         capture_output=True, text=True)
    (directory / log).write_text(run.stdout + run.stderr)
    if run.returncode:
        raise RuntimeError(f'Exit {run.returncode}; inspect {directory / log}')
    return run.stdout + run.stderr


def exhaustive_stats(log):
    counts = re.search(r'PASS pixel_pwm:.*?(\d+) frames and (\d+) slot/value checks', log)
    events = re.search(r'PASS pixel_pwm output events: (\d+) known events;.*?minimum high=([0-9.]+) ns low=([0-9.]+) ns', log)
    if not counts or not events:
        raise RuntimeError('Exhaustive run did not finish its functional/event checks')
    return dict(frames=int(counts[1]), slot_value_checks=int(counts[2]),
                known_events=int(events[1]), minimum_high_ns=float(events[2]),
                minimum_low_ns=float(events[3]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot-source', type=Path,
                        help='initial exact old TB copied from an actual-run frozen input')
    args = parser.parse_args()
    evidence = ROOT / 'evidence/research'
    old = evidence / 'input-snapshots' / OLD_SHA / TB_PATH
    evidence.mkdir(parents=True, exist_ok=True)
    if args.snapshot_source:
        origin = args.snapshot_source.resolve()
        if sha(origin) != OLD_SHA:
            raise RuntimeError('Requested snapshot source does not have the recorded old TB hash')
        if old.exists() and sha(old) != OLD_SHA:
            raise RuntimeError('Refusing to overwrite a different public snapshot')
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_bytes(origin.read_bytes())
        origin_locator = str(origin.relative_to(ROOT))
    else:
        origin_locator = str(old.relative_to(ROOT))
    current = ROOT / TB_PATH
    rtl = ROOT / 'rtl/pixel_pwm.v'
    for path, expected in [(old, OLD_SHA), (current, CURRENT_SHA), (rtl, RTL_SHA)]:
        if not path.exists() or sha(path) != expected:
            raise RuntimeError(f'Input differs from this revision-pair review: {path}')
    sources = {str(p.relative_to(ROOT)): sha(p) for p in [old, current, rtl, Path(__file__)]}
    raw_root = ROOT / 'build/research'
    raw_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='input-mapping-', dir=raw_root))
    for name, path in [('old-tb.v', old), ('current-tb.v', current), ('pixel_pwm.v', rtl)]:
        shutil.copyfile(path, work / name)
    versions = {}
    for tool in ['iverilog', 'vvp']:
        text = execute([tool, '-V'], work, f'{tool}-version.log')
        versions[tool] = dict(version=text.splitlines()[0],
                              binary_sha256=sha(Path(shutil.which(tool)).resolve()))
    binaries = {}
    exhaustive = {}
    for name in ['old', 'current']:
        binary = work / f'{name}.vvp'
        execute(['iverilog', '-g2012', '-Wall', '-s', 'tb_pixel_pwm', '-o', binary,
                 work / 'pixel_pwm.v', work / f'{name}-tb.v'], work, f'{name}-compile.log')
        binaries[name] = binary
        log = execute(['vvp', binary, f'+OUT={work / (name + "-default.csv")}'],
                      work, f'{name}-default-exhaustive.log')
        exhaustive[name] = exhaustive_stats(log)
    if exhaustive['old'] != exhaustive['current']:
        raise RuntimeError('Default exhaustive statistics differ')
    if exhaustive['current'] != dict(frames=518, slot_value_checks=133159,
                                    known_events=543, minimum_high_ns=1000., minimum_low_ns=1000.):
        raise RuntimeError('Default exhaustive coverage differs from the reviewed baseline')
    if (work / 'old-default.csv').read_bytes() != (work / 'current-default.csv').read_bytes():
        raise RuntimeError('Default pre-exhaustive exported event trace differs')
    traces = []
    for duty, enable in CASES:
        case = f'd{duty:03d}-en{enable}'
        paths = []
        for name, binary in binaries.items():
            path = work / f'{case}-{name}.csv'
            execute(['vvp', binary, '+TRACE_ONLY=1', f'+DUTY={duty}', f'+ENABLE={enable}',
                     f'+OUT={path}'], work, f'{case}-{name}.log')
            paths.append(path)
        if paths[0].read_bytes() != paths[1].read_bytes():
            raise RuntimeError('Default trace differs: ' + case)
        with paths[0].open() as handle:
            count = sum(1 for _ in csv.DictReader(handle))
        traces.append(dict(case=case, duty=duty, enable=enable, event_rows=count,
                           old_trace_sha256=sha(paths[0]), current_trace_sha256=sha(paths[1]),
                           byte_identical=True))
    if any(sha(ROOT / path) != digest for path, digest in sources.items()):
        raise RuntimeError('A reviewed source changed during the comparisons')
    # Publish compact proof only after all 22 simulations passed.
    outputs = {}
    for name in ['old', 'current']:
        dest = evidence / f'input-mapping-{name}-exhaustive.log'
        shutil.copyfile(work / f'{name}-default-exhaustive.log', dest)
        outputs[str(dest.relative_to(ROOT))] = sha(dest)
    trace_folder = evidence / 'input-mapping-traces'
    trace_folder.mkdir(exist_ok=True)
    for row in traces:
        dest = trace_folder / (row['case'] + '.csv')
        shutil.copyfile(work / (row['case'] + '-old.csv'), dest)
        row['common_trace_file'] = str(dest.relative_to(ROOT))
        outputs[str(dest.relative_to(ROOT))] = sha(dest)
    difference = evidence / 'input-mapping-tb.diff'
    difference.write_text(''.join(difflib.unified_diff(
        old.read_text().splitlines(keepends=True), current.read_text().splitlines(keepends=True),
        fromfile=str(old.relative_to(ROOT)), tofile=TB_PATH)))
    outputs[str(difference.relative_to(ROOT))] = sha(difference)
    affected = []
    for path in sorted((ROOT / 'evidence').rglob('*.json')):
        if path.parent == evidence:
            continue
        record = json.loads(path.read_text())
        if not isinstance(record, dict):
            continue
        for key in ['source_hashes', 'source_sha256', 'audit_inputs_sha256', '']:
            hashes = record.get(key) if key else record
            if isinstance(hashes, dict) and hashes.get(TB_PATH) == OLD_SHA:
                affected.append(dict(evidence_file=str(path.relative_to(ROOT)),
                                     hash_field=(key + '.' if key else '') + TB_PATH,
                                     recorded_input_sha256=OLD_SHA))
    manifest = dict(
        schema_version=1, evidence_level='RTL default-behavior equivalence across one testbench logging revision; no SPICE rerun or physical/SDF equivalence claim',
        passed=True, raw_directory=str(work.relative_to(ROOT)),
        historical_input=dict(original_path=TB_PATH, sha256=OLD_SHA,
                              public_snapshot=str(old.relative_to(ROOT)), copied_from=origin_locator),
        current_input=dict(path=TB_PATH, sha256=CURRENT_SHA),
        rtl_input=dict(path='rtl/pixel_pwm.v', sha256=RTL_SHA),
        revision_scope='TRACE_REALTIME is optional and defaults to 0; tests omit the flag. When explicitly 1, CSV formatting uses $realtime with 0.001 ns precision. RTL and default integer-time output path are unchanged.',
        interpretation='Historical source_hashes remain the hashes actually used. This mapping preserves old bytes and separately demonstrates default functional compatibility of current source; it does not retag past runs as executed with the new TB.',
        affected_evidence_records=affected,
        simulation_runs=22, exhaustive_runs=2, trace_runs=20, paired_trace_cases=10,
        exhaustive_statistics=exhaustive, default_exported_trace_byte_identical=True,
        default_exported_trace_sha256=sha(work / 'old-default.csv'), trace_comparisons=traces,
        source_hashes=sources, output_hashes=outputs, tools=versions)
    (evidence / 'input-mapping.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k:manifest[k] for k in ['passed', 'raw_directory', 'simulation_runs',
                       'paired_trace_cases', 'exhaustive_statistics']}, indent=2))


if __name__ == '__main__':
    main()
