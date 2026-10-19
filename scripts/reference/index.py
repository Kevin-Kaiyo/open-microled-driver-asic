"""Publish a candidate index and explicit coupled-DC conditions from raw decks."""
from pathlib import Path
import json,re
import numpy as np
from probe import sha
ROOT=Path(__file__).resolve().parents[2];E=ROOT/'evidence/reference'
def main():
    summary=json.loads((E/'servo-summary.json').read_text());work=ROOT/summary['workdir'];conditions=[]
    for folder in sorted(work.glob('coupled-*')):
        if not folder.is_dir():continue
        deck=(folder/'case.spice').read_text();data=np.loadtxt(folder/'data.dat',skiprows=1,ndmin=2)[0]
        val=lambda pattern:float(re.search(pattern,deck,re.M)[1])
        vset=val(r'^VSET vset 0 ([^\n]+)$');rset=val(r'^RSET sense 0 ([^\n]+)$')
        conditions.append(dict(case=folder.name,corner=re.search(r'^\.lib sm141064.ngspice (\w+)$',deck,re.M)[1],
                               temperature_c=val(r'^\.temp (.+)$'),logic_v=val(r'^VDD vdd 0 (.+)$'),led_supply_v=val(r'^VLED led_a 0 (.+)$'),
                               pwm_v=val(r'^VPWM pwm 0 (.+)$'),vset_v=vset,rset_ohm=rset,vset_error_fraction=vset/.5-1,rset_error_fraction=rset/5000-1,
                               iout_a=float(data[1]),iref_a=float(data[2]),testbench_sha256=sha(folder/'case.spice'),raw_data_sha256=sha(folder/'data.dat'),
                               raw_case=str(folder.relative_to(ROOT))))
    assert len(conditions)==18
    (E/'servo-coupled-conditions.json').write_text(json.dumps(conditions,indent=2)+'\n')
    candidates={}
    for key,name in [('beta','beta'),('vset_servo','servo')]:
        value=json.loads((E/(name+'-summary.json')).read_text())
        candidates[key]=dict(summary=f'evidence/reference/{name}-summary.json',summary_sha256=sha(E/(name+'-summary.json')),
                             status=value['status'],validation=f'evidence/reference/{name}-validation.json')
    supplementary={name:dict(path='evidence/reference/'+name,sha256=sha(E/name)) for name in ['servo-coupled-conditions.json','servo-boundaries.json','junction-sensitivity.json','junction-zero-controls.json','sensitivity-validation.json']}
    (E/'summary.json').write_text(json.dumps(dict(status='two_candidates_and_boundary_audits_complete',candidates=candidates,supplementary=supplementary),indent=2)+'\n')
    print('Indexed two candidates, 18 explicit coupled DC conditions and finite boundary audits')
if __name__=='__main__':main()
