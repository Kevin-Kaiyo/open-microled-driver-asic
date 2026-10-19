"""Rasterize the full real common-top GDS polygons, retain text as SVG text."""
from pathlib import Path
import json,hashlib
import klayout.db as k
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Patch,Rectangle
from matplotlib.collections import PatchCollection
ROOT=Path(__file__).resolve().parents[3];run=ROOT/'build/layout-v3/joint-r2';out=ROOT/'evidence/layout-v3/joint-r2';out.mkdir(parents=True,exist_ok=True)
l=k.Layout();l.read(str(run/'startup_integrated_v3.gds'));c=l.cell('startup_integrated_v3');dbu=l.dbu
styles={21:('N-well','#dae6ee'),204:('P-well','#d8eadd'),22:('Active','#95b5a1'),30:('Poly gate','#c16c45'),33:('Contact','#30383d'),34:('Metal1','#738ab4'),35:('Via1','#293b50'),36:('Metal2','#427f9e'),38:('Via2','#233c4a'),42:('Metal3','#7c678f'),40:('Via3','#624e76'),46:('Metal4','#d6a244'),41:('Via4','#8b6627'),81:('Metal5','#c1637f')}
plt.rcParams['font.family']=['Avenir Next','Arial','sans-serif'];plt.rcParams['svg.fonttype']='none';fig,ax=plt.subplots(figsize=(18,6.5),facecolor='#fafbf8');ax.set_facecolor('#fafbf8');count=0
for idx in sorted(l.layer_indexes(),key=lambda i:l.get_info(i).layer):
 inf=l.get_info(idx)
 if inf.datatype or inf.layer not in styles:continue
 patches=[];it=c.begin_shapes_rec(idx)
 while not it.at_end():
  s=it.shape()
  if s.is_box()or s.is_polygon()or s.is_path():
   p=s.polygon.transformed(it.trans());patches.append(Polygon([(q.x*dbu,q.y*dbu)for q in p.each_point_hull()]));count+=1
  it.next()
 ax.add_collection(PatchCollection(patches,facecolor=styles[inf.layer][1],edgecolor='none',alpha=.88,rasterized=True))
ax.text(25,239,'Analog / 39 MOS + external passive ports',fontsize=13,color='#253945');ax.text(750,239,'PWM + recovery logic',fontsize=12,color='#253945')
for n,(x,y)in {'RAW_PWM':(702,156.32),'FAULT':(712,163.04),'PERMIT':(722,164.16)}.items():ax.annotate(n,(x,y),xytext=(695,190+9*['RAW_PWM','FAULT','PERMIT'].index(n)),fontsize=8,arrowprops=dict(arrowstyle='->',color='#33424a'))
ax.text(25,254,'Common test core / real GF180MCU GDS geometry',fontsize=17,color='#253945');ax.text(25,229,'R5 local analog routing; shared valid VLOGIC; independent VREF. No pad ring / ESD / package.',fontsize=9,color='#52636d')
ax.set(xlim=(5,970),ylim=(5,265),xlabel='x (µm)',ylabel='y (µm)');ax.set_aspect('equal');ax.spines[['top','right']].set_visible(False);ax.legend(handles=[Patch(facecolor=styles[i][1],label=styles[i][0])for i in [22,30,34,36,42,46,81]],loc='lower center',bbox_to_anchor=(.5,-.25),ncol=7,frameon=False,fontsize=10)
fig.savefig(out/'overview.png',dpi=200,bbox_inches='tight',pad_inches=.3);fig.savefig(out/'overview.svg',dpi=200,bbox_inches='tight',pad_inches=.3);plt.close(fig)
b=c.bbox();data=dict(bbox_um=[b.left*dbu,b.bottom*dbu,b.right*dbu,b.top*dbu],polygons_rendered=count,gds_sha256=hashlib.sha256((run/'startup_integrated_v3.gds').read_bytes()).hexdigest(),scope='All recognized physical layers rendered from actual GDS; no simulated materials or fields');(out/'geometry-summary.json').write_text(json.dumps(data,indent=2)+'\n');print(data)
