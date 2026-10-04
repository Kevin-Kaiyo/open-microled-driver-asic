"""Render the actual joint GDS and top-route geometry for the teaching report."""
from pathlib import Path
import argparse
import hashlib
import json
import klayout.db as k
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--gds', type=Path, required=True)
parser.add_argument('--routing', type=Path, required=True)
parser.add_argument('--output', type=Path, default=ROOT/'docs/research/figures/integrated-top.png')
args = parser.parse_args()
layout = k.Layout()
layout.read(str(args.gds))
top = layout.cell('pixel_integrated')
routing = json.loads(args.routing.read_text())
plt.rcParams.update({'font.family': ['Avenir Next', 'PingFang SC'], 'font.size': 10})
fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.5), gridspec_kw={'width_ratios': [1.3, 1]}, facecolor='white')
styles = {22: '#dbe6e4', 30: '#a69a8e', 34: '#d7dfe7', 36: '#92afbc',
          42: '#857994', 46: '#6b9da8', 81: '#758ab6'}
for ax in axes:
    for layer in layout.layer_indexes():
        info = layout.get_info(layer)
        if info.datatype != 0 or info.layer not in styles:
            continue
        iterator = top.begin_shapes_rec(layer)
        while not iterator.at_end():
            shape = iterator.shape()
            if shape.is_box() or shape.is_polygon() or shape.is_path():
                polygon = shape.polygon.transformed(iterator.trans())
                points = [(p.x*layout.dbu, p.y*layout.dbu) for p in polygon.each_point_hull()]
                ax.add_patch(Polygon(points, facecolor=styles[info.layer], edgecolor='none', alpha=.65))
            iterator.next()
    for route in routing['routes']:
        x0, y0, x1, y1 = route['rect_um']
        color = {'pwm_link': '#7a457b', 'VDD': '#246e76', 'VSS': '#416190'}.get(route['net'], '#9aa9b2')
        ax.add_patch(Rectangle((x0, y0), x1-x0, y1-y0, color=color, alpha=.95))
    ax.set_aspect('equal')
    ax.spines[['top', 'right']].set_visible(False)
    ax.set_xlabel('x (µm)')
    ax.set_ylabel('y (µm)')
axes[0].set(xlim=(15, 340), ylim=(15, 218), title='Actual joint GDS: 305 × 180 µm bbox')
axes[0].text(73, 152, '6-MOS analog\n20/4 µm mirror', ha='center', color='#254d5a')
axes[0].text(240, 210, 'Registered PWM macro', ha='center', color='#254d5a')
axes[0].annotate('PWM Metal3', xy=(135, 111.52), xytext=(83, 63),
                 arrowprops={'arrowstyle': '->', 'color': '#7a457b'}, color='#7a457b')
axes[1].set(xlim=(114, 157), ylim=(92, 126), title='Actual cross-macro routing detail')
for text, point, label, color in [
    ('PWM / M3', (127, 111.52), (116, 122), '#7a457b'),
    ('VDD / M4', (140, 114), (148, 121), '#246e76'),
    ('VSS / M5', (135, 99), (117, 94), '#416190')]:
    axes[1].annotate(text, xy=point, xytext=label, color=color,
                     arrowprops={'arrowstyle': '->', 'color': color}, fontsize=9)
fig.suptitle('One pixel: frozen macros + new PWM and power routes', x=.06, ha='left', color='#173f4c', fontsize=15)
fig.text(.06, .01, 'Derived directly from published GDS polygons. No pads / ESD / package; bbox is not a die specification.', color='#56717b', fontsize=9)
fig.tight_layout(rect=(0, .08, 1, .93))
args.output.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(args.output, dpi=180, bbox_inches='tight', facecolor='white')
plt.close(fig)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
record = {'evidence_class': 'Original rendering of actual generated geometry',
          'source_sha256': {str(p.resolve().relative_to(ROOT)): sha(p) for p in [args.gds, args.routing, Path(__file__)]},
          'output': str(args.output.resolve().relative_to(ROOT)), 'output_sha256': sha(args.output)}
(ROOT/'evidence/research/integration-figure.json').write_text(json.dumps(record, indent=2)+'\n')
print(args.output)
