"""Render the actual GDS polygons into a readable teaching figure."""
from pathlib import Path
import argparse
import klayout.db as kdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Patch
plt.rcParams["font.family"] = ["Avenir Next", "Arial", "sans-serif"]

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--gds", type=Path, default=ROOT / "build/layout/work_v2/pixel_driver_layout.gds")
parser.add_argument("--output", type=Path, default=ROOT / "evidence/layout/layout.png")
args = parser.parse_args()
layout = kdb.Layout()
layout.read(str(args.gds))
top = layout.top_cell()
dbu = layout.dbu
styles = {
    21: ("Well", "#dae6ee", 0.65),
    204: ("Pwell", "#d8eadd", 0.65),
    22: ("Active", "#95b5a1", 0.85),
    30: ("Poly gate", "#c16c45", 0.90),
    33: ("Contact", "#30383d", 1.0),
    34: ("Metal1", "#738ab4", 0.75),
    35: ("Via1", "#293b50", 1.0),
    36: ("Metal2", "#427f9e", 0.75),
    38: ("Via2", "#233c4a", 1.0),
    42: ("Metal3", "#7c678f", 0.85),
}
fig, ax = plt.subplots(figsize=(13, 5.5), facecolor="#fafbf8")
ax.set_facecolor("#fafbf8")
for layer in sorted(layout.layer_indexes(), key=lambda i: layout.get_info(i).layer):
    info = layout.get_info(layer)
    if info.datatype != 0 or info.layer not in styles:
        continue
    name, color, alpha = styles[info.layer]
    iterator = top.begin_shapes_rec(layer)
    while not iterator.at_end():
        shape = iterator.shape()
        if shape.is_box() or shape.is_polygon() or shape.is_path():
            polygon = shape.polygon.transformed(iterator.trans())
            xy = [(point.x * dbu, point.y * dbu) for point in polygon.each_point_hull()]
            ax.add_patch(Polygon(xy, facecolor=color, edgecolor=color, linewidth=0.3, alpha=alpha))
        iterator.next()
for name, x, w, l in (("MREF", 10, 10, 2), ("MOUT", 25, 10, 2), ("MPASS", 40, 2, 1),
                      ("MCLAMP", 55, 2, 1), ("MINV_N", 70, 2, 1), ("MINV_P", 85, 4, 1)):
    ax.text(x, 29, f"{name}\nW/L = {w}/{l} µm", ha="center", va="bottom", fontsize=10, color="#293840")
for name, y in (("VSS", 0), ("bias", 2), ("gate", 4), ("pwm", 6), ("pwm_b", 8), ("led_k", 10), ("vlogic", 12)):
    ax.text(-1.2, y, name, ha="right", va="center", fontsize=9, color="#293840")
ax.set(xlim=(-8, 99), ylim=(-3, 36), xlabel="x (µm)", ylabel="y (µm)")
ax.set_aspect("equal")
ax.spines[["top", "right"]].set_visible(False)
ax.tick_params(colors="#657179")
ax.set_title("One-pixel 6-MOS analog cell — actual GF180MCU GDS polygons", loc="left", fontsize=15, pad=14, color="#253945")
legend_layers = (22, 30, 34, 36, 42)
ax.legend(handles=[Patch(facecolor=styles[i][1], label=styles[i][0]) for i in legend_layers],
          loc="lower center", bbox_to_anchor=(0.5, -0.3), ncol=5, frameon=False, fontsize=9)
fig.tight_layout()
args.output.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(args.output, dpi=180, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.2)
plt.close(fig)
