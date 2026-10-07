"""Independent frame experiment -> actual one-pixel RTL -> frozen signal PEX.

The frame receiver is a Python functional model. Only pixel_pwm is actual RTL;
only the selected pixel/output-stage signal cutout is transistor simulated.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile

import numpy as np
from frame_model import Frame, FrameReceiver, encode_frame, code_to_duty

ROOT = Path(__file__).resolve().parents[2]
PDK = ROOT / 'build/layout/pdk/gf180mcuD'
PERIOD_NS = 256000
ORIGIN_NS = 2000
SELECTED = 5
CODES = [0, 16, 1024, 2048, 4079, 4095, 0]
ACCEPT_NS = [1000, 400000, 900000, 1400000, 1900000, 2400000, 2900000]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, folder, log):
    p = subprocess.run([str(a) for a in args], cwd=folder, text=True, capture_output=True)
    (folder / log).write_text(p.stdout + p.stderr)
    if p.returncode or (str(args[0]) == 'ngspice' and
                        re.search(r'(?im)^Error:|timestep too small|simulation interrupted', p.stdout + p.stderr)):
        raise RuntimeError('Command failed: ' + str(folder / log))
    return p.stdout


def pattern(code, step):
    # Independent deterministic 4x4 logical pattern; a moving mask changes one
    # logical coordinate. The selected coordinate has the requested scalar.
    values = [((i * 719 + step * 313) % 4096) if i != step % 16 else 0 for i in range(16)]
    values[SELECTED] = code
    return tuple(values)


def scenario(faults=False, timeout=False):
    receiver = FrameReceiver(pixel_count=16, boundary_period_ns=PERIOD_NS,
                             boundary_origin_ns=ORIGIN_NS,
                             command_timeout_ns=400000 if timeout else 1000000,
                             receive_timeout_ns=50000)
    transactions = []
    steps = [(1000, 4095)] if timeout else zip(ACCEPT_NS, CODES)
    for i, (now, code) in enumerate(steps):
        frame = Frame(i + 1, max(0, now - 1000), pattern(code, i))
        wire = encode_frame(frame)
        transactions.append((now, 'valid', wire, True))
        if faults:
            bad = bytearray(encode_frame(Frame(i + 100, max(0, now - 1000), pattern(4095, i))))
            bad[-1] ^= 1
            transactions.extend([
                (now + 5000, 'bad_crc', bytes(bad), True),
                (now + 10000, 'bad_length', wire[:-1], True),
                (now + 15000, 'duplicate', wire, True),
                (now + 20000, 'future_timestamp', encode_frame(Frame(i + 200, now + 20001, pattern(4095, i))), True),
                (now + 22000, 'out_of_order', encode_frame(Frame(i, max(0,now-1000), pattern(4095,i))), True),
                (now + 25000, 'partial', wire[:10], False),
            ])
            if i >= 2:
                transactions.append((now + 23000, 'expired_command', encode_frame(Frame(i + 300,0,pattern(4095,i))), True))
    count = 4 if timeout else 14
    queries = [(ORIGIN_NS + n * PERIOD_NS, 'boundary', b'', False) for n in range(count)]
    items = sorted(transactions + queries, key=lambda row: (row[0], row[1] == 'boundary'))
    records, frames = [], []
    for now, name, wire, end in items:
        if name == 'boundary':
            receiver.advance(now)
            code = receiver.active_codes[SELECTED]
            frames.append(dict(frame=len(frames), control_commit_boundary_ns=now,
                               pwm_frame_start_ns=now + 500,
                               frame_id=receiver.active_frame_id, code=code,
                               duty=code_to_duty(code), enable=1,
                               active_codes=list(receiver.active_codes)))
        else:
            receiver.receive_chunk(wire, now, end=end)
            records.append(dict(time_ns=now, kind=name, wire_hex=wire.hex(), end=end,
                                wire_sha256=hashlib.sha256(wire).hexdigest()))
    receiver.advance(ORIGIN_NS + count * PERIOD_NS)
    return dict(transactions=records, events=receiver.events, frames=frames,
                stop_ns=2500 + count * PERIOD_NS)


def integral(t, current, left, right):
    if np.any(np.diff(t) <= 0) or not np.isfinite(current).all() or t[0] > left or t[-1] < right - 8 * abs(np.spacing(right)):
        raise RuntimeError('Incomplete waveform')
    mask = (t > left) & (t < right)
    x = np.r_[left, t[mask], right]
    y = np.r_[np.interp(left, t, current), current[mask], np.interp(right, t, current)]
    return float(np.sum(np.diff(x) * (y[:-1] + y[1:]) / 2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish-evidence', action='store_true')
    args = parser.parse_args()
    checks = []
    def check(name, value):
        checks.append({'name': name, 'passed': bool(value)})
        if not value:
            raise RuntimeError(name)
    contract = json.loads((ROOT / 'evidence/robustness/stage-contract.json').read_text())
    check('Frozen signal model SHA', sha(ROOT / contract['model_path']) == contract['model_sha256'])
    check('No old RC stacking', contract['replaces_old_analog_buf_spef_link'] is True)
    definition = re.search(r'(?im)^\.subckt\s+(\S+)\s+(.+)$', (ROOT / contract['model_path']).read_text())
    check('Exact declared ordered pins', definition[1] == contract['subckt'] and definition[2].split() == contract['ports_order'])
    for name, h in contract['required_inputs_sha256'].items():
        check('Provenance ' + name, sha(ROOT / name) == h)
    for lock in ['layout/pdk-lock.json', 'scripts/physical/pdk-lock.json']:
        for name, h in json.loads((ROOT / lock).read_text())['files'].items():
            check('Pinned PDK ' + name, sha(PDK / name) == h)
    (ROOT / 'build/control').mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='frame-', dir=ROOT / 'build/control'))
    sources = ['scripts/control/run.py', 'scripts/control/frame_model.py', 'tests/test_frame_model.py',
               'sim/rtl/tb_frame_replay.v', 'rtl/pixel_pwm.v', 'analog/models/microled.spice',
               'evidence/robustness/stage-contract.json', 'docs/specifications/frame-experiment-v0.1.md',
               'layout/pdk-lock.json', 'scripts/physical/pdk-lock.json', contract['model_path']]
    hashes = {}
    for name in sources:
        src = ROOT / name; dst = work / 'inputs' / name; dst.parent.mkdir(parents=True, exist_ok=True)
        hashes[name] = sha(src); shutil.copyfile(src, dst)
        check('Frozen input ' + name, sha(dst) == hashes[name] == sha(src))
    frozen = work / 'inputs'
    tools = {'ngspice': command(['ngspice','--version'],work,'ngspice-version.log'),
             'iverilog': command(['iverilog','-V'],work,'iverilog-version.log')}
    binary = work / 'replay.vvp'
    command(['iverilog', '-g2012', '-s', 'tb_frame_replay', '-o', binary,
             frozen / 'rtl/pixel_pwm.v', frozen / 'sim/rtl/tb_frame_replay.v'], work, 'rtl-compile.log')
    runs, traces = {}, {}
    for name in ['clean', 'faults', 'timeout']:
        result = scenario(faults=name == 'faults', timeout=name == 'timeout')
        (work / (name + '-functional.json')).write_text(json.dumps(result, indent=2) + '\n')
        stimulus = work / (name + '-commands.txt')
        stimulus.write_text(''.join(f"{f['duty']} {f['enable']}\n" for f in result['frames']))
        output = work / (name + '-events.csv'); samples = work / (name + '-samples.csv')
        log = command(['vvp', binary, f'+SOURCE={stimulus}', f'+OUT={output}',
                       f'+SAMPLES={samples}', f"+FRAMES={len(result['frames'])}"], work, name + '-rtl.log')
        check('Actual RTL replay ' + name, 'PASS replay:' in log)
        with output.open() as f:
            traces[name] = [(int(r['time_ns']), int(r['pwm'])) for r in csv.DictReader(f)]
        with samples.open() as f:
            rows = list(csv.DictReader(f))
        check('Every complete RTL slot ' + name, len(rows) == len(result['frames']) * 256 and
              all(int(r['pwm']) == (int(r['slot']) < result['frames'][int(r['frame'])]['duty']) for r in rows))
        runs[name] = result
    check('Faults leave all active frames identical', runs['clean']['frames'] == runs['faults']['frames'])
    check('Faults leave actual RTL events identical', traces['clean'] == traces['faults'])
    check('Boundary timeout clears software active frame', [r['duty'] for r in runs['timeout']['frames']] == [256, 256, 0, 0])
    check('Normal planned scalar duties', [r['duty'] for r in runs['clean']['frames']] == [0,0,1,1,64,64,128,128,255,255,256,256,0,0])
    led_is = 100e-6 / math.expm1((2.8 - 100e-6 * 50) / (3 * 8.617333262145e-5 * 300.15))
    def folder(name):
        target = work / name; target.mkdir()
        for model in ['design.ngspice', 'sm141064.ngspice']:
            (target / model).symlink_to(os.path.relpath(PDK / 'libs.tech/ngspice' / model, target))
        return target
    def run_spice(target, deck, filename):
        (target / 'testbench.spice').write_text(deck)
        command(['ngspice', '-b', 'testbench.spice'], target, 'ngspice.log')
        return np.atleast_2d(np.loadtxt(target / filename, skiprows=1))
    cal = folder('led-calibration')
    data = run_spice(cal, f'''Independent synthetic calibration
.param LED_IS={led_is:.17g}
.include "{frozen / 'analog/models/microled.spice'}"
IREF 0 a 100u
XLED a 0 microled
.options reltol=1e-9 abstol=1e-14 vntol=1e-10
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
op
wrdata values.dat v(a)
quit
.endc
.end
''', 'values.dat')
    cal_v = float(data[0, 1]); check('Independent LED DC calibration', abs(cal_v - 2.8) < 1e-5)
    def deck(raw, stop_ns, step, dc=False):
        neighbors = '\n'.join(f'VN{n} {r["node"]} 0 0' for n,r in enumerate(contract['neighbor_sources']))
        pins = ' '.join(contract['pin_bindings'][p] for p in contract['ports_order'])
        ctl = 'op' if dc else f'tran 10n {stop_ns}n 0 {step}n'
        return f'''Independent frame replay into frozen nominal selected signal PEX
.include design.ngspice
.param sw_stat_global=0 sw_stat_mismatch=0 LED_IS={led_is:.17g}
.lib sm141064.ngspice typical
.temp 27
VLOGIC vbuffer 0 3.3
VREF refrail 0 3.3
BIREF refrail bias I=100u
VLED rail 0 5
VLEDLOAD rail led_anode 0
VIN input 0 {raw}
.include "{frozen / 'analog/models/microled.spice'}"
XLED led_anode led_k microled
{neighbors}
.include "{frozen / contract['model_path']}"
XJOINT {pins} {contract['subckt']}
.options reltol=1e-7 abstol=1e-14 vntol=1e-9
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
{ctl}
wrdata waveform.dat v(pwm) v(gate) v(bias) v(led_k) i(VLEDLOAD)
quit
.endc
.end
'''
    dc = {}
    for level in [0, 1]:
        target = folder('dc-' + str(level)); data = run_spice(target, deck(str(level * 3.3), 0, 10, True), 'waveform.dat')
        dc[str(level)] = float(data[0, 5])
    check('Full-on DC target 100uA +/-5%', abs(dc['1']/100e-6-1) <= .05)
    check('Off DC numerical guard', abs(dc['0']) < 1e-9)
    analog = {}
    for name, trace, stop_ns, step in [('clean', 'clean', runs['clean']['stop_ns'], 10),
                                       ('lowest-fine', 'clean', 1026500, 1),
                                       ('timeout', 'timeout', runs['timeout']['stop_ns'], 10)]:
        target = folder(name)
        points = [(0, 0)]; old = 0
        for stamp, value in traces[trace]:
            if stamp + 1 >= stop_ns:
                break
            if value != old:
                points.extend([(stamp, old * 3.3), (stamp + 1, value * 3.3)])
            old = value
        points.append((stop_ns, old * 3.3))
        raw = 'PWL(\n' + '\n'.join(f'+ {t}n {v:.17g}' for t,v in points) + '\n+)'
        data = run_spice(target, deck(raw, stop_ns, step), 'waveform.dat')
        check('Finite ordered analog waveform ' + name, data.shape[1] == 6 and np.isfinite(data).all() and np.all(np.diff(data[:,0]) > 0))
        results = []
        for frame in runs[trace]['frames']:
            left = frame['pwm_frame_start_ns'] * 1e-9; right = left + PERIOD_NS * 1e-9
            if right > stop_ns * 1e-9 + 1e-15:
                continue
            charge = integral(data[:,0], data[:,5], left, right)
            expected = dc['1'] * frame['duty'] * 1e-6
            error = charge / expected - 1 if expected else None
            results.append(dict(frame=frame['frame'], code=frame['code'], duty=frame['duty'],
                                window_s=[left, right], charge_c=charge, current_uA=charge/(right-left)*1e6,
                                ideal_quantized_charge_c=expected, quantized_area_error_pct=None if error is None else error*100))
        analog[name] = dict(maxstep_ns=step, waveform_sha256=sha(target/'waveform.dat'),
                            deck_sha256=sha(target/'testbench.spice'), frames=results)
    for i in [2, 3]:
        coarse = analog['clean']['frames'][i]['charge_c']; fine = analog['lowest-fine']['frames'][i]['charge_c']
        check(f'Lowest-code area frame {i}', abs(analog['clean']['frames'][i]['quantized_area_error_pct']) <= 2)
        check(f'10-to-1ns numerical sensitivity frame {i}', abs(fine/coarse-1) <= .002)
    check('Final settled off frame guard', abs(analog['clean']['frames'][13]['current_uA']) < .001)
    check('Timeout final settled off frame guard', abs(analog['timeout']['frames'][3]['current_uA']) < .001)
    quantization = []
    for code in CODES:
        duty = code_to_duty(code)
        quantization.append(dict(code=code, duty=duty, command_normalized=code/4095,
                                 pwm_normalized=duty/256, normalized_error=duty/256-code/4095))
    check('Selected command half-slot quantization bound', all(abs(r['normalized_error']) <= 1/512 for r in quantization))
    artifacts = {str(p.relative_to(work)): sha(p) for p in work.rglob('*') if p.is_file() and 'inputs' not in p.parts}
    result = dict(passed=True, stage='frame experiment v0.1 / one-pixel v0.4 electrical backend',
                  raw_directory=str(work.relative_to(ROOT)), checks=checks, source_sha256=hashes,
                  tools=tools,
                  conditions={'logical_positions':16,'logical_geometry':[4,4],'pattern_seed':0,
                              'pattern_generator':'deterministic arithmetic v0.1; no camera or optical scene',
                              'electrically_simulated_pixels':1,'selected_index':SELECTED,
                              'clock_hz':1000000,'pwm_slots':256,'receiver_period_ns':PERIOD_NS,
                              'receiver_origin_ns':ORIGIN_NS,'receiver_to_pwm_ns':500,
                              'MOS_corner':'typical','MOS_temperature_c':27,'logic_v':3.3,'LED_rail_v':5,
                              'reference_uA':100,'LED':'unchanged synthetic dynamic model; not measured optical data',
                              'input_ramp_ns':1,'neighbor_boundary':'34 explicit ideal 0V sources',
                              'analog_scope':contract['scope'],'reset_low_extension_0_to_500ns':True},
                  scenarios=runs, analog=analog, calibration_v=cal_v, dc_current_a=dc,
                  quantization=quantization, transient_runs=3, circuit_dc_runs=2, LED_calibrations=1,
                  slot_checks=sum(len(r['frames'])*256 for r in runs.values()),
                  fault_electrical_replay='Identical actual RTL event sequence; shares clean analog run, no duplicate electrical run claimed',
                  raw_sha256=artifacts,
                  limitations=['No receiver RTL/physical implementation','No actual bus or hardware',
                               'Software boundary timeout is not asynchronous hardware protection',
                               'No new extraction or PG/reference generator','No dynamic/thermal/optical measurements'])
    (work/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    if args.publish_evidence:
        output=ROOT/'evidence/control'; output.mkdir(exist_ok=True)
        (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
        with (output/'frame-metrics.csv').open('w') as f:
            writer=csv.DictWriter(f,fieldnames=['scenario','frame','code','duty','start_s','end_s','charge_c','current_uA','quantized_area_error_pct'])
            writer.writeheader()
            for name,r in analog.items():
                for row in r['frames']:
                    writer.writerow(dict(scenario=name,**{k:row[k] for k in ['frame','code','duty','charge_c','current_uA','quantized_area_error_pct']},start_s=row['window_s'][0],end_s=row['window_s'][1]))
    print(f"PASS {len(checks)} checks; 3 transient / 2 circuit DC / 1 LED calibration; {result['slot_checks']} RTL slots; {work.relative_to(ROOT)}")


if __name__ == '__main__':
    main()
