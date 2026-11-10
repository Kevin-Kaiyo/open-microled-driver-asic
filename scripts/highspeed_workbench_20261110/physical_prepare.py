"""Read locked historical high-speed GDS and render source-backed 2D panels."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

import klayout.db as k
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Polygon

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'build/highspeed-workbench-20261110/physical'
DOC = ROOT / 'docs/research/highspeed-workbench-20261110/physical'
EVID = ROOT / 'evidence/highspeed-workbench-20261110'
SOURCE = ROOT / 'evidence/highspeed-nrz-robustness-layout'
TECH = 'libs.tech/magic/gf180mcuD.tech'
COLORS = {
    21: ('N-well', '#94b6e0', 'nwell,pwell'),
    204: ('P-well', '#dfafb5', 'nwell,pwell'),
    22: ('Active', '#51a878', 'alldiff'),
    30: ('Poly', '#bc4566', 'allpoly'),
    33: ('Contact', '#172738', None),
    34: ('Metal1', '#3c73cb', 'allm1'),
    35: ('Via1', '#18406f', 'via'),
    36: ('Metal2', '#06958b', 'allm2'),
    38: ('Via2', '#00594e', 'via2'),
    42: ('Metal3', '#d68e24', 'allm3'),
    40: ('Via3', '#98571c', 'via3'),
    46: ('Metal4', '#8356bd', 'allm4'),
}
CORES = [('A', 'hv-A8-ties-r5', 'Voltage-mode'), ('B', 'hv-r2', 'Current steering')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def read_core(route, revision, title, heights):
    source = SOURCE / revision / route
    contract_path = source / 'physical-contract.json'
    contract = load(contract_path)
    top = contract['top']
    gds = source / 'generate' / f'{top}.gds'
    rc = source / 'full-rc' / f'{top}_rc.spice'
    geometry_path = source / 'gds-geometry-audit.json'
    drc_path = source / 'klayout-result.json'
    pex_path = source / 'pex-audit.json'
    lvs = source / 'readback-lvs.log'
    schematic = source / 'source/schematic.spice'
    electrical = source / 'selected-electrical-source.spice'
    geometry = load(geometry_path)
    drc = load(drc_path)
    pex = load(pex_path)
    assert sha(gds) == contract['gds_sha256'] == geometry['gds_sha256'] and geometry['passed']
    assert sha(rc) == pex['full_rc_sha256'] and pex['passed'] and pex['rc_collapse_lvs']['passed']
    assert {sha(schematic), sha(electrical)} == set(contract['source_sha256'].values())
    assert drc['passed'] and drc['item_count'] == 0
    assert 'Final result: Circuits match uniquely.' in lvs.read_text()

    layout = k.Layout()
    layout.read(str(gds))
    cell = layout.cell(top)
    dbu = layout.dbu
    box = cell.bbox()
    bbox = [v * dbu for v in [box.left, box.bottom, box.right, box.top]]
    assert all(abs(a - b) < dbu / 2 for a, b in zip(bbox, contract['bbox_um']))
    regions = {n: k.Region(cell.begin_shapes_rec(layout.layer(n, 0))).merged() for n in COLORS}
    landing_pairs = [(35, 34, 36), (38, 36, 42), (40, 42, 46)]
    for cut, lower, upper in landing_pairs:
        assert (regions[cut] - regions[lower]).is_empty()
        assert (regions[cut] - regions[upper]).is_empty()

    polygons, inventory, contacts = [], [], Counter()
    for li in layout.layer_indexes():
        info = layout.get_info(li)
        layer = info.layer
        selected = info.datatype == 0 and layer in COLORS
        count, texts = 0, 0
        for iterator in cell.begin_shapes_rec(li).each():
            shape = iterator.shape()
            if shape.is_text():
                texts += 1
            elif shape.is_box() or shape.is_polygon() or shape.is_path():
                count += 1
                if not selected:
                    continue
                polygon = shape.polygon.transformed(iterator.trans())
                assert polygon.holes() == 0, (route, layer)
                kind = COLORS[layer][2]
                if layer == 33:
                    contact = k.Region(polygon)
                    active = (contact - regions[22]).is_empty()
                    poly = (contact - regions[30]).is_empty()
                    assert active != poly and (contact - regions[34]).is_empty()
                    kind = 'alldiffcont' if active else 'pc'
                    contacts[kind] += 1
                points = [[p.x, p.y] for p in polygon.each_point_hull()]
                polygons.append(dict(layer=layer, points=points, height=heights[kind]))
        inventory.append(dict(layer=layer, datatype=info.datatype, included=selected,
                              polygons=count, texts=texts))

    receipt = dict(route=route, title=title, revision=revision, top=top, dbu_um=dbu,
                   bbox_um=bbox, width_um=contract['width_um'], height_um=contract['height_um'],
                   bbox_area_um2=contract['area_um2'], ports=contract['ports'],
                   port_anchor_um=contract['port_anchor_um'], devices=contract['devices'],
                   inventory=inventory, contact_types=dict(contacts), via_landings=landing_pairs,
                   selected_polygons=len(polygons), historical_checks=dict(klayout_drc_items=0,
                   gds_readback_lvs='unique match', rc_collapsed_lvs='unique match',
                   extracted=pex['counts']), source_sha256={str(p.relative_to(ROOT)): sha(p)
                   for p in [gds, rc, contract_path, geometry_path, drc_path, pex_path, lvs, schematic, electrical]})
    return receipt, polygons


def render_2d(cores):
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none',
                         'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 2, figsize=(13, 8.2), facecolor='#f8fafc')
    fig.subplots_adjust(left=.067, bottom=.18, top=.77, right=.97, wspace=.2)
    fig.text(.067, .947, 'Historical high-speed driver cores', fontsize=25, weight='bold', color='#112d41')
    fig.text(.067, .906, 'Same XY scale  /  GF180MCU-D  /  GDS polygon readback  /  top view',
             fontsize=12, color='#4f6275')
    for ax, core in zip(axes, cores):
        summary = core['summary']
        dbu = summary['dbu_um']
        ax.set_title(f"{summary['route']}  |  {summary['title']}  ·  {summary['revision']}",
                     loc='left', fontsize=13, weight='bold', color='#112d41', pad=36)
        mos = summary['historical_checks']['extracted']['mos']
        ax.text(0, 1.035, f"{mos} MOS + 1 R   /   {summary['width_um']:.3f} × {summary['height_um']:.3f} µm",
                transform=ax.transAxes, fontsize=10.5, color='#53687a')
        ax.set_facecolor('#fff')
        for layer in COLORS:
            color = COLORS[layer][1]
            for p in core['polygons']:
                if p['layer'] != layer:
                    continue
                ax.add_patch(Polygon([(x*dbu, y*dbu) for x,y in p['points']], closed=True,
                                     facecolor=color, edgecolor=color, linewidth=.25,
                                     alpha=.32 if layer in {21, 204} else .82))
        for d in summary['devices']:
            ax.annotate('M'+d['name'], (d['cx'], d['cy']), xytext=(d['cx'], 33+(d['cx']%4)*1.5),
                        ha='center', va='bottom', rotation=65, fontsize=6.6, color='#16293b',
                        arrowprops=dict(arrowstyle='-', color='#7b8795', lw=.45))
        # The output anchor is readable and uses the original local GDS port location.
        x, y = summary['port_anchor_um']['OUT']
        ax.plot(x, y, marker='o', ms=4, color='#002c3c', markeredgecolor='#fff', markeredgewidth=.7)
        ax.annotate('OUT port', (x,y), xytext=(x+11,y-10), fontsize=8.3, color='#002c3c',
                    bbox=dict(facecolor='white', edgecolor='none', alpha=.87, pad=1.4),
                    arrowprops=dict(arrowstyle='-', color='#002c3c', lw=.7))
        ax.set(xlim=(-10, 58), ylim=(-42, 42), xlabel='X (µm)', ylabel='Y (µm)')
        ax.set_aspect('equal', adjustable='box')
        ax.tick_params(labelsize=9, colors='#53687a', length=3)
        ax.spines[['bottom','left']].set_color('#acb9c3')
    fig.legend([Patch(facecolor=v[1]) for v in COLORS.values()], [v[0] for v in COLORS.values()],
               loc='lower center', ncol=6, frameon=False, fontsize=10, bbox_to_anchor=(.5,.071))
    fig.text(.067, .045, 'M labels = schematic instance centers from physical contract  •  OUT = local port anchor  •  implant and marker layers retained in GDS',
             fontsize=9.3, color='#53687a')
    fig.savefig(DOC / 'actual-layout-2d.svg')
    fig.savefig(DOC / 'actual-layout-2d.png', dpi=155)
    plt.close(fig)


def main():
    for path in [RUN, DOC, EVID]:
        path.mkdir(parents=True, exist_ok=True)
    tech = ROOT / 'build/layout/pdk/gf180mcuD' / TECH
    lock_path = ROOT / 'layout/pdk-lock.json'
    lock = load(lock_path)
    assert sha(tech) == lock['files'][TECH]
    heights = {}
    for lineno, line in enumerate(tech.read_text().splitlines(), 1):
        match = re.match(r'\s*height\s+(\S+)\s+(-?[\d.]+)\s+(-?[\d.]+)', line)
        if match:
            kind, z, thickness = match.groups()
            heights[kind] = dict(z=float(z), thickness=float(thickness), tech_line=lineno)
    core_models = []
    for route, revision, title in CORES:
        summary, polygons = read_core(route, revision, title, heights)
        core_models.append(dict(summary=summary, polygons=polygons))
        print(f"{route}: {summary['selected_polygons']} selected polygons, {summary['contact_types']} contacts, 3 via levels checked")
    layers = {n: dict(name=row[0], color=row[1], nominal_height=heights.get(row[2]))
              for n,row in COLORS.items()}
    stack = dict(technology_file=TECH, technology_sha256=sha(tech), lock_sha256=sha(lock_path),
                 nominal_unit='µm', z_multiplier=6, exploded_gap_per_tier_um=2,
                 layers=layers, contact_height={'diffusion': heights['alldiffcont'], 'poly': heights['pc']})
    save(RUN / 'gds-model.json', dict(cores=core_models, stack=stack))
    render_2d(core_models)
    save(EVID / 'physical-sources.json', dict(schema_version=1, stack=stack,
         klayout_version=k.__version__, matplotlib_version=matplotlib.__version__,
         cores=[c['summary'] for c in core_models]))


if __name__ == '__main__':
    main()
