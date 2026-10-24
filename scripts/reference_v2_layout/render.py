"""Render actual GDS polygons at equal XY scale; never synthesize a mock layout."""
from pathlib import Path
import argparse
import hashlib
import json
import klayout.db as k
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Patch

ROOT = Path(__file__).resolve().parents[2]
STYLES = {55:("Dualgate 6V", "#e7d5a1", .45), 21:("N-well", "#d3e4ec", .65),
          204:("P-well", "#d9e7db", .65), 22:("Active", "#87ad96", .85),
          30:("Poly", "#bb765d", .9), 33:("Contact", "#293d44", 1),
          34:("Metal1", "#879cb5", .8), 35:("Via1", "#31475b", 1),
          36:("Metal2", "#36879b", .8), 38:("Via2", "#31475b", 1),
          42:("Metal3", "#9477a4", .8), 40:("Via3", "#31475b", 1),
          46:("Metal4", "#b2934e", .8), 41:("Via4", "#31475b",1),
          81:("Metal5", "#bd6580", .85)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    base, output = ROOT/a.run, ROOT/a.out
    output.mkdir(parents=True, exist_ok=True)
    status = json.loads((base/"status.json").read_text())
    for route in status:
        c = json.loads((base/route/"physical-contract.json").read_text())
        gds = base/route/"generate"/(c["top"]+".gds")
        digest = hashlib.sha256(gds.read_bytes()).hexdigest()
        assert digest == c["gds_sha256"]
        lay = k.Layout()
        lay.read(str(gds))
        top = lay.cell(c["top"])
        polygons = []
        fig, ax = plt.subplots(figsize=(15, 7), facecolor="#fafbf8")
        for layer, (name, color, opacity) in STYLES.items():
            idx = lay.layer(layer, 0)
            for poly in k.Region(top.begin_shapes_rec(idx)).each():
                points = [[q.x*lay.dbu, q.y*lay.dbu] for q in poly.each_point_hull()]
                assert poly.holes() == 0
                polygons.append(dict(layer=layer, points=points))
                ax.add_patch(Polygon(points, facecolor=color, edgecolor=color, lw=.15, alpha=opacity))
        b = c["bbox_um"]
        for d in c["devices"]:
            ax.text(d["cx"], d["cy"]+d["w_um"]/2+5,
                    d["name"]+"\n"+f"{d['w_um']:g}/{d['l_um']:g}",
                    ha="center", va="bottom", fontsize=6, color="#263d4b")
        for n, (x,y) in c["port_anchor_um"].items():
            ax.text(x, y-2, n, fontsize=5, va="top", ha="left", color="#4d465b")
        ax.set_aspect("equal")
        ax.set(xlim=(b[0]-4, b[2]+4), ylim=(b[1]-5,b[3]+20),
               xlabel="x (µm)", ylabel="y (µm)",
               title=f"{c['top']} | {len(c['devices'])} MOS | {c['width_um']:.2f} × {c['height_um']:.2f} µm")
        ax.spines[["top", "right"]].set_visible(False)
        present={p["layer"] for p in polygons}
        fig.legend(handles=[Patch(facecolor=STYLES[i][1], label=STYLES[i][0])
                            for i in [55,21,22,30,34,36,42,46,81] if i in present], loc="lower center",
                   ncol=8, frameon=False, fontsize=8)
        fig.text(.06,.08,"Actual GDS readback; equal XY scale. Standalone MOS module; external R/C and precision anchor excluded.",
                 fontsize=9, color="#546975")
        fig.tight_layout(rect=(0,.12,1,1))
        for suffix in ("svg", "png"):
            fig.savefig(output/(route+"-layout."+suffix), dpi=160)
        plt.close(fig)
        (output/(route+"-geometry.json")).write_text(json.dumps(dict(
            gds=str(gds.relative_to(ROOT)), gds_sha256=digest,
            bbox_um=b, contract=c, styles=STYLES, polygons=polygons),separators=(",",":"))+"\n")


if __name__ == "__main__":
    main()
