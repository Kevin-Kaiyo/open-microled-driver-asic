from pathlib import Path
import json,re,subprocess,fcntl,hashlib
import numpy as np
root=Path('/Users/kimmy/Projects/open-microled-driver-asic');out=root/'build/reference-v2-audit/tian-r1';out.mkdir(parents=True,exist_ok=False)
rows=[]
for bit in [0,1]:
 p=root/f'build/nrz-reference-v2/ac-base-r1/ac_TT-{bit}-LDO/testbench.spice';base=p.read_text()
 values={}
 for method in ['voltage','current']:
  work=out/f'bit{bit}-{method}';work.mkdir()
  deck=base[:base.index('.control')]
  if method=='current':
   deck=deck.replace('VLOOP regfbamp regfb DC 0 AC 1','VRETURN inject regfb 0\nVFORWARD inject regfbamp 0\nIINJECT 0 inject DC 0 AC 1')
   measure='let transfer=i(VRETURN)/i(VFORWARD)'
  else:measure='let transfer=-v(regfb)/v(regfbamp)'
  deck+='''.control
set numdgt=15
set wr_singlescale
set wr_vecnames
op
wrdata op.dat v(vreg) v(sense) v(bias) i(VRAW)
ac dec 80 1 100meg
'''+measure+'''
wrdata transfer.dat real(transfer) imag(transfer)
quit
.endc
.end
'''
  (work/'testbench.spice').write_text(deck)
  with open('/tmp/open-microled-nrz-ngspice.lock','a') as lock,(work/'ngspice.log').open('w') as log:
   fcntl.flock(lock,fcntl.LOCK_EX);r=subprocess.run(['ngspice','-b','testbench.spice'],cwd=work,stdout=log,stderr=subprocess.STDOUT,timeout=60)
  assert r.returncode==0
  a=np.loadtxt(work/'transfer.dat',skiprows=1);values[method]=a[:,1]+1j*a[:,2];freq=a[:,0]
 v=values['voltage'];i=values['current'];t=(v*i-1)/(v+i+2);db=20*np.log10(abs(t));phase=np.unwrap(np.angle(t))*180/np.pi
 np.savetxt(out/f'bit{bit}.csv',np.c_[freq,v.real,v.imag,i.real,i.imag,t.real,t.imag,db,phase],delimiter=',',header='frequency_Hz,Tv_re,Tv_im,Ti_re,Ti_im,T_re,T_im,T_dB,Tphase_deg',comments='')
 crosses=[]
 for k in np.flatnonzero(db[:-1]*db[1:]<=0):
  u=-db[k]/(db[k+1]-db[k]);crosses.append({'f_Hz':float(np.exp(np.log(freq[k])+u*np.log(freq[k+1]/freq[k]))),'phase':float(phase[k]+u*(phase[k+1]-phase[k])),'direction':'down' if db[k]>db[k+1] else 'up'})
 rows.append({'bit':bit,'lowfreq_Tv':[float(v[0].real),float(v[0].imag)],'lowfreq_Ti':[float(i[0].real),float(i[0].imag)],'lowfreq_T':[float(t[0].real),float(t[0].imag)],'crossings':crosses})
res={'note':'Independent review diagnostic; not selected circuit or qualification','method':'Tv=-Vreturn/Vforward; Ti=Ireturn/Iforward; T=(TvTi-1)/(Tv+Ti+2)','rows':rows}
(out/'summary.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
