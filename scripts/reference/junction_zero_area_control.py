"""Read actual zero-area BSIM junction currents for paired hard-initial controls."""
from pathlib import Path
import json,re,shutil,tempfile
import numpy as np
import probe as p
import servo as s
import run as b
ROOT=p.ROOT;E=ROOT/'evidence/reference'
DEVICES=['pbias','ptail','pd1','pd2','nd1','nd2','nstage','pload','preg','pout']
def main():
    main=json.loads((E/'servo-summary.json').read_text());base=ROOT/main['workdir']/'inputs'
    w=Path(tempfile.mkdtemp(prefix='junction-zero-controls-',dir=ROOT/'build/reference'));f=w/'inputs';shutil.copytree(base,f)
    shutil.copyfile(Path(__file__),f/'scripts/reference/junction_zero_area_control.py')
    p.REF=f/'analog/reference/vset_servo.spice';p.PDK=f/'pdk'
    old=p.run;vectors=[f'@m.xref.x{n}.m0[{j}]' for n in DEVICES for j in ['ibd','ibs']]
    def add_currents(folder,body,control,*args,**kwargs):
        control=re.sub(r'(?m)^save (.*)$',lambda m:'save '+m[1]+' '+' '.join(vectors),control)
        lets='\n'.join(f'let j{k}={v}' for k,v in enumerate(vectors))
        control=re.sub(r'(?m)^wrdata data.dat (.*)$',lambda m:lets+'\nwrdata data.dat '+m[1]+' '+' '.join(f'j{k}' for k in range(20)),control)
        return old(folder,body,control,*args,**kwargs)
    p.run=add_currents;results=[]
    for name in ['tt','fast']:
        for initial in ['low','high']:
            row=s.tran(w/f'{name}-{initial}',s.STATE[name],kind='initial',initial=initial)
            a=np.loadtxt(ROOT/row['raw_waveform'],skiprows=1);currents=a[:,-20:]
            diode={n:{j:dict(min_a=float(currents[:,k*2+q].min()),max_a=float(currents[:,k*2+q].max())) for q,j in enumerate(['ibd','ibs'])} for k,n in enumerate(DEVICES)}
            results.append(dict(envelope=name,**row,model_reported_junction_currents=diode))
    summary=dict(status='complete_zero_area_junction_current_controls',workdir=str(w.relative_to(ROOT)),candidate_source_sha256=p.sha(p.REF),
                 paired_source_sha256=main['source_hashes']['analog/reference/vset_servo.spice'],script_sha256=p.sha(Path(__file__)),results=results,
                 interpretation='Same frozen zero-area candidate, waveform settings and initial conditions, adding @ibd/@ibs saves only. Compare to junction-sensitivity.json; no physical geometry retuning.')
    b.save(w/'junction-zero-controls.json',summary);shutil.copyfile(w/'junction-zero-controls.json',E/'junction-zero-controls.json')
    print(json.dumps([dict(envelope=r['envelope'],initial=r['initial_state'],pload=r['model_reported_junction_currents']['pload']) for r in results],indent=2))
if __name__=='__main__':main()
