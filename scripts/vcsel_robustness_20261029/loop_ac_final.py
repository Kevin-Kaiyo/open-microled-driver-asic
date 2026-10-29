#!/usr/bin/env python3
"""Series-voltage injection around high-impedance LDO feedback input; approximate loop-gain diagnostic."""
from pathlib import Path
import json,re,subprocess
import numpy as np
from run import ROOT,BUILD,CIR,sha,emit

def ac(name,cornerlabel='TT',branch='D',rz=0.,bleed=5000.,cldo=30e-12):
 work=BUILD/name
 if work.exists():return json.loads((work/'result.json').read_text())
 work.mkdir();src=BUILD/f'regulated-{cornerlabel}-1-r8';deck=(src/'testbench.spice').read_text();text=(src/'inputs/driver.spice').read_text()
 rz=10000. if branch=='L' else 100000.
 for q in ['L','D']:
  pass
 lines=[]
 for line in text.splitlines():
  w=line.split()
  if line.startswith('X') and len(w)>5 and w[2]==branch+'fb':w[2]+='_test';line=' '.join(w)
  lines.append(line)
 text='\n'.join(lines).replace('.ends vcsel_servo',f'VLOOP {branch}fb_test {branch}fb DC 0 AC 1\n.ends vcsel_servo')+'\n'
 (work/'driver.spice').write_text(text)
 deck=deck.replace(str(src/'inputs/driver.spice'),str(work/'driver.spice'))
 deck=re.sub(r'CLDO=\S+',f'CLDO={cldo}',deck)
 deck=deck[:deck.index('.control')]+f'''.control
set numdgt=12
set wr_singlescale
set wr_vecnames
save v(xdrv.{branch.lower()}fb) v(xdrv.{branch.lower()}fb_test)
ac dec 60 1 1e9
wrdata ac.dat v(xdrv.{branch.lower()}fb) v(xdrv.{branch.lower()}fb_test)
quit
.endc
.end
'''
 (work/'testbench.spice').write_text(deck)
 with (work/'ngspice.log').open('w') as f:code=subprocess.run(['ngspice','-b','testbench.spice'],cwd=work,stdout=f,stderr=subprocess.STDOUT).returncode
 a=np.loadtxt(work/'ac.dat',skiprows=1);freq=a[:,0];fb=a[:,1]+1j*a[:,2];test=a[:,3]+1j*a[:,4];gain=-fb/test;mag=20*np.log10(abs(gain));phase=np.unwrap(np.angle(gain))*180/np.pi
 cross=np.flatnonzero((mag[:-1]>=0)&(mag[1:]<0));xs=[]
 for k in cross:
  alpha=mag[k]/(mag[k]-mag[k+1]);xs.append(dict(unity_Hz=float(np.exp(np.log(freq[k])*(1-alpha)+np.log(freq[k+1])*alpha)),phase_margin_deg=float(180+phase[k]*(1-alpha)+phase[k+1]*alpha)))
 result=dict(case=name,branch=branch,corner=cornerlabel,rz_ohm=rz,bleed_ohm=bleed,cldo_F=cldo,low_frequency_gain_dB=float(mag[0]),unity_crossings=xs,exit_code=code,source_circuit_sha256=sha(src/'inputs/driver.spice'),modified_circuit_sha256=sha(work/'driver.spice'),deck_sha256=sha(work/'testbench.spice'),data_sha256=sha(work/'ac.dat'),method='Approximate -Vfb/Vfb_test series voltage injection at amplifier feedback gate, DC operating point retained; input capacitance nonzero, not a formal foundry stability signoff')
 result['revision']='r8';result['dc_state']=json.loads((src/'result.json').read_text())['nodes_final_V'];result['interpretation']='SS dropout is not regulation; do not label missingunitycrossing as sufficientPM' if cornerlabel=='SS' else 'RegulatedDC operatingpoint, one selectedfeedbackgate injection'
 emit(work/'result.json',result);np.savez_compressed(work/'plot.npz',frequency_Hz=freq,loop_gain_dB=mag,phase_deg=phase)
 print(json.dumps(result),flush=True);return result
if __name__=='__main__':
 for rz,bleed,cldo in [(0.,0.,100e-12),(10000.,0.,100e-12),(10000.,10000.,100e-12),(10000.,10000.,300e-12)]:
  for branch in ['L','D']:ac(f'ac-TT-{branch}-rz{rz}-bleed{bleed}-c{cldo}',branch=branch,rz=rz,bleed=bleed,cldo=cldo)
