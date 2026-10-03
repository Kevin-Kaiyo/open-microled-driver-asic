"""Exercise actual routed SDF and replay its measured PWM into analog RC.

Canonical cell models are not edited. Unsupported simulator arcs are counted
and retained; the clock-to-PWM path is independently checked against the SDF.
This is one-way timing replay with an assumed output load, not joint layout.
"""
from pathlib import Path
import argparse
import collections
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_phase1 as phase
import numpy as np


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(argv, log, cwd=ROOT):
    result = subprocess.run([str(v) for v in argv], cwd=cwd, capture_output=True, text=True)
    log.write_text(result.stdout + result.stderr)
    log.with_suffix(log.suffix + '.command.json').write_text(json.dumps(
        dict(argv=[str(v) for v in argv], exit_code=result.returncode), indent=2) + '\n')
    if result.returncode:
        raise RuntimeError(f'Command exit {result.returncode}: {log}')
    return log.read_text()


def sdf_clock_path(path):
    """Read the unique positive buffer/FF path from clk to pwm, preserving arcs.

    Only this path is evaluated. Logic arcs on the FF D-input are deliberately
    excluded from this scalar calculation; full setup/hold comes from STA.
    """
    tokens = re.findall(r'"[^"\\]*(?:\\.[^"\\]*)*"|[()]|[^()\s]+', path.read_text())
    stack = [[]]
    for token in tokens:
        if token == '(':
            new = []
            stack[-1].append(new)
            stack.append(new)
        elif token == ')':
            stack.pop()
        else:
            stack[-1].append(token)
    root = stack[0][0]
    graph = collections.defaultdict(list)
    def typ(delay):
        values = delay[0].split(':')
        return float(values[1] if len(values) == 3 else values[0])
    def delays(values):
        result = [typ(v) for v in values]
        return (result[0], result[1] if len(result) > 1 else result[0])
    for cell in (v for v in root if isinstance(v, list) and v[0] == 'CELL'):
        fields = {v[0]: v[1:] for v in cell[1:]}
        instance = fields['INSTANCE'][0] if fields['INSTANCE'] else ''
        ctype = fields['CELLTYPE'][0].strip('"')
        for record in fields['DELAY'][0][1:]:
            if record[0] == 'INTERCONNECT':
                graph[record[1]].append((record[2], delays(record[3:]), 'wire', instance))
            elif record[0] == 'IOPATH':
                source = record[1]
                source = source[-1] if isinstance(source, list) else source
                is_ff = '__dffq_' in ctype
                is_buffer = re.search(r'__(?:clk)?buf_\d+$', ctype)
                if is_ff and source == 'CLK' or is_buffer:
                    graph[instance + '.' + source].append((instance + '.' + record[2],
                        delays(record[3:]), 'ff' if is_ff else 'buffer', instance))
    paths = []
    def walk(node, steps, visited):
        if node == 'pwm':
            paths.append(steps)
            return
        if node in visited:
            return
        for dest, delay, kind, instance in graph[node]:
            walk(dest, steps + [dict(source=node, destination=dest, rise_ns=delay[0],
                                    fall_ns=delay[1], kind=kind, instance=instance)], visited | {node})
    walk('clk', [], set())
    if len(paths) != 1 or sum(s['kind'] == 'ff' for s in paths[0]) != 1:
        raise ValueError('Expected exactly one positive buffer/FF clk-to-pwm SDF path')
    steps = paths[0]
    rise = sum(s['rise_ns'] for s in steps)
    falling_output = False
    fall = 0.0
    for step in steps:
        falling_output |= step['kind'] == 'ff'
        fall += step['fall_ns'] if falling_output else step['rise_ns']
    return dict(steps=steps, predicted_rise_delay_ns=rise, predicted_fall_delay_ns=fall)


