#!/usr/bin/env python3
"""DC calibration and initial transient probe of the real GF180 steering circuit.

Generated files stay in build; compact summary is evidence. The LED DC curve is
measured-static; 200 fF and package 1 ohm / 0.5 nH are explicit assumptions.
This probe is not the unified receiver / comparison experiment.
"""
from pathlib import Path
import hashlib,json,re,subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
PDK=ROOT/'build/layout/pdk/gf180mcuD/libs.tech/ngspice'
NET=ROOT/'analog/highspeed_nrz/steering_driver.spice'
LED=ROOT/'analog/models/measured-led/lin2026-yellow20-dc.spice'
BUILD=ROOT/'build/highspeed-nrz/steering-probe-v2-060um'
EVIDENCE=ROOT/'evidence/highspeed-nrz/steering-prototype.json'
NODES=['data','out','vdd','vdummy','xdut.bias','xdut.gb','xdut.gp','xdut.vx','xdut.dummy','led_k']
MOS={
 'XREF':['xdut.bias','xdut.bias','0','0'],
 'XBASE':['out','xdut.bias','0','0'],
 'XTAIL':['xdut.vx','xdut.bias','0','0'],
 'XLED':['out','xdut.gp','xdut.vx','0'],
 'XDUMMY':['xdut.dummy','xdut.gb','xdut.vx','0'],
 'XINV1N':['xdut.gb','data','0','0'],
 'XINV1P':['xdut.gb','data','vdd','vdd'],
 'XINV2N':['xdut.gp','xdut.gb','0','0'],
 'XINV2P':['xdut.gp','xdut.gb','vdd','vdd'],
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(name,rref=100e3,wtail=6e-6,state=0,rate=None):
 p=BUILD/name;p.mkdir(parents=True,exist_ok=True)
 for f in ['design.ngspice','sm141064.ngspice']:
  q=p/f
  if not q.exists():q.symlink_to(PDK/f)
 duration=0 if rate is None else 32/rate
 src=str(3.3*state) if rate is None else f'PULSE(0 3.3 {4/rate:.12g} 20p 20p {0.5/rate-20e-12:.12g} {1/rate:.12g})'
 ctrl='op' if rate is None else f'tran {min(5e-12,1/rate/100):.12g} {duration:.12g} 0 {min(5e-12,1/rate/100):.12g}'
 deck=f'''Real GF180 current-steering NRZ prototype
.include design.ngspice
.param sw_stat_global=0 sw_stat_mismatch=0
.lib sm141064.ngspice typical
.include "{NET}"
.include "{LED}"
.temp 27
VDD vdd 0 3.3
VDUMMY vdummy 0 3.3
VLED vled 0 5
VSEN vled led_a 0
VDATA data 0 {src}
XLED led_a led_k lin2026_yellow20_dc
CLED vled led_k 200f
RPKG led_k lpkg 1
LPKG lpkg out 0.5n
XDUT data out vdd vdummy 0 hs_nrz_steering RREF={rref:.15g} WTAIL={wtail:.15g}
.options reltol=1e-6 abstol=1e-14 vntol=1e-8 method=trap
.control
set noaskquit
set numdgt=15
set wr_vecnames
set wr_singlescale
{ctrl}
wrdata waveform.dat i(vsen) i(vled) i(vdd) i(vdummy) i(vdata) {' '.join('v('+n+')' for n in NODES)}
quit
.endc
.end
'''
 (p/'testbench.spice').write_text(deck)
 r=subprocess.run(['ngspice','-b','testbench.spice'],cwd=p,capture_output=True,text=True)
 log=r.stdout+r.stderr;(p/'ngspice.log').write_text(log)
 if r.returncode or re.search(r'(?im)^error:|fatal|timestep too small|simulation interrupted',log):raise RuntimeError(str(p/'ngspice.log'))
 d=np.loadtxt(p/'waveform.dat',skiprows=1,ndmin=2)
 assert np.isfinite(d).all()
 return p,d
def stress(d):
 volts={n:d[:,6+i] for i,n in enumerate(NODES)};volts['0']=np.zeros(len(d))
 result={}
 for m,n in MOS.items():
  v={k:volts[node] for k,node in zip('dgsb',n)}
  result[m]={a+b:float(np.max(np.abs(v[a]-v[b]))) for a,b in [('g','s'),('g','d'),('g','b'),('d','s'),('d','b'),('s','b')]}
 return result
def main():
 BUILD.mkdir(parents=True,exist_ok=True);EVIDENCE.parent.mkdir(parents=True,exist_ok=True)
 lo,hi=30e3,200e3
 for j in range(19):
  rref=(lo+hi)/2;p,d=run(f'cal-rref-{j:02d}',rref=rref)
  if d[0,1]>25e-6:lo=rref
  else:hi=rref
 rref=(lo+hi)/2;lo,hi=3e-6,9e-6
 for j in range(19):
  wtail=(lo+hi)/2;p,d=run(f'cal-wtail-{j:02d}',rref=rref,wtail=wtail,state=1)
  if d[0,1]>100e-6:hi=wtail
  else:lo=wtail
 wtail=(lo+hi)/2;results=[]
 for state in [0,1]:
  p,d=run(f'dc-{state}',rref,wtail,state)
  results.append(dict(case=f'dc-{state}',led_conduction_a=float(d[0,1]),bias_v=float(d[0,10]),rail_power_w=dict(led=float(-5*d[0,2]),vdd=float(-3.3*d[0,3]),dummy=float(-3.3*d[0,4])),stress_v=stress(d),raw_directory=str(p.relative_to(ROOT))))
 for rate in [1e8,1e9]:
  p,d=run(f'tran-{rate:.0e}',rref,wtail,rate=rate)
  mask=d[:,0]>=8/rate;t=d[mask,0];y=d[mask]
  integrator=np.trapezoid if hasattr(np,'trapezoid') else np.trapz
  mean=lambda a:float(integrator(a,t)/(t[-1]-t[0]))
  pwr=mean(-5*y[:,2]-3.3*y[:,3]-3.3*y[:,4])
  results.append(dict(case=f'tran-{rate:.0e}',toggle_period_s=1/rate,nrz_equivalent_bit_rate_bps=2*rate,led_conduction_min_a=float(y[:,1].min()),led_conduction_max_a=float(y[:,1].max()),rail_power_w=pwr,energy_per_equivalent_bit_j=pwr/(2*rate),stress_v=stress(y),raw_directory=str(p.relative_to(ROOT))))
 summary=dict(interface='hs_nrz_steering data out vdd vdummy vss params: RREF WTAIL',rref_ohm=rref,wtail_m=wtail,rdummy_ohm=28e3,wb_m=2e-6,lmirror_m=1e-6,wswitch_m=1e-6,lswitch_m=.28e-6,results=results,scope='TT 27C DC calibration and alternating-input prototype; not unified PRBS receiver experiment, no optical BER',load='Measured-static Lin2026 yellow20 curve with assumed 200fF, cathode series 1ohm and 0.5nH',rails_v={'vled':5,'vdd':3.3,'vdummy':3.3},power_boundary='LED plus VDD (reference and predriver) plus dummy rail; excludes ideal input driver source and regulators',device_count=9,geometry='AD=AS=W*0.6um; PD=PS=2*(W+0.6um), isolated diffusions, not extracted',source_hashes={str(x.relative_to(ROOT)):sha(x) for x in [NET,LED,Path(__file__),PDK/'design.ngspice',PDK/'sm141064.ngspice']})
 EVIDENCE.write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
