"""Small external REFOUT bleed feasibility control; geometry unchanged."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,re,shutil,subprocess,tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[2];E=ROOT/'evidence/analog-v3'
def main():
 parent=json.loads((E/'pex-r5-cc30/summary.json').read_text());base=ROOT/parent['raw_directory'];w=Path(tempfile.mkdtemp(prefix='bleed-',dir=ROOT/'build/analog-v3'));cases=[]
 for val in [None,10e6,100e6]:
  for kind in ['dc','startup']:cases.append((val,kind))
 def run(item):
  val,kind=item;name=f'{kind}_{"none" if val is None else int(val)}';p=w/name;p.mkdir();template=base/('dc_tt_1' if kind=='dc' else 'startup_tt_100')/'testbench.spice';deck=template.read_text()
  if val is not None:deck=deck.replace('.control',f'RBLEED refout 0 {val}\n.control')
  deck=re.sub(r'(?m)^(wrdata .*?)$',r'\1 v(xdut.refout.t2) v(xdut.vref.t0)',deck)
  (p/'testbench.spice').write_text(deck);r=subprocess.run(['ngspice','-b','testbench.spice'],cwd=p,text=True,capture_output=True);(p/'ngspice.log').write_text(r.stdout+r.stderr)
  row=dict(name=name,bleed_ohm=val,kind=kind)
  if r.returncode or re.search(r'(?im)^Error:|Timestep too small',r.stdout+r.stderr):row['completed']=False;row['log']=str(p/'ngspice.log');return row
  d=np.atleast_2d(np.loadtxt(p/('op.dat' if kind=='dc' else 'waveform.dat'),skiprows=1));row['completed']=True
  if kind=='dc':row.update(led_current_a=float(d[0,1]),refout_v=float(d[0,4]),relative_nominal_error_pct=100*(float(d[0,1])/100e-6-1),bleed_dc_a=0 if val is None else float(d[0,4])/val)
  else:
   t=d[:,0];m=t<20e-6;bias=d[:,25]-d[:,26];row.update(startup_peak_a=float(np.abs(d[m,1]).max()),pout_source_above_bulk_max_v=float(bias.max()),initial_pout_source_above_bulk_v=float(bias[0]),pout_ibs_max_abs_a=float(np.abs(d[:,24]).max()),recovered_current_a=float(np.mean(d[t>35e-6,1])));np.savetxt(p/'waveform.csv',d,delimiter=',',header='time,'+','.join(f'v{k}' for k in range(1,d.shape[1])),comments='')
  return row
 with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(run,cases))
 s=dict(schema_version=1,raw_directory=str(w.relative_to(ROOT)),source_dut_sha256=parent['dut_sha256'],cc_pf=30,csense_pf=0,results=rows,status='external_resistor_feasibility_control_not_final_qualification',limitations=['Only TT27C/3.3V/5V 100ns startup and nominal DC. No resistor tolerance, physical body leakage, package capacitance or full rerun implied.','Bleed resistor is an external new candidate and not present in currently frozen39MOS evidence. Keep baseline failure and current-level tradeoff explicit.'])
 (w/'summary.json').write_text(json.dumps(s,indent=2)+'\n');shutil.copyfile(w/'summary.json',E/'bleed-control.json');print(json.dumps(s,indent=2))
if __name__=='__main__':main()
