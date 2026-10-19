"""New r5 external-bleed candidate transient supply/load/setpoint probes."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,re,subprocess,tempfile,shutil
import numpy as np
ROOT=Path(__file__).resolve().parents[2];E=ROOT/'evidence/analog-v3'
def main():
 s=json.loads((E/'pex-r5-bleed10M-fftrial/summary.json').read_text());base=ROOT/s['raw_directory'];w=Path(tempfile.mkdtemp(prefix='disturbance-bleed-',dir=ROOT/'build/analog-v3'));original=(base/'dc_tt_1/testbench.spice').read_text()
 cases=[('ref_step','VREFRAIL','refrail',3.3,2.97),('led_step','VLED','rail',5,4.5),('setpoint_step','VSET','vset',.5,.505)]
 def run(c):
  name,src,node,before,after=c;p=w/name;p.mkdir();d=re.sub(r'(?m)^'+src+r' .*$',f'{src} {node} 0 PWL(0 {before} 10u {before} 10.1u {after} 25u {after} 25.1u {before} 50u {before})',original);d=d.replace('\nop\n','\ntran 1n 50u 0 2n\n').replace('wrdata op.dat','wrdata waveform.dat');(p/'testbench.spice').write_text(d);r=subprocess.run(['ngspice','-b','testbench.spice'],cwd=p,text=True,capture_output=True);(p/'ngspice.log').write_text(r.stdout+r.stderr)
  if r.returncode or re.search(r'(?im)^Error:|Timestep too small',r.stdout+r.stderr):return dict(name=name,completed=False,log=str(p/'ngspice.log'))
  a=np.loadtxt(p/'waveform.dat',skiprows=1);t=a[:,0];i=a[:,1];final=float(np.mean(i[t>45e-6]));k=np.flatnonzero((t>=25.1e-6)&(np.abs(i-final)>.005*abs(final)));settle=0 if not len(k) else float(t[k[-1]+1]-25.1e-6) if k[-1]+1<len(t) else None
  result=dict(name=name,completed=True,conditions=dict(envelope='TT27C',logic_v=3.3,led_nominal_v=5,cc_pf=30,csense_pf=30,bleed_ohm=1e7,source=src,source_nominal=before,source_disturbed=after),current_min_a=float(i.min()),current_max_a=float(i.max()),final_current_a=final,after_restore_settle_0p5pct_s=settle,settle_5us_pass=settle is not None and settle<5e-6,last5us_pp_a=float(np.ptp(i[t>45e-6])));np.savetxt(p/'compact.csv',a,delimiter=',',header='time_s,'+','.join(f'vector{k}' for k in range(1,a.shape[1])),comments='');return result
 with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(run,cases))
 result=dict(schema_version=1,raw_directory=str(w.relative_to(ROOT)),source_dut_sha256=s['dut_sha256'],results=rows,scope='Full extracted r5 39MOS with external30pF compensation,30pF sense load,10Meg bleed. TT electrical step sensitivities only, no optical/package/thermal validation.')
 (w/'summary.json').write_text(json.dumps(result,indent=2)+'\n');shutil.copyfile(w/'summary.json',E/'disturbances-bleed.json');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
