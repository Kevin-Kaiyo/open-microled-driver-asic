#!/usr/bin/env python3
"""Explicit nonphysical controls isolating resistor substrate return and input time constant."""
import argparse,json,shutil
import explore as e
r=e.r

def add_control(work,label,length,local=False):
 e.create(work);m=json.loads((work/'manifest.json').read_text())
 src=e.ROOT/('build/highspeed-nrz-pvt-layout/poly58-local-r3/A/full-rc/hs_voltage_pvt_rc.spice' if local else 'build/highspeed-nrz-pvt-layout/poly58-r1/A/full-rc/hs_voltage_pvt_rc.spice')
 lines=[]
 for line in src.read_text().splitlines():
  p=line.split()
  if len(p)>4 and p[4]=='ppolyf_u_1k_6p0':
   if not local:p[3]='VSS'
   line=' '.join(p).replace('r_length=58u',f'r_length={length:g}u')
  lines.append(line)
 dst=work/'inputs'/(f'A-local-poly{length:g}.spice' if local else 'A-body-direct.spice' if length==58 else f'A-body-direct-poly{length:g}.spice');txt='\n'.join(lines)+'\n'
 if dst.exists() and dst.read_text()!=txt:raise ValueError('Historical control would change')
 dst.write_text(txt)
 definition={'path':str(dst.relative_to(work/'inputs')),'sha256':r.sha(dst),'source':r.rel(src),'source_sha256':r.sha(src),'diagnostic':'Intentional ideal zero-R bulk tie on XRIN only. Length changes do not update extracted C. Not physical repair evidence.'}
 if label not in m['variants']['A']:
  m['variants']['A'][label]=definition;r.emit(work/'manifest.json',m)
 else:
  previous=m['variants']['A'][label]
  if previous['path']!=definition['path'] or previous['sha256']!=definition['sha256']:raise ValueError('Historical definition mismatch')
 script=work/'control-sources'/f'{r.sha(__file__)}.py';script.parent.mkdir(exist_ok=True);shutil.copy2(__file__,script)
 return work

def main():
 p=argparse.ArgumentParser();p.add_argument('--length',type=float,default=58);p.add_argument('--local',action='store_true');a=p.parse_args();label=f'LOCAL-P{a.length:g}' if a.local else 'BODYDIRECT' if a.length==58 else f'BODYDIRECT-P{a.length:g}';w=e.ROOT/'build/highspeed-nrz-pvt/diagnostic-controls';add_control(w,label,a.length,a.local)
 for kind,corner,temp,vdd in ([('fast_cold','ff',-40,3.6)] if a.length==58 else [('slow_hot','ss',125,3),('fast_cold','ff',-40,3.6)]):
  c=r.case_spec(w,'A',label,1,kind=kind,corner=corner,temp_C=temp,vdd_V=vdd);row=e.metrics(w,r.run_case(w,c));print(json.dumps(row),flush=True)
if __name__=='__main__':main()
