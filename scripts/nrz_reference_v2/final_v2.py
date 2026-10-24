#!/usr/bin/env python3
"""Selected integrated-layout VI reference: immutable, bounded electrical matrix."""
from pathlib import Path
import argparse,datetime,json,shutil
import run as r
import validate as v
import vi_startup
OLD=r.ROOT/'build/highspeed-nrz-robustness/selected-a8-b58-r4'
WORK=r.BUILD/'selected-final-r2'
PVT=[('TT','typical',27,3.3),('SS','ss',125,2.95),('FF','ff',-40,3.65)]
def freeze(core,contract):
 if WORK.exists():return v.verify(WORK)
 WORK.mkdir(parents=True);inp=WORK/'inputs'
 for name in ['legacy/run.py','legacy/metrics.py','legacy/analyze.py','led.spice','pdk/design.ngspice','pdk/sm141064.ngspice','physical/B-AFTER.spice','physical/B-contract.json']:
  dest=inp/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(OLD/'inputs'/name,dest)
 shutil.copy2(OLD/'stimulus.json',WORK/'stimulus.json');shutil.copy2(core,inp/'physical/B-reference-RC.spice');shutil.copy2(contract,inp/'physical/integrated-contract.json')
 for p in Path(__file__).parent.glob('*.py'):
  dest=inp/'pipeline'/p.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest)
 old=json.loads((OLD/'manifest.json').read_text());selected={'path':'physical/B-reference-RC.spice','sha256':r.sha(core),'reference_v2':True,'direct_raw':True,'disable_clamp':True,'switched_keeper':True,'keeper_ohm':1.8e6,'rdummy_ohm':50000,'reference_control':'12MOS VI, external DISABLE clamp and conditional keeper, integrated with old B in real GDS/fullRC','source_blocks':[{'path':r.rel(core),'sha256':r.sha(core)},{'path':r.rel(contract),'sha256':r.sha(contract)}],'top_level_interconnect':'Actual routed integrated top, all extracted R/C retained'}
 m={'created':datetime.datetime.now().isoformat(),'base_commit':'112ba95969ac6a2141c305324ea694e7b96c0765','parent_manifest_sha256':r.sha(OLD/'manifest.json'),'common':old['common'],'variants':{'B':{'BASELINE':old['variants']['B']['AFTER'],'REFERENCE':selected}},'stimulus_sha256':r.sha(WORK/'stimulus.json'),'source_hashes':{str(p.relative_to(inp)):r.sha(p) for p in inp.rglob('*') if p.is_file()},'scope':{'rate_Gbps':.5,'receiver':'Original PRBS/training/validation and62.5uA fixedthreshold unchanged','LED':'Original measuredstatic model,200fF; no temperature fit','energy':'Actual all source v(t)*i(t) plus DATA, including RAW,VREF and DISABLE; external reference internalIq separately budgeted','terminal_screen':'03v3 sixpairs3.63V and06v0 sixpairs6.0V; gatepairs separately, not SOA signoff','board_boundary':'External2.5V anchor,200k/50k divider,RSET20k,RIBIAS100k,RDUMMY50k,RKEEP1.8M,IN2-to-boardGND150pF,VINinput100nF ESR.2,RAWinput.25ohm/.5nH,GPIO100ohm. Not onchipPEX.','startup_contract':'ExternalDISABLE3.3V asserted before supplies; release20us after1us anchor ramp begins; holdLED<=2uA, reach100uA±5% within2us afterrelease. Not autonomousPOR or zero-current off.','tolerance':'Deterministic independent resistor initialerror and signedlinearTC; genericanchor initialerror/linearTC are engineering assumptions, not a vendor boxTC guarantee','resources':{'retained_build_budget_GiB':2,'free_floor_GiB':5}}}
 m['scope']['component_selection']=json.loads((r.EVIDENCE/'final-scope-amendment-conditional-keeper.json').read_text())['selected_BOM']
 m['scope']['keeper_interface']='RKEEP OUT-to-KRET1.8Mohm external; onchip06MOS KRET-to-VSS controlled byDISABLE. Conducts duringhold, disconnected duringnormalNRZ.'
 r.emit(WORK/'manifest.json',m);return v.verify(WORK)
