"""Verify three mathematical PWL boundaries, independently of physical validity.

No source-data fit is changed. The 101 in-domain replay checks are a separate
denominator in lin2026-yellow20-fit.json.
"""
from pathlib import Path
import csv
import hashlib
import json
import math
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / 'analog/models/measured-led/lin2026-yellow20-dc.spice'
CSV = ROOT / 'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv'
FOLDER = ROOT / 'build/led-fit/boundary-probes'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    FOLDER.mkdir(parents=True, exist_ok=True)
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in (MODEL, CSV, Path(__file__))}
    frozen_model = FOLDER / MODEL.name
    frozen_model.write_bytes(MODEL.read_bytes())
    with CSV.open() as source:
        rows = list(csv.DictReader(source))
    current = [float(row['current_A']) for row in rows]
    voltage = [float(row['voltage_V']) for row in rows]
    results = []
    for index, applied in enumerate((-0.1, 1.0, 6.8)):
        deck = f'''Boundary probe: forced LED terminal voltage
.include "{frozen_model}"
VTEST a 0 {applied}
XLED a 0 lin2026_yellow20_dc
.options reltol=1e-9 abstol=1e-17 vntol=1e-11
.control
set numdgt=15
set wr_singlescale
op
wrdata result.dat v(a) i(VTEST)
quit
.endc
.end
'''
        name = f'case-{index}'
        (FOLDER / f'{name}.spice').write_text(deck)
        (FOLDER / 'result.dat').unlink(missing_ok=True)
        run = subprocess.run(['ngspice', '-b', f'{name}.spice'], cwd=FOLDER,
                             text=True, capture_output=True)
        (FOLDER / f'{name}.log').write_text(run.stdout + run.stderr)
        if run.returncode or not (FOLDER / 'result.dat').exists():
            raise RuntimeError(f'Boundary OP failed: {name}')
        observed = -float((FOLDER / 'result.dat').read_text().split()[-1])
        if applied <= voltage[0]:
            expected = applied * current[0] / voltage[0]
        else:
            expected = current[-1] + ((applied - voltage[-1]) *
                (current[-1] - current[-2]) / (voltage[-1] - voltage[-2]))
        delta = observed - expected
        passed = math.isfinite(observed) and abs(delta) <= max(1e-15, abs(expected) * 1e-9)
        results.append(dict(voltage_V=applied, ngspice_current_A=observed,
                            linear_extension_expected_A=expected,
                            difference_A=delta, passed=passed))
    if not all(row['passed'] for row in results):
        raise RuntimeError('A PWL boundary probe disagrees with linear extension')
    if any(sha(ROOT / name) != digest for name, digest in hashes.items()):
        raise RuntimeError('A source changed during the boundary probes')
    report = dict(
        evidence_level='isolated mathematical boundary behavior only; no physical LED validation outside source range',
        runs=len(results), separate_from_in_domain_replay_runs=101,
        conclusion='linear extrapolation below first and above last PWL knot; no endpoint clamp',
        source_hashes=hashes,
        ngspice_version=subprocess.check_output(['ngspice', '--version'], text=True),
        points=results)
    destination = ROOT / 'evidence/led-fit/lin2026-yellow20-boundaries.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
