#!/usr/bin/env python3
"""Local VI two-injection diagnostic with closed/injectedOP consistency."""
from pathlib import Path
import argparse,datetime,fcntl,hashlib,json,re,shutil,subprocess
import numpy as np
import run as r
import validate as v
SOURCE=Path(__file__).read_bytes();SHA=hashlib.sha256(SOURCE).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--comp',choices=['miller3','shunt15','shunt150'],required=True);ap.add_argument('--corner',default='ff');ap.add_argument('--temp',type=float,default=-40);ap.add_argument('--vdd',type=float,default=3.65);ap.add_argument('--bit',type=int,default=1);ap.add_argument('--work',type=Path,default=r.BUILD/'clamped-r1');ap.add_argument('--suffix',default='r2');ap.add_argument('--comp-package',action='store_true');a=ap.parse_args()
 work=a.work;options={'miller3':{'compensation':'miller','vi_comp_F':3e-12},'shunt15':{'compensation':'shunt','vi_comp_F':15e-12},'shunt150':{'compensation':'shunt','vi_comp_F':150e-12}}[a.comp]
 if a.comp_package:options['comp_package']={'r_ohm':1.,'l_H':5e-9,'esr_ohm':.5}
 top=r.BUILD/f'vi-loop-{a.comp}-{a.corner}-b{a.bit}-{a.suffix}';assert not top.exists();top.mkdir();(top/'executed-vi_loop.py').write_bytes(SOURCE)
 case=v.case(work,'B','loop',a.corner,a.temp,a.vdd,variant='REFERENCE',dc_bit=a.bit,**options)
 r.emit(top/'plan.json',{'created_before_execution':datetime.datetime.now().isoformat(),'case':case,'method':'DCzero seriesvoltage and shuntcurrent injections atVI sensegate, T=(TvTi-1)/(Tv+Ti+2); closedOP+allinjectedOPcompared','hypothesis':'A decadeincreaseN2shunt15→150p lowersdominantpole/bandwidth; noassumptionthatPWMcompensationtransfers','source_sha256':SHA})
 base,_,_,_=r.build_deck(work,case);core=work/'inputs/physical/B-reference-RC.spice';body=core.read_text()
 candidates=[line for line in body.splitlines() if line.startswith('X') and len(line.split())>5 and line.split()[5].lower()=='pfet_06v0' and 'sense' in line.split()[2].lower()];assert len(candidates)==1,candidates
 line=candidates[0];parts=line.split();gate=parts[2];portnames=r.parse_core(core)[1];gatevector=gate if gate.lower() in portnames else 'xdrv.'+gate;opened=body.replace(line,' '.join(parts[:2]+['FB_IN']+parts[3:]));out={};ops=[];records=[]
 for method in ['voltage','current','closed']:
  folder=top/method;folder.mkdir();dut=body;extra='';signals=''
  if method=='voltage':dut=opened;extra=f'VINJECT FB_IN {gate} DC 0 AC 1';signals=f'v({gatevector}) v(xdrv.FB_IN)'
  if method=='current':dut=opened;extra=f'VRETURN INJECT {gate} 0\nVFORWARD INJECT FB_IN 0\nIINJECT 0 INJECT DC 0 AC 1';signals='i(v.xdrv.VRETURN) i(v.xdrv.VFORWARD)'
  dut=re.sub(r'(?im)^.ends',extra+'\n.ends',dut);(folder/'core.spice').write_text(dut)
  deck=base.split('.control')[0].replace(str(core),str(folder/'core.spice'))
  ctl=('ac dec 100 1 100meg\nwrdata ac.dat '+signals) if signals else ''
  deck+='.control\nset numdgt=15\nset wr_vecnames\nset wr_singlescale\nsave all\nop\nwrdata op.dat v(sense) v(bias) v(out) v(in2) v(ictrl) v(vin)\n'+ctl+'\nquit\n.endc\n.end\n';(folder/'testbench.spice').write_text(deck)
  with open('/tmp/open-microled-nrz-ngspice.lock','a') as lock,(folder/'ngspice.log').open('w') as log:
   fcntl.flock(lock,fcntl.LOCK_EX);p=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,stdout=log,stderr=subprocess.STDOUT,timeout=60)
  assert p.returncode==0;assert not re.search(r'(?im)^Error:|timestep too small|simulation interrupted',(folder/'ngspice.log').read_text())
  ops.append(np.loadtxt(folder/'op.dat',skiprows=1));records.append({'method':method,'deck_sha256':r.sha(folder/'testbench.spice'),'core_sha256':r.sha(folder/'core.spice'),'log_sha256':r.sha(folder/'ngspice.log')})
  if signals:out[method]=np.loadtxt(folder/'ac.dat',skiprows=1)
 av=out['voltage'];ai=out['current'];f=av[:,0];tv=-(av[:,1]+1j*av[:,2])/(av[:,3]+1j*av[:,4]);ti=(ai[:,1]+1j*ai[:,2])/(ai[:,3]+1j*ai[:,4]);T=(tv*ti-1)/(tv+ti+2);g=20*np.log10(abs(T));ph=np.unwrap(np.angle(T))*180/np.pi
 crossings=[]
 for k in np.flatnonzero((g[:-1]>=0)&(g[1:]<0)):
  frac=-g[k]/(g[k+1]-g[k]);crossings.append({'frequency_Hz':float(np.exp(np.log(f[k])+frac*np.log(f[k+1]/f[k]))),'phase_margin_deg':float(180+ph[k]+frac*(ph[k+1]-ph[k]))})
 result={'case':case,'compensation':a.comp,'dc_gain_db':float(g[0]),'dc_phase_deg':float(ph[0]),'crossings':crossings,'closed_injected_op_max_delta':max(float(np.max(abs(x-ops[-1]))) for x in ops[:-1]),'records':records,'injection_gate':gate,'source_sha256':SHA,'scope':'Localtwo-injectionreturnratioestimate; onlyphysical/modelconditiontested, notsiliconstabilitysignoff.'}
 r.emit(top/'result.json',result);r.emit(r.EVIDENCE/(top.name+'.json'),result);np.savetxt(top/'loop.csv',np.c_[f,g,ph],delimiter=',',header='frequency_Hz,gain_dB,phase_deg',comments='');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
