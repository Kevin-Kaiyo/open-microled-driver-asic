"""Independent audit of frame v0.1 -> RTL -> frozen one-pixel signal PEX.

No runner, receiver, encoder or integration code is imported. Golden wires use
byte offsets and bit strings, CRC uses the reflected bit recurrence, scalar
rounding uses exact fractions, and current uses original-panel antiderivatives.
This audit confirms only the stages explicitly executed by this experiment.
"""
from pathlib import Path
from fractions import Fraction
from collections import Counter
import argparse
import csv
import hashlib
import json
import math
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PERIOD = 256000
ORIGIN = 2000
SELECTED = 5
ACCEPT = [1000, 400000, 900000, 1400000, 1900000, 2400000, 2900000]
CODES = [0, 16, 1024, 2048, 4079, 4095, 0]
PLANNED = [0, 0, 1, 1, 64, 64, 128, 128, 255, 255, 256, 256, 0, 0]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def crc32(data):
    value = 0xFFFFFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xEDB88320 if value & 1 else 0)
    return value ^ 0xFFFFFFFF


def rounding(code):
    value = Fraction(code * 256, 4095) + Fraction(1, 2)
    return value.numerator // value.denominator


def payload(codes):
    bits = ''.join(format(code, '012b') for code in codes)
    bits += '0' * ((-len(bits)) % 8)
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))


def wire(frame_id, timestamp, codes):
    data = payload(codes)
    header = (b'MLEX' + bytes([1, 12]) + len(codes).to_bytes(2, 'big')
              + frame_id.to_bytes(4, 'big') + timestamp.to_bytes(8, 'big')
              + len(data).to_bytes(4, 'big'))
    body = header + data
    return body + crc32(body).to_bytes(4, 'big')


def decode(data, count=16):
    if len(data) < 24:
        raise ValueError('partial_header')
    if data[:4] != b'MLEX':
        raise ValueError('wrong_magic')
    if data[4] != 1:
        raise ValueError('wrong_version')
    if data[5] != 12:
        raise ValueError('wrong_code_width')
    pixels = int.from_bytes(data[6:8], 'big')
    if pixels != count:
        raise ValueError('wrong_pixel_count')
    length = int.from_bytes(data[20:24], 'big')
    if length != (pixels * 12 + 7) // 8:
        raise ValueError('wrong_payload_length')
    if len(data) < 24 + length + 4:
        raise ValueError('partial_frame')
    if len(data) > 24 + length + 4:
        raise ValueError('extra_bytes')
    if crc32(data[:-4]) != int.from_bytes(data[-4:], 'big'):
        raise ValueError('bad_crc')
    bits = ''.join(format(byte, '08b') for byte in data[24:-4])
    if any(bit != '0' for bit in bits[pixels * 12:]):
        raise ValueError('nonzero_padding')
    return {'frame_id': int.from_bytes(data[8:12], 'big'),
            'timestamp_ns': int.from_bytes(data[12:20], 'big'),
            'codes': [int(bits[i:i + 12], 2) for i in range(0, pixels * 12, 12)]}


def pattern(code, step):
    result = [0 if i == step % 16 else (719 * i + 313 * step) % 4096
              for i in range(16)]
    result[SELECTED] = code
    return result


