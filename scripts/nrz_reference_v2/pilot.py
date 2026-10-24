#!/usr/bin/env python3
"""Bounded DC-only coupled pilot; no claim of layout or transient closure."""
from pathlib import Path
import datetime,fcntl,gzip,hashlib,json,shutil,subprocess,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2];WORK=ROOT/'build/nrz-reference-v2/pilot-r1';EVID=ROOT/'evidence/nrz-reference-v2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def emit(p,j):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(j,indent=2)+'\n')
def main():
 assert not WORK.exists(),'immutable pilot destination exists'
 assert shutil.disk_usage(ROOT).free>=5*1024**3
 inp=WORK/'inputs';inp.mkdir(parents=True)
 old=ROOT/'build/highspeed-nrz-robustness/selected-a8-b58-r4/inputs'
 files={'design.ngspice':old/'pdk/design.ngspice','sm141064.ngspice':old/'pdk/sm141064.ngspice','led.spice':old/'led.spice','core.spice':old/'physical/B-AFTER.spice','power.spice':ROOT/'analog/nrz_reference_v2/bias_power_pilot.spice','pilot.py':Path(__file__)}
 for n,p in files.items():shutil.copy2(p,inp/n)
 conditions=[('TT','typical',27,3.3),('SS','ss',125,2.95),('FF','ff',-40,3.65)]
 plans=[dict(label=l,corner=c,temp_C=t,vdd_V=v,bit=b) for l,c,t,v in conditions for b in [0,1]]
 emit(WORK/'plan.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':plans,'input_sha256':{n:sha(inp/n) for n in files},'geometry':'OldcoretruefullRC plusnewpower prelayoutwithassumed .44umdiffusion','anchor':'Externalideal2.5V plus.2ohm,200k/50kdivider; deterministicfiniteanchorstresslater','acceptance':'Pilot diagnose25uAservo,3.3VLDO,DCthresholdfeasibility; nofrozenRXtransientclaim'})
 rows=[]
 for c in plans:
  folder=WORK/(c['label']+str(c['bit']));folder.mkdir()
  expr=['v(vreg)','v(vset)','v(sense)','v(bias)','v(dummy)','v(out)','v(fb)','i(VMON)','i(VLED)','i(VRAW)','i(VREF)','i(VDD)','v(ipb)','v(in2)','v(ictrl)','v(lpb)','v(ln2)','v(lctrl)']
  deck=f'''NRZ reference V2 coupled prelayout DC pilot
.include "{inp/'design.ngspice'}"
.param sw_stat_global=0 sw_stat_mismatch=0
.lib "{inp/'sm141064.ngspice'}" {c['corner']}
.lib "{inp/'sm141064.ngspice'}" res_{c['corner']}
.temp {c['temp_C']}
.include "{inp/'core.spice'}"
.include "{inp/'power.spice'}"
.include "{inp/'led.spice'}"
VRAW vin 0 5
VREF refsrc 0 2.5
RREFOUT refsrc vref .2
RDIVH vref vset 200k
RDIVL vset 0 50k
VDD vdd 0 {c['vdd_V']}
VDATA data 0 {c['bit']*c['vdd_V']}
VLED led_a 0 5
XCORE data out vdd 0 bias dummy hs_steering_robust
XPOWER vin 0 vset sense bias fb vreg ipb in2 ictrl lpb ln2 lctrl nrz_bias_power
RIBIAS ipb 0 100k
RLBIAS lpb 0 100k
CICOMP in2 ictrl 3p
CLCOMP ln2 lctrl 3p
RSET sense mon 20k
VMON mon 0 0
RFBH vreg fb 56k
RFBL fb 0 10k
RCAP vreg cap .2
COUT cap 0 10n
RDUMMY vreg dummy 28k
XLED led_a led_dc_k lin2026_yellow20_dc
VSENSE led_dc_k led_k 0
CLED led_a led_k 200f
RPKG led_k pkg 1
LPKG pkg out .5n
.options reltol=1e-6 abstol=1e-13 vntol=1e-8 method=gear
.control
set numdgt=15
set wr_singlescale
set wr_vecnames
op
wrdata waveform.dat {' '.join(expr)}
quit
.endc
.end
'''
  (folder/'testbench.spice').write_text(deck)
  with open('/tmp/open-microled-nrz-ngspice.lock','a') as lock,(folder/'ngspice.log').open('w') as log:
   fcntl.flock(lock,fcntl.LOCK_EX)
   p=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,stdout=log,stderr=subprocess.STDOUT,timeout=30)
  row={'case':c,'exit_code':p.returncode,'deck_sha256':sha(folder/'testbench.spice'),'log_sha256':sha(folder/'ngspice.log'),'simulation_ok':False}
  raw=folder/'waveform.dat'
  if p.returncode==0 and raw.exists():
   a=np.atleast_2d(np.loadtxt(raw,skiprows=1));assert a.shape[1]==len(expr)+1 and np.isfinite(a).all()
   row.update(simulation_ok=True,values=dict(zip(expr,a[-1,1:])))
  if raw.exists():
   orig=sha(raw);gz=raw.with_suffix('.dat.gz')
   with raw.open('rb') as fi,gzip.open(gz,'wb',compresslevel=6) as fo:shutil.copyfileobj(fi,fo)
   assert hashlib.sha256(gzip.open(gz,'rb').read()).hexdigest()==orig
   row.update(waveform_sha256=sha(gz),uncompressed_sha256=orig,roundtrip_verified=True);raw.unlink()
  emit(folder/'result.json',row);rows.append(row);print(json.dumps(row),flush=True)
 emit(EVID/'pilot-r1.json',{'work':str(WORK.relative_to(ROOT)),'rows':rows,'source_sha256':sha(__file__)})
if __name__=='__main__':main()
