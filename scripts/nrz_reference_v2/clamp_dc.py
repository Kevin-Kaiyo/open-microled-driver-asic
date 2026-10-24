#!/usr/bin/env python3
"""Independent ascending/descending threshold test for candidate3MOSclamp."""
from pathlib import Path
import datetime,fcntl,gzip,hashlib,json,shutil,subprocess
import numpy as np
import run as r
WORK=r.BUILD/'clamp-dc-r1'
def main():
 assert not WORK.exists();WORK.mkdir();inp=WORK/'inputs';inp.mkdir()
 old=r.BUILD/'selected-r1/inputs'
 for name,p in {'design.ngspice':old/'pdk/design.ngspice','sm141064.ngspice':old/'pdk/sm141064.ngspice','clamp.spice':r.ROOT/'analog/nrz_reference_v2/startup_clamp_candidate.spice','clamp_dc.py':Path(__file__)}.items():shutil.copy2(p,inp/name)
 cases=[dict(label=l,corner=c,temp=t,direction=d) for l,c,t in [('TT','typical',27),('SS','ss',125),('FF','ff',-40)] for d in ['up','down']]
 r.emit(WORK/'plan.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cases,'fixture':'Ideal25uAcurrent injection plusoldREF03W2L1diode; fixtureisnotimplementedreference','acceptance':'Measure threshold whenBIAScrosses0.1V and90%off-stateBIAS; up/downdifference, nodevoltages and residualclampcurrent. Noengineeredhysteresis.'})
 rows=[]
 for c in cases:
  f=WORK/(c['label']+'-'+c['direction']);f.mkdir();sweep='0 3.5 .01' if c['direction']=='up' else '3.5 0 -.01'
  deck=f'''3MOS startup clamp independent threshold
.include "{inp/'design.ngspice'}"
.param sw_stat_global=0 sw_stat_mismatch=0
.lib "{inp/'sm141064.ngspice'}" {c['corner']}
.temp {c['temp']}
.include "{inp/'clamp.spice'}"
VIN vin 0 5
VREG vreg 0 0
RUP vreg det 1meg
RDN det 0 1meg
IREF 0 bias 25u
XDI bias bias 0 0 nfet_03v3 w=2u l=1u ad=.88p as=.88p pd=4.88u ps=4.88u
XCL vin 0 bias det cpp nrz_startup_clamp
.options reltol=1e-7 abstol=1e-14 vntol=1e-9
.control
set numdgt=15
set wr_singlescale
set wr_vecnames
dc VREG {sweep}
wrdata waveform.dat v(vreg) v(bias) v(cpp) v(det) i(VIN)
quit
.endc
.end
'''
  (f/'testbench.spice').write_text(deck)
  with open('/tmp/open-microled-nrz-ngspice.lock','a') as lock,(f/'ngspice.log').open('w') as log:
   fcntl.flock(lock,fcntl.LOCK_EX);p=subprocess.run(['ngspice','-b','testbench.spice'],cwd=f,stdout=log,stderr=subprocess.STDOUT,timeout=30)
  assert p.returncode==0;raw=f/'waveform.dat';a=np.loadtxt(raw,skiprows=1);a=a[np.argsort(a[:,1])];maxb=float(a[-1,2]);held=a[a[:,2]<=.1,1];released=a[a[:,2]>=.9*maxb,1]
  row={'case':c,'off_state_bias_V':maxb,'last_held_VREG_V':float(held[-1]),'first90pct_release_VREG_V':float(released[0]),'vin_current_released_A':float(-a[-1,5]),'maxCPP_V':float(a[:,3].max()),'minCPP_V':float(a[:,3].min()),'deck_sha256':r.sha(f/'testbench.spice'),'log_sha256':r.sha(f/'ngspice.log')}
  original=r.sha(raw);gz=f/'waveform.dat.gz'
  with raw.open('rb') as fi,gzip.open(gz,'wb',compresslevel=6) as fo:shutil.copyfileobj(fi,fo)
  assert hashlib.sha256(gzip.open(gz,'rb').read()).hexdigest()==original;raw.unlink()
  row.update(waveform_sha256=r.sha(gz),uncompressed_sha256=original,roundtrip_verified=True);r.emit(f/'result.json',row);rows.append(row);print(json.dumps(row),flush=True)
 r.emit(r.EVIDENCE/'clamp-dc-r1.json',{'work':r.rel(WORK),'rows':rows})
if __name__=='__main__':main()
