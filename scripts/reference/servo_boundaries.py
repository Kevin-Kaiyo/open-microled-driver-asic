"""Late/existing VSET boundaries and signed per-terminal stress from actual traces."""
from pathlib import Path
import json, shutil, tempfile
import numpy as np
import probe as p
import servo as s
import run as b
ROOT=p.ROOT;E=ROOT/'evidence/reference'
PINS=[('pbias','p','pb','pb','vdd','vdd'),('ptail','p','tail','pb','vdd','vdd'),('pd1','p','n1','vset','tail','vdd'),('pd2','p','n2','sense','tail','vdd'),
      ('nd1','n','n1','n1','0','0'),('nd2','n','n2','n1','0','0'),('nstage','n','ctrl','n2','0','0'),('pload','p','ctrl','ctrl','vdd','vdd'),
      ('preg','p','sense','ctrl','vdd','vdd'),('pout','p','bias','ctrl','vdd','vdd'),('mref_load','n','bias','bias','0','0')]
def stress(a):
    v={n:a[:,i] for n,i in zip(['pb','ctrl','n1','n2','tail','vdd','sense','bias','vset'],[11,9,7,8,10,12,6,5,13])};v['0']=np.zeros(len(a))
    result={}
    for name,typ,d,g,source,bulk in PINS:
        row={}
        for label,x,y in [('vgs',g,source),('vgd',g,d),('vgb',g,bulk),('vds',d,source),('vsb',source,bulk),('vdb',d,bulk)]:
            diff=v[x]-v[y];row[label]={'min_v':float(diff.min()),'max_v':float(diff.max()),'max_abs_v':float(np.abs(diff).max())}
        # Positive = p-n junction forward polarity, not proof of substantial current.
        sign=1 if typ=='p' else -1
        row['body_source_forward_polarity_max_v']=float(np.max(sign*(v[source]-v[bulk])))
        row['body_drain_forward_polarity_max_v']=float(np.max(sign*(v[d]-v[bulk])))
        row['type']=typ;row['DGSB']=[d,g,source,bulk];result[name]=row
    return result
def main():
    main=json.loads((E/'servo-summary.json').read_text());base=ROOT/main['workdir']/'inputs'
    w=Path(tempfile.mkdtemp(prefix='servo-boundaries-',dir=ROOT/'build/reference'));f=w/'inputs';f.mkdir()
    for name in ['analog/reference/vset_servo.spice','scripts/reference/servo.py','scripts/reference/probe.py','scripts/reference/run.py']:
        src=base/name;dst=f/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        if p.sha(src)!=main['source_hashes'][name] or p.sha(ROOT/name)!=p.sha(src):raise RuntimeError('Candidate identity changed')
    for name in ['design.ngspice','sm141064.ngspice']:
        dst=f/'pdk'/name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(base/'pdk'/name,dst)
    shutil.copyfile(Path(__file__),f/'scripts/reference/servo_boundaries.py')
    p.PDK=f/'pdk';p.REF=f/'analog/reference/vset_servo.spice'
    cases=[];stop=60e-6
    for case in ['vdd_on_vset_step','vset_late_after_vdd','vset_early_before_vdd']:
        rail='3.3' if case=='vdd_on_vset_step' else b.pwl([(0,0),(1e-6,0),(1.1e-6,3.3),(stop,3.3)])
        vset='.5' if case=='vset_early_before_vdd' else b.pwl([(0,0),(20e-6,0),(20.1e-6,.5),(stop,.5)])
        body=s.body(s.STATE['tt'],clamp=None,rail=rail,setpoint=vset)
        nodes=' '.join('v('+n+')' for n in s.NODES)
        a=p.run(w/case,body,f'''option reltol=1e-6 abstol=1e-12 vntol=1e-7
save {nodes} i(vsense) i(vdd) i(vrefrail)
tran 10n {stop} 0 10n
let iout=i(vsense)
let iref=i(vsense)
let supply=-i(vdd)
let refrail=i(vrefrail)
wrdata data.dat iout iref supply refrail {nodes}
''')
        t=a[:,0];current=a[:,1];final=b.integ(t,current,50e-6,60e-6)/10e-6
        origin=1.1e-6 if case=='vset_early_before_vdd' else 20.1e-6
        bad=np.flatnonzero((t>=origin)&(np.abs(current-final)>.01*abs(final)))
        settling=max(0,float(t[bad[-1]+1])-origin) if len(bad) and bad[-1]+1<len(t) else (None if len(bad) else 0)
        cases.append(dict(case=case,raw_waveform=str((w/case/'data.dat').relative_to(ROOT)),
                          vset_zero_2_to_19us_mean_current_a=b.integ(t,current,2e-6,19e-6)/17e-6 if case!='vset_early_before_vdd' else None,
                          final_current_a=final,peak_current_a=float(current.max()),minimum_current_a=float(current.min()),
                          sense_min_v=float(a[:,6].min()),bias_min_v=float(a[:,5].min()),settling_after_event_s=settling,settles_within_20us=settling is not None and settling<20e-6,
                          terminal_stress=stress(a)))
    # Keep physical cold ramps, deliberate hard IC tests, and VSET steps separate.
    audit=[]
    for row in main['startup']:
        a=np.loadtxt(ROOT/row['raw_waveform'],skiprows=1)
        group='hard_initial_state' if row['kind']=='initial' else ('physical_supply_ramp' if row['kind']=='cold' else 'vset_step')
        audit.append(dict(group=group,envelope=row['envelope'],kind=row['kind'],initial_state=row.get('initial_state'),rise_s=row.get('rise_s'),
                          raw_waveform=row['raw_waveform'],terminal_stress=stress(a),sense_min_v=float(a[:,6].min()),bias_min_v=float(a[:,5].min())))
    summary=dict(status='complete_finite_boundary_audit',candidate_summary_sha256=p.sha(E/'servo-summary.json'),candidate_source_sha256=p.sha(p.REF),
                 script_sha256=p.sha(Path(__file__)),workdir=str(w.relative_to(ROOT)),vset_cases=cases,existing_waveform_terminal_audit=audit,
                 interpretation=['All added cases use a diode-connected NMOS20/4 load at reference output; no LED is connected in these startup probes.',
                                 'Negative VSENSE is the servo resistor/regulator node, not an LED terminal. LED reverse-voltage claims cannot be made here.',
                                 'PREG has P+ drain/n-well body: negative VSENSE is reverse body-junction polarity; PD2 sees it at an insulated gate. Signed VDB/VSB and VGS/VGD/VGB must be read per transistor.',
                                 'A positive forward-polarity voltage indicates direction only, not a foundry allowable limit or measured diode current. External terminal differences omit internal distributed fields.',
                                 'Hard UIC states deliberately preload internal charges. Recovery is not safe startup. Physically ramped cases are reported separately.',
                                 'No voltage-source temperature accuracy is established: VSET +/-0.1% remains a full-envelope external assumption.'])
    b.save(w/'servo-boundaries.json',summary);shutil.copyfile(w/'servo-boundaries.json',E/'servo-boundaries.json')
    print(json.dumps([{k:v for k,v in r.items() if k!='terminal_stress'} for r in cases],indent=2))
if __name__=='__main__':main()
