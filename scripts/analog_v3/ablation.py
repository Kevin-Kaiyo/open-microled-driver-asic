"""Diagnostic ONLY: remove selected extracted parasitics, never fabricate result."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,re,shutil,subprocess,tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[2];E=ROOT/'evidence/analog-v3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 old=json.loads((E/'pex-r4-cc3/summary.json').read_text());base=ROOT/old['raw_directory'];w=Path(tempfile.mkdtemp(prefix='ablation-',dir=ROOT/'build/analog-v3'))
 dut=(base/'inputs/dut.spice').read_text();deck=(base/'startup_tt_100/testbench.spice').read_text();deck=deck.replace('tran 10n 40000n 0 2n','tran 1n 2u 0 .2n')
 # Keep original DC and all MOS junction/intrinsic models. Only listed physical RC removed.
 tests={'baseline':lambda x:False,'without_extracted_C':lambda x:x[0][0]=='C','without_LED_K_C':lambda x:x[0][0]=='C' and 'LED_K' in x[1:3], 'without_REFOUT_LED_K':lambda x:x[0][0]=='C' and set(x[1:3])=={'REFOUT','LED_K'},'without_REFOUT_C':lambda x:x[0][0]=='C' and 'REFOUT' in x[1:3], 'without_VREF_C':lambda x:x[0][0]=='C' and 'VREF' in x[1:3], 'without_FAULT_HB_C':lambda x:x[0][0]=='C' and 'FAULT_HB' in x[1:3], 'without_PG_C':lambda x:x[0][0]=='C' and any(n in ['VREF','VSAFE','VBUF','VSS','LED_A'] for n in x[1:3]), 'without_LED_K_and_FAULT_HB_C':lambda x:x[0][0]=='C' and any(n in ['LED_K','FAULT_HB'] for n in x[1:3]),'near_zero_R':lambda x:False}
 def run(item):
  name,pred=item;p=w/name;p.mkdir();removed=[];lines=[]
  for line in dut.splitlines():
   x=line.split()
   if x and pred(x):removed.append(line);continue
   if x and name=='near_zero_R' and x[0].startswith('R'):line=' '.join(x[:3]+['1u']);removed.append('REDUCED '+line)
   lines.append(line)
  (p/'dut.spice').write_text('\n'.join(lines)+'\n');d=deck.replace(str(base/'inputs/dut.spice'),str(p/'dut.spice'));(p/'testbench.spice').write_text(d)
  r=subprocess.run(['ngspice','-b','testbench.spice'],cwd=p,text=True,capture_output=True);(p/'ngspice.log').write_text(r.stdout+r.stderr)
  if r.returncode or 'Timestep too small' in r.stderr:return dict(name=name,completed=False,log=str(p/'ngspice.log'))
  a=np.loadtxt(p/'waveform.dat',skiprows=1);i=a[:,1];k=np.argmax(abs(i));return dict(name=name,completed=True,removed_count=len(removed),removed=removed,peak_a=float(np.abs(i).max()),peak_time_s=float(a[k,0]),ledk_peak_voltage_v=float(a[k,2]),bias_peak_voltage_v=float(a[k,3]),raw_directory=str(p.relative_to(ROOT)))
 with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(run,tests.items()))
 s=dict(schema_version=1,source_dut_sha256=sha(base/'inputs/dut.spice'),raw_directory=str(w.relative_to(ROOT)),status='diagnostic_nonphysical_ablation_not_qualification',results=rows,limitation='Each ablation circuit deletes or nearly shorts real extracted elements; only baseline is actual full extracted network. Nonlinear charge terms and source impedances interact, differences cannot be summed as independent contributions.')
 (w/'summary.json').write_text(json.dumps(s,indent=2)+'\n');shutil.copyfile(w/'summary.json',E/'pex-r4-ablation.json');print(json.dumps(s,indent=2))
if __name__=='__main__':main()
