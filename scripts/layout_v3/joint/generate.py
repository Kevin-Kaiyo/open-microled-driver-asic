"""Common top: actual v3 PWM/recovery logic and 39-MOS analog macro."""
from pathlib import Path
import json,re,hashlib
import klayout.db as k
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'build/layout-v3/joint-r2';OUT.mkdir(parents=True,exist_ok=True);SRC=ROOT/'layout/startup_v3/joint';SRC.mkdir(exist_ok=True)
sources=['build/layout-v3/r5/generate/startup_test_macro.gds','build/control-v3/physical/final/gds/pixel_control_v3.gds'];l=k.Layout();l.dbu=.001
for p in sources:l.read(str(ROOT/p))
c=l.create_cell('startup_integrated_v3');c.insert(k.CellInstArray(l.cell('startup_test_macro').cell_index(),k.Trans(0,False,25000,25000)));c.insert(k.CellInstArray(l.cell('pixel_control_v3').cell_index(),k.Trans(1,False,950000,25000)))
layers={'Metal2':36,'Via2':38,'Metal3':42,'Via3':40,'Metal4':46,'Via4':41,'Metal5':81};routes=[]
def rect(n,layer,x1,y1,x2,y2):c.shapes(l.layer(layers[layer],0)).insert(k.DBox(x1,y1,x2,y2));routes.append(dict(net=n,layer=layer,rect_um=[x1,y1,x2,y2]))
def wire(n,layer,pts,w):
 for (x,y),(a,b) in zip(pts,pts[1:]):assert x==a or y==b;rect(n,layer,min(x,a)-w/2,min(y,b)-w/2,max(x,a)+w/2,max(y,b)+w/2)
def via(n,lo,hi,cut,x,y,power=False):
 if power:
  for layer in [lo,hi]:rect(n,layer,x-.55,y-.55,x+.55,y+.55)
  for a in [-.26,.26]:
   for b in [-.26,.26]:rect(n,cut,x+a-.13,y+b-.13,x+a+.13,y+b+.13)
 else:
  for layer in [lo,hi]:rect(n,layer,x-.3,y-.3,x+.3,y+.3)
  d=.13;rect(n,cut,x-d,y-d,x+d,y+d)
contract=json.loads((ROOT/'layout/startup_v3/contract.json').read_text());pins={}
for n in contract['ports']:
 x=contract['port_anchor_um'][n]+25;y=contract['buses_um'][n]+25;pins[n]=dict(layer='Metal3',rect_um=[x-.2,y-.2,x+.2,y+.2])
lef=(ROOT/'build/control-v3/physical/final/lef/pixel_control_v3.lef').read_text();digital={}
for n,body in re.findall(r'  PIN (\S+)\n(.*?)  END \1',lef,re.S):
 layer,coords=re.search(r'LAYER (\w+) ;\s*RECT ([\d. -]+) ;',body).groups();a,b,x,y=map(float,coords.split());digital[n]=dict(layer=layer,rect_um=[950-y,25+a,950-b,25+x])
for net,dig,corridor in [('RAW_PWM','raw_pwm',700),('FAULT','fault',710),('PERMIT','permit',720)]:
 r=pins[net]['rect_um'];sx=(r[0]+r[2])/2;sy=(r[1]+r[3])/2;r=digital[dig]['rect_um'];dx=(r[0]+r[2])/2;dy=(r[1]+r[3])/2
 wire(net,'Metal3',[(sx,sy),(corridor,sy)],.56);via(net,'Metal3','Metal4','Via3',corridor,sy);wire(net,'Metal4',[(corridor,sy),(corridor,dy)],.56);via(net,'Metal3','Metal4','Via3',corridor,dy);wire(net,'Metal3',[(corridor,dy),(dx,dy)],.56);via(net,'Metal2','Metal3','Via2',dx,dy)
# Explicit common valid logic supply: VSAFE, VBUF and digital VDD are VLOGIC.
for net,physical,yrail in [('VLOGIC','VSAFE',48.04),('VLOGIC','VBUF',48.04),('VSS','VSS',51.34)]:
 r=pins[physical]['rect_um'];x=(r[0]+r[2])/2;y=(r[1]+r[3])/2;via(net,'Metal3','Metal4','Via3',x,y,True);wire(net,'Metal4',[(x,y),(x,yrail)],1.1);via(net,'Metal4','Metal5','Via4',x,yrail,True);wire(net,'Metal5',[(x,yrail),(770,yrail)],1.1)
for net,y in [('VLOGIC',48.04),('VSS',51.34)]:via(net,'Metal4','Metal5','Via4',770,y,True)
ports={n:p for n,p in pins.items()if n not in ['VSAFE','VBUF']};ports['VLOGIC']=dict(layer='Metal5',rect_um=[760,47.49,762,48.59])
for n,p in digital.items():
 if n not in ['VDD','VSS','fault','raw_pwm','permit']:ports[n]=p
for n,p in ports.items():
 r=p['rect_um'];c.shapes(l.layer(layers[p['layer']],10)).insert(k.DText(n,k.DTrans((r[0]+r[2])/2,(r[1]+r[3])/2)))
l.write(str(OUT/'startup_integrated_v3.gds'))
manifest=dict(top=c.name,placements=dict(analog=dict(origin_um=[25,25],rotation=0),digital=dict(origin_um=[950,25],rotation=90)),ports=ports,routes=routes,inputs_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()for p in sources},notice='External-passive mixed-signal test core; no pads, ESD, POR, package or external regulator. VSAFE/VBUF/digital VDD share VLOGIC; VREF remains independent.')
(OUT/'routing.json').write_text(json.dumps(manifest,indent=2)+'\n')
tcl=['gds read $env(V3_JOINT_GDS)','load startup_integrated_v3','select top cell']
for n,p in ports.items():tcl+=['box values '+' '.join(f'{v:.4f}um'for v in p['rect_um']),f'label {{{n}}} center {p["layer"].lower()}','port make']
tcl+=['drc style drc(full)','drc style','drc check','drc catchup','puts "JOINT_DRC_COUNT [drc list count total]"','puts "JOINT_DRC_ERRORS [drc listall why]"','save startup_integrated_v3','extract all','ext2spice lvs','ext2spice','quit -noprompt'];(OUT/'extract.tcl').write_text('\n'.join(tcl)+'\n')
# Logical reference independently instantiates the frozen macro and synthesized PNL.
analog=' '.join(f'.{n}({"VLOGIC" if n in ["VSAFE","VBUF"] else n})'for n in contract['ports'])
ports_decl='inout '+', '.join(n for n in ports if '['not in n and n not in ['clk','rst','enable','recover_request','protected_monitor'])+', input clk, rst, enable, recover_request, input [8:0] duty, output protected_monitor'
body='module startup_integrated_v3('+ports_decl+');\npixel_control_v3 digital (.clk(clk),.rst(rst),.enable(enable),.duty(duty),.fault(FAULT),.recover_request(recover_request),.raw_pwm(RAW_PWM),.permit(PERMIT),.protected_monitor(protected_monitor),.VDD(VLOGIC),.VSS(VSS));\nstartup_test_macro analog ('+analog.replace(' ', ', ')+');\nendmodule\n';(SRC/'startup_integrated_v3.v').write_text(body)
print(OUT)
