"""Inspect actual local terminals and signed BSIM junction currents at startup OP."""
from pathlib import Path
import json,re,subprocess,tempfile,shutil,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[2];E=ROOT/'evidence/analog-v3'
def main():
 s=json.loads((E/'pex-r5-cc30/summary.json').read_text());base=ROOT/s['raw_directory'];w=Path(tempfile.mkdtemp(prefix='body-audit-',dir=ROOT/'build/analog-v3'));original=(base/'dc_tt_1/testbench.spice').read_text()
 nodes=['v(xdut.refout.t2)','v(xdut.vref.t0)','v(xdut.vref.t1)','v(xdut.ctrl.t3)','v(xdut.refout.t0)','v(xdut.vsafe.t8)','v(xdut.bias.t2)','v(xdut.fault.t6)'];curr=[f'@m.xdut.x{n}.m0[{q}]' for n in [28,20,7] for q in ['id','ibd','ibs']]
 rows=[]
 for name,ref,safe,flt,vset,gmin in [('prepowered_fault',0,3.3,3.3,.5,1e-12),('prepowered_fault_vset0',0,3.3,3.3,0,1e-12),('all_rails_zero',0,0,0,0,1e-12),('normal_powered',3.3,3.3,0,.5,1e-12),('prepowered_gmin_low',0,3.3,3.3,.5,1e-14),('prepowered_gmin_high',0,3.3,3.3,.5,1e-10)]:
  p=w/name;p.mkdir();deck=original
  for src,node,val in [('VREFRAIL','refrail',ref),('VSAFE','saferail',safe),('VBUF','bufrail',safe),('VFAULT','fault',flt),('VRAW','raw_pwm',0),('VPERMIT','permit',0),('VSET','vset',vset)]:deck=re.sub(r'(?m)^'+src+' .*$',f'{src} {node} 0 {val}',deck)
  if name=='all_rails_zero':deck=re.sub(r'(?m)^VLED .*$', 'VLED rail 0 0',deck)
  deck=deck.replace('.options ',f'.options gmin={gmin} ')
  deck=re.sub(r'(?m)^save .*$', 'save all '+' '.join(curr),deck);deck=re.sub(r'(?m)^wrdata .*$', 'wrdata op.dat '+' '.join(nodes+curr),deck)
  (p/'testbench.spice').write_text(deck);r=subprocess.run(['ngspice','-b','testbench.spice'],cwd=p,text=True,capture_output=True);(p/'ngspice.log').write_text(r.stdout+r.stderr)
  if r.returncode or 'Error:' in r.stderr:raise RuntimeError(str(p))
  d=np.loadtxt(p/'op.dat',skiprows=1);row=dict(name=name,conditions=dict(vref_v=ref,vsafe_v=safe,fault_v=flt,vset_v=vset,gmin_s=gmin),vectors=dict(zip(nodes+curr,map(float,d[1:]))));row['pout_source_above_bulk_v']=float(d[1]-d[2]);rows.append(row)
 result=dict(schema_version=1,raw_directory=str(w.relative_to(ROOT)),source_summary_sha256=hashlib.sha256((E/'pex-r5-cc30/summary.json').read_bytes()).hexdigest(),dut_sha256=s['dut_sha256'],results=rows,interpretation='Maximum +REFOUT above POUT well already exists in the t=0 DC operating point. Keeping VSET=0 leaves it unchanged; all rails=0 removes it. An unpowered VREF with prepowered isolation well permits finite model leakage to establish the floating REFOUT potential. Model diode currents are recorded; the voltage alone must not be presented as measured latch-up/substrate injection or harmlessness qualification.',limitations=['No extracted substrate resistance, parasitic bipolar, latch-up test, foundry power-sequence acceptance or body-current limit provided.','Floating-node DC may be governed in part by gmin conductance; gmin sensitivity is explicitly recorded. Signed ibd/ibs are reported by the BSIM4 compact model and include its numerical conventions; they do not constitute a measured reliability limit.'])
 (w/'summary.json').write_text(json.dumps(result,indent=2)+'\n');shutil.copyfile(w/'summary.json',E/'body-audit.json');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
