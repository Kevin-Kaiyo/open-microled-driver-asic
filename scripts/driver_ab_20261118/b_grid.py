#!/usr/bin/env python3
"""Cross previously separated MOS, temperature, supply and RSET conditions on the exact B DC deck."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from itertools import product
import json
from pathlib import Path
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TAG = 'driver-ab-20261118'
BUILD = ROOT / 'build' / TAG / 'b-grid'
EV = ROOT / 'evidence' / TAG
FIXED = {
    ('typical', 27, 100), ('typical', -40, 100), ('typical', 85, 100),
    ('typical', 27, 95), ('typical', 27, 105), ('ss', 85, 95),
    ('ff', -40, 105), ('sf', 85, 95), ('fs', -40, 105),
}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def replace_line(deck, pattern, replacement):
    result, count = re.subn(pattern, lambda m: replacement(m), deck, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f'Expected one {pattern!r} in source, found {count}')
    return result


def case(variant, source_dir, point):
    section, temp, supply, tolerance_bp, level = point
    target = 100 if level else 25
    src = source_dir / f'tt-DC-L{level}' / 'testbench.spice'
    work = BUILD / variant / f'{section}_{temp}C_{supply}pct_{tolerance_bp:+d}bp_L{level}'
    work.mkdir(parents=True, exist_ok=True)
    deck = src.read_text()
    dependencies = {}

    def redirect(match):
        dep = (src.parent / match.group(2)).resolve(strict=True)
        dependencies[str(dep.relative_to(ROOT))] = sha(dep)
        return match.group(1) + '"' + os.path.relpath(dep, work) + '"'
    deck = re.sub(r'^(\.(?:include|lib) )"([^"]+)"', redirect, deck, flags=re.MULTILINE)
    deck = replace_line(deck, r'^(\.lib .+) typical$', lambda m: m[1] + ' ' + section)
    deck = replace_line(deck, r'^\.temp .+$', lambda m: f'.temp {temp}')
    for port, node, nominal in [('VIN', 'vin_src', 3.3), ('VDD', 'vdd_src', 3.3),
                                 ('VLED', 'led_src', 5), ('VD0', 'data0_src', 3.3*level)]:
        deck = replace_line(deck, rf'^{port} {node} 0 .+$',
                            lambda m: f'{port} {node} 0 {nominal*supply/100:.16g}')
    rset = float(re.search(r'^XDRV .* RSET=(\S+)', deck, re.MULTILINE)[1])
    deck = replace_line(deck, r'^(XDRV .+ RSET=)\S+',
                        lambda m: m[1] + f'{rset*(1+tolerance_bp/10000):.16g}')
    path = work / 'testbench.spice'
    if path.is_file() and path.read_text() != deck:
        raise ValueError(f'Existing, different deck {path}')
    path.write_text(deck)
    with (work / 'ngspice.log').open('w') as log:
        subprocess.run(['ngspice', '-b', path.name], cwd=work, check=True,
                       stdout=log, stderr=subprocess.STDOUT, timeout=45)
    raw = work / 'waveform.dat'
    header, values = raw.read_text().splitlines()
    assert header.lower().split()[1] == 'i(vsense)'
    current = float(values.split()[1]) * 1e6
    return dict(model=section, temp_C=temp, supply_percent=supply, RSET_offset_bp=tolerance_bp,
                level=level, target_uA=target, ILED_uA=current, error_percent=100*(current/target-1),
                original_PVT_point=(section,temp,supply) in FIXED, RSET_nominal_ohm=rset,
                source=str(src.relative_to(ROOT)), source_sha256=sha(src), deck=str(path.relative_to(ROOT)),
                deck_sha256=sha(path), dependencies=dependencies, raw_sha256=sha(raw))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', help='Unique study label')
    parser.add_argument('source_dir', type=Path, help='Variant directory containing frozen tt-DC-L0/L1')
    parser.add_argument('--final-grid',action='store_true',help='Store late confirmation grid separately from the frozen sizing scan')
    args = parser.parse_args()
    global BUILD
    if args.final_grid:
        BUILD=ROOT/'build'/TAG/'b-final-grid'
    points = product(('typical','ss','ff','sf','fs'), (-40,27,85), (95,100,105), (-10,0,10), (0,1))
    with ThreadPoolExecutor(max_workers=2) as pool:
        runs = list(pool.map(lambda point: case(args.variant, args.source_dir.resolve(), point), points))
    result = {}
    for tol in (-10,0,10):
        rows = [r for r in runs if r['RSET_offset_bp'] == tol]
        for subset, condition in [('all45', lambda r: True), ('original9', lambda r: r['original_PVT_point']),
                                  ('extra36', lambda r: not r['original_PVT_point'])]:
            result[f'{tol}bp_{subset}'] = {
                str(target): dict(pass_count=sum(abs(r['error_percent']) <= 1 for r in rows
                                                if r['target_uA'] == target and condition(r)),
                                  ILED_min_uA=min(r['ILED_uA'] for r in rows if r['target_uA']==target and condition(r)),
                                  ILED_max_uA=max(r['ILED_uA'] for r in rows if r['target_uA']==target and condition(r)))
                for target in (25,100)}
    out = EV / f'b-grid-{args.variant}.json'
    out.write_text(json.dumps(dict(method='DC factorial reusing unmodified integrated subcircuits. Fixed emitter IV and res_typical. RSET perturbations in basis points (10 bp = 0.1%).', summary=result, runs=runs), indent=2)+'\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
