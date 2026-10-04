"""Plot actual GDS geometry and frozen-macro origins, with new physical routes."""
from pathlib import Path
import argparse,json
import klayout.db as k
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Rectangle
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--run',default='r3');a=p.parse_args();folder=ROOT/'build/integration'/a.run
l=k.Layout();l.read(str(folder/'pixel_integrated.gds'));c=l.cell('pixel_integrated');j=json.loads((folder/'routing.json').read_text())
plt.rcParams['font.family']='Avenir Next'
fig,ax=plt.subplots(figsize=(11,7),dpi=180);fig.patch.set_facecolor('#fcfdfc');ax.set_facecolor('#fcfdfc')
for level,color,alpha in [(21,'#e5eadf',.7),(22,'#dbe9dd',.7),(30,'#cae1dd',.3),(34,'#b3b5b7',.5),(36,'#aec9c6',.5),(42,'#00968f',.8),(46,'#c58a41',.8),(81,'#244f76',.8)]:
 polygons=[];reg=k.Region(c.begin_shapes_rec(l.layer(level,0)))
 for s in reg.each():polygons.append([(pt.x*l.dbu,pt.y*l.dbu)for pt in s.each_point_hull()])
 if polygons:ax.add_collection(PolyCollection(polygons,facecolor=color,edgecolor='none',alpha=alpha))
for name,(x,y)in j['placements_origin_um'].items():
 b=l.cell(name).bbox();bb=[b.left*l.dbu+x,b.bottom*l.dbu+y,b.right*l.dbu+x,b.top*l.dbu+y]
 ax.add_patch(Rectangle((bb[0],bb[1]),bb[2]-bb[0],bb[3]-bb[1],fill=False,edgecolor='#77838c',lw=.8,linestyle='--'))
 ax.text((bb[0]+bb[2])/2,bb[3]+5,'Analog: 6 MOS'if name=='pixel_driver_layout'else'Digital: registered PWM',ha='center',va='bottom',size=11,color='#29435a')
ax.annotate('PWM / Metal3\n30 µm × 0.56 µm',xy=(130,111.52),xytext=(104,72),arrowprops=dict(arrowstyle='-',color='#008c86'),ha='center',size=10,color='#008c86')
ax.annotate('VDD / Metal4',xy=(140,88),xytext=(110,52),arrowprops=dict(arrowstyle='-',color='#b37a31'),ha='center',size=10,color='#a87029')
ax.annotate('VSS / Metal5',xy=(135,98),xytext=(74,89),arrowprops=dict(arrowstyle='-',color='#244f76'),ha='center',size=10,color='#244f76')
ax.text(25,162,'95 × 37.66 µm\n20/4 µm mirror',size=10,color='#3f545d')
ax.text(260,15,'180 × 180 µm',size=10,ha='center',color='#3f545d')
ax.set_xlim(10,344);ax.set_ylim(8,222);ax.set_aspect('equal');ax.set_xlabel('x (µm)');ax.set_ylabel('y (µm)');ax.set_title('One-pixel common physical top — actual GDS',loc='left',size=16,color='#223d53',pad=20)
for sp in ['top','right']:ax.spines[sp].set_visible(False)
fig.text(.12,.02,'305 × 180 µm macro-span bounding box • 19 bare ports • no pads / ESD / package',size=10,color='#52656d')
fig.tight_layout(rect=[0,.05,1,1]);dest=ROOT/'evidence/integration/layout.png';fig.savefig(dest);plt.close(fig);print(dest)
