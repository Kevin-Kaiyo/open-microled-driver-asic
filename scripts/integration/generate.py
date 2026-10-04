"""Place frozen macros and physically route the one-pixel common top (GF180D)."""
from pathlib import Path
import argparse,hashlib,json,re
import klayout.db as k
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--run',default='r2');a=p.parse_args()
OUT=ROOT/'build/integration'/a.run;OUT.mkdir(parents=True,exist_ok=True)
l=k.Layout();l.dbu=.001
sources=['evidence/layout/pixel_driver_layout.gds','evidence/physical/digital/gds/pixel_pwm.gds']
for p in sources:l.read(str(ROOT/p))
top=l.create_cell('pixel_integrated')
placements={'pixel_pwm':(150.,25.),'pixel_driver_layout':(25.,105.52)}
for name,(x,y) in placements.items():top.insert(k.CellInstArray(l.cell(name).cell_index(),k.Trans(round(x/l.dbu),round(y/l.dbu))))
layers={'Metal3':42,'Via3':40,'Metal4':46,'Via4':41,'Metal5':81}
routes=[]
def rect(net,layer,a,b,c,d):
 r=[a,b,c,d];top.shapes(l.layer(layers[layer],0)).insert(k.DBox(*r));routes.append(dict(net=net,layer=layer,rect_um=r))
def wire(net,layer,points,width):
 for (a,b),(c,d) in zip(points,points[1:]):
  if a!=c and b!=d:raise ValueError('Manhattan routes only')
  rect(net,layer,min(a,c)-width/2,min(b,d)-width/2,max(a,c)+width/2,max(b,d)+width/2)
def via(net,low,high,cut,x,y):
 rect(net,low,x-.35,y-.35,x+.35,y+.35)
 rect(net,high,x-.35,y-.35,x+.35,y+.35)
 rect(net,cut,x-.13,y-.13,x+.13,y+.13)
# PWM aligns two actual Metal3 pins. Extension at digital pin is within its pin.
wire('pwm_link','Metal3',[(119.7,111.52),(150.28,111.52)],.56)
# VDD uses Metal4, VSS Metal5; crossings are deliberately insulated.
wire('VDD','Metal4',[(173.04,57.33),(140,57.33),(140,117.52),(26,117.52)],.70)
# Digital M4 VDD pin at x=173.04 already joins M5 inside the frozen macro.
# Do not duplicate its existing Via4 in the parent hierarchy.
via('VDD','Metal3','Metal4','Via3',26,117.52)
wire('VSS','Metal5',[(160,60.63),(135,60.63),(135,105.52),(26,105.52)],.70)
via('VSS','Metal3','Metal4','Via3',26,105.52)
via('VSS','Metal4','Metal5','Via4',26,105.52)
# Top signal/control ports remain at existing frozen pins; no implied pads/ESD.
ports={}
lef=(ROOT/'evidence/physical/digital/lef/pixel_pwm.lef').read_text()
for name,body in re.findall(r'  PIN (\S+)\n(.*?)  END \1',lef,re.S):
 if name in ['VDD','VSS','pwm']:continue
 layer,coords=re.search(r'LAYER (\w+) ;\s*RECT ([\d. -]+) ;',body).groups()
 r=[float(s) for s in coords.split()];ports[name]=dict(layer=layer,rect_um=[r[0]+150,r[1]+25,r[2]+150,r[3]+25])
for name,y in [('bias',2),('gate',4),('pwm_b',8),('led_k',10)]:
 ports[name]=dict(layer='Metal3',rect_um=[25,105.52+y-.3,28,105.52+y+.3])
ports['VDD']=dict(layer='Metal4',rect_um=[139.65,116.5,140.35,117.52])
ports['VSS']=dict(layer='Metal5',rect_um=[134.65,104.5,135.35,105.52])
ports['pwm_monitor']=dict(layer='Metal3',rect_um=[125,111.24,126,111.8])
# Add proper text datatype 10, then Magic annotates ordered electrical ports.
for name,p in ports.items():
 r=p['rect_um'];rect(name,p['layer'],*r)
 top.shapes(l.layer(layers[p['layer']],10)).insert(k.DText(name,k.DTrans((r[0]+r[2])/2,(r[1]+r[3])/2)))
l.write(str(OUT/'pixel_integrated.gds'))
manifest=dict(topcell=top.name,dbu_um=l.dbu,placements_origin_um=placements,placement_scope='GDS origins; analog bbox y=-.3…37.36 remains unchanged',bbox_um=[v*l.dbu for v in [top.bbox().left,top.bbox().bottom,top.bbox().right,top.bbox().top]],ports=ports,routes=routes,inputs_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['evidence/layout/pixel_driver_layout.lef','evidence/physical/digital/lef/pixel_pwm.lef']})
(OUT/'routing.json').write_text(json.dumps(manifest,indent=2)+'\n')
tcl=['gds read $env(INTEGRATION_GDS)','load pixel_integrated','select top cell']
for number,(name,p) in enumerate(ports.items(),1):
 r=p['rect_um'];tcl += ['box values '+' '.join(f'{v:.3f}um' for v in r),f'label {{{name}}} center {p["layer"].lower()}','port make']
tcl += ['drc style drc(full)','drc style','drc check','drc catchup','puts "INTEGRATION_DRC_COUNT [drc list count total]"','puts "INTEGRATION_DRC_ALL [drc listall count]"','select top cell','box sel','puts "INTEGRATION_DRC_ERRORS [drc listall why]"','save pixel_integrated','extract all','ext2spice lvs','ext2spice','quit -noprompt']
(OUT/'extract.tcl').write_text('\n'.join(tcl)+'\n')
print(OUT)