def following_boundary(now):
    if now < ORIGIN:
        return ORIGIN
    return ORIGIN + ((now - ORIGIN) // PERIOD + 1) * PERIOD


def ceiling_boundary(now):
    if now <= ORIGIN:
        return ORIGIN
    return ORIGIN + ((now - ORIGIN + PERIOD - 1) // PERIOD) * PERIOD


def expected_scenario(name):
    """Golden schedule derived from the declared input cases, not receiver state."""
    inputs = [(1000, 4095)] if name == 'timeout' else list(zip(ACCEPT, CODES))
    transactions, event_specs = [], []
    valid = []
    for step, (arrival, code) in enumerate(inputs):
        codes = pattern(code, step)
        timestamp = max(0, arrival - 1000)
        frame_id = step + 1
        good = wire(frame_id, timestamp, codes)
        staged = [('valid', arrival, good, True, None, frame_id)]
        if name == 'faults':
            corrupt = bytearray(wire(step + 100, timestamp, pattern(4095, step)))
            corrupt[-1] ^= 1
            staged += [('bad_crc', arrival + 5000, bytes(corrupt), True, 'bad_crc', None),
                       ('bad_length', arrival + 10000, good[:-1], True, 'partial_frame', None),
                       ('duplicate', arrival + 15000, good, True, 'duplicate_id', frame_id),
                       ('future_timestamp', arrival + 20000,
                        wire(step + 200, arrival + 20001, pattern(4095, step)),
                        True, 'future_timestamp', step + 200),
                       ('out_of_order', arrival + 22000,
                        wire(step, timestamp, pattern(4095, step)), True, 'out_of_order_id', step),
                       ('partial', arrival + 25000, good[:10], False, None, None)]
            if step >= 2:
                staged += [('expired_command', arrival + 23000,
                            wire(step + 300, 0, pattern(4095, step)),
                            True, 'expired_before_commit', step + 300)]
        for kind, time, data, end, rejection, rejected_id in staged:
            transactions.append({'time_ns': time, 'kind': kind, 'wire_hex': data.hex(),
                                 'end': end, 'wire_sha256': hashlib.sha256(data).hexdigest()})
            event_specs.append((time, 1, dict(event='assembly_started', time_ns=time,
                               frame_id=None, reason=None, deadline_ns=time + 50000)))
            if kind == 'valid':
                commit = following_boundary(time)
                psha = hashlib.sha256(payload(codes)).hexdigest()
                event_specs.append((time, 2, dict(event='frame_accepted', time_ns=time,
                    frame_id=frame_id, reason='validated_pending', commit_time_ns=commit,
                    timestamp_ns=timestamp, payload_sha256=psha,
                    wire_sha256=hashlib.sha256(data).hexdigest())))
                event_specs.append((commit, 0, dict(event='frame_committed', time_ns=commit,
                    frame_id=frame_id, reason='validated_boundary', timestamp_ns=timestamp,
                    codes=codes, duties=[rounding(v) for v in codes])))
                valid.append((commit, frame_id, codes))
            elif end:
                event_specs.append((time, 2, dict(event='receive_rejected', time_ns=time,
                    frame_id=rejected_id, reason=rejection,
                    wire_sha256=hashlib.sha256(data).hexdigest())))
            else:
                event_specs.append((time + 50000, 0, dict(event='receive_timeout',
                    time_ns=time + 50000, frame_id=None, reason='partial_timeout',
                    received_bytes=len(data))))
    count = 4 if name == 'timeout' else 14
    if name == 'timeout':
        event_specs.append((ceiling_boundary(400000), 0, dict(event='command_timeout',
            time_ns=ceiling_boundary(400000), frame_id=1, reason='clear_at_boundary',
            codes=[0] * 16, duties=[0] * 16)))
    events, active = [], [0] * 16
    for _, _, details in sorted(event_specs, key=lambda row: (row[0], row[1])):
        if details['event'] in ('frame_committed', 'command_timeout'):
            active = details['codes']
        events.append(details | {'active_payload_sha256': hashlib.sha256(payload(active)).hexdigest()})
    frames = []
    for index in range(count):
        boundary = ORIGIN + index * PERIOD
        eligible = [item for item in valid if item[0] <= boundary]
        _, ident, values = eligible[-1] if eligible else (0, None, [0] * 16)
        if name == 'timeout' and boundary >= ceiling_boundary(400000):
            ident, values = None, [0] * 16
        frames.append(dict(frame=index, control_commit_boundary_ns=boundary,
            pwm_frame_start_ns=boundary + 500, frame_id=ident, code=values[SELECTED],
            duty=rounding(values[SELECTED]), enable=1, active_codes=values))
    return dict(transactions=sorted(transactions, key=lambda row: row['time_ns']), events=events, frames=frames,
                stop_ns=2500 + count * PERIOD)


def integrate(t, y, left, right):
    """Clip original panels in their normalized coordinate and integrate."""
    if not np.isfinite(t).all() or not np.isfinite(y).all() or np.any(np.diff(t) <= 0):
        raise ValueError('Nonfinite/unordered waveform')
    if t[0] > left or t[-1] < right - 8 * abs(np.spacing(right)):
        raise ValueError('Missing actual measurement interval')
    ids = np.flatnonzero((t[:-1] < right) & (t[1:] > left))
    width = t[ids + 1] - t[ids]
    a = (np.maximum(left, t[ids]) - t[ids]) / width
    b = (np.minimum(right, t[ids + 1]) - t[ids]) / width
    delta = y[ids + 1] - y[ids]
    return float(np.sum(width * (y[ids] * (b - a) + delta * (b * b - a * a) / 2)))


def threshold_events(t, y, fraction, rising):
    threshold = 3.3 * fraction
    mask = ((y[:-1] < threshold) & (y[1:] >= threshold) if rising else
            (y[:-1] > threshold) & (y[1:] <= threshold))
    ids = np.flatnonzero(mask)
    return t[ids] + (threshold - y[ids]) * (t[ids + 1] - t[ids]) / (y[ids + 1] - y[ids])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path, default=ROOT / 'evidence/control/summary.json')
    args = parser.parse_args()
    summary_path = args.summary.resolve()
    document = json.loads(summary_path.read_text())
    original_summary_sha = sha(summary_path)
    work = ROOT / document['raw_directory']
    frozen = work / 'inputs'
    checks = []
    def check(name, value, **details):
        checks.append(dict(name=name, passed=bool(value), **details))
        if not value:
            raise AssertionError(name)
    def close(name, actual, declared, absolute=1e-22):
        residual = abs(actual - declared)
        check(name, math.isfinite(actual) and residual <= max(absolute, abs(actual) * 2e-11),
              actual=actual, declared=declared, residual=residual)
    check('Published and local raw summary identity', sha(work / 'summary.json') == original_summary_sha)
    check('Runner guard results', document['passed'] is True and all(row['passed'] for row in document['checks']))
    for name, digest in document['source_sha256'].items():
        check('As-run and current source SHA ' + name, sha(frozen / name) == digest == sha(ROOT / name))
    for name, digest in document['raw_sha256'].items():
        check('Raw artifact SHA ' + name, sha(work / name) == digest)
    for name in ['ngspice-version.log', 'iverilog-version.log']:
        check('Version receipt retained ' + name, name in document['raw_sha256'])
    check('Independent CRC reference', crc32(b'123456789') == 0xCBF43926)
    golden = bytes.fromhex('4d4c4558010c000100000001000000000000000000000002010001568c54')
    check('External fixed wire and field decode', wire(1, 0, [16]) == golden and
          decode(golden, 1) == dict(frame_id=1, timestamp_ns=0, codes=[16]))
    all_duties = [rounding(code) for code in range(4096)]
    check('Exact scalar full-domain nearest rounding', all_duties[0] == 0 and all_duties[-1] == 256
          and all(a <= b for a, b in zip(all_duties, all_duties[1:]))
          and all(abs(Fraction(d, 256) - Fraction(c, 4095)) <= Fraction(1, 512)
                  for c, d in enumerate(all_duties)), commands=4096)
    conditions = document['conditions']
    wanted = dict(logical_positions=16, electrically_simulated_pixels=1, selected_index=5,
                  clock_hz=1000000, pwm_slots=256, receiver_period_ns=256000,
                  receiver_origin_ns=2000, receiver_to_pwm_ns=500, MOS_corner='typical',
                  MOS_temperature_c=27, logic_v=3.3, LED_rail_v=5, reference_uA=100,
                  input_ramp_ns=1, reset_low_extension_0_to_500ns=True)
    check('Explicit functional / RTL / electrical conditions', all(conditions[k] == v for k, v in wanted.items()))
    traces, golden_scenarios = {}, {}
    actual_slot_count = 0
    for name in ['clean', 'faults', 'timeout']:
        expected = expected_scenario(name)
        golden_scenarios[name] = expected
        saved = json.loads((work / (name + '-functional.json')).read_text())
        check('Scenario raw/published identity ' + name, saved == document['scenarios'][name])
        check('Independent transactions / policies / atomic active states ' + name, saved == expected,
              transactions=len(saved['transactions']), events=len(saved['events']), frames=len(saved['frames']))
        for transaction in saved['transactions']:
            data = bytes.fromhex(transaction['wire_hex'])
            kind = transaction['kind']
            if kind in ('bad_crc', 'bad_length'):
                try:
                    decode(data)
                    reason = 'unexpected_accept'
                except ValueError as error:
                    reason = str(error)
                check('Independent malformed wire ' + name + str(transaction['time_ns']),
                      reason == ('bad_crc' if kind == 'bad_crc' else 'partial_frame'))
            elif kind != 'partial':
                frame = decode(data)
                check('Independent good header and payload ' + name + str(transaction['time_ns']),
                      len(frame['codes']) == 16 and len(data) == 52)
        with (work / (name + '-samples.csv')).open() as stream:
            rows = list(csv.DictReader(stream))
        expected_samples = []
        for frame in expected['frames']:
            for slot in range(256):
                expected_samples.append(dict(time_ns=frame['pwm_frame_start_ns'] + slot * 1000 + 1,
                    frame=frame['frame'], slot=slot, pwm=int(frame['enable'] and slot < frame['duty'])))
        actual = [{k: int(v) for k, v in row.items()} for row in rows]
        check('Every actual RTL time/frame/slot/value ' + name, actual == expected_samples, slots=len(rows))
        actual_slot_count += len(rows)
        command_lines = (work / (name + '-commands.txt')).read_text().splitlines()
        check('Functional commands replayed verbatim ' + name,
              command_lines == [f"{f['duty']} {f['enable']}" for f in expected['frames']])
        expected_events, state = [(500, 0)], 0
        for sample in expected_samples:
            if sample['pwm'] != state:
                expected_events.append((sample['time_ns'] - 1, sample['pwm']))
                state = sample['pwm']
        with (work / (name + '-events.csv')).open() as stream:
            events = [(int(row['time_ns']), int(row['pwm'])) for row in csv.DictReader(stream)]
        # The harness reaches the next rising edge before stop. Final commands
        # are off, so this produces no additional known transition in these cases.
        check('Actual complete RTL transition sequence ' + name, events == expected_events)
        check('Registered clock event and pulse guards ' + name,
              all(t % 1000 == 500 and v in (0, 1) for t, v in events)
              and all(b[0] - a[0] >= 1000 for a, b in zip(events, events[1:])))
        check('RTL success receipt ' + name,
              f"PASS replay: {len(expected['frames'])} frames, {len(expected_samples)} slot checks"
              in (work / (name + '-rtl.log')).read_text())
        traces[name] = events
    check('Actual total slot denominator', actual_slot_count == 8192 == document['slot_checks'])
    check('Matched bad-input experiment preserves RTL sequence', traces['clean'] == traces['faults'])
    check('Predeclared active scalar sequences',
          [f['duty'] for f in golden_scenarios['clean']['frames']] == PLANNED
          and [f['duty'] for f in golden_scenarios['timeout']['frames']] == [256, 256, 0, 0])
    check('Complete selected quantization row count', len(document['quantization']) == len(CODES))
    for code, row in zip(CODES, document['quantization']):
        check('Selected scalar mapping ' + str(code), row['code'] == code and row['duty'] == rounding(code))
        close('Selected normalized command ' + str(code), code / 4095, row['command_normalized'], 1e-16)
        close('Selected normalized PWM ' + str(code), rounding(code) / 256, row['pwm_normalized'], 1e-16)
        close('Selected normalized error ' + str(code), rounding(code) / 256 - code / 4095,
              row['normalized_error'], 1e-16)
    contract = json.loads((frozen / 'evidence/robustness/stage-contract.json').read_text())
    check('Electrical scope matches frozen projection contract', conditions['analog_scope'] == contract['scope'])
    model = frozen / contract['model_path']
    check('Exact frozen nominal PEX SHA', sha(model) == contract['model_sha256'])
    definition = re.search(r'(?im)^\.subckt\s+(\S+)\s+(.+)$', model.read_text())
    check('Exact frozen ordered model ports', definition[1] == contract['subckt']
          and definition[2].split() == contract['ports_order']
          and set(contract['pin_bindings']) == set(contract['ports_order']))
    check('No legacy stacking contract', contract['replaces_old_analog_buf_spef_link'] is True)
    for name, digest in contract['required_inputs_sha256'].items():
        check('Frozen PEX provenance ' + name, sha(ROOT / name) == digest)
    pdk = ROOT / 'build/layout/pdk/gf180mcuD'
    for lock in ['layout/pdk-lock.json', 'scripts/physical/pdk-lock.json']:
        for name, digest in json.loads((frozen / lock).read_text())['files'].items():
            check('Pinned physical PDK ' + lock + ' ' + name, sha(pdk / name) == digest)
    expected_pins = 'XJOINT ' + ' '.join(contract['pin_bindings'][p] for p in contract['ports_order']) + ' ' + contract['subckt']
    cal_data = np.atleast_2d(np.loadtxt(work / 'led-calibration/values.dat', skiprows=1))
    check('Independent calibration shape and target', cal_data.shape == (1, 2)
          and np.isfinite(cal_data).all() and abs(cal_data[0, 1] - 2.8) < 1e-5)
    close('Calibration reported scalar', float(cal_data[0, 1]), document['calibration_v'], 1e-12)
    expected_is = 100e-6 / math.expm1((2.8 - 100e-6 * 50) / (3 * 8.617333262145e-5 * 300.15))
    cal_deck = (work / 'led-calibration/testbench.spice').read_text()
    close('Calibrated synthetic IS arithmetic', expected_is,
          float(re.search(r'LED_IS=([^\s]+)', cal_deck)[1]), 1e-35)
    dc, recalculated, edges = {}, {}, {}
    for folder in ['dc-0', 'dc-1', 'clean', 'lowest-fine', 'timeout']:
        text = (work / folder / 'testbench.spice').read_text()
        active_lines = [line.strip() for line in text.splitlines()
                        if line.strip() and not line.lstrip().startswith(('*', '+'))]
        instances = [line for line in active_lines if re.match(r'(?i)^X', line)]
        check('Exactly one joint model and one LED ' + folder,
              instances == ['XLED led_anode led_k microled', expected_pins])
        includes = re.findall(r'(?im)^\.include\s+(.+)$', text)
        check('Only declared simulation models ' + folder, includes == ['design.ngspice',
              f'"{frozen / "analog/models/microled.spice"}"', f'"{model}"'])
        check('Fixed rails / reference / MOS conditions ' + folder,
              all(line in active_lines for line in ['.lib sm141064.ngspice typical', '.temp 27',
                  'VLOGIC vbuffer 0 3.3', 'VREF refrail 0 3.3', 'BIREF refrail bias I=100u',
                  'VLED rail 0 5', 'VLEDLOAD rail led_anode 0']))
        neighbors = [line for line in active_lines if re.match(r'^VN\d+\s', line)]
        check('34 declared stiff-ground neighbors ' + folder,
              neighbors == [f'VN{i} {r["node"]} 0 0' for i, r in enumerate(contract['neighbor_sources'])]
              and len(neighbors) == 34)
        for model_name in ['design.ngspice', 'sm141064.ngspice']:
            check('Actual simulator PDK model identity ' + folder + ' ' + model_name,
                  sha(work / folder / model_name) == sha(pdk / 'libs.tech/ngspice' / model_name))
        log = (work / folder / 'ngspice.log').read_text()
        check('No ngspice failure receipt ' + folder,
              not re.search(r'(?im)^Error:|timestep too small|simulation interrupted', log))
        data = np.atleast_2d(np.loadtxt(work / folder / 'waveform.dat', skiprows=1))
        with (work / folder / 'waveform.dat').open() as stream:
            header = stream.readline().split()
        check('Recorded vector identity and dimensions ' + folder,
              header
              == [('vbuffer' if folder.startswith('dc-') else 'time'),
                  'v(pwm)', 'v(gate)', 'v(bias)', 'v(led_k)', 'i(VLEDLOAD)']
              and data.shape[1] == 6 and np.isfinite(data).all())
        if folder.startswith('dc-'):
            level = folder[-1]
            check('Actual DC level and one-point output ' + folder,
                  f'VIN input 0 {float(level) * 3.3}' in active_lines and data.shape[0] == 1)
            dc[level] = float(data[0, 5])
            close('DC declared current ' + level, dc[level], document['dc_current_a'][level])
            continue
        scenario_name = 'timeout' if folder == 'timeout' else 'clean'
        stop = 1026500 if folder == 'lowest-fine' else golden_scenarios[scenario_name]['stop_ns']
        step = 1 if folder == 'lowest-fine' else 10
        check('Actual transient stop/maxstep ' + folder, f'tran 10n {stop}n 0 {step}n' in active_lines
              and document['analog'][folder]['maxstep_ns'] == step)
        points, previous = [(0, 0.0)], 0
        for stamp, value in traces[scenario_name]:
            if stamp + 1 >= stop:
                break
            if previous != value:
                points += [(stamp, previous * 3.3), (stamp + 1, value * 3.3)]
            previous = value
        points.append((stop, previous * 3.3))
        pwl_text = re.search(r'(?is)VIN input 0 PWL\((.*?)\)', text)[1]
        actual_points = [(int(t), float(v)) for t, v in re.findall(r'\+\s+(\d+)n\s+([^\s]+)', pwl_text)]
        check('Exact actual-RTL PWL voltage/timing ' + folder, actual_points == points)
        check('Raw transient current time ordering ' + folder, np.all(np.diff(data[:, 0]) > 0))
        result = []
        for frame in golden_scenarios[scenario_name]['frames']:
            start = (frame['pwm_frame_start_ns']) * 1e-9
            end = (frame['pwm_frame_start_ns'] + PERIOD) * 1e-9
            if end > stop * 1e-9 + 1e-15:
                continue
            charge = integrate(data[:, 0], data[:, 5], start, end)
            ideal = dc['1'] * frame['duty'] * 1e-6
            area = (charge / ideal - 1) * 100 if ideal else None
            result.append(dict(frame=frame['frame'], code=frame['code'], duty=frame['duty'],
                window_s=[start, end], charge_c=charge, current_uA=charge / (end - start) * 1e6,
                ideal_quantized_charge_c=ideal, quantized_area_error_pct=area))
        reported = document['analog'][folder]
        check('Exact raw electrical deck / waveform hashes ' + folder,
              reported['deck_sha256'] == sha(work / folder / 'testbench.spice')
              and reported['waveform_sha256'] == sha(work / folder / 'waveform.dat'))
        check('Correct complete measurement frame count ' + folder, len(reported['frames']) == len(result))
        for actual, declared in zip(result, reported['frames']):
            ident = folder + ' frame ' + str(actual['frame'])
            check('Frame identity and window ' + ident,
                  all(actual[k] == declared[k] for k in ['frame', 'code', 'duty'])
                  and np.allclose(actual['window_s'], declared['window_s'], rtol=0, atol=1e-18))
            for key in ['charge_c', 'current_uA', 'ideal_quantized_charge_c']:
                close('Independent raw integration ' + ident + ' ' + key, actual[key], declared[key],
                      1e-12 if key == 'current_uA' else 1e-22)
            if actual['quantized_area_error_pct'] is None:
                check('No invented off area denominator ' + ident, declared['quantized_area_error_pct'] is None)
            else:
                close('Independent DC-area denominator ' + ident,
                      actual['quantized_area_error_pct'], declared['quantized_area_error_pct'], 1e-9)
        recalculated[folder] = result
        edge_summary = {}
        t, voltage = data[:, 0], data[:, 1]
        for rising in [True, False]:
            expected_stamps = [stamp * 1e-9 for stamp, value in traces[scenario_name][1:]
                               if value == int(rising) and stamp + 1 < stop]
            mid = threshold_events(t, voltage, .5, rising)
            check('Actual PEX edge count and propagated timing ' + folder + str(rising),
                  len(mid) == len(expected_stamps)
                  and all(-1e-14 <= actual - source <= 10e-9 for actual, source in zip(mid, expected_stamps)))
            early = threshold_events(t, voltage, .3 if rising else .7, rising)
            late = threshold_events(t, voltage, .7 if rising else .3, rising)
            check('Corresponding PEX slew thresholds ' + folder + str(rising),
                  len(early) == len(mid) == len(late))
            width = (late - early) * 1e9
            check('Locked 30-70/70-30 slew budget ' + folder + str(rising),
                  np.all(width >= 0) and np.all(width <= 3))
            edge_summary['rise' if rising else 'fall'] = dict(count=len(mid),
                times_s=mid.tolist(), maximum_slew_ns=float(width.max()) if len(width) else None)
        up = np.array(edge_summary['rise']['times_s'])
        down = np.array(edge_summary['fall']['times_s'])
        spans = [(b[b > a][0] - a) * 1e9 for begin, b in [(up, down), (down, up)]
                 for a in begin if np.any(b > a)]
        check('Actual PEX pulse length guard ' + folder, all(span >= 950 for span in spans))
        edge_summary['minimum_complete_high_or_low_ns'] = min(spans) if spans else None
        edges[folder] = edge_summary
        if folder == 'timeout':
            timeout_data = data
    check('Circuit DC full-on and off guards', 95e-6 <= dc['1'] <= 105e-6 and abs(dc['0']) < 1e-9)
    sensitivities = []
    for index in [2, 3]:
        coarse = recalculated['clean'][index]['charge_c']
        fine = recalculated['lowest-fine'][index]['charge_c']
        change = abs(fine / coarse - 1) * 100
        check('Predeclared lowest-code area ' + str(index),
              abs(recalculated['clean'][index]['quantized_area_error_pct']) <= 2)
        check('Independent finite-step sensitivity ' + str(index), change <= .2,
              frame=index, change_pct=change)
        sensitivities.append(dict(frame=index, change_pct=change))
    check('Late clean and timeout off frames', abs(recalculated['clean'][13]['current_uA']) < .001
          and abs(recalculated['timeout'][3]['current_uA']) < .001)
    check('Claimed simulation run denominators', document['transient_runs'] == 3
          and document['circuit_dc_runs'] == 2 and document['LED_calibrations'] == 1)
    rejection_counts = dict(Counter(row['reason'] for row in document['scenarios']['faults']['events']
                                   if row['event'] == 'receive_rejected'))
    partial_timeouts = sum(row['event'] == 'receive_timeout' for row in document['scenarios']['faults']['events'])
    check('Exact declared rejection / partial-timeout denominator', rejection_counts == {
        'bad_crc': 7, 'partial_frame': 7, 'duplicate_id': 7, 'future_timestamp': 7,
        'out_of_order_id': 7, 'expired_before_commit': 5} and partial_timeouts == 7)
    clear_event = next(row for row in document['scenarios']['timeout']['events'] if row['event'] == 'command_timeout')
    rtl_fall = next(time for time, value in traces['timeout'][1:] if value == 0)
    pwm_fall_ns = edges['timeout']['fall']['times_s'][0] * 1e9
    current_threshold = dc['1'] / 2
    t, current = timeout_data[:, 0], timeout_data[:, 5]
    ids = np.flatnonzero((current[:-1] > current_threshold) & (current[1:] <= current_threshold)
                         & (t[1:] >= rtl_fall * 1e-9))
    check('Observed branch half-full falling crossing', len(ids) >= 1)
    index = ids[0]
    current_fall_ns = (t[index] + (current_threshold - current[index])
                       * (t[index + 1] - t[index]) / (current[index + 1] - current[index])) * 1e9
    timeout_timing = dict(command_timestamp_ns=0, command_timeout_ns=400000,
        deadline_ns=400000, functional_clear_ns=clear_event['time_ns'],
        actual_RTL_fall_ns=rtl_fall, actual_PEX_PWM_50pct_fall_ns=pwm_fall_ns,
        actual_branch_half_full_fall_ns=current_fall_ns,
        branch_threshold_a=current_threshold,
        deadline_to_functional_clear_ns=clear_event['time_ns'] - 400000,
        functional_clear_to_RTL_ns=rtl_fall - clear_event['time_ns'],
        RTL_to_PEX_PWM_50pct_ns=pwm_fall_ns - rtl_fall,
        RTL_to_branch_half_full_ns=current_fall_ns - rtl_fall,
        definition='First saved-panel downward crossing after RTL fall; PWM threshold=1.65V; branch threshold=0.5 times this run DC full-on current. Branch includes displacement current; these thresholds are observables, not safe-off certification or optical extinction.')
    check('Timeout stages kept distinct', clear_event['time_ns'] == 514000 and rtl_fall == 514500
          and 0 <= pwm_fall_ns - rtl_fall <= 10 and 0 <= current_fall_ns - rtl_fall <= 100)
    # Prove the independent panel audit rejects a real missing interval.
    try:
        integrate(np.array([0., 1.]), np.array([1., 1.]), 0., 1.001)
        rejected = False
    except ValueError:
        rejected = True
    check('Missing measurement interval rejected', rejected)
    check('Summary unchanged during review', sha(summary_path) == original_summary_sha)
    result = dict(schema_version=1, date='2026-10-07', passed=True,
        summary_sha256=original_summary_sha, validator_sha256=sha(Path(__file__)),
        raw_directory=document['raw_directory'], checks=checks, check_count=len(checks),
        raw_integrated_frames=sum(map(len, recalculated.values())), actual_RTL_slot_checks=actual_slot_count,
        quantization_domain_commands=4096, electrical_results=recalculated,
        electrical_edge_checks=edges, finite_step_sensitivity=sensitivities,
        fault_rejection_counts=rejection_counts, partial_timeout_events=partial_timeouts,
        invalid_fault_transactions=sum(rejection_counts.values()) + partial_timeouts,
        timeout_timing=timeout_timing,
        source_sha256=document['source_sha256'],
        method='Independent offsets/MSB bit strings/bitwise CRC; exact Fraction rounding; fixed-input golden event schedule and complete RTL time-slot-event sequence; original saved waveform panels clipped in normalized u and analytically integrated; no runner/model imports',
        scope={'functional_receiver_model':True,'actual_single_pixel_RTL':True,
               'selected_one_pixel_joint_signal_PEX':True,'receiver_RTL':False,
               'array_ASIC':False,'full_PG_PEX':False,'silicon':False,'optical_measurement':False},
        limitations=document['limitations'])
    target = ROOT / 'evidence/control/validation.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(f'PASS independent audit: {len(checks)} checks; {actual_slot_count} RTL slots; '
          f'{result["raw_integrated_frames"]} complete electrical frame integrals')


if __name__ == '__main__':
    main()
