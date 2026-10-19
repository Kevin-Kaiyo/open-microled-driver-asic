"""Select reproducible validated solver experiments without overwriting failures."""
from pathlib import Path
import hashlib,json,shutil,re
import numpy as np
ROOT=Path(__file__).resolve().parents[2];E=ROOT/'evidence/analog-v3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 bp=E/'pex-r5-final-bleed10M/summary.json';gp=E/'pex-r5-bleed10M-startup-grid/summary.json';base=json.loads(bp.read_text());grid=json.loads(gp.read_text());assert base['dut_sha256']==grid['dut_sha256']
 for k in ['cc_pf','csense_pf','bleed_ohm']:assert base[k]==grid[k]
 assert len(base['results'])==17 and len(grid['results'])==10
 by={r['name']:r for r in grid['results']};selected=[];d=E/'final';d.mkdir(exist_ok=True);manifest=[]
 for original in base['results']:
  isstart=original['kind']=='startup';src=grid if isstart else base;sp=gp if isstart else bp;row=dict(by[original['name']] if isstart else original);raw=ROOT/src['raw_directory']/row['name'];deck=(raw/'testbench.spice').read_text()
  if isstart:
   assert 'non-increasing PWL' not in (raw/'ngspice.log').read_text();m=re.search(r'VREFRAIL refrail 0 PWL\((.*?)\)',deck,re.S);pairs=np.asarray(list(map(float,m[1].replace('+',' ').split()))).reshape(-1,2);v={'tt':3.3,'ss':2.97,'ff':3.63}[row['envelope']];wanted=v*np.minimum(pairs[:,0]/(row['ramp_ns']/1e9),1);assert np.all(np.diff(pairs[:,0])>0) and np.max(abs(pairs[:,1]-wanted))<1e-14
  paths={n:dict(path=str((raw/n).relative_to(ROOT)),sha256=sha(raw/n)) for n in ['testbench.spice','waveform.dat','rtl-events.csv','ngspice.log']}
  row.update(source_summary_path=str(sp.relative_to(ROOT)),source_summary_sha256=sha(sp),source_raw_directory=str(raw.relative_to(ROOT)),source_artifacts=paths,selected_solver_reason='Same source PWL function with integer-tick collinear local grid and1ps TSTEP; dense first-step/corner resolution.' if isstart else 'Ordinary full-window solver; waveform convergence checked on d1 fine/coarse pair.')
  selected.append(row);manifest.append(dict(name=row['name'],**paths))
 result=dict(base);result.update(tag='selected-r5-cc30-csense30-bleed10M',results=selected,selected_solver_rules={'startup':'All10 startup cases are from the full40us integer-tick0.1ps local-grid run, not a mixture cherry-picked per passing result. Linear rail function unchanged.','normal_fault':'All3 fault and4normal cases are from original full17case run. Their circuit, rail, resistor and capacitor inputs are identical to startup-grid run.','scope':'Actual39MOS fullRC macro+actualRTL pin replay; not full system silicon qualification.','failed_runs_preserved':[str(bp.relative_to(ROOT)),'evidence/analog-v3/pex-r4-cc3/summary.json','evidence/analog-v3/pex-r5-bleed10M-fftrial/summary.json']},source_runs={str(bp.relative_to(ROOT)):sha(bp),str(gp.relative_to(ROOT)):sha(gp)},passed=all(r['passed'] for r in selected) and all(r['passed'] for r in base['dc_results']),raw_directory_note='Default raw_directory is original full suite; use each row source_raw_directory for selected startup waves.',selection_script_sha256=sha(Path(__file__)))
 (d/'summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');(d/'source-artifacts.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'passed':result['passed'],'count':len(selected),'max_startup_a':max(r['startup']['branch_max_abs_a'] for r in selected if r['kind']=='startup'),'failed':[r['name'] for r in selected if not r['passed']]}))
if __name__=='__main__':main()