def simulate_rc(case, folder, events, rc_netlist, maxstep):
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('design.ngspice', 'sm141064.ngspice'):
        link = folder / name
        link.unlink(missing_ok=True)
        link.symlink_to(os.path.relpath(phase.MODEL_DIR / name, folder))
    deck = phase.make_deck(case, folder, events, maxstep)
    text = deck.read_text()
    include = next(line for line in text.splitlines() if 'analog/driver/pixel_driver.spice' in line)
    text = text.replace(include, f'.include "{rc_netlist}"')
    text = text.replace('XPIXEL led_k pwm vlogic bias gate pwm_b pixel_driver',
                        'XPIXEL 0 bias gate pwm pwm_b led_k vlogic pixel_driver_layout')
    text = text.replace('set wr_vecnames', 'set numdgt=15\nset wr_vecnames')
    deck.write_text(text)
    waveform = folder / 'waveform.dat'
    waveform.unlink(missing_ok=True)
    log = command(['ngspice', '-b', deck], folder / 'ngspice.log', folder)
    if not waveform.exists() or re.search(r'(?im)^\s*(?:error|fatal)', log):
        raise RuntimeError(f'ngspice did not produce a valid waveform: {folder}')
    data = np.loadtxt(waveform, skiprows=1)
    if data.ndim != 2 or data.shape[1] != 7 or not np.isfinite(data).all():
        raise ValueError('Invalid analog RC samples')
    time, current = data[:, 0], data[:, 6]
    phase.windowed(time, current)
    return dict(average_branch_current_uA=phase.average(time, current) * 1e6,
                measured_digital_duty=phase.digital_duty(events), samples=len(time),
                maxstep_ns=maxstep * 1e9, waveform_sha256=sha(waveform),
                deck_sha256=sha(deck), log_sha256=sha(folder / 'ngspice.log'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name', default='pwm-v0.2-sized')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/physical-flow/sdf-coupled-v0.2')
    parser.add_argument('--publish-evidence', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    implementation = ROOT / 'build/physical-flow' / args.run_name
    final = implementation / 'final'
    pdk = ROOT / 'build/layout/pdk/gf180mcuD'
    phase.MODEL_DIR = pdk / 'libs.tech/ngspice'
    lock = json.loads((ROOT / 'scripts/digital/library-lock.json').read_text())
    for name, expected in lock['files'].items():
        if sha(pdk / name) != expected:
            raise ValueError(f'Locked cell model mismatch: {name}')
    model_paths = [pdk / name for name in lock['files'] if name.endswith('.v')]
    wrapper = output / 'cell-models.v'
    wrapper.write_text('`timescale 1ns/1ps\n' + ''.join(f'`include "{p}"\n' for p in model_paths))
    netlist = final / 'nl/pixel_pwm.nl.v'
    tb = ROOT / 'sim/rtl/tb_pixel_pwm.v'
    sdf_tb = ROOT / 'sim/rtl/tb_pixel_pwm_sdf.v'
    binary = output / 'implemented.vvp'
    compile_log = command(['iverilog', '-g2012', '-gspecify', '-ginterconnect', '-s', 'tb_pixel_pwm_sdf',
        '-o', binary, wrapper, netlist, tb, sdf_tb], output / 'compile.log')
    corners = {}
    for sdf in sorted((final / 'sdf').glob('*/*.sdf')):
        corner = sdf.parent.name
        folder = output / corner
        folder.mkdir(parents=True, exist_ok=True)
        trace = folder / 'events.csv'
        log = command(['vvp', binary, f'+SDF={sdf}', '+TRACE_REALTIME=1', f'+OUT={trace}'], folder / 'exhaustive.log')
        for marker in ('518 frames and 133159 slot/value checks', '543 known events'):
            if marker not in log:
                raise RuntimeError(f'SDF self-check did not finish: {corner}')
        path = sdf_clock_path(sdf)
        unmatched = re.findall(r'Unable to match ModPath.* in tb_pixel_pwm_sdf.tb.dut.(\S+)', log)
        critical = {s['instance'] for s in path['steps'] if s['instance']}
        if critical.intersection(unmatched) or 'Could not find net' in log:
            raise RuntimeError(f'Critical output path or interconnect failed annotation: {corner}')
        instance_types = dict((instance, cell) for cell, instance in re.findall(
            r'(gf180mcu_fd_sc_mcu7t5v0__\w+)\s+(\w+)\s*\(', netlist.read_text()))
        if any(not re.search(r'__(?:xor2|xnor2)_', instance_types.get(instance, '')) for instance in unmatched):
            raise RuntimeError(f'Unexpected unannotated cell: {corner}')
        if any('Unable to match ModPath' not in line for line in log.splitlines() if 'SDF ERROR:' in line):
            raise RuntimeError(f'Unexpected SDF error: {corner}')
        events = phase.read_events(trace)
        delays = {str(value): [t*1e9 - (round((t*1e9-500)/1000)*1000+500)
                              for t, v in events if v == value] for value in (0, 1)}
        for value, key in ((0, 'predicted_fall_delay_ns'), (1, 'predicted_rise_delay_ns')):
            if max(abs(d - path[key]) for d in delays[str(value)]) > 0.005:
                raise ValueError(f'SDF critical-path delay differs from actual CSV: {corner}')
        pulse = re.search(r'minimum high=([\d.]+) ns low=([\d.]+) ns', log)
        corners[corner] = dict(sdf_sha256=sha(sdf), csv_sha256=sha(trace), log_sha256=sha(folder / 'exhaustive.log'),
            frames=518, slot_checks=133159, known_pwm_events=543,
            minimum_high_ns=float(pulse[1]), minimum_low_ns=float(pulse[2]),
            unmatched_modpath_count=len(unmatched), unmatched_instances=sorted(set(unmatched)),
            unsupported_timingcheck_count=log.count('TIMINGCHECK not supported'),
            output_path=path, measured_edge_delays_ns={k:sorted(set(round(v,3) for v in vs)) for k,vs in delays.items()})
        print(f'SDF {corner}: exhaustive passed; output rise={path["predicted_rise_delay_ns"]:.3f} ns', flush=True)
    if len(corners) != 9:
        raise RuntimeError('Nine actual extracted timing corners are required')
    # Replay the nominal SDF and ideal RTL through the same frozen analog RC.
    rc = output / 'pixel_driver_rc.spice'
    shutil.copyfile(ROOT / 'evidence/layout/pixel_driver_rc.spice', rc)
    rtl_binary = output / 'rtl.vvp'
    command(['iverilog', '-g2012', '-s', 'tb_pixel_pwm', '-o', rtl_binary,
             ROOT / 'rtl/pixel_pwm.v', tb], output / 'rtl-compile.log')
    calibration = phase.calibrate_led(output)
    sdf = final / 'sdf/nom_tt_025C_3v30/pixel_pwm__nom_tt_025C_3v30.sdf'
    analog = []
    for duty in (0, 1, 64, 255, 256):
        case = dict(name=f'duty_{duty:03d}', duty=duty, enable=1,
                    corner='typical', vf_v=2.8, supply_v=5.0, temperature_c=27)
        results = {}
        for variant, executable, plusargs in [('rtl', rtl_binary, []),
                ('sdf', binary, [f'+SDF={sdf}', '+TRACE_REALTIME=1'])]:
            folder = output / 'analog-rc' / case['name'] / variant
            folder.mkdir(parents=True, exist_ok=True)
            trace = folder / 'events.csv'
            log = command(['vvp', executable, *plusargs, '+TRACE_ONLY=1', f'+DUTY={duty}', f'+OUT={trace}'],
                          folder / 'digital.log')
            phase.verify_trace_window(log)
            events = phase.read_events(trace)
            results[variant] = simulate_rc(case, folder, events, rc, 50e-9 if duty == 1 else 200e-9)
        delta = results['sdf']['average_branch_current_uA'] - results['rtl']['average_branch_current_uA']
        tolerance = max(abs(results['rtl']['average_branch_current_uA'])*0.002, 0.001)
        analog.append(dict(duty=duty, results=results, delta_current_uA=delta,
                           tolerance_uA=tolerance, passed=abs(delta)<=tolerance))
        print(f'RC duty={duty}: SDF-RTL current delta={delta:.8f} uA', flush=True)
    summary = dict(evidence_level='Post-route SDF supported-path simulation and one-way replay into separately extracted analog RC',
        implementation_run=args.run_name, compile_diagnostics=dict(log_sha256=sha(output / 'compile.log'),
            unsupported_ifnone_paths=compile_log.count('ifnone with an edge-sensitive path is not supported'),
            unsupported_timing_checks=compile_log.count('Timing checks are not supported.')),
        corners=corners, analog_rc=analog, led_calibration=calibration,
        conditions=dict(clock_period_ns=1000, cell_model_timescale='1ns/1ps', sdf_selection='typ delay in each extracted corner',
            sample_delay_ns=100, output_event_allowance_ns=50, measurement_window_s=phase.WINDOW,
            analog_logic_supply_v=3.3, analog_led_supply_v=5.0, analog_temperature_c=27,
            analog_synthetic_led_vf_v=2.8, analog_input_slew_ns=10, digital_sta_output_load_fF=72.91,
            coupling='CSV event replay via ideal voltage source; no analog feedback into digital delay',
            scope='output clock/buffer/FF SDF arcs checked independently; unsupported XOR/XNOR arcs and timing checks remain; STA supplies setup/hold evidence'),
        input_sha256={str(p.relative_to(ROOT)):sha(p) for p in [netlist, tb, sdf_tb,
                     ROOT / 'rtl/pixel_pwm.v', ROOT / 'scripts/run_phase1.py', ROOT / 'analog/models/microled.spice',
                     ROOT / 'evidence/layout/pixel_driver_rc.spice', *model_paths,
                     phase.MODEL_DIR / 'design.ngspice', phase.MODEL_DIR / 'sm141064.ngspice']},
        runner_sha256=sha(Path(__file__)), tools={}, passed=all(r['passed'] for r in analog))
    for tool, flags in [('iverilog',['-V']),('vvp',['-V']),('ngspice',['--version'])]:
        executable = Path(shutil.which(tool)).resolve()
        summary['tools'][tool] = dict(binary_sha256=sha(executable),
            version=command([tool,*flags],output/(tool+'-version.log')))
    (output / 'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    if not summary['passed']:
        raise RuntimeError('SDF-to-analog RC paired guard failed')
    if args.publish_evidence:
        evidence=ROOT/'evidence/physical/sdf'
        evidence.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(output/'summary.json',evidence/'summary.json')
        for corner in corners:
            dest=evidence/corner
            dest.mkdir(exist_ok=True)
            for name in ('events.csv','exhaustive.log'):
                shutil.copyfile(output/corner/name,dest/name)
        for case in analog:
            for variant in ('rtl','sdf'):
                source=output/'analog-rc'/f'duty_{case["duty"]:03d}'/variant
                dest=evidence/'analog-rc'/f'duty_{case["duty"]:03d}'/variant
                dest.mkdir(parents=True,exist_ok=True)
                for name in ('events.csv','digital.log','testbench.spice','ngspice.log'):
                    shutil.copyfile(source/name,dest/name)
    print('PASS: 9 SDF exhaustive cases; 10 analog RC transients; 3 LED DC calibrations')


if __name__ == '__main__':
    main()
