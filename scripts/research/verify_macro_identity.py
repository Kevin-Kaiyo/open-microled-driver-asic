"""Independently compare frozen macro polygons after hierarchical integration.

This verifies the copied macro geometry, not the added route connectivity or
DRC. Those require their separate extraction and rule-deck results.
"""
from pathlib import Path
import argparse
import hashlib
import json
import klayout.db as kdb

ROOT = Path(__file__).resolve().parents[2]
MACROS = {
    'pixel_driver_layout': (
        'evidence/layout/pixel_driver_layout.gds',
        '20ff3a9d180eb0ef19de7a17a82e492e9153d2d7cf8ae77585024b10c7f431ad'),
    'pixel_pwm': (
        'evidence/physical/digital/gds/pixel_pwm.gds',
        '2045ef4da8a9e83f1db109372454504c66b6d3e963704ddb0caaf64118307aa2'),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gds', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    integrated = kdb.Layout()
    integrated.read(str(args.gds))
    top = integrated.cell('pixel_integrated')
    if top is None or [c.name for c in integrated.top_cells()] != ['pixel_integrated']:
        raise RuntimeError('Expected one integrated top cell')
    instances = list(top.each_inst())
    if sorted(i.cell.name for i in instances) != sorted(MACROS) or any(i.is_regular_array() for i in instances):
        raise RuntimeError('Expected exactly one instance of each frozen macro')
    placements = {i.cell.name: str(i.dtrans) for i in instances}
    results = {}
    for name, (relative, expected) in MACROS.items():
        source_path = ROOT / relative
        if sha(source_path) != expected:
            raise RuntimeError('Frozen v0.2 macro input changed: ' + relative)
        source = kdb.Layout()
        source.read(str(source_path))
        original = source.cell(name)
        copied = integrated.cell(name)
        if original is None or copied is None or source.dbu != integrated.dbu:
            raise RuntimeError('Macro missing or database unit changed: ' + name)
        layers = sorted(set((source.get_info(i).layer, source.get_info(i).datatype)
                            for i in source.layer_indexes()) |
                        set((integrated.get_info(i).layer, integrated.get_info(i).datatype)
                            for i in integrated.layer_indexes()))
        checks = []
        for layer, datatype in layers:
            old_index = source.find_layer(layer, datatype)
            new_index = integrated.find_layer(layer, datatype)
            old = kdb.Region(original.begin_shapes_rec(old_index)) if old_index is not None else kdb.Region()
            new = kdb.Region(copied.begin_shapes_rec(new_index)) if new_index is not None else kdb.Region()
            difference = old ^ new
            if not difference.is_empty():
                raise RuntimeError(f'Macro geometry changed: {name} layer {layer}/{datatype}')
            checks.append({'layer': layer, 'datatype': datatype,
                           'xor_area_um2': difference.area() * source.dbu**2})
        results[name] = {'source_path': relative, 'source_sha256': expected,
                         'bbox_um': [v * source.dbu for v in
                                     [original.bbox().left, original.bbox().bottom,
                                      original.bbox().right, original.bbox().top]],
                         'layer_polygon_checks': checks, 'passed': True}
    data = {'passed': True, 'scope': 'Recursive per-layer polygon identity of both copied frozen macros; does not prove added routing',
            'integrated_gds': str(args.gds), 'integrated_gds_sha256': sha(args.gds),
            'placements': placements,
            'klayout_version': kdb.__version__, 'macros': results,
            'source_hashes': {'scripts/research/verify_macro_identity.py': sha(Path(__file__))}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + '\n')
    print('PASS both frozen macro polygon sets match; actual integrated GDS hash recorded')


if __name__ == '__main__':
    main()
