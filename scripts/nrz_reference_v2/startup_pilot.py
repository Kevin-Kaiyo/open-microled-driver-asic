#!/usr/bin/env python3
"""Declared first dynamics screen for fixed19MOS coupled pilot; retained raw and extrema."""
from pathlib import Path
import datetime,fcntl,gzip,hashlib,json,re,shutil,subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/nrz-reference-v2/pilot-r1';WORK=ROOT/'build/nrz-reference-v2/startup-r1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def emit(p,j):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(j,indent=2)+'\n')
def main():
 assert not WORK.exists(); assert shutil.disk_usage(ROOT).free>=5*1024**3
 WORK.mkdir();shutil.copytree(BASE/'inputs',WORK/'inputs');shutil.copy2(__file__,WORK/'startup_pilot.py')
 cs=[dict(label=q,kind='ramp',method='gear',maxstep_ns=5) for q in ['TT','SS','FF']]+[dict(label='TT',kind='late_anchor',method='gear',maxstep_ns=5),dict(label='TT',kind='loadstep',method='gear',maxstep_ns=5)]
 emit(WORK/'plan.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs,'physical_model':'oldB fullRC + 19MOS prelayout .44umdiffusion','acceptance':'diagnostic: no nonfinite/solver failure, outputsettledwithin2%ofDC by20us, last2us ripple<1%, explicitallMOS3.63/6Vscreen; lateanchorunsupportedcurrentisretainedfailure','source_sha256':sha(__file__)})
 rows=[]
 for c in cs:
  ident=c['label']+'-'+c['kind'];f=WORK/ident;f.mkdir()
  txt=(BASE/(c['label']+'0')/'testbench.spice').read_text().replace(str(BASE/'inputs'),str(WORK/'inputs'))
  vdd={'TT':3.3,'SS':2.95,'FF':3.65}[c['label']]
  if c['kind']=='loadstep':
   txt=re.sub(r'^VDATA.*$',f'VDATA data 0 PULSE(0 {vdd} 5u 20p 20p 5u 10u)',txt,flags=re.M)
  else:
   txt=txt.replace('VRAW vin 0 5','VRAW vin 0 PWL(0 0 1u 5)').replace('VLED led_a 0 5','VLED led_a 0 PWL(0 0 1u 5)')
   txt=txt.replace(f'VDD vdd 0 {vdd}',f'VDD vdd 0 PWL(0 0 1u {vdd})')
   ref='PWL(0 0 1u 2.5)' if c['kind']=='ramp' else 'PWL(0 0 3u 0 3.1u 2.5)'
   txt=txt.replace('VREF refsrc 0 2.5','VREF refsrc 0 '+ref)
  # Save each actual MOS D/G/S/B node, including core RC body nodes.
  devices=[]
  for filename,prefix,portmap in [('core.spice','xcore',{'data':'data','out':'out','vdd':'vdd','vss':'0','bias':'bias','dummy':'dummy'}),('power.spice','xpower',{'vin':'vin','vss':'0','vset':'vset','sense':'sense','iout':'bias','regfb':'fb','vreg':'vreg','ipb':'ipb','in2':'in2','ictrl':'ictrl','lpb':'lpb','ln2':'ln2','lctrl':'lctrl'})]:
   source=re.sub(r'\n\s*\+\s*',' ',(WORK/'inputs'/filename).read_text())
   for line in source.splitlines():
    p=line.lower().split()
    if len(p)>5 and p[0].startswith('x') and p[5] in ['nfet_06v0','pfet_06v0','nfet_03v3','pfet_03v3']:
     devices.append({'instance':prefix+'.'+p[0],'model':p[5],'nodes':[portmap.get(n,prefix+'.'+n) for n in p[1:5]]})
  oldvec=re.search(r'^wrdata waveform.dat (.*)$',txt,re.M).group(1).split()
  nodes=sorted({n for d in devices for n in d['nodes']} - {'0'})
  vec=oldvec+[f'v({n})' for n in nodes if f'v({n})' not in oldvec]+['v(led_a)','v(vin)','v(refsrc)','v(vdd)']
  vec=list(dict.fromkeys(vec));txt=re.sub(r'^wrdata waveform.dat .*$', 'wrdata waveform.dat '+' '.join(vec),txt,flags=re.M)
  tran=f'tran {c["maxstep_ns"]}n 20u 0 {c["maxstep_ns"]}n'+(' uic' if c['kind']!='loadstep' else '')
  txt=txt.replace('\nop\n','\n'+tran+'\n')
  (f/'testbench.spice').write_text(txt)
  with open('/tmp/open-microled-nrz-ngspice.lock','a') as lock,(f/'ngspice.log').open('w') as log:
   fcntl.flock(lock,fcntl.LOCK_EX);p=subprocess.run(['ngspice','-b','testbench.spice'],cwd=f,stdout=log,stderr=subprocess.STDOUT,timeout=120)
  row={'case':c,'exit_code':p.returncode,'deck_sha256':sha(f/'testbench.spice'),'log_sha256':sha(f/'ngspice.log'),'vectors':vec,'devices':devices,'simulation_ok':False}
  raw=f/'waveform.dat'
  if p.returncode==0 and raw.exists():
   a=np.atleast_2d(np.loadtxt(raw,skiprows=1));assert a.shape[1]==len(vec)+1 and np.isfinite(a).all() and abs(a[-1,0]-20e-6)<1e-12
   v={n:a[:,i+1] for i,n in enumerate(vec)};t=a[:,0];last=t>18e-6
   limits=[]
   for d in devices:
    terms=[np.zeros(len(t)) if n=='0' else v[f'v({n})'] for n in d['nodes']]
    diffs={pair:float(np.max(np.abs(terms[i]-terms[j]))) for pair,i,j in [('VDS',0,2),('VGS',1,2),('VGD',1,0),('VGB',1,3),('VSB',2,3),('VDB',0,3)]}
    lim=6 if '06v0' in d['model'] else 3.63;limits.append(d|{'maxpairs_V':diffs,'limit_V':lim,'passed':max(diffs.values())<=lim})
   row.update(simulation_ok=True,rows=len(t),voltages={n:{'min':float(v[n].min()),'max':float(v[n].max()),'final':float(v[n][-1]),'last2us_pp':float(np.ptp(v[n][last]))} for n in ['v(vreg)','v(sense)','v(bias)']},current_LED_A={'min':float((-v['i(VLED)']).min()),'max':float((-v['i(VLED)']).max()),'final':float(-v['i(VLED)'][-1])},device_screen=limits,device_screen_passed=all(d['passed'] for d in limits))
  if raw.exists():
   orig=sha(raw);gz=f/'waveform.dat.gz'
   with raw.open('rb') as fi,gzip.open(gz,'wb',compresslevel=6) as fo:shutil.copyfileobj(fi,fo)
   assert hashlib.sha256(gzip.open(gz,'rb').read()).hexdigest()==orig
   row.update(waveform_sha256=sha(gz),uncompressed_sha256=orig,roundtrip_verified=True);raw.unlink()
  emit(f/'result.json',row);rows.append(row)
  print(json.dumps({k:v for k,v in row.items() if k not in ['devices','vectors','device_screen']}),flush=True)
 emit(ROOT/'evidence/nrz-reference-v2/startup-r1.json',{'work':str(WORK.relative_to(ROOT)),'rows':rows})
if __name__=='__main__':main()
