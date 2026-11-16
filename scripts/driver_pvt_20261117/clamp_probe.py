#!/usr/bin/env python3
"""Separate gate overdrive, body bias and MOS corner in the B clamp."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PRIOR = ROOT / 'build/driver-interface-20261115/MicroLED/B-protected_v6r'
WORK = ROOT / 'build/driver-pvt-20261117/clamp-probe'
EVIDENCE = ROOT / 'evidence/driver-pvt-20261117/clamp-probe.json'
CASES = [('typical', 27), ('typical', -40), ('typical', 85),
         ('ss', 27), ('ff', 27), ('sf', 27), ('fs', 27),
         ('ss', 85), ('ff', -40), ('sf', 85), ('fs', -40)]
GATE_AT_20NS = 1.432299719
SOURCE_AT_20NS = 1.86767585
VDS_AT_20NS = 2.15278997


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_deck(corner, temperature, clamp):
    def instance(suffix, drain, gate, source):
        return ' '.join([clamp[0] + suffix, drain, gate, source, '0', *clamp[5:]])

    return f'''B protection clamp static bias probe
.include design.ngspice
.param sw_stat_global=0 sw_stat_mismatch=0
.lib sm141064.ngspice {corner}
.temp {temperature}
VGS g 0 0
VSB s 0 {SOURCE_AT_20NS}
BGATE gs 0 V=v(s)+v(g)
VDS d s {VDS_AT_20NS}
VDS0 d0 0 {VDS_AT_20NS}
{instance('_BODY', 'd', 'gs', 's')}
{instance('_ZERO', 'd0', 'g', '0')}
.control
set wr_vecnames
set wr_singlescale
set numdgt=16
dc VGS 0.8 2.6 0.005
wrdata sweep.dat v(g) i(VDS) i(VDS0)
quit
.endc
.end
'''


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    source = PRIOR / 'DC-L1/testbench.spice'
    clamp = next(line.split() for line in source.read_text().splitlines() if line.startswith('XCLAMP '))
    manifest = PRIOR / 'manifest.json'
    inputs = json.loads(manifest.read_text())['inputs']
    model_hashes = {}
    for name in ['design.ngspice', 'sm141064.ngspice']:
        model = PRIOR / 'inputs/pdk' / name
        model_hashes[name] = sha(model)
        assert model_hashes[name] == inputs[f'pdk/{name}']
        shutil.copyfile(model, WORK / name)

    records = []
    for corner, temp in CASES:
        folder = WORK / f'{corner}-{temp:+d}C'
        folder.mkdir(exist_ok=True)
        source_deck = folder / 'probe.spice'
        source_deck.write_text(build_deck(corner, temp, clamp))
        # Model includes in the locked library are relative to ngspice cwd.
        for name in model_hashes:
            link = folder / name
            if not link.exists():
                link.symlink_to(WORK / name)
        log = folder / 'ngspice.log'
        with log.open('w') as stream:
            subprocess.run(['ngspice', '-b', 'probe.spice'], cwd=folder,
                           stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=60)
        trace = folder / 'sweep.dat'
        data = np.loadtxt(trace, skiprows=1, ndmin=2)
        assert data.shape == (361, 4) and np.isfinite(data).all()
        assert np.allclose(data[:, 0], data[:, 1])
        vgs, body_biased, source_tied = data[:, 1], -data[:, 2], -data[:, 3]
        sample = lambda curve, voltage: float(np.interp(voltage, vgs, curve) * 1e6)
        records.append({
            'corner': corner, 'mos_temp_C': temp,
            'drain_branch_uA_at_historical_vgs': [sample(body_biased, GATE_AT_20NS),
                                                 sample(source_tied, GATE_AT_20NS)],
            'drain_branch_uA_at_minus_5pct_gate_swing': sample(body_biased, GATE_AT_20NS - .165),
            'drain_branch_uA_at_plus_5pct_gate_swing': sample(body_biased, GATE_AT_20NS + .165),
            'case': str(folder.relative_to(ROOT)), 'deck_sha256': sha(source_deck),
            'trace_sha256': sha(trace), 'log_sha256': sha(log),
        })
    report = {
        'prior_clamp_instance': ' '.join(clamp),
        'prior_deck': str(source.relative_to(ROOT)), 'prior_deck_sha256': sha(source),
        'model_sha256': model_hashes, 'model_manifest_sha256': sha(manifest), 'vds_V': VDS_AT_20NS,
        'vgs_at_previous_20ns_V': GATE_AT_20NS,
        'vsb_V': [SOURCE_AT_20NS, 0], 'cases': records,
        'scope': 'Independent DC forced-bias branch measurement. No LED, output, or gate feedback. The ±0.165 V sensitivities move only VGS, not all supplies. Drain branch includes model leakage; it is neither LED forward current nor a transient prediction.',
    }
    EVIDENCE.write_text(json.dumps(report, indent=2) + '\n')
    for row in records:
        print(row['corner'], row['mos_temp_C'], row['drain_branch_uA_at_historical_vgs'],
              row['drain_branch_uA_at_minus_5pct_gate_swing'],
              row['drain_branch_uA_at_plus_5pct_gate_swing'])


if __name__ == '__main__':
    main()
