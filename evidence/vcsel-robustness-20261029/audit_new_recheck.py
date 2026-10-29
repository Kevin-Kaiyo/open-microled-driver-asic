#!/usr/bin/env python3
"""Audit completed new VCSEL frames without importing their runner/analyzer."""
from pathlib import Path
import argparse
import json
import numpy as np
from audit_recheck import ROOT, EV, UI, END, sha, load_module, positive_pwl, uniform_rx, receiver


def run(case, label):
    work = ROOT/'build/vcsel-robustness-20261029'/case
    m = json.loads((work/'manifest.json').read_text())
    r = json.loads((work/'result.json').read_text())
    a_dir = work/('analysis-'+label)
    result = json.loads((a_dir/'result.json').read_text())
    plan = json.loads((a_dir/'plan.json').read_text())
    c = m['config']
    assert c['mode'] == 'frame' and c['nbits'] == 4736 and c['rate'] == 3.2
    assert abs(m['end_s']-END) < 1e-18
    assert r['simulation_ok'] and r['manifest_sha256'] == sha(work/'manifest.json')
    assert r['deck_sha256'] == sha(work/'testbench.spice')
    assert result['plan_sha256'] == sha(a_dir/'plan.json')
    for name, digest in m['source_hashes'].items():
        assert sha(ROOT/name) == digest, name
    for name, digest in plan['sources'].items():
        assert sha(a_dir/'inputs'/name) == digest, name
    wave = ROOT/r['waveform']['path']
    wave_sha = sha(wave)
    assert wave_sha == r['waveform']['sha256'] == plan['waveform_sha256']
    native = np.loadtxt(wave, skiprows=1)
    ix = {name: k+1 for k, name in enumerate(m['expressions'])}
    assert np.all(np.diff(native[:, 0]) > 0) and abs(native[-1, 0]-END) < 1e-15

    # Compare every physical MOS subcircuit call against the node inventory.
    pins = dict(D='d',DB='db',OUT='out',VLASER='vlaser',VDD='vdd',VREF='vref',
                VSS='0',VSET='vset',VREGSET='vregset',VL='vl')
    from_text = {}
    for line in (work/'inputs/driver.spice').read_text().splitlines():
        words = line.split()
        if len(words) >= 6 and words[5] in ['nmos_3p3','pmos_3p3']:
            assert words[0] not in from_text
            from_text[words[0]] = [pins.get(n, 'xdrv.'+n.lower()) for n in words[1:5]]
    assert from_text == {d['instance']:d['nodes'] for d in m['devices']}
    devices = []
    for dev in m['devices']:
        v = [np.zeros(len(native)) if n == '0' else native[:, ix['v('+n+')']] for n in dev['nodes']]
        pairs = {(i,j):float(np.max(abs(v[i]-v[j]))) for i in range(4) for j in range(i+1,4)}
        pair = max(pairs, key=pairs.get)
        forward = max(float(np.max(v[3]-v[0])), float(np.max(v[3]-v[2])), 0.) if dev['model'].startswith('n') else max(float(np.max(v[0]-v[3])), float(np.max(v[2]-v[3])), 0.)
        devices.append(dict(instance=dev['instance'],max_terminal_V=pairs[pair],
                            terminal_indices_DGSB=list(pair),body_forward_V=forward))
    max_terminal = max(d['max_terminal_V'] for d in devices)
    max_body = max(d['body_forward_V'] for d in devices)
    assert abs(max_terminal-r['max_terminal_V']) < 1e-12
    assert abs(max_body-r['max_body_forward_V']) < 1e-12
    device_ok = max_terminal <= 3.63 and max_body <= .3
    assert device_ok == r['device_screen_passed']

    energy = {}
    for port, node in m['ports'].items():
        power = -native[:, ix['v('+node+')']]*native[:, ix['i('+port+')']]
        values = positive_pwl(native[:, 0], power)
        for key, value in values.items():
            assert abs(value-r['energy_by_port'][port][key]) < 1e-22
        energy[port] = values
    energy_pJ = sum(v['positive_J'] for v in energy.values())/4096*1e12
    assert abs(energy_pJ-r['total_energy']['positive_pJ_per_offered_payload_bit']) < 1e-9

    optical_path = a_dir/'inputs/scripts/three_gbps_experiment/vcsel_model.py'
    optical = load_module(optical_path)
    t = np.linspace(0, END, int(np.ceil(END/(plan['grid_ps']*1e-12)))+1)
    current = np.interp(t, native[:, 0], native[:, ix['v(jmon)']])
    power = optical.optical_power(t, current, response='figure3mA_proxy')
    low, high = optical.static_power(np.array([.003,.007]))
    eq = 25+(power-low)*75/(high-low)
    filtered = uniform_rx(eq, t[1]-t[0])
    stimulus = json.loads((work/'stimulus.json').read_text())
    assert sha(work/'stimulus.json') == m['stimulus_sha256']
    rx = receiver(t, filtered, np.array(stimulus['bits']))
    expected = result['receiver']
    assert rx['errors'] == expected['validation']['bit_errors']
    assert abs(rx['margin_uAeq']-expected['validation']['decision_distance_min_uA']) < 1e-7
    assert abs(rx['time_ps']-expected['horizontal_margin']['min_ps']) < 1e-5
    assert abs(rx['delay_ps']-expected['sampling']['delay_s']*1e12) < 1e-7
    native_min = float(native[:, ix['v(jmon)']].min())
    native_max = float(native[:, ix['v(jmon)']].max())
    domain_ok = native_min >= .002 and native_max <= .0075 and float(power.min()) >= 0
    rx_ok = rx['errors'] == 0 and rx['margin_uAeq'] >= 7.5 and rx['time_ps'] >= 100
    combined = bool(domain_ok and device_ok and rx_ok and expected['checks']['training_error_free'])
    assert combined == result['combined_screen_passed']
    rails = {}
    for node in ['vlaser','vdd','vref','vl','xdrv.dr','xdrv.bctrl','xdrv.tctrl']:
        key = 'v('+node+')'
        if key in ix:
            v = native[:, ix[key]]
            rails[node] = [float(v.min()),float(v.max())]
    return dict(case=case,analysis_label=label,config=c,manifest_sha256=sha(work/'manifest.json'),
                waveform_sha256=wave_sha,analysis_sha256=sha(a_dir/'result.json'),
                MOS_inventory_count=len(devices),all_MOS_nodes_match_netlist=True,
                receiver_independent=rx,energy_by_port=energy,positive_pJ_per_offered_payload_bit=energy_pJ,
                native_current_range_mA=[native_min*1e3,native_max*1e3],native_model_domain_passed=bool(domain_ok),
                maximum_terminal_V=max_terminal,terminal_headroom_mV=(3.63-max_terminal)*1e3,
                maximum_body_forward_V=max_body,worst_devices=sorted(devices,key=lambda d:d['max_terminal_V'],reverse=True)[:4],
                observed_rail_ranges_V=rails,combined_screen_passed=combined,
                checked_saved_receiver=True,checked_saved_energy=True,checked_saved_stress=True,
                optical_proxy_source_sha256=sha(optical_path))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', action='append', required=True)
    ap.add_argument('--label', required=True)
    ap.add_argument('--output', default='audit-new-frame-recheck.json')
    args = ap.parse_args()
    assert '/' not in args.output and args.output.startswith('audit-') and args.output.endswith('.json')
    rows=[]
    for case in args.case:
        row=run(case,args.label);rows.append(row)
        print(json.dumps({k:v for k,v in row.items() if k in ['case','receiver_independent','positive_pJ_per_offered_payload_bit','terminal_headroom_mV','combined_screen_passed']},indent=2),flush=True)
    out=dict(script_sha256=sha(__file__),common_helpers_sha256=sha(Path(__file__).with_name('audit_recheck.py')),
             scope='Independent native-waveform energy/stress and receiver training evaluation; same frozen physical optical proxy. No SPICE rerun, optical measurement, calibrated receiver noise, silicon or physical signoff.',rows=rows)
    (EV/args.output).write_text(json.dumps(out,indent=2)+'\n')
