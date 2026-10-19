"""Actual GDS polygons with true coordinates; no simulated 3-D materials."""
from pathlib import Path
import json,hashlib,sys
import klayout.db as k
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Patch
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/(sys.argv[2] if len(sys.argv)>2 else 'evidence/layout-v3');OUT.mkdir(exist_ok=True)
gds=ROOT/(sys.argv[1] if len(sys.argv)>1 else 'build/layout-v3/r5')/'generate/startup_test_macro.gds';contract=json.loads((ROOT/'layout/startup_v3/contract.json').read_text())
l=k.Layout();l.read(str(gds));c=l.cell('startup_test_macro');dbu=l.dbu
styles={21:('N-well','#dae6ee',.7),204:('P-well','#d8eadd',.7),22:('Active','#95b5a1',.9),30:('Poly gate','#c16c45',.9),33:('Contact','#30383d',1),34:('Metal1','#738ab4',.8),35:('Via1','#293b50',1),36:('Metal2','#427f9e',.8),38:('Via2','#233c4a',1),42:('Metal3','#7c678f',.85)}
polys=[]
for idx in l.layer_indexes():
 info=l.get_info(idx)
 if info.datatype or info.layer not in styles:continue
 it=c.begin_shapes_rec(idx)
 while not it.at_end():
  s=it.shape()
  if s.is_box() or s.is_polygon() or s.is_path():
   p=s.polygon.transformed(it.trans());pts=[[round(q.x*dbu,4),round(q.y*dbu,4)] for q in p.each_point_hull()];polys.append(dict(layer=info.layer,points=pts))
  it.next()
bbox=[v*dbu for v in [c.bbox().left,c.bbox().bottom,c.bbox().right,c.bbox().top]]
geometry=dict(top=c.name,gds_sha256=hashlib.sha256(gds.read_bytes()).hexdigest(),dbu_um=dbu,bbox_um=bbox,polygons=polys,layers={i:dict(name=v[0],color=v[1]) for i,v in styles.items()},ports={n:dict(layer=42,xy_um=[contract.get('port_anchor_um',{}).get(n,1.5),contract['buses_um'][n]]) for n in contract['ports']},notice='Actual 2D GDS polygons only; no pad ring, packaging, material field or thermal simulation')
(OUT/'geometry.json').write_text(json.dumps(geometry,separators=(',',':'))+'\n')
plt.rcParams['font.family']=['Avenir Next','Arial','sans-serif'];plt.rcParams['svg.fonttype']='none'
views=[('overview',(-28,680),(-6,213),'39-MOS external-passive test macro / actual GDS'),('reference-detail',(-2,222),(82,207),'Reference servo: actual device geometry and routing'),('isolation-detail',(222,330),(82,163),'Transmission-gate reference isolation / actual GDS'),('fault-buffer-detail',(316,659),(86,112),'Fault logic, LED clamp, pixel inverter and official buffer'),('welltap-detail',(638.5,647),(98.5,106),'Official buf_2 and adjacent filltie: repaired PMOS well connection')]
for name,xlim,ylim,title in views:
 fig,ax=plt.subplots(figsize=(16,7 if name=='overview' else 6),facecolor='#fafbf8');ax.set_facecolor('#fafbf8')
 for p in polys:
  xs=[q[0]for q in p['points']];ys=[q[1]for q in p['points']]
  if max(xs)<xlim[0]or min(xs)>xlim[1]or max(ys)<ylim[0]or min(ys)>ylim[1]:continue
  label,color,alpha=styles[p['layer']];ax.add_patch(Polygon(p['points'],facecolor=color,edgecolor=color,linewidth=.15,alpha=alpha))
 if name=='overview':
  for label,a,b in [('Reference servo / 10 MOS',0,222),('TG / 5 MOS',222,312),('Fault gate / 10 MOS',312,492),('LED clamp',492,528),('Pixel / 6 MOS',528,636),('Buf + tap',636,648)]:ax.plot([a,b],[203,203],color='#1b5664',lw=1);ax.text((a+b)/2,206,label,ha='center',va='bottom',fontsize=8,rotation=0)
  for n,y in contract['buses_um'].items():
   if n in contract.get('port_anchor_um',{}):
    x=contract['port_anchor_um'][n];ax.plot(x,y,'o',ms=2,color='#913a24');ax.text(x,y+1.4,n,ha='center',va='bottom',fontsize=5,color='#293840')
 elif name=='welltap-detail':
  ax.annotate('filltie: well / substrate contacts',(645.1,103.9),xytext=(640,105.1),arrowprops=dict(arrowstyle='->',color='#263f47'),fontsize=10)
  ax.annotate('VBUF rail / PMOS bulk',(644.8,103.92),xytext=(640,104.6),arrowprops=dict(arrowstyle='->',color='#263f47'),fontsize=10)
  ax.text(642.1,98.8,'buf_2 / 6 MOS',ha='center',fontsize=10);ax.text(645.05,98.8,'filltie',ha='center',fontsize=10)
 else:
  for d in contract['devices']:
   if xlim[0]<d['cx']<xlim[1]:ax.text(d['cx'],min(ylim[1]-2,d['cy']+d['w']/2+4),f"{d['name']}\n{d['w']:g}/{d['l']:g}",ha='center',va='bottom',fontsize=7,rotation=0)
 ax.set(xlim=xlim,ylim=ylim,xlabel='x (µm)',ylabel='y (µm)');ax.set_aspect('equal');ax.spines[['top','right']].set_visible(False);ax.set_title(title,loc='left',fontsize=14,pad=12,color='#253945')
 ax.legend(handles=[Patch(facecolor=styles[i][1],label=styles[i][0])for i in [21,22,30,34,36,42]],loc='lower center',bbox_to_anchor=(.5,-.32 if name=='fault-buffer-detail' else -.22),ncol=6,frameon=False,fontsize=9)
 fig.savefig(OUT/(name+'.png'),dpi=190,bbox_inches='tight',pad_inches=.3);fig.savefig(OUT/(name+'.svg'),bbox_inches='tight',pad_inches=.3);plt.close(fig)
print(json.dumps(dict(bbox_um=bbox,area_um2=(bbox[2]-bbox[0])*(bbox[3]-bbox[1]),polygons=len(polys),views=len(views))))
