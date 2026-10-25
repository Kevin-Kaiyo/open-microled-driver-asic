#!/usr/bin/env python3
"""New matched schematic experiments. Frozen inputs; explicit common port energy."""
from pathlib import Path
import argparse,csv,datetime,gzip,hashlib,importlib.util,json,os,re,shutil,subprocess,tempfile,time
import numpy as np
EXECUTION_SOURCE=Path(__file__).read_bytes()
EXECUTION_SHA=hashlib.sha256(EXECUTION_SOURCE).hexdigest()
ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/fair-driver-v1'
MODELS=ROOT/'build/nrz-reference-v2/selected-final-r2/inputs'
ROUTES='ABC'
DEFAULT_PARAMS={'A':{'RH':177683.3997653013,'RL':87444.56014738003},'B':{'RSET':20000.,'WTAIL':5.76e-6,'RINL':8e-6},'C':{'RSET':20125.423810323304,'WUNIT':2.02e-6,'RINL':8e-6}}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def emit(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(p)
def module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def init(work,parameters=None):
 work=Path(work).resolve();assert work.is_relative_to(BUILD.resolve())
 if (work/'manifest.json').exists():return verify(work)
 work.mkdir(parents=True,exist_ok=True);dest=work/'inputs';dest.mkdir()
 for name in ['common','route_a','route_b','route_c']:shutil.copy2(ROOT/f'analog/fair_driver_v1/{name}.spice',dest/f'{name}.spice')
 for name in ['design.ngspice','sm141064.ngspice']:
  (dest/'pdk').mkdir(exist_ok=True);shutil.copy2(MODELS/'pdk'/name,dest/'pdk'/name)
 shutil.copy2(MODELS/'led.spice',dest/'led.spice')
 if (Path(__file__).parent/'receiver.py').exists():shutil.copy2(Path(__file__).parent/'receiver.py',dest/'receiver.py')
 info={'created':datetime.datetime.now().astimezone().isoformat(),'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'parameters':parameters or DEFAULT_PARAMS,'inputs':{str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file()},'common':{'LED':'Lin2026 yellow20 static; thermal/optical unspecified','CLED_F':200e-15,'RLED_ohm':1,'LLED_H':.5e-9,'VLED_V':5,'VDD_nominal_V':3.3,'VIN_nominal_V':5,'VREF_V':2.5,'edge_s':20e-12,'RDATA_ohm':100,'power_boundary':'VIN,VDD,VREF,VLED,D0,D1,DISABLE input ports; includes all instantiated MOS/R/C inside, but not upstream source IC internal losses, receiver or clock/host electronics.','physical_level':'new schematic only, uniform estimated junctions; no PEX or inherited layout claim','startup':'normal communication starts from OP; power-up separate diagnostic, not hidden in a settled transient','net_throughput':'4096 payload bits divided by full4736-bit test-frame duration; no implemented protocol/FEC claim'},'ngspice_version':subprocess.check_output(['ngspice','--version'],text=True)}
 if (dest/'receiver.py').exists():
  emit(work/'stimulus.json',module(dest/'receiver.py','fair_rx_init').make_stimulus());info['stimulus_sha256']=sha(work/'stimulus.json')
 emit(work/'manifest.json',info)
 return info

def verify(work):
 m=json.loads((work/'manifest.json').read_text())
 for name,wanted in m['inputs'].items():assert sha(work/'inputs'/name)==wanted,'Frozen input drift: '+name
 if 'stimulus_sha256' in m:assert sha(work/'stimulus.json')==m['stimulus_sha256'],'Frozen stimulus drift'
 return m

def definitions(work):
 defs={}
 for p in (work/'inputs').glob('*.spice'):
  current=None
  for line in re.sub(r'\n\s*\+\s*',' ',p.read_text()).splitlines():
   s=line.strip()
   if not s or s.startswith('*'):continue
   if s.lower().startswith('.subckt'):
    words=s.split();cut=next((i for i,x in enumerate(words) if x.lower()=='params:'),len(words));current=words[1].lower();defs[current]={'ports':[x.lower() for x in words[2:cut]],'lines':[]}
   elif s.lower().startswith('.ends'):current=None
   elif current:defs[current]['lines'].append(s)
 return defs

def inventory(work,route,ports):
 defs=definitions(work);devices=[];nodes=set()
 def expand(sub,mapping,prefix):
  def node(x):
   x=x.lower();return '0' if x=='0' else mapping.get(x,prefix+'.'+x)
  for line in defs[sub]['lines']:
   p=line.split();kind=p[0][0].upper()
   if kind=='X' and len(p)>5 and p[5].lower() in ['nfet_03v3','pfet_03v3','nfet_06v0','pfet_06v0']:
    ns=[node(x) for x in p[1:5]];nodes.update(ns);devices.append({'instance':prefix+'.'+p[0].lower(),'nodes':ns,'model':p[5].lower()})
   elif kind=='X':
    nested=next((x.lower() for x in p[1:] if x.lower() in defs),None)
    if nested:
     newmap=dict(zip(defs[nested]['ports'],[node(x) for x in p[1:1+len(defs[nested]['ports'])]]));expand(nested,newmap,prefix+'.'+p[0].lower())
    elif len(p)>4 and p[4].lower()=='ppolyf_u_1k_6p0':nodes.update(node(x) for x in p[1:4])
    else:raise ValueError('Unknown instance '+line)
   elif kind in 'RCLV':nodes.update(node(x) for x in p[1:3])
 expand('fair_'+route.lower(),dict(zip(defs['fair_'+route.lower()]['ports'],ports)),'xdrv')
 return devices,sorted(nodes-{'0'})

def pwl(values,ui,high,edge,skew=0):
 points=[(0,values[0]*high)]
 for i in range(1,len(values)):
  if values[i]!=values[i-1]:
   t=i*ui+skew;points += [(t,values[i-1]*high),(t+edge,values[i]*high)]
 points.append((len(values)*ui+max(skew,0),values[-1]*high))
 return 'PWL('+ ' '.join(f'{t:.16g} {v:.16g}' for t,v in points)+')'

def deck(work,case):
 m=verify(work);rte=case['route'];corner=case.get('corner','typical');vdd=case.get('vdd_V',3.3);params=dict(m['parameters'][rte]);params.update(case.get('parameters',{}));f=work/'inputs';kind=case.get('kind','transient');gnd='diegnd' if case.get('ground_package') else '0'
 assert kind in ['dc','transient'],'Unsupported analysis kind'
 assert case.get('pulse_rail') in [None,'VIN','VDD'],'Unsupported pulse rail'
 if kind!='dc':assert 'stimulus_sha256' in m,'Transient requires frozen stimulus'
 ports=['d0','d1','out','vin','vdd','vref',gnd,'disable']
 devices,nodes=inventory(work,rte,ports);source_values={'VIN':case.get('vin_V',5.),'VDD':vdd,'VREF':2.5*(1+case.get('reference_error',0)),'VLED':case.get('vled_V',5.),'VDISABLE':0.}
 lines=[]
 for name,target,res,ind,cap in [('VIN','vin',.25,.5e-9,100e-9),('VDD','vdd',1.,2e-9,100e-9)]:
  value=source_values[name]
  if case.get('pulse_rail')==name:
   value=f'PULSE({value} {value+case.get("pulse_V",.05)} 200n 2n 2n 20n 800n)'
  lines += [f'{name} {name.lower()}_src 0 {value}',f'R{name} {name.lower()}_src {name.lower()}_p {res}',f'L{name} {name.lower()}_p {target} {ind}',f'RC{name} {target} {name.lower()}_c .2',f'C{name} {name.lower()}_c {gnd} {cap}']
 lines += [f'VREF vref_src 0 {source_values["VREF"]}',f'RREF vref_src vref .2',f'VLED led_src 0 {source_values["VLED"]}',f'RLEDSRC led_src led_a .25','VDISABLE disable 0 0']
 if gnd!='0':lines+=['RGND diegnd gndp 1','LGND gndp 0 2n']
 if kind=='dc':
  level=case['level'];d1,d0=([[0,0],[0,1],[1,1],[1,0]][level] if rte=='C' else [0,level]);drive=[str(d0*vdd),str(d1*vdd)];command='op';frame=None
 else:
  st=json.loads((work/'stimulus.json').read_text());eta=st['eta'];line_rate=case['net_rate_Gbps']*1e9/eta;b=st['bits'];sym_ui=(2 if rte=='C' else 1)/line_rate
  d0=b[1::2] if rte=='C' else b;d1=b[::2] if rte=='C' else [0]*len(b)
  drive=[pwl(d0,sym_ui,vdd,20e-12),pwl(d1,sym_ui,vdd,20e-12,case.get('skew_s',0))]
  frame=len(b)/line_rate;step=sym_ui/case.get('steps_per_symbol',40);command=f'tran {step:.16g} {frame:.16g} 0 {step:.16g}'
 for i,value in enumerate(drive):lines += [f'VD{i} data{i}_src 0 {value}',f'RD{i} data{i}_src d{i} 100']
 passparams=' '.join(f'{k}={v:.16g}' for k,v in params.items())
 vectors=[('iled_cond','i(VSENSE)'),('led_a','v(led_a)'),('led_k','v(led_k)'),('out','v(out)'),('d0','v(d0)'),('d1','v(d1)')]
 # Full internal nodes stay in the solver for native stress extrema. Export only
 # common observable/port traces after linearize, to bound storage without changing solve.
 if case.get('export_full_native') or kind=='dc':
  for n in nodes:
   if n not in [x for x,y in vectors]:vectors.append((n,f'v({n})'))
 sources={'VIN':'vin_src','VDD':'vdd_src','VREF':'vref_src','VLED':'led_src','VD0':'data0_src','VD1':'data1_src','VDISABLE':'disable'}
 for name,n in sources.items():vectors += [(name+'_voltage',f'v({n})'),(name+'_current',f'i({name})')]
 native=[]
 if kind!='dc' and not case.get('export_full_native'):
  for k,(name,node) in enumerate(sources.items()):
   native += [f'let fp=-v({node})*i({name})','let q0=fp[0,length(fp)-2]','let q1=fp[1,length(fp)-1]','let dt=time[1,length(time)-1]-time[0,length(time)-2]',f'let fe{k}c=mean(dt*abs(q0*q1)/(2*(abs(q0)+abs(q1)+1e-300))*(q0*q1<0))*(length(fp)-1)','let fe=integ((fp+abs(fp))/2)',f'let fe{k}p=fe[length(fe)-1]-fe{k}c','unlet fe','let fe=integ((abs(fp)-fp)/2)',f'let fe{k}r=fe[length(fe)-1]-fe{k}c','unlet fe',f'print fe{k}p fe{k}r fe{k}c',f'unlet fp q0 q1 dt fe{k}p fe{k}r fe{k}c']
  vnode=lambda n:'0' if n=='0' else f'v({n})'
  for k,d in enumerate(devices):
   for j,(i,l) in enumerate(( (i,l) for i in range(4) for l in range(i+1,4) )):
    native += [f'let fs{k}x{j}=vecmax(abs({vnode(d["nodes"][i])}-{vnode(d["nodes"][l])}))',f'print fs{k}x{j}',f'unlet fs{k}x{j}']
   sign=1 if d['model'].startswith('nfet') else -1
   for j in [0,2]:native += [f'let fb{k}x{j}=vecmax({sign}*({vnode(d["nodes"][3])}-{vnode(d["nodes"][j])}))',f'print fb{k}x{j}',f'unlet fb{k}x{j}']
  # Export full native time/current; no downsampling enters the receiver.
  vectors=[('iled_cond','i(VSENSE)')]
 text=f'''Fair matched schematic {case['name']}
.include "{f/'pdk/design.ngspice'}"
.param sw_stat_global=0 sw_stat_mismatch=0
.lib "{f/'pdk/sm141064.ngspice'}" {corner}
.lib "{f/'pdk/sm141064.ngspice'}" res_{case.get('res_corner',corner)}
.temp {case.get('temp_C',27)}
.include "{f/'common.spice'}"
.include "{f/('route_'+rte.lower()+'.spice')}"
.include "{f/'led.spice'}"
{chr(10).join(lines)}
XDRV {' '.join(ports)} fair_{rte.lower()} {passparams}
XLED led_a led_dc_k lin2026_yellow20_dc
VSENSE led_dc_k led_k 0
CLED led_a led_k {case.get('led_cap_F',200e-15):.16g}
RPKG led_k pk 1
LPKG pk out .5n
.options reltol={case.get('reltol',1e-5)} abstol=1e-13 vntol=1e-7 chgtol=1e-16 method={case.get('method','gear')} maxord=2
.control
set numdgt=15
set wr_singlescale
set wr_vecnames
{command}
{chr(10).join(native)}
wrdata waveform.dat {' '.join(x[1] for x in vectors)}
quit
.endc
.end
'''
 return text,{'vectors':{k:i+1 for i,(k,e) in enumerate(vectors)},'devices':devices,'sources':sources,'parameters':params,'frame_duration_s':frame,'physical_level':m['common']['physical_level'],'export_mode':'full-native' if case.get('export_full_native') or kind=='dc' else 'native-led+native-energy-stress'}

def signed_integrals(t,p):
 if len(t)<2:return {'positive_J':0.,'returned_J':0.,'net_J':0.}
 dt=np.diff(t);a=p[:-1];b=p[1:];same=a*b>=0;positive=float(np.sum(np.where(same& (a+b>=0),.5*(a+b)*dt,0.)));returned=float(np.sum(np.where(same& (a+b<0),-.5*(a+b)*dt,0.)))
 cross=~same
 if np.any(cross):
  q=dt[cross]*np.abs(a[cross])/(np.abs(a[cross])+np.abs(b[cross]));area_a=.5*a[cross]*q;area_b=.5*b[cross]*(dt[cross]-q)
  positive+=float(np.maximum(area_a,0).sum()+np.maximum(area_b,0).sum());returned+=float(-np.minimum(area_a,0).sum()-np.minimum(area_b,0).sum())
 return {'positive_J':positive,'returned_J':returned,'net_J':positive-returned}

def evaluate(raw,meta,case,work):
 verify(work)
 a=np.loadtxt(raw,skiprows=1,ndmin=2);assert np.isfinite(a).all();t=a[:,0];v=meta['vectors'];values=lambda n:np.zeros(len(t)) if n=='0' else a[:,v[n]]
 scalar={k:float(x) for k,x in re.findall(r'^([a-z][a-z0-9]*)\s*=\s*([-+0-9.eE]+)\s*$',(raw.parent/'ngspice.log').read_text(),flags=re.M)}
 compact=meta.get('export_mode')=='native-led+native-energy-stress'
 result={'sample_count':len(t),'i_led_A':float(a[-1,v['iled_cond']]),'energy':{},'stress':[]}
 for k,name in enumerate(meta['sources']):
  if compact:
   ep,er=scalar[f'fe{k}p'],scalar[f'fe{k}r'];result['energy'][name]={'positive_J':ep,'returned_J':er,'net_J':ep-er,'native_clipped_trapezoid_crossing_correction_J':scalar[f'fe{k}c']}
  else:
   power=-a[:,v[name+'_voltage']]*a[:,v[name+'_current']]
   result['energy'][name]={'DC_power_W':float(power[-1])} if case.get('kind')=='dc' else signed_integrals(t,power)
 for k,d in enumerate(meta['devices']):
  limit=3.63 if '03v3' in d['model'] else 6.
  if compact:mx=max(scalar[f'fs{k}x{j}'] for j in range(6));body=max(scalar[f'fb{k}x{j}'] for j in [0,2])
  else:
   ds=[values(n) for n in d['nodes']];mx=max(float(np.abs(ds[i]-ds[j]).max()) for i in range(4) for j in range(i+1,4));body=max(float((ds[3]-ds[i] if d['model'].startswith('nfet') else ds[i]-ds[3]).max()) for i in [0,2])
  result['stress'].append({'instance':d['instance'],'model':d['model'],'max_pair_V':mx,'limit_V':limit,'passed':mx<=limit,'max_body_forward_V':body})
 result['device_voltage_passed']=all(x['passed'] for x in result['stress']);result['max_body_forward_V']=max(x['max_body_forward_V'] for x in result['stress'])
 if case.get('kind')=='dc':
  target=([25,50,75,100] if case['route']=='C' else [25,100])[case['level']]*1e-6
  result.update(target_A=target,current_error_percent=100*(result['i_led_A']/target-1),DC_power_W=sum(x['DC_power_W'] for x in result['energy'].values()))
 else:
  st=json.loads((work/'stimulus.json').read_text());rx=module(work/'inputs/receiver.py','fair_rx_case').analyze(t,a[:,v['iled_cond']],st,case['route'],case['net_rate_Gbps']);result['receiver']=rx
  totals={key:sum(x[key] for x in result['energy'].values()) for key in ['positive_J','returned_J','net_J']};totals.update({key.replace('_J','_pJ_per_payload_bit'):value/4096*1e12 for key,value in list(totals.items())});result['total_energy']=totals
  result['mean_LED_current_A']=float(np.trapezoid(a[:,v['iled_cond']],t)/(t[-1]-t[0]));result['passed']=bool(result['device_voltage_passed'] and rx['passed'])
 return result

def run(work,case):
 work=Path(work).resolve();verify(work);folder=work/'cases'/case['name'];assert not folder.exists(),'Refuse overwrite: '+str(folder)
 if shutil.disk_usage(ROOT).free<5*1024**3:raise RuntimeError('Storage guard: minimum5GiB free')
 used=sum(p.stat().st_size for p in BUILD.rglob('*') if p.is_file());assert used<2*1024**3,'Stage2GiB budget guard'
 folder.mkdir(parents=True);text,meta=deck(work,case);(folder/'testbench.spice').write_text(text);emit(folder/'case.json',case)
 source=EXECUTION_SOURCE;execpath=work/'execution-sources'/('run-'+EXECUTION_SHA+'.py');execpath.parent.mkdir(exist_ok=True)
 if not execpath.exists():execpath.write_bytes(source)
 start=time.time();timed_out=False
 try:
  proc=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,capture_output=True,text=True,timeout=case.get('timeout_s',300));output=proc.stdout+proc.stderr;code=proc.returncode
 except subprocess.TimeoutExpired as err:
  timed_out=True;output='TIMEOUT after '+str(case.get('timeout_s',300))+'s\n'+''.join(x.decode(errors='replace') if isinstance(x,bytes) else (x or '') for x in [err.stdout,err.stderr]);code=None
 (folder/'ngspice.log').write_text(output);raw=folder/'waveform.dat'
 rec={'case':case,'metadata':meta,'runner_sha256':EXECUTION_SHA,'deck_sha256':sha(folder/'testbench.spice'),'exit_code':code,'timed_out':timed_out,'elapsed_s':time.time()-start,'simulation_ok':code==0 and raw.exists()}
 if rec['simulation_ok']:
  try:rec['metrics']=evaluate(raw,meta,case,work)
  except Exception as err:rec['analysis_error']=repr(err)
 if raw.exists():
  before=sha(raw);gz=folder/'waveform.dat.gz'
  with raw.open('rb') as src,gzip.open(gz,'wb',compresslevel=5) as dst:shutil.copyfileobj(src,dst)
  h=hashlib.sha256()
  with gzip.open(gz,'rb') as f:
   for b in iter(lambda:f.read(2**20),b''):h.update(b)
  assert h.hexdigest()==before;rec.update(raw_sha256=before,gzip_sha256=sha(gz),gzip_bytes=gz.stat().st_size);raw.unlink()
 emit(folder/'result.json',rec);return rec

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,required=True);ap.add_argument('--init',action='store_true');ap.add_argument('--case',type=Path);a=ap.parse_args()
 if a.init:init(a.work)
 if a.case:
  r=run(a.work,json.loads(a.case.read_text()));print(json.dumps({'case':r['case']['name'],'simulation_ok':r['simulation_ok'],'metrics':r.get('metrics',{}).get('i_led_A')},indent=2))
if __name__=='__main__':main()
