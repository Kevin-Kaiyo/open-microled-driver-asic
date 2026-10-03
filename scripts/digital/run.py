"""Hash-checked GF180 PWM synthesis and bounded gate simulation regression.

No placement, STA, SDF, parasitic extraction or physical sign-off is performed.
"""
from pathlib import Path
import argparse
import collections
import csv
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quoted(path):
    return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"') + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdk', type=Path, default=ROOT / 'build/layout/pdk/gf180mcuD')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/digital')
    parser.add_argument('--publish-evidence', action='store_true')
    args = parser.parse_args()
    pdk, build = args.pdk.resolve(), args.output.resolve()
    build.mkdir(parents=True, exist_ok=True)
    (build / 'summary.json').unlink(missing_ok=True)
    invocations = []

    def command(argv, name):
        argv = [str(a) for a in argv]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
        (build / name).write_text(result.stdout + result.stderr)
        invocations.append(dict(argv=argv, log=name, exit_code=result.returncode))
        (build / 'commands.json').write_text(json.dumps(invocations, indent=2) + '\n')
        if result.returncode:
            raise RuntimeError(f'{argv[0]} exit={result.returncode}; see {build / name}')
        return result.stdout + result.stderr

    for tool in ('yosys', 'yosys-abc', 'iverilog', 'vvp'):
        if not shutil.which(tool):
            raise RuntimeError(f'Missing {tool}; see docs/digital/README.md')
    lock = json.loads((HERE / 'library-lock.json').read_text())
    for name, digest in lock['files'].items():
        if sha(pdk / name) != digest:
            raise RuntimeError(f'PDK input hash mismatch: {name}')
    versions = {}
    for tool, flags in (('yosys', ['-V']), ('yosys-abc', ['-c', 'version']), ('iverilog', ['-V']), ('vvp', ['-V'])):
        text = command([tool, *flags], f'version-{tool}.log')
        versions[tool] = dict(text=text.strip(), binary_sha256=sha(Path(shutil.which(tool)).resolve()))

    rtl, tb = ROOT / 'rtl/pixel_pwm.v', ROOT / 'sim/rtl/tb_pixel_pwm.v'
    command(['iverilog', '-g2012', '-Wall', '-s', 'tb_pixel_pwm', '-o', build / 'rtl.vvp', rtl, tb], 'rtl-compile.log')
    rtl_log = command(['vvp', build / 'rtl.vvp', f'+OUT={build / "rtl-events.csv"}'], 'rtl-selfcheck.log')
    command([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_bridge.py', '-v'], 'bridge-tests.log')
    library = pdk / next(n for n in lock['files'] if n.endswith('.lib'))
    netlist, mapped = build / 'pixel_pwm_mapped.v', build / 'pixel_pwm_mapped.json'
    script = '\n'.join([
        f'read_liberty -lib {quoted(library)}',
        f'read_verilog {quoted(rtl)}',
        'synth -top pixel_pwm -noabc',
        f'dfflibmap -liberty {quoted(library)}',
        f'abc -liberty {quoted(library)}',
        'clean', 'check -assert',
        f'stat -top pixel_pwm -liberty {quoted(library)}',
        f'write_verilog -noattr {quoted(netlist)}',
        f'write_json {quoted(mapped)}', ''])
    (build / 'synthesis.ys').write_text(script)
    synthesis_log = command(['yosys', '-Q', '-T', '-s', build / 'synthesis.ys'], 'synthesis.log')
    design = json.loads(mapped.read_text())['modules']['pixel_pwm']
    cells = design['cells']
    if any(not c['type'].startswith(lock['library'] + '__') for c in cells.values()):
        raise RuntimeError('Unmapped/internal cell remains')
    pwm_bit = design['ports']['pwm']['bits']
    drivers = [(name, c) for name, c in cells.items()
               for pin, bits in c['connections'].items()
               if c['port_directions'].get(pin) == 'output' and bits == pwm_bit]
    if (len(drivers) != 1 or drivers[0][1]['type'] != lock['library'] + '__dffq_1'
            or drivers[0][1]['connections']['CLK'] != design['ports']['clk']['bits']):
        raise RuntimeError('PWM must be directly driven by one rising-edge DFF clocked from clk')
    model_paths = [pdk / n for n in lock['files'] if n.endswith('.v')]
    wrapper = '`timescale 1ns/1ps\n' + ''.join(f'`include {quoted(p)}\n' for p in model_paths)
    (build / 'cell-models.v').write_text(wrapper)
    mode_logs = dict(rtl=rtl_log)
    compile_diagnostics = {}
    for mode, flags in (
        ('gate-functional', ['-DFUNCTIONAL']),
        ('gate-placeholder-delay', ['-gspecify', '-Ptb_pixel_pwm.SAMPLE_DELAY_NS=100',
                                    '-Ptb_pixel_pwm.OUTPUT_EVENT_MAX_DELAY_NS=1']),
    ):
        diagnostics = command(['iverilog', '-g2012', *flags, '-s', 'tb_pixel_pwm', '-o',
                               build / (mode + '.vvp'), build / 'cell-models.v', netlist, tb], mode + '-compile.log')
        compile_diagnostics[mode] = dict(lines=len(diagnostics.splitlines()),
            unsupported_ifnone_paths=diagnostics.count('ifnone with an edge-sensitive path is not supported'),
            unsupported_timing_checks=diagnostics.count('Timing checks are not supported.'),
            raw_log_sha256=sha(build / (mode + '-compile.log')))
        mode_logs[mode] = command(['vvp', build / (mode + '.vvp'), f'+OUT={build / (mode + "-events.csv")}'], mode + '.log')
    event_stats = {}
    for mode, log in mode_logs.items():
        match = re.search(r'PASS pixel_pwm:.*?([0-9]+) frames and ([0-9]+) slot/value checks', log)
        pulse = re.search(r'([0-9]+) known events;.*?minimum high=([0-9.]+) ns low=([0-9.]+) ns', log)
        if not match or not pulse:
            raise RuntimeError(f'{mode} did not complete both exhaustive and event checks')
        event_stats[mode] = dict(frames=int(match[1]), slot_value_checks=int(match[2]),
            known_events=int(pulse[1]), minimum_high_ns=float(pulse[2]), minimum_low_ns=float(pulse[3]))
    raw_rtl = (build / 'rtl-events.csv').read_bytes()
    if raw_rtl != (build / 'gate-functional-events.csv').read_bytes():
        raise RuntimeError('Functional gate trace differs from actual RTL trace')
    with (build / 'gate-placeholder-delay-events.csv').open() as handle:
        delayed = [(int(r['time_ns']), int(r['pwm'])) for r in csv.DictReader(handle)]
    with (build / 'rtl-events.csv').open() as handle:
        ideal = [(int(r['time_ns']), int(r['pwm'])) for r in csv.DictReader(handle)]
    if delayed != [(stamp + 1, value) for stamp, value in ideal]:
        raise RuntimeError('Selected specify output path did not produce the expected 1 ns edge shift')
    trace_cases = []
    for duty, enable in [(0, 1), (1, 1), (64, 1), (128, 1), (192, 1), (255, 1), (256, 1), (257, 1), (511, 1), (256, 0)]:
        case = f'd{duty:03d}-en{enable}'
        files = []
        for mode, binary in [('rtl', 'rtl.vvp'), ('gate', 'gate-functional.vvp')]:
            path = build / f'trace-{case}-{mode}.csv'
            command(['vvp', build / binary, '+TRACE_ONLY=1', f'+DUTY={duty}', f'+ENABLE={enable}', f'+OUT={path}'], f'trace-{case}-{mode}.log')
            files.append(path)
        if files[0].read_bytes() != files[1].read_bytes():
            raise RuntimeError(f'RTL/functional gate trace mismatch: {case}')
        trace_cases.append(dict(duty=duty, enable=enable, identical=True))
    area = re.search(r"Chip area for module.*?: ([0-9.]+)", synthesis_log)
    source_paths = [rtl, tb, HERE / 'run.py', HERE / 'library-lock.json']
    summary = dict(schema_version=1, passed=True,
        evidence_level='RTL simulation, GF180 standard-cell synthesis, functional and placeholder-delay gate simulation',
        host=dict(system=platform.system(), machine=platform.machine(), python=platform.python_version()),
        tools=versions, library=lock, source_hashes={str(p.relative_to(ROOT)): sha(p) for p in source_paths},
        synthesis=dict(cell_count=len(cells), cell_types=dict(collections.Counter(c['type'] for c in cells.values())),
            liberty_cell_area_um2=float(area[1]) if area else None,
            pwm_direct_dff=drivers[0][0], netlist_sha256=sha(netlist)),
        simulations=event_stats, trace_cases=trace_cases, compile_diagnostics=compile_diagnostics,
        delay_model=dict(functional_ns=0, specified_template_ns=1, clock_period_ns=1000,
            specify_support='Icarus supports the exercised CLK-to-Q path; conditional edge-sensitive ifnone paths are unsupported',
            physical_status='No Liberty-derived delay annotation, STA, SDF, placement, clock tree, extracted wires, setup/hold or silicon claim'),
        bridge_test_log_sha256=sha(build / 'bridge-tests.log'))
    (build / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    if args.publish_evidence:
        evidence = ROOT / 'evidence/digital'
        evidence.mkdir(parents=True, exist_ok=True)
        for name in ('summary.json', 'rtl-selfcheck.log', 'bridge-tests.log', 'synthesis.log',
                     'pixel_pwm_mapped.v', 'rtl-events.csv', 'gate-functional.log',
                     'gate-functional-events.csv', 'gate-placeholder-delay.log',
                     'gate-placeholder-delay-events.csv'):
            shutil.copyfile(build / name, evidence / name)
    print(f'PASS digital: {len(cells)} GF180 cells; exhaustive RTL/gate checks and 10 identical trace cases')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
