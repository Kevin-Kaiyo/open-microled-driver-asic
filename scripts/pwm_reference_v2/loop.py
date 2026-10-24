#!/usr/bin/env python3
"""Bounded two-injection local-loop diagnostic, same package and bias network."""
from pathlib import Path
import argparse, importlib.util, json, re, subprocess, fcntl, time, hashlib
import numpy as np
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('rr',HERE/'run.py');r=importlib.util.module_from_spec(sp);sp.loader.exec_module(r)
SOURCE=Path(__file__).read_bytes();SHA=hashlib.sha256(SOURCE).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cff',type=float,required=True);ap.add_argument('--n2c',type=float);ap.add_argument('--pcb',action='store_true');ap.add_argument('--n2rl',action='store_true');ap.add_argument('--cf',type=float,default=100);ap.add_argument('--rf',type=float,default=100);ap.add_argument('--damp',type=float,default=0);ap.add_argument('--led',type=float,default=5);ap.add_argument('--revision',default='');ap.add_argument('--cc',type=float,default=30);ap.add_argument('--cs',type=float,default=30);ap.add_argument('--corner',default='typical');ap.add_argument('--temp',type=float,default=27);ap.add_argument('--voltage',type=float,default=3.3);a=ap.parse_args();m=r.freeze()
 tag=f'loop_cff{a.cff:g}_cc{a.cc:g}_cs{a.cs:g}_{a.corner}_{a.temp:g}'
 tag+=f'_n2c{a.n2c:g}' if a.n2c else '';tag+=f'_pcb{a.cf:g}n_r{a.rf:g}' if a.pcb else '';tag+=f'_damp{a.damp:g}' if a.damp else '';tag+='_n2rl' if a.n2rl else '';tag+='_'+a.revision if a.revision else '';top=r.WORK/tag;top.mkdir(exist_ok=True)
 if (top/'result.json').exists():raise RuntimeError('Immutable loop identity already completed: '+tag)
 source=r.INPUT/'executed_sources'/SHA/'loop.py';source.parent.mkdir(parents=True,exist_ok=True)
 if not source.exists():source.write_bytes(SOURCE)
 body=(r.INPUT/'dut.spice').read_text();x6=next(l for l in body.splitlines() if l.startswith('X6 '));ports=x6.split();gate=ports[2];assert gate.upper().startswith('SENSE')
 openbody=body.replace(x6,' '.join(ports[:2]+['FB_IN']+ports[3:]));outs={};ops=[];records=[]
 for method in ['voltage','current','closed']:
  p=top/method;p.mkdir(exist_ok=True)
  c=m.case(tag+'_'+method,kind='dc');c.update(cff_pf=a.cff,package='stress',corner=a.corner,temp_c=a.temp,logic_v=a.voltage,led_v=a.led)
  if a.n2c:c['comp_n2_pf']=a.n2c
  if a.pcb:c.update(comp_return='0',candidate=True,filter_location='board',filter_c_nf=a.cf,filter_r_ohm=a.rf,driver_r_ohm=10)
  if a.n2rl:c.update(comp_pin_package=True)
  if a.damp:c['comp_damp_ohm']=a.damp
  d=r.make_deck(c,p,m).split('.control')[0].replace('CCOMP n2 ctrl 30p',f'CCOMP n2 ctrl {a.cc}p').replace('CSENSE sense 0 30p',f'CSENSE sense 0 {a.cs}p')
  if method=='voltage':extra=f'VINJECT FB_IN {gate} DC 0 AC 1';out=f'v(xdut.{gate}) v(xdut.FB_IN)';dut=openbody
  elif method=='current':extra=f'VRETURN INJECT {gate} 0\nVFORWARD INJECT FB_IN 0\nIINJECT 0 INJECT DC 0 AC 1';out='i(v.xdut.VRETURN) i(v.xdut.VFORWARD)';dut=openbody
  else:extra='';out='';dut=body
  dut=re.sub(r'(?im)^.ends',extra+'\n.ends',dut)
  d=d.replace(str(r.INPUT/'dut.spice'),str(p/'dut.spice'))
  ctl='ac dec 100 1 1G\nwrdata ac.dat '+out if out else ''
  d+='.control\nset numdgt=15\nset wr_vecnames\nset wr_singlescale\nsave all\nop\nwrdata op.dat v(sense) v(refout) v(bias) v(led_k) v(n2) v(ctrl)\n'+ctl+'\nquit\n.endc\n.end\n'
  h=hashlib.sha256(d.encode()).hexdigest()
  if (p/'testbench.spice').exists():assert (p/'testbench.spice').read_text()==d;assert (p/'dut.spice').read_text()==dut
  else:
   (p/'testbench.spice').write_text(d);(p/'dut.spice').write_text(dut)
   with open(r.LOCK,'a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX);q=subprocess.run(['ngspice','-b','testbench.spice'],cwd=p,text=True,capture_output=True,timeout=60)
   (p/'ngspice.log').write_text(q.stdout+q.stderr)
  log=(p/'ngspice.log').read_text();assert not re.search(r'(?im)^Error:|timestep too small|simulation interrupted',log),log[-1000:]
  ops.append(np.loadtxt(p/'op.dat',skiprows=1));records.append(dict(method=method,deck_sha256=h,dut_sha256=r.sha(p/'dut.spice'),log_sha256=r.sha(p/'ngspice.log')))
  if out:outs[method]=np.loadtxt(p/'ac.dat',skiprows=1)
 av=outs['voltage'];ai=outs['current'];f=av[:,0];tv=-(av[:,1]+1j*av[:,2])/(av[:,3]+1j*av[:,4]);ti=(ai[:,1]+1j*ai[:,2])/(ai[:,3]+1j*ai[:,4]);T=(tv*ti-1)/(tv+ti+2);g=20*np.log10(abs(T));ph=np.unwrap(np.angle(T))*180/np.pi;j=np.flatnonzero((g[:-1]>=0)&(g[1:]<0));cross=[dict(frequency_hz=float(10**np.interp(0,[g[k+1],g[k]],[np.log10(f[k+1]),np.log10(f[k])])),phase_margin_deg=float(180+np.interp(0,[g[k+1],g[k]],[ph[k+1],ph[k]]))) for k in j]
 result=dict(name=tag,cff_pf=a.cff,cc_pf=a.cc,cs_pf=a.cs,comp_n2_pf=a.n2c,pcb_filter=a.pcb,filter_c_nf=a.cf,filter_r_ohm=a.rf,comp_damp_ohm=a.damp,n2_pin_package=a.n2rl,corner=a.corner,temp_c=a.temp,logic_v=a.voltage,led_v=a.led,crossings=cross,dc_loop_gain_db=float(g[0]),closed_injected_op_max_delta_v=max(float(np.max(abs(o-ops[-1]))) for o in ops[:-1]),records=records,executed_source_sha256=SHA,helper_runner_sha256=r.SOURCE_SHA,source_manifest_sha256=r.sha(m.frozen_manifest_path),complete_source_identity=True,limitation='Local two-injection return-ratio estimate; includes same stress package. No full silicon stability qualification.')
 r.save(top/'result.json',result);r.save(r.EVID/(tag+'.json'),result);np.savetxt(r.EVID/(tag+'.csv'),np.c_[f,g,ph],delimiter=',',header='frequency_hz,loop_gain_db,loop_phase_deg',comments='');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
