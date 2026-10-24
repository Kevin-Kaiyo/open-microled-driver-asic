#!/usr/bin/env python3
"""One-variable LDO compensation diagnostic; VI compensation unchanged."""
import datetime,json
import experiment as e
import run as r
from startup_metrics import analyze

def main():
 e.freeze(e.WORK)
 cs=[e.make('ldo30p_'+kind,dc_bit=1,ldo_ccomp_F=30e-12,startup={'kind':kind,'stop_s':100e-6,'maxstep_s':10e-9}) for kind in ['ramp','loadstep']]
 plan=e.WORK/'plan-ldo-compensation-30p.json'
 assert not plan.exists();r.emit(plan,{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs,'hypothesis':'ActualLDOloop underdamped with3p and10n; increase only LDO MillerC to30p tolowercrossover. VI unchanged3p. Baseline sameTT startup retained.','acceptance':{'vreg_envelope_after5us_loadstep_V':[3.234,3.366],'startup_final_vreg_V':[3.234,3.366],'last10us_pp_max_V':.033},'startup_current':'125uA boundstillassessed; LDOcompensationnotpresumedtosolveVIovershoot'})
 rows=[]
 for c in cs:
  row=analyze(e.WORK,c,r.run_case(e.WORK,c));rows.append(row);print(json.dumps(row),flush=True)
 r.emit(r.EVIDENCE/'ldo-compensation-30p.json',{'rows':rows})
if __name__=='__main__':main()
