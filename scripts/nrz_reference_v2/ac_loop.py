#!/usr/bin/env python3
"""Actual-RC series-voltage return ratio; explicitly reports injection loading approximation."""
from pathlib import Path
import argparse,datetime,fcntl,gzip,json,shutil,subprocess
import numpy as np
import experiment as e
import run as r

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=['base','ldo30p','esr100'],default='base');a=ap.parse_args();work=r.BUILD/('ac-'+a.variant+'-r1');assert not work.exists();work.mkdir()
 options={'base':{},'ldo30p':{'ldo_ccomp_F':30e-12},'esr100':{'cout_esr_ohm':100}}[a.variant]
 conditions=[('TT','typical',27,3.3),('SS','ss',125,2.95),('FF','ff',-40,3.65)] if a.variant=='base' else [('TT','typical',27,3.3)]
 plans=[e.make('ac_'+lab,co,t,vdd,dc_bit=b,**options)|{'loop':loop} for lab,co,t,vdd in conditions for b in [0,1] for loop in ['LDO','VI'] if a.variant=='base' or loop=='LDO']
 r.emit(work/'plan.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':plans,'method':'DC-zero seriesAC1V at amplifierfeedbackinput, T=-V(return)/V(input), otherloop remainsclosed. Voltageinjection requires sufficiently lowreturnsourceZ vsampinputZ. ReportnominaldividerR bound/inputZ atcross asloadingindicator; notTian/multiloop robustreturnratio.', 'dc_consistency':'injectionDC0 preservesoperatingpoint','acceptance':'diagnostic stability margins; all unity crossings retained, phaseunwrappedfromlowfrequency; notaloneproofnonlinearstartup'})
 mapping=json.loads((e.WORK/'inputs/physical/N-contract.json').read_text())['extracted_device_mapping']
 vi=next(x for x in mapping if x['original_instance'].upper()=='XIPD2');vi_inst='XN_'+vi['extracted_instance'][1:]
 rows=[]
 for c in plans:
  ident=c['kind']+'-'+str(c['dc_bit'])+'-'+c['loop'];f=work/ident;f.mkdir()
  deck,_,_,_=r.build_deck(e.WORK,c)
  if c['loop']=='LDO':
   # Top portREGFB is only feedbackamplifiergate in the19MOSmodule.
   line=next(x for x in deck.splitlines() if x.startswith('XDRV '));parts=line.split();idx=parts.index('regfb');parts[idx]='regfbamp';deck=deck.replace(line,' '.join(parts));probe='VLOOP regfbamp regfb DC 0 AC 1';returnnode='regfb';inputnode='regfbamp';bound=56000*10000/(56000+10000)
   deck=deck.replace('.control',probe+'\n.control')
  else:
   core=e.WORK/'inputs/physical/B-reference-RC.spice';txt=core.read_text();line=next(x for x in txt.splitlines() if x.split() and x.split()[0].upper()==vi_inst.upper());parts=line.split();returnn=parts[2];parts[2]='VIINJECT';txt=txt.replace(line,' '.join(parts)).replace('.ends nrz_b_reference_v2','VLOOP VIINJECT '+returnn+' DC 0 AC 1\n.ends nrz_b_reference_v2');(f/'instrumented-core.spice').write_text(txt);deck=deck.replace(str(core),str(f/'instrumented-core.spice'));returnnode='xdrv.'+returnn;inputnode='xdrv.viinject';bound=20000
  control=f'''.control
set numdgt=15
set wr_singlescale
set wr_vecnames
op
wrdata op.dat v(vreg) v(sense) v(bias) i(VRAW)
ac dec 80 1 100meg
let loopgain=-v({returnnode})/v({inputnode})
wrdata ac.dat real(loopgain) imag(loopgain)
quit
.endc
.end
'''
  deck=deck[:deck.index('.control')]+control;(f/'testbench.spice').write_text(deck)
  with open('/tmp/open-microled-nrz-ngspice.lock','a') as lock,(f/'ngspice.log').open('w') as log:
   fcntl.flock(lock,fcntl.LOCK_EX);p=subprocess.run(['ngspice','-b','testbench.spice'],cwd=f,stdout=log,stderr=subprocess.STDOUT,timeout=60)
  row={'case':c,'exit_code':p.returncode,'injection_return_node':returnnode,'injection_amplifier_node':inputnode,'return_R_upper_estimate_ohm':bound,'deck_sha256':r.sha(f/'testbench.spice'),'log_sha256':r.sha(f/'ngspice.log'),'source_sha256':r.sha(__file__)}
  if p.returncode==0 and (f/'ac.dat').exists():
   ar=np.loadtxt(f/'ac.dat',skiprows=1);freq=ar[:,0];h=ar[:,1]+1j*ar[:,2];db=20*np.log10(abs(h));phase=np.unwrap(np.angle(h))*180/np.pi
   crossings=[]
   for k in np.flatnonzero(db[:-1]*db[1:]<=0):
    u=-db[k]/(db[k+1]-db[k]);crossings.append({'frequency_Hz':float(np.exp(np.log(freq[k])+u*np.log(freq[k+1]/freq[k]))),'phase_deg':float(phase[k]+u*(phase[k+1]-phase[k])),'phase_margin_deg':float(180+phase[k]+u*(phase[k+1]-phase[k]))})
   row.update(simulation_ok=True,dc_loop_gain_dB=float(db[0]),dc_loop_phase_deg=float(phase[0]),unity_crossings=crossings,op_values=np.loadtxt(f/'op.dat',skiprows=1).tolist())
  else:row['simulation_ok']=False
  r.emit(f/'result.json',row);rows.append(row);print(json.dumps(row),flush=True)
 r.emit(r.EVIDENCE/('ac-'+a.variant+'-r1.json'),{'rows':rows,'note':'Seriesvoltage injection approximation, not rigorousTianbothport returnratio. Structuralinputcap/sourceimpedancecondition requiresreview.'})
if __name__=='__main__':main()
