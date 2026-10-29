#!/usr/bin/env python3
"""Independent energy/stress/NRZ training checks from native stored waveforms.

Uses the frozen physical optical proxy, but an independently coded uniform-grid
RX recurrence and NRZ training/crossing evaluation. Does not run SPICE.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / 'evidence/vcsel-robustness-20261029'
UI = 1 / 3.7e9
END = 4736 * UI


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def load_module(path):
    spec = importlib.util.spec_from_file_location('audit_optical', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def positive_pwl(t, p):
    """Area above zero of each linear power segment, using triangle geometry."""
    a, b, dt = p[:-1], p[1:], np.diff(t)
    full = (a >= 0) & (b >= 0)
    crossing = ((a < 0) & (b > 0)) | ((a > 0) & (b < 0))
    area = float(np.sum(dt[full] * (a[full] + b[full]) / 2))
    positive_end = np.maximum(a[crossing], b[crossing])
    area += float(np.sum(dt[crossing] * positive_end**2 / (2 * np.abs(b[crossing] - a[crossing]))))
    net = float(np.sum(dt * (a + b) / 2))
    return dict(positive_J=area, returned_J=area-net, net_J=net)


def uniform_rx(x, step, hz=5e9):
    # y[k] = d*y[k-1] + a*x[k-1] + b*x[k] for a linear input segment.
    tau = 1 / (2 * math.pi * hz)
    d = math.exp(-step / tau)
    q = -math.expm1(-step / tau) * tau / step
    a, b = q-d, 1-q
    forcing = a*x[:-1] + b*x[1:]
    y = np.empty(len(x)); y[0] = x[0]
    for k, value in enumerate(forcing, 1):
        y[k] = d*y[k-1] + value
    return y


def crossing_times(t, y, threshold=62.5):
    d = y-threshold
    ix = np.flatnonzero(d[:-1]*d[1:] < 0)
    crossing = t[ix] - d[ix]*(t[ix+1]-t[ix])/(d[ix+1]-d[ix])
    zero = d == 0
    edge = zero & (np.r_[True, ~zero[:-1]] | np.r_[~zero[1:], True])
    return np.unique(np.r_[crossing, t[edge]])


def measures(t, y, crossings, indices, bits, delay, lower, upper):
    when = indices*UI+delay
    sample = np.interp(when, t, y)
    signed = (2*bits-1)*(sample-62.5)
    pos = np.searchsorted(crossings, when, side='right')
    extended = np.r_[lower, crossings, upper]
    previous = np.maximum(extended[pos], lower)
    following = np.minimum(extended[pos+1], upper)
    hm = np.maximum(0, np.minimum(when-previous, following-when))
    hm[signed <= 0] = 0
    return dict(errors=int(np.sum((sample >= 62.5) != bits)),
                margin_uAeq=float(signed.min()), time_ps=float(hm.min()*1e12))


def receiver(t, y, bits):
    train_idx, val_idx = np.arange(64, 512), np.arange(576, 4672)
    prefix = t < 576*UI
    tc, yc = t[prefix], y[prefix]
    train_crossings = crossing_times(tc, yc)
    scores = []
    for ps in range(0, 8001, 5):
        point = measures(t, y, train_crossings, train_idx, bits[train_idx], ps*1e-12, 64*UI, tc[-1])
        scores.append(min(point['margin_uAeq']/7.5, point['time_ps']/100))
    chosen = int(np.argmax(scores))
    delay = chosen*5e-12
    value = measures(t, y, crossing_times(t, y), val_idx, bits[val_idx], delay, 0, END)
    value.update(delay_ps=chosen*5, training_joint_score=float(scores[chosen]), candidate_count=len(scores))
    return value


def run_old(case):
    work = ROOT / 'build/three-gbps-experiment-20261027/vcsel-driver' / case
    manifest = json.loads((work/'manifest.json').read_text())
    result = json.loads((work/'result.json').read_text())
    analysis = work/'analysis-v3-diagnostic'
    expected = json.loads((analysis/'result.json').read_text())
    source = analysis/'inputs/scripts/three_gbps_experiment/vcsel_model.py'
    optical = load_module(source)
    wave = ROOT/result['waveform']['path']
    assert sha(wave) == result['waveform']['sha256']
    native = np.loadtxt(wave, skiprows=1)
    ix = {name: k+1 for k, name in enumerate(manifest['expressions'])}
    assert np.all(np.diff(native[:, 0]) > 0) and abs(native[-1, 0]-END) < 1e-15
    ports = {'VLASER':'laser_src','VDD':'vdd_src','VREF':'ref_src','VD':'d_src','VDB':'db_src'}
    energy = {port: positive_pwl(native[:, 0], -native[:, ix['v('+node+')']]*native[:, ix['i('+port+')']]) for port, node in ports.items()}
    worst = []
    for dev in manifest['devices']:
        v = [np.zeros(len(native)) if n == '0' else native[:, ix['v('+n+')']] for n in dev['nodes']]
        pairs = {(a,b): float(np.max(abs(v[a]-v[b]))) for a in range(4) for b in range(a+1,4)}
        max_pair = max(pairs, key=pairs.get)
        body = np.max(np.r_[v[3]-v[0], v[3]-v[2], 0]) if dev['model'].startswith('n') else np.max(np.r_[v[0]-v[3], v[2]-v[3], 0])
        worst.append({'instance':dev['instance'],'max_terminal_V':pairs[max_pair],'terminal_indices_DGSB':list(max_pair),'body_forward_V':float(body)})
    t = np.linspace(0, END, int(np.ceil(END/2.5e-12))+1)
    current = np.interp(t, native[:, 0], native[:, ix['v(jmon)']])
    power = optical.optical_power(t, current, response='figure3mA_proxy')
    low, high = optical.static_power(np.array([.003,.007]))
    eq = 25+(power-low)*75/(high-low)
    filtered = uniform_rx(eq, t[1]-t[0])
    stimulus = json.loads((work/'stimulus.json').read_text())
    rx = receiver(t, filtered, np.array(stimulus['bits']))
    exp = expected['receiver']
    assert rx['errors'] == exp['validation']['bit_errors']
    assert abs(rx['margin_uAeq']-exp['validation']['decision_distance_min_uA']) < 1e-7
    assert abs(rx['time_ps']-exp['horizontal_margin']['min_ps']) < 1e-5
    assert abs(rx['delay_ps']-exp['sampling']['delay_s']*1e12) < 1e-7
    exact = json.loads((work/'energy-exact.json').read_text())
    for port, values in energy.items():
        for key, value in values.items():
            assert abs(value-exact['energy_by_port'][port][key]) < 1e-22
    assert abs(max(d['max_terminal_V'] for d in worst)-max(max(d['max_abs_terminal_V'].values()) for d in result['stress'])) < 1e-12
    return dict(case=case,waveform_sha256=sha(wave),manifest_sha256=sha(work/'manifest.json'),
                receiver_independent=rx,energy_by_port=energy,
                positive_pJ_per_offered_payload_bit=sum(v['positive_J'] for v in energy.values())/4096*1e12,
                worst_devices=sorted(worst,key=lambda d:d['max_terminal_V'],reverse=True)[:4],
                maximum_terminal_V=max(d['max_terminal_V'] for d in worst),maximum_body_forward_V=max(d['body_forward_V'] for d in worst),
                checked_saved_receiver=True,checked_saved_energy=True,checked_saved_stress=True,
                optical_proxy_source_sha256=sha(source),saved_energy_record=exact)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', action='append', required=True)
    args = ap.parse_args()
    rows=[]
    for case in args.case:
        row=run_old(case);rows.append(row)
        print(json.dumps({k:v for k,v in row.items() if k in ['case','receiver_independent','positive_pJ_per_offered_payload_bit','maximum_terminal_V']},indent=2),flush=True)
    out=dict(script_sha256=sha(__file__),scope='Independent postprocess of prior baseline, no new SPICE run; same frozen optical proxy, independent RX recurrence/NRZ training and native PWL power integration.',rows=rows)
    (EV/'audit-baseline-recheck.json').write_text(json.dumps(out,indent=2)+'\n')
