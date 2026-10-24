#!/usr/bin/env python3
"""Single-variable output ESR + closed-loop DC sign checks; not invalid AC PM based."""
import datetime,json
import experiment as e
import run as r
import validate as v
from startup_metrics import analyze

def main():
 e.freeze(e.WORK)
 cs=[e.make('esr100_'+kind,dc_bit=1,cout_esr_ohm=100,startup={'kind':kind,'stop_s':100e-6,'maxstep_s':10e-9}) for kind in ['ramp','loadstep']]
 for q,co,t,vdd in [('TT','typical',27,3.3),('SS','ss',125,2.95),('FF','ff',-40,3.65)]:
  for bit in [0,1]:
   for sign in [-1,1]:cs.append(e.make('dc_sign_'+q+'_'+str(sign),co,t,vdd,dc_bit=bit,anchor_error=sign*.002))
 plan=e.WORK/'plan-stability-diagnostics.json';assert not plan.exists()
 r.emit(plan,{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs,'hypotheses':['IncreaseonlyCOUTESR .2→100Ω withCOUT10n/Cc3p, introduceESRzero~159kHz; do not useinvalidseriesACPM asbasis','Anchor±.2% yieldsVSET±1mV; verifyclosedloopDCderivativepositive~6.6 forLDO and~50uA/V forVI'],'invalid_AC':'evidence/nrz-reference-v2/ac-base-r1.json PM is an invalid diagnostic pending returnratio validation; sign/phase/multicross artifacts prevent stabilityclaim'})
 rows=[]
 for c in cs:
  res=r.run_case(e.WORK,c)
  row=analyze(e.WORK,c,res) if c.get('startup') else v.analyze(e.WORK,res)
  rows.append(row);print(json.dumps(row),flush=True)
 r.emit(r.EVIDENCE/'stability-diagnostics.json',{'rows':rows})
if __name__=='__main__':main()
