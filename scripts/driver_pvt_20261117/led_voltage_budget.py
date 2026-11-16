#!/usr/bin/env python3
"""Translate the A/B current window to a voltage budget using the shared I–V curve."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / 'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv'
OUTPUT = ROOT / 'evidence/driver-pvt-20261117/led-voltage-budget.json'


def main():
    with MODEL.open() as stream:
        rows = list(csv.DictReader(stream))
    current = np.array([float(row['current_A']) for row in rows])
    voltage = np.array([float(row['voltage_V']) for row in rows])
    assert np.all(np.diff(current) > 0) and np.all(np.diff(voltage) > 0)
    cases = []
    for target in [25, 100]:
        vmin, vtarget, vmax = np.interp(np.array([.99, 1, 1.01]) * target * 1e-6, current, voltage)
        iminus, iplus = np.interp([vtarget - .25, vtarget + .25], voltage, current) * 1e6
        cases.append({'I_target_uA': target, 'VAK_target_V': float(vtarget),
                      'VAK_tolerance_mV': [float((vmin - vtarget) * 1e3), float((vmax - vtarget) * 1e3)],
                      'I_at_fixed_cathode_and_VLED_shift_minus_plus_0p25_V_uA': [float(iminus), float(iplus)]})
    result = {'data': str(MODEL.relative_to(ROOT)), 'data_sha256': hashlib.sha256(MODEL.read_bytes()).hexdigest(),
              'cases': cases, 'scope': 'Inverse piecewise-linear I–V. ±0.25 V response assumes fixed cathode. Circuit feedback and parasitic drops are absent.'}
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(cases, indent=2))


if __name__ == '__main__':
    main()