def case(label,co='typical',t=27,vdd=3.3,**kw):
 return v.case(WORK,'B',label,co,t,vdd,variant='REFERENCE',compensation='shunt',vi_comp_F=kw.pop('vi_comp_F',150e-12),**kw)
def joint(label):
 if label=='SS':return {'resistor_errors':{'RSET':.01,'RDUMMY':.01},'resistor_tc_ppm':{'RSET':100,'RDUMMY':100},'anchor_error':-.0005,'anchor_tc_ppm':-30,'vin_V':4.75}
 return {'resistor_errors':{'RSET':-.01,'RDUMMY':-.01},'resistor_tc_ppm':{'RSET':100,'RDUMMY':100},'anchor_error':.0005,'anchor_tc_ppm':-30,'vin_V':5.25}
def precision_joint(label):
 kw=joint(label);kw['resistor_errors']['RSET']=.001 if label=='SS' else -.001;kw['resistor_tc_ppm']['RSET']=25
 return kw
def plan(stage):
 cs=[]
 if stage=='dc':
  for label,co,t,vd in PVT:
   for b in [0,1]:cs.append(case('DC_'+label,co,t,vd,dc_bit=b))
   for resistor in ['RSET','RDUMMY']:
    for error in [-.01,.01]:
     for tc in [-100,100]:
      for b in [0,1]:cs.append(case(f'DC_{label}_{resistor}_{error}_{tc}',co,t,vd,dc_bit=b,resistor_errors={resistor:error},resistor_tc_ppm={resistor:tc}))
   for voltage in [4.75,5.25]:
    for b in [0,1]:cs.append(case(f'DC_{label}_RAW{voltage}',co,t,vd,dc_bit=b,vin_V=voltage))
  for resistor in ['RSET','RDUMMY']:
   for error in [-.05,.05]:
    for b in [0,1]:cs.append(case(f'DC_NEG5_{resistor}_{error}',dc_bit=b,resistor_errors={resistor:error}))
  for label,co,t,vd in PVT[1:]:
   for sign in [-1,1]:
    for b in [0,1]:cs.append(case(f'DC_{label}_anchor{sign}',co,t,vd,dc_bit=b,anchor_error=sign*.0005,anchor_tc_ppm=sign*30))
   for b in [0,1]:cs.append(case(f'DC_{label}_joint',co,t,vd,dc_bit=b,**joint(label)))
   for b in [0,1]:cs.append(case(f'DC_{label}_precision_joint',co,t,vd,dc_bit=b,**precision_joint(label)))
   for error in [-.001,.001]:
    for tc in [-25,25]:
     for b in [0,1]:cs.append(case(f'DC_{label}_precision_RSET_{error}_{tc}',co,t,vd,dc_bit=b,resistor_errors={'RSET':error},resistor_tc_ppm={'RSET':tc}))
  for sign in [-1,1]:
   for b in [0,1]:cs.append(case(f'DC_divider{sign}',dc_bit=b,resistor_errors={'RDIVH':sign*.001,'RDIVL':-sign*.001}))
  for b in [0,1]:cs.append(case('DC_anchor_Rout100',dc_bit=b,anchor_rout_ohm=100))
 elif stage=='nrz':
  for label,co,t,vd in PVT:cs.append(case('NRZ_'+label,co,t,vd))
  for label,co,t,vd in PVT[1:]:cs.append(case('NRZ_'+label+'_precision_joint',co,t,vd,**precision_joint(label)))
  pulse=lambda amplitude:{'kind':'pulse','amplitude_V':amplitude,'delay_ui':300,'edge_ui':1,'width_ui':32,'period_ui':127}
  for rail,amp in [('VRAW',.25),('VLED',.05),('VDD',.05)]:cs.append(case('NRZ_FF_'+rail+'pulse','ff',-40,3.65,rail_profiles={rail:pulse(amp)}))
  cs.append(case('NRZ_FF_supply_package','ff',-40,3.65,supply_package={'r_vdd_ohm':1.,'l_vdd_H':2e-9,'r_vss_ohm':1.,'l_vss_H':2e-9},r_vin_ohm=1.,l_vin_H=2e-9,r_pkg=4.,l_pkg=2e-9))
  cs.append(case('NRZ_FF_numerical','ff',-40,3.65,steps_per_ui=80,reltol=2e-6,method='trap'))
 elif stage=='startup':
  start={'stop_s':100e-6,'maxstep_s':10e-9,'disable_release_s':20e-6}
  for label,co,t,vd in PVT:cs.append(case('startup_'+label,co,t,vd,dc_bit=1,startup=start))
  cs.append(case('startup_late_anchor',dc_bit=1,startup=start|{'anchor_delay_s':30e-6,'disable_release_s':50e-6}))
  cs.append(case('startup_early_release_NEG',dc_bit=1,startup=start|{'anchor_delay_s':30e-6}))
  for mult in [.8,1.2]:cs.append(case(f'startup_FF_comp{mult}','ff',-40,3.65,dc_bit=1,vi_comp_F=150e-12*mult,startup=start))
  cs.append(case('startup_FF_passive_extreme','ff',-40,3.65,dc_bit=1,cout_F=80e-9,cout_esr_ohm=1.,resistor_errors={'RKEEP':.01},resistor_tc_ppm={'RKEEP':-100},startup=start))
  restart={'VRAW':[[0,5],[20e-6,5],[21e-6,0],[23e-6,0],[24e-6,5]],'VLED':[[0,5]],'VDD':[[0,3.65]],'VREF':[[0,2.5]],'VDISABLE':[[0,0],[19.9e-6,0],[20e-6,3.3],[44e-6,3.3],[44.1e-6,0]]}
  cs.append(case('restart_FF_residual_LED_anchor','ff',-40,3.65,dc_bit=1,startup=start|{'initial_op':True,'rail_pwl':restart,'disable_release_s':44e-6,'hold_windows_s':[[20.2e-6,44e-6]]}))
  cs.append(case('startup_FF_numerical','ff',-40,3.65,dc_bit=1,reltol=2e-6,method='trap',startup=start|{'maxstep_s':5e-9}))
  cs.append(case('startup_FF_comp_package','ff',-40,3.65,dc_bit=1,comp_package={'r_ohm':1.,'l_H':5e-9,'esr_ohm':.5},startup=start))
 elif stage=='slow':
  for label,co,t,vd in PVT:cs.append(case('long_loadstep_'+label,co,t,vd,dc_bit=1,startup={'kind':'loadstep','stop_s':100e-6,'maxstep_s':10e-9}))
  for name,rail,startvalue,lowvalue in [('RAW','VRAW',5,4.75),('anchor','VREF',2.5,2.475)]:
   profiles={'VRAW':[[0,5]],'VLED':[[0,5]],'VDD':[[0,3.65]],'VREF':[[0,2.5]],'VDISABLE':[[0,0]]}
   profiles[rail]=[[0,startvalue],[20e-6,startvalue],[20.01e-6,lowvalue],[40e-6,lowvalue],[40.01e-6,startvalue]]
   cs.append(case('long_'+name+'_drop_recover','ff',-40,3.65,dc_bit=1,startup={'kind':'disturbance','initial_op':True,'rail_pwl':profiles,'stop_s':100e-6,'maxstep_s':10e-9}))
 else:raise ValueError(stage)
 return cs
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--core',type=Path);ap.add_argument('--contract',type=Path);ap.add_argument('--stage',choices=['freeze','dc','nrz','startup','slow'],required=True);args=ap.parse_args()
 if args.stage=='freeze':freeze(args.core,args.contract);return
 v.verify(WORK);cs=plan(args.stage);path=WORK/f'plan-{args.stage}.json'
 if path.exists():assert json.loads(path.read_text())['cases']==cs
 else:r.emit(path,{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs,'source_sha256':r.sha(__file__),'acceptance':'Original RX thresholds forNRZ; DC current target deviations reported separately from device screens; startup hold/ready/fullpeak/latewindow separate.'})
 rows=[]
 for c in cs:
  result=r.run_case(WORK,c)
  if args.stage=='slow':row=vi_startup.analyze_slow(WORK,c,result)
  else:row=vi_startup.analyze(WORK,c,result) if c.get('startup') else v.analyze(WORK,result)
  rows.append(row);print(json.dumps(row),flush=True)
 r.emit(r.EVIDENCE/f'{WORK.name}-{args.stage}.json',{'rows':rows,'plan_sha256':r.sha(path),'manifest_sha256':r.sha(WORK/'manifest.json')})
if __name__=='__main__':main()
