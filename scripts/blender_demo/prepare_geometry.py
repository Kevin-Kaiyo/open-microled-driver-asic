"""Audit real r5 GDS XY polygons and attach pinned Magic visualization heights.

Run with build/layout/venv/bin/python.  These height annotations are tool
technology data, not a calibrated process cross-section or device simulation.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

import klayout.db as k

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build/blender-demo"
GDS = ROOT / "evidence/layout-v3/r5/startup_test_macro.gds"
GEOMETRY = ROOT / "evidence/layout-v3/r5/geometry.json"
TECH = ROOT / "build/layout/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.tech"
LOCK = ROOT / "layout/pdk-lock.json"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def canonical(points):
    # Source shapes have no holes. A multiset comparison preserves all vertices.
    return tuple(sorted(tuple(v) for v in points))


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    raw = json.loads(GEOMETRY.read_text())
    lock = json.loads(LOCK.read_text())
    assert sha(GDS) == raw["gds_sha256"]
    assert sha(TECH) == lock["files"]["libs.tech/magic/gf180mcuD.tech"]
    layout = k.Layout()
    layout.read(str(GDS))
    top = layout.cell(raw["top"])
    dbu = layout.dbu
    inventory, source_vertices = [], Counter()
    for li in layout.layer_indexes():
        info = layout.get_info(li)
        iterator = top.begin_shapes_rec(li)
        count = texts = holes = 0
        while not iterator.at_end():
            shape = iterator.shape()
            if shape.is_box() or shape.is_polygon() or shape.is_path():
                p = shape.polygon.transformed(iterator.trans())
                count += 1
                holes += p.holes()
                if info.datatype == 0 and str(info.layer) in raw["layers"]:
                    source_vertices[(info.layer, canonical([[v.x, v.y] for v in p.each_point_hull()]))] += 1
            elif shape.is_text():
                texts += 1
            iterator.next()
        inventory.append(dict(layer=info.layer, datatype=info.datatype, polygons=count,
                              holes=holes, texts=texts, included=(info.datatype == 0 and str(info.layer) in raw["layers"])))
    assert not any(x["holes"] for x in inventory), "Preserve holes before adapting this exporter to another GDS"
    json_vertices = Counter((p["layer"], canonical([[round(x/dbu), round(y/dbu)] for x,y in p["points"]])) for p in raw["polygons"])
    assert json_vertices == source_vertices
    regions = {n: k.Region(top.begin_shapes_rec(layout.layer(n, 0))).merged() for n in [22,30,33,34,35,36,38,42]}

    heights = {}
    for lineno, line in enumerate(TECH.read_text().splitlines(), 1):
        match = re.match(r"\s*height\s+(\S+)\s+(-?[\d.]+)\s+(-?[\d.]+)", line)
        if match:
            typ,z,t = match.groups()
            heights[typ] = dict(z_nominal_um=float(z), thickness_nominal_um=float(t), source_line=lineno, magic_type=typ)
    layer_types = {21:"nwell,pwell", 204:"nwell,pwell", 22:"alldiff", 30:"allpoly", 34:"allm1", 35:"via", 36:"allm2", 38:"via2", 42:"allm3"}
    layers = {}
    for layer, metadata in raw["layers"].items():
        n = int(layer)
        layers[layer] = dict(metadata, gds_layer=n, gds_datatype=0)
        if n == 33:
            layers[layer]["variants"] = {name:heights[typ] for name,typ in [("diffusion_contact","alldiffcont"),("poly_contact","pc")]}
        else:
            layers[layer].update(heights[layer_types[n]])
    counts = Counter()
    exported = []
    for i, p in enumerate(raw["polygons"]):
        n = p["layer"]
        record = dict(p, source_polygon_index=i)
        if n == 33:
            poly = k.Polygon([k.Point(round(x/dbu),round(y/dbu)) for x,y in p["points"]])
            contact = k.Region(poly)
            active = (contact-regions[22]).is_empty()
            gate = (contact-regions[30]).is_empty()
            assert active != gate, (i,"Ambiguous contact landing")
            assert (contact-regions[34]).is_empty(), (i,"Contact missing Metal1 landing")
            landing = "diffusion_contact" if active else "poly_contact"
            record["contact_class"] = landing
            record["landing_layer"] = 22 if active else 30
            record.update(heights["alldiffcont" if active else "pc"])
            counts[landing] += 1
        else:
            record.update(heights[layer_types[n]])
        record["z_top_nominal_um"] = record["z_nominal_um"] + record["thickness_nominal_um"]
        exported.append(record)
    via_checks = []
    for cut,lower,upper in [(35,34,36),(38,36,42)]:
        lo = (regions[cut]-regions[lower]).area() * dbu * dbu
        hi = (regions[cut]-regions[upper]).area() * dbu * dbu
        assert lo == hi == 0
        via_checks.append(dict(cut_layer=cut, lower_layer=lower, upper_layer=upper,
                               missing_lower_area_um2=lo, missing_upper_area_um2=hi))
    limitations = [
        "XY vertices are the exact selected r5 GDS polygon vertices. GDS is a layout database, not a 3D process structure.",
        "Z and thickness are nominal height annotations from the pinned open PDK Magic extraction technology, not foundry-certified physical section data.",
        "Well and active slabs are teaching visualization proxies. They do not reconstruct implantation depth, doping, depletion region, gate dielectric, silicide, liners, or diffusion profile.",
        "Colors are layer identifiers, not measured material appearance. No unverified metal composition is assigned.",
        "Layer 31/0 Pplus, 32/0 Nplus, 55/0 Dualgate, 112/1 V5_XTOR and 42/10 pin shapes are omitted from solid rendering; they remain in the original GDS and audit inventory.",
        "Any Z exaggeration or exploded-layer gap must be labeled. It changes display geometry only; electrical connectivity comes from the original GDS and LVS.",
        "No Blender render establishes TCAD, electromagnetic, thermal, circuit, reliability, manufacturing, or optical validation. No actual MicroLED, package, pad ring or complete die is modeled.",
    ]
    source_hashes = {str(p.relative_to(ROOT)):sha(p) for p in [GDS,GEOMETRY,TECH,LOCK,Path(__file__).resolve()]}
    audit = dict(schema_version=1, scope="r5 analog macro, 39 MOS; teaching 3D visualization", top=raw["top"],
                 bbox_um=raw["bbox_um"], dbu_um=dbu, source_sha256=source_hashes,
                 height_source=str(TECH.relative_to(ROOT)), height_source_units="microns, extract section line 3251",
                 layers=layers, all_gds_layers=inventory, polygon_counts=dict(Counter(p["layer"] for p in exported)),
                 total_polygons=len(exported), exact_selected_GDS_vertex_multisets_equal=True,
                 contacts=dict(counts), contact_classification="Whole contact polygon must be inside exactly one of merged Active 22/0 or Poly2 30/0, and inside Metal1 34/0.",
                 via_landing_checks=via_checks, limitations=limitations)
    save("stack-audit.json", audit)
    save("geometry-3d.json", dict(schema_version=1, top=raw["top"], bbox_um=raw["bbox_um"],
                                 dbu_um=dbu, xy_units="um", z_units="um, nominal technology annotations",
                                 polygons=exported,layers=layers, ports=raw["ports"],
                                 gds_sha256=sha(GDS), limitations=limitations))
    save("audit-manifest.json",dict(source_sha256=source_hashes,
        output_sha256={n:sha(OUT/n) for n in ["stack-audit.json","geometry-3d.json"]},passed=True))
    print(json.dumps(dict(passed=True,total_polygons=len(exported),contacts=dict(counts),output=str(OUT)),ensure_ascii=False))


if __name__ == "__main__":
    main()
