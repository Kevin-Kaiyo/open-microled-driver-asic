#!/usr/bin/env python3
"""Freeze and test genuinely re-extracted HV layout; previous evidence stays immutable."""
import argparse,datetime,json,shutil
from pathlib import Path
import run as r
import validate as v

def freeze(work,physical):
    if (work/'final-identity.json').exists():return v.verify(work)
    if (work/'cases').exists():raise ValueError('cannot replace already simulated inputs')
    v.freeze(work);m=json.loads((work/'manifest.json').read_text())
    for q in 'AB':
        folder=physical/q
        src=next((folder/'full-rc').glob('*_rc.spice'));dst=work/'inputs/physical'/f'{q}-AFTER.spice';shutil.copy2(src,dst)
        sub,ports,devices=r.parse_core(dst)
        m['variants'][q]['AFTER'].update({'source':r.rel(src),'sha256':r.sha(dst),'subckt':sub,'ports':ports})
        for name in ['physical-contract.json','selected-electrical-source.spice']:
            src=folder/name;dst=work/'inputs/physical'/f'{q}-{name}'
            if src.exists():shutil.copy2(src,dst)
        contract=folder/'physical-contract.json'
        if contract.exists():
            shutil.copy2(contract,work/'inputs/physical'/f'{q}-contract.json');m['physical_contract'][q]=json.loads(contract.read_text())
    m['source_hashes']={str(p.relative_to(work/'inputs')):r.sha(p) for p in (work/'inputs').rglob('*') if p.is_file()}
    m['physical_work']=r.rel(physical);m['scope']['storage_budget_GiB']=6
    m['scope']['candidate']='Genuinely generated and re-extracted06v0/03v3 mixed device layout. Source and physical contracts pinned; no post-extraction current recalibration.'
    r.emit(work/'manifest.json',m);r.emit(work/'final-identity.json',{'manifest_sha256':r.sha(work/'manifest.json'),'created':datetime.datetime.now().isoformat(),'physical_work':r.rel(physical)})
    return m

def case(work,q,label,corner='ff',temp=-40,vdd=3.65,rate=None,**kw):
    if rate is None:rate=.4 if q=='A' else .5
    c=v.case(work,q,label,corner,temp,vdd,**kw)
    old=c['rate_Gbps'];c['rate_Gbps']=rate;c['name']=c['name'].replace(f'-{old:g}G-',f'-{rate:g}G-')
    return c

def plan(work,stage,routes):
    cs=[]
    for q in routes:
        if stage=='targets':
            for label,co,t,vd in [('SSminus50','ss',125,2.95),('SS','ss',125,3.),('FFplus50','ff',-40,3.65),('TT','typical',27,3.3)]:
                cs.append(case(work,q,label,co,t,vd))
            if q=='A':
                for label,co,t,vd in [('SS_1G','ss',125,3.),('FFplus50_1G','ff',-40,3.65)]:cs.append(case(work,q,label,co,t,vd,rate=1))
        elif stage=='dc':
            for label,co,t,vd in [('TT','typical',27,3.3),('SSminus50','ss',125,2.95),('FFplus50','ff',-40,3.65)]:
                for bit in [0,1]:cs.append(case(work,q,label+'_DC',co,t,vd,dc_bit=bit))
        elif stage=='stress':
            cs.append(case(work,q,'joint_SSmin_VLEDaux','ss',125,2.95,rail_offsets_V=({'VLED':-.05,'VH':.05,'VL':.05} if q=='A' else {'VLED':-.05,'VDUMMY':-.05})))
            for label,co,t,vd in [('SSminus50','ss',125,2.95),('FFplus50','ff',-40,3.65)]:
                for rc in ['typical','ss','ff']:
                    if rc!=co:cs.append(case(work,q,label+'_res_'+rc,co,t,vd,res_corner=rc))
            for delta in [-.05,.05]:
                cs.append(case(work,q,'VLED_'+str(delta),rail_offsets_V={'VLED':delta}))
                cs.append(case(work,q,'aux_'+str(delta),rail_offsets_V={k:delta for k in (['VH','VL'] if q=='A' else ['VDUMMY'])}))
            cs.append(case(work,q,'package_R4_L2',r_pkg=4,l_pkg=2e-9))
            pulse={'kind':'pulse','amplitude_V':.05,'delay_ui':300,'edge_ui':1,'width_ui':32,'period_ui':127}
            cs.append(case(work,q,'VDDpulse_tracking',vdd=3.6,rail_profiles={'VDD':pulse},data_mode='tracking'))
        elif stage=='numerical':
            for label,co,t,vd in [('SSminus50','ss',125,2.95),('FFplus50','ff',-40,3.65)]:
                cs.append(case(work,q,label+'_gear80',co,t,vd,steps_per_ui=80))
            cs.append(case(work,q,'FFplus50_trap',steps_per_ui=100,method='trap'))
        elif stage=='rates':
            if q=='B':
                for label,co,t,vd in [('SSminus50','ss',125,2.95),('FFplus50','ff',-40,3.65),('TT','typical',27,3.3)]:
                    cs.append(case(work,q,label+'_common04',co,t,vd,rate=.4))
            else:cs.append(case(work,q,'SSminus50_rate05','ss',125,2.95,rate=.5))
        else:raise ValueError('unknown stage')
    return cs

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',default='build/highspeed-nrz-robustness/final-hv-r1');p.add_argument('--physical');p.add_argument('--stage',choices=['targets','dc','stress','numerical','rates','summary'],default='targets');p.add_argument('--routes',default='AB');a=p.parse_args();work=r.ROOT/a.work
    if a.physical:freeze(work,r.ROOT/a.physical)
    v.verify(work)
    if a.stage!='summary':
        cs=plan(work,a.stage,a.routes);r.emit(work/f'plan-{a.stage}-{a.routes}.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs})
        for c in cs:print(json.dumps(v.analyze(work,r.run_case(work,c))),flush=True)
    v.summarize(work)
if __name__=='__main__':main()
