#!/usr/bin/env python3
"""Bounded C internal-node diagnostic; never evaluates full-frame RX or energy."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GRAY = ((0, 0), (0, 1), (1, 1), (1, 0))
LIMIT = 100*1024**2


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def emit(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def stimulus():
    symbols = [0]*8
    events = []
    for before in range(4):
        for after in range(4):
            if before == after:
                continue
            symbols.extend([before]*4)
            events.append({'from': before, 'to': after, 'transition_symbol': len(symbols)})
            symbols.extend([after]*4)
    symbols.extend([symbols[-1]]*8)
    assert len(symbols) == 112 and len(events) == 12
    assert {(e['from'], e['to']) for e in events} == {(a, b) for a in range(4) for b in range(4) if a != b}
    for event in events:
        j = event['transition_symbol']
        assert symbols[j-4:j] == [event['from']]*4
        assert symbols[j:j+4] == [event['to']]*4
    return symbols, events


def crossing(t, values, at, end, threshold, rising):
    valid = (t[:-1] >= at) & (t[1:] <= end)
    if rising:
        valid &= (values[:-1] < threshold) & (values[1:] >= threshold)
    else:
        valid &= (values[:-1] > threshold) & (values[1:] <= threshold)
    indices = np.flatnonzero(valid)
    if not len(indices):
        return None
    k = indices[0]
    when = t[k]+(t[k+1]-t[k])*(threshold-values[k])/(values[k+1]-values[k])
    return float((when-at)*1e12)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--work', type=Path, default=ROOT/'build/fair-driver-v1/c-transition-probe')
    ap.add_argument('--source', type=Path, default=ROOT/'build/fair-driver-v1/matched-r2')
    args = ap.parse_args()
    symbols, events = stimulus()
    assert crossing(np.array([0., 1., 2.])*1e-12, np.array([0., 1., 2.]), 0, 2e-12, .5, True) == .5
    if args.self_test:
        print('112 symbols; all12 directed transitions held4+4; analytic crossing passed'); return
    work, source = args.work.resolve(), args.source.resolve()
    if work.exists():
        raise FileExistsError('Refuse overwrite: '+str(work))
    if shutil.disk_usage(ROOT).free < 5*1024**3:
        raise RuntimeError('Minimum5GiB free guard')
    baseline_path = source/'cases/RX-TT-C-0.5G/result.json'
    baseline = json.loads(baseline_path.read_text())
    runner = source/'execution-sources'/('run-'+baseline['runner_sha256']+'.py')
    assert sha(runner) == baseline['runner_sha256']
    spec = importlib.util.spec_from_file_location('frozen_diagnostic_deck_engine', runner)
    engine = importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)
    engine.verify(source)
    work.mkdir(parents=True)
    shutil.copytree(source/'inputs', work/'inputs')
    for name in ['manifest.json', 'stimulus.json']:
        shutil.copy2(source/name, work/name)
    shutil.copy2(runner, work/'frozen-deck-engine.py')
    shutil.copy2(__file__, work/'execution-source.py')
    case = dict(baseline['case']); case.update(name='C-all12-short-internal', export_full_native=True)
    full_deck, meta = engine.deck(work, case)
    (work/'template-fullframe.spice').write_text(full_deck)
    ui = 2*(4096/4736)/(.5e9)
    stop = len(symbols)*ui
    d1, d0 = zip(*(GRAY[x] for x in symbols))
    deck = full_deck
    changed = []
    for name, replacement in [
        ('VD0', 'VD0 data0_src 0 '+engine.pwl(d0, ui, 3.3, 20e-12)),
        ('VD1', 'VD1 data1_src 0 '+engine.pwl(d1, ui, 3.3, 20e-12)),
        ('tran', f'tran {ui/40:.16g} {stop:.16g} 0 {ui/40:.16g}')]:
        old = re.findall(r'^'+name+r' .*$', deck, flags=re.M)
        assert len(old) == 1
        deck = re.sub(r'^'+name+r' .*$', replacement, deck, flags=re.M)
        changed.append({'field': name, 'old_sha256': hashlib.sha256(old[0].encode()).hexdigest(),
                        'new_sha256': hashlib.sha256(replacement.encode()).hexdigest()})
    # Keep all requested internal nodes; additional DI/GB/VX expose the physical
    # stages between decoder outputs and current steering. No guessed MOS property.
    nodes = ['d0', 'd1', 'xdrv.t1', 'xdrv.t3', 'xdrv.gp1', 'xdrv.gp2', 'xdrv.gp3',
             'xdrv.bias', 'out', 'xdrv.di1', 'xdrv.di2', 'xdrv.di3',
             'xdrv.gb1', 'xdrv.gb2', 'xdrv.gb3', 'xdrv.vx1', 'xdrv.vx2', 'xdrv.vx3',
             'xdrv.n_or', 'xdrv.p_or', 'xdrv.n_stack', 'xdrv.n_and', 'xdrv.nb0', 'vdd',
             'led_a', 'led_k']
    vectors = [('iled_cond', 'i(VSENSE)'), ('sink_package', 'i(LPKG)')]+[(node, f'v({node})') for node in nodes]
    original_export = re.findall(r'^wrdata .*$', deck, flags=re.M)
    assert len(original_export) == 1
    new_export = 'wrdata waveform.dat '+' '.join(expr for _, expr in vectors)
    deck = re.sub(r'^wrdata .*$', new_export, deck, flags=re.M)
    changed.append({'field': 'wrdata', 'old_sha256': hashlib.sha256(original_export[0].encode()).hexdigest(),
                    'new_sha256': hashlib.sha256(new_export.encode()).hexdigest()})
    (work/'testbench.spice').write_text(deck)
    emit(work/'diagnostic-stimulus.json', {'symbols': symbols, 'events': events,
                                         'symbol_UI_s': ui, 'duration_s': stop,
                                         'boundary': 'Short held-transition internal-node diagnostic; not4096-bit validation or energy ranking.'})
    emit(work/'identity.json', {'source_work': str(source), 'source_manifest_sha256': sha(source/'manifest.json'),
                               'source_case_sha256': sha(baseline_path), 'source_runner_sha256': sha(runner),
                               'execution_source_sha256': sha(__file__), 'input_hashes': engine.verify(work)['inputs'],
                               'template_deck_sha256': sha(work/'template-fullframe.spice'),
                               'diagnostic_deck_sha256': sha(work/'testbench.spice'),
                               'diagnostic_stimulus_sha256': sha(work/'diagnostic-stimulus.json'),
                               'changed_testbench_lines': changed, 'case': case,
                               'vectors': {name: i+1 for i, (name, _) in enumerate(vectors)}})
    start = time.monotonic()
    try:
        process = subprocess.run(['ngspice', '-b', 'testbench.spice'], cwd=work,
                                 capture_output=True, text=True, timeout=180)
        code, output, timeout = process.returncode, process.stdout+process.stderr, False
    except subprocess.TimeoutExpired as error:
        code, timeout = None, True
        output = 'TIMEOUT180s\n'+''.join(x.decode(errors='replace') if isinstance(x, bytes) else (x or '')
                                        for x in [error.stdout, error.stderr])
    (work/'ngspice.log').write_text(output)
    raw = work/'waveform.dat'
    record = {'exit_code': code, 'timed_out': timeout, 'elapsed_s': time.monotonic()-start,
              'diagnostic_only': True, 'simulation_ok': code == 0 and raw.exists()}
    if raw.exists():
        record['raw_sha256'] = sha(raw); record['raw_bytes'] = raw.stat().st_size
        if raw.stat().st_size > LIMIT:
            record['analysis_error'] = 'Diagnostic raw exceeded100MiB budget'
        elif record['simulation_ok']:
            data = np.loadtxt(raw, skiprows=1)
            assert np.isfinite(data).all()
            t = data[:, 0]; columns = {name: data[:, i+1] for i, (name, _) in enumerate(vectors)}
            record['sample_count'] = len(t)
            node_value = lambda n: np.zeros(len(t)) if n == '0' else columns[n]
            stress = []
            for device in meta['devices']:
                if all(n == '0' or n in columns for n in device['nodes']):
                    d, g, s, b = (node_value(n) for n in device['nodes'])
                    nfet = device['model'].startswith('nfet')
                    bias = np.maximum(b-d, b-s) if nfet else np.maximum(d-b, s-b)
                    k = int(np.argmax(bias))
                    stress.append({'instance': device['instance'], 'model': device['model'],
                                   'max_body_forward_V': float(bias[k]), 'time_s': float(t[k]),
                                   'nodes': device['nodes']})
            record['observable_body_forward'] = stress
            stats = []
            for event in events:
                before, after = event['from'], event['to']; at = event['transition_symbol']*ui
                selected = (t >= at) & (t < at+2*ui)
                row = dict(event, at_s=at, node_edges=[], node_extrema={})
                logical = {'d0': (GRAY[before][1], GRAY[after][1]),
                           'd1': (GRAY[before][0], GRAY[after][0]),
                           'xdrv.t1': (int(before >= 1), int(after >= 1)),
                           'xdrv.t3': (int(before >= 3), int(after >= 3))}
                for unit in [1, 2, 3]:
                    logical['xdrv.gp'+str(unit)] = (int(before >= unit), int(after >= unit))
                for node, (old, new) in logical.items():
                    if old != new:
                        row['node_edges'].append({'node': node, 'direction': 'rise' if new else 'fall',
                            'delay_to_half_VDD_ps': crossing(t, columns[node], at, at+2*ui, 1.65, bool(new))})
                for node in nodes:
                    row['node_extrema'][node] = {'min_V': float(columns[node][selected].min()),
                                                'max_V': float(columns[node][selected].max())}
                prior = (t > at-.5*ui) & (t < at-.1*ui)
                later = (t > at+3.5*ui) & (t < at+3.9*ui)
                low, high = float(columns['iled_cond'][prior].mean()), float(columns['iled_cond'][later].mean())
                row['iled_before_uA'], row['iled_after_uA'] = low*1e6, high*1e6
                row['iled_50percent_delay_ps'] = crossing(t, columns['iled_cond'], at, at+3.5*ui, (low+high)/2, high > low)
                row['iled_90percent_delay_ps'] = crossing(t, columns['iled_cond'], at, at+3.5*ui, low+.9*(high-low), high > low)
                row['iled_at_frozen_delay_uA'] = float(np.interp(at+1.125*ui, t, columns['iled_cond'])*1e6)
                cap_current = columns['sink_package']-columns['iled_cond']
                sample_at = at+1.125*ui
                row['sink_at_frozen_delay_uA'] = float(np.interp(sample_at, t, columns['sink_package'])*1e6)
                row['CLED_current_at_frozen_delay_uA'] = float(np.interp(sample_at, t, cap_current)*1e6)
                row['sink_after_1ns_uA'] = float(np.interp(at+1e-9, t, columns['sink_package'])*1e6)
                row['iled_after_1ns_uA'] = float(np.interp(at+1e-9, t, columns['iled_cond'])*1e6)
                charge_window = (t >= at) & (t <= at+3.5*ui)
                charge_indices = np.flatnonzero(charge_window)
                first, last = charge_indices[0], charge_indices[-1]
                delta_v = ((columns['led_a'][last]-columns['led_k'][last])-
                           (columns['led_a'][first]-columns['led_k'][first]))
                q_kcl = float(np.trapezoid(cap_current[charge_window], t[charge_window]))
                q_cv = float(200e-15*delta_v)
                row['CLED_charge_check'] = {'t0_s': float(t[first]), 't1_s': float(t[last]),
                                           'integral_sink_minus_ILED_C': q_kcl,
                                           'C_times_delta_LED_voltage_C': q_cv,
                                           'difference_C': q_kcl-q_cv,
                                           'polarity': 'CLED anode->cathode; I(LPKG)=I(VSENSE)+I(CLED).'}
                stats.append(row)
            record['transitions'] = stats
        gz = work/'waveform.dat.gz'
        with raw.open('rb') as source_stream, gzip.open(gz, 'wb', compresslevel=5) as target:
            shutil.copyfileobj(source_stream, target)
        with gzip.open(gz, 'rb') as stream:
            verified = hashlib.sha256(stream.read()).hexdigest()
        assert verified == record['raw_sha256']
        record['gzip_sha256'] = sha(gz); record['gzip_bytes'] = gz.stat().st_size
        raw.unlink()
    record['retained_bytes'] = sum(p.stat().st_size for p in work.rglob('*') if p.is_file())
    record['budget_passed'] = record['retained_bytes'] < LIMIT
    record['limits_zh'] = ['只诊断短暂态内部传播，不调用原全帧evaluate，不计算BER/接收通过或pJ/payload排名。',
                           '单个TT数值配置、无PEX；正向体结电压不等于已提取体结电流或已证实损伤。',
                           'ILED是VSENSE导电支路；节点时序只支持观察到的相关传播现象，仍需受控改动才能确认修复因果。']
    emit(work/'result.json', record)
    print(json.dumps({k: record[k] for k in ['simulation_ok', 'timed_out', 'elapsed_s', 'retained_bytes', 'budget_passed']}))


if __name__ == '__main__':
    main()
