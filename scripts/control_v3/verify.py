from pathlib import Path
import hashlib,json,os,re,subprocess,sys
from run import ROOT,B,E,IMAGE,run,sha
F=B/'physical/final'; out=B/'verification';out.mkdir(exist_ok=True)
mode=sys.argv[1]
if mode=='sta':
 env=dict(os.environ,LIMA_HOME=str(ROOT/'build/physical-flow/lima'))
 results=[]
 for c in json.loads((B/'inputs/config.json').read_text())['STA_CORNERS']:
  cmd=['limactl','shell','asic','nerdctl','run','--rm','-v',f'{ROOT}:{ROOT}','-w',str(ROOT),'-e',f'ASICFLOW_ROOT={ROOT}','-e',f'ASICFLOW_RUN={B}/physical','-e',f'ASICFLOW_CORNER={c}',IMAGE,'openroad','-no_init','-exit',str(ROOT/'scripts/control_v3/sta.tcl')]
  text=run(cmd,out/(c+'.log'),env)
  assert 'R2R_END_HOLD' in text and 'ASYNC_CHECK_END' in text and '[ERROR' not in text
  setup=text.split('R2R_BEGIN_SETUP')[1].split('R2R_END_SETUP')[0]; hold=text.split('R2R_BEGIN_HOLD')[1].split('R2R_END_HOLD')[0]
  ns=lambda t:[float(x) for x in re.findall(r'([-\d.]+)\s+slack \(\w+\)',t)]
  a,b=ns(setup),ns(hold); assert a and b and min(a)>=0 and min(b)>=0
  results.append({'corner':c,'r2r_setup_min_ns':min(a),'r2r_hold_min_ns':min(b),'log_sha256':sha(out/(c+'.log'))})
 (E/'sta.json').write_text(json.dumps({'passed':True,'corners':results,'scope':'Extracted digital macro. SDC inputs assumed 200 ns synchronous arrivals. Does not prove arbitrary asynchronous release metastability safety.'},indent=2)+'\n')
elif mode=='gate':
 pdk=ROOT/'build/layout/pdk/gf180mcuD'
 lock=json.loads((ROOT/'scripts/digital/library-lock.json').read_text())
 paths=[pdk/n for n in lock['files'] if n.endswith('.v')]
 wrapper=out/'cells.v'; wrapper.write_text('`timescale 1ns/1ps\n'+''.join(f'`include "{p}"\n' for p in paths))
 cmd=['iverilog','-g2012','-DFUNCTIONAL','-s','tb_safety','-o',str(out/'gate.vvp'),str(wrapper),str(F/'nl/pixel_control_v3.nl.v'),str(ROOT/'scripts/control_v3/tb_control.v')]
 run(cmd,out/'gate-compile.log')
 results=[]
 for d,f,s in [(0,-1,-1),(1,-1,-1),(64,-1,-1),(256,-1,-1),(511,-1,-1),(256,520125,-1),(256,520125,519900),(64,520125,-1),(1,520125,-1),(0,520125,-1)]:
  name=f'd{d}-f{f}-s{s}'; csv=out/(name+'.csv')
  text=run(['vvp',str(out/'gate.vvp'),f'+DUTY={d}',f'+FAULT_NS={f}',f'+STOP_NS={s}',f'+OUT={csv}'],out/(name+'.log'))
  assert 'SAFETY_CASE_PASS' in text
  results.append({'case':name,'passed':True,'log_sha256':sha(out/(name+'.log'))})
 (E/'gate.json').write_text(json.dumps({'passed':True,'cases':results,'netlist_sha256':sha(F/'nl/pixel_control_v3.nl.v'),'scope':'Functional postroute netlist; zero delay; no analog/metastability claim'},indent=2)+'\n')
else:raise ValueError(mode)
