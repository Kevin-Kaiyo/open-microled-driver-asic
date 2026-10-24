#!/usr/bin/env python3
"""Frozen-input PWM reference diagnostics; each case identity is immutable.

The legacy runner supplies stimulus syntax only. This runner freezes it, the
models, its math helpers and its own executed source bytes, then emits compact
observations without saving every internal PEX node at every step.
"""
from pathlib import Path
import argparse,fcntl,gzip,hashlib,importlib.util,json,re,shutil,subprocess,tempfile,time
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
SOURCE_BYTES=Path(__file__).read_bytes();SOURCE_SHA=hashlib.sha256(SOURCE_BYTES).hexdigest()
WORK=ROOT/'build/pwm-reference-v2/20261024';EVID=ROOT/'evidence/pwm-reference-v2/20261024';INPUT=WORK/'inputs'
LOCK='/tmp/open-microled-pwm-reference-v2-ngspice.lock'
VEC=['i(VLEDLOAD)','v(refrail,diegnd)','v(refrail_board)','v(ctrl,diegnd)','v(sense,diegnd)','v(n2,diegnd)','v(refout,diegnd)','v(bias,diegnd)','v(led_k)','v(rail)','v(diegnd)','v(raw_pwm,diegnd)','v(fault,diegnd)','v(permit,diegnd)','v(pwm_drive,diegnd)','v(gate,diegnd)','i(VREFRAIL)','@d.xled.dled[id]','@d.xled.dled[capcur]','v(xdut.ctrl.t3,xdut.vref.t1)','i(VSAFE)','i(VBUF)']
IDX={v:k+1 for k,v in enumerate(VEC)}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def enforce_budget():
    free=shutil.disk_usage(ROOT).free
    if free<5*1024**3:raise RuntimeError('Free disk below5GiB; do not expand')
    used=sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file()) if WORK.exists() else 0
    if used>1.5*1024**3:raise RuntimeError('New branch raw budget1.5GiB reached')

def freeze():
    enforce_budget();INPUT.mkdir(parents=True,exist_ok=True);EVID.mkdir(parents=True,exist_ok=True)
    original=ROOT/'build/pwm-robustness/20261024/inputs'
    files={n:original/n for n in ['design.ngspice','sm141064.ngspice','dut.spice','microled.spice','pixel_pwm.v','pixel_safety.v','tb_safety.v','math.py']}
    files['legacy_runner_original.py']=ROOT/'scripts/pwm_robustness/run.py'
    files['old_loop_runner.py']=ROOT/'scripts/analog_v3/ac_macro.py'
    files['scope.json']=ROOT/'analog/pwm_reference_v2/scope.json'
    for src in sorted((ROOT/'analog/pwm_reference_v2').glob('*')):
        if src.suffix in ['.spice','.json']:files[src.name]=src
    records={}
    for n,src in files.items():
        dst=INPUT/n
        if n=='final-network.json' and dst.exists() and sha(dst)!=sha(src):
            n='final-network-'+sha(src)[:16]+'.json';dst=INPUT/n
        if dst.exists():assert sha(dst)==sha(src),f'Frozen source drift: {n}'
        else:shutil.copy2(src,dst)
        records[n]={'source':str(src.relative_to(ROOT)),'sha256':sha(dst)}
    assert sha(INPUT/'dut.spice')=='d6ebc340c5f2096c43e1358b851d68590fefddbf47b5cc6e746ffc3c12851424'
    legacy=(INPUT/'legacy_runner_original.py').read_text().replace('ROOT = Path(__file__).resolve().parents[2]',f'ROOT = Path({str(ROOT)!r})').replace("ROOT/'scripts/safety/run.py'",f"Path({str(INPUT/'math.py')!r})")
    relocated=INPUT/'legacy_runner_relocated.py'
    if relocated.exists():assert relocated.read_text()==legacy
    else:relocated.write_text(legacy)
    records['legacy_runner_relocated.py']={'source':'path-relocated frozen legacy source; no circuit/stimulus function change','sha256':sha(relocated)}
    sourcecopy=INPUT/'executed_sources'/SOURCE_SHA/'run.py';sourcecopy.parent.mkdir(parents=True,exist_ok=True)
    if not sourcecopy.exists():sourcecopy.write_bytes(SOURCE_BYTES)
    spec=importlib.util.spec_from_file_location('frozen_legacy',relocated);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.WORK=WORK;m.EVID=EVID;m.INPUT=INPUT
    r=subprocess.run(['iverilog','-g2012','-s','tb_safety','-o',str(WORK/'safety.vvp'),str(INPUT/'pixel_pwm.v'),str(INPUT/'pixel_safety.v'),str(INPUT/'tb_safety.v')],text=True,capture_output=True);(WORK/'rtl-compile.log').write_text(r.stdout+r.stderr);assert r.returncode==0
    manifest={'baseline_commit':'112ba95969ac6a2141c305324ea694e7b96c0765','files':records,'executed_runner_source':str(sourcecopy.relative_to(ROOT)),'executed_runner_sha256':SOURCE_SHA,'old_directories_read_only':True}
    payload=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode();mh=hashlib.sha256(payload).hexdigest();mp=INPUT/'manifests'/f'{mh}.json';mp.parent.mkdir(parents=True,exist_ok=True)
    if mp.exists():assert mp.read_bytes()==payload
    else:mp.write_bytes(payload)
    m.frozen_manifest_path=mp;save(EVID/'input-manifest.json',manifest)
    (WORK/'ngspice-version.log').write_text(subprocess.check_output(['ngspice','--version'],text=True))
    return m

def cases(m):
    out=[]
    for ff in [0,60,1000]:
        for kind in ['dc','step','ac']:
            c=m.case(f'pilot_{kind}_cff{ff}_obs2',kind=kind,stop_ns=50000);c.update(package='stress',cff_pf=ff,step_rail='ref',edge_ns=10);out.append(c)
    for n,r,full,order in [('strict_ideal_fullmesh',0,True,2),('strict_ideal_adaptive',0,False,2),('strict_r10_fullmesh',10,True,2),('strict_r10_gear1_fullmesh',10,True,1)]:
        c=m.case('startup_diagnostic_'+n,kind='startup',stop_ns=40000);c.update(package='stress',candidate=True,filter_location='board',filter_c_nf=100,startup_mesh_full=full,gear_order=order,driver_r_ohm=r);out.append(c)
    c=m.case('comp_n2_150p_step',kind='step',stop_ns=50000);c.update(package='stress',comp_n2_pf=150,step_rail='ref',edge_ns=10);out.append(c)
    c=m.case('softstart_v1_comp150_startup_shortmesh',kind='startup',stop_ns=40000);c.update(package='stress',comp_n2_pf=150,softstart=True,driver_r_ohm=10);out.append(c)
    for kind in ['dc','step','startup','fault','pwm']:
        c=m.case('shunt150_board100n_'+kind,kind=kind,stop_ns={'dc':0,'step':50000,'startup':40000,'fault':66125,'pwm':540000}[kind]);c.update(package='stress',comp_n2_pf=150,candidate=True,filter_location='board',filter_c_nf=100,driver_r_ohm=10,step_rail='ref',edge_ns=10,dc_reference_case='shunt150_board100n_dc');out.append(c)
    for name,opts in [('step_window100u',dict(kind='step',stop_ns=100000)),('startup_fullmesh',dict(kind='startup',stop_ns=40000,startup_mesh_full=True)),('startup_fullmesh_fine',dict(kind='startup',stop_ns=40000,startup_mesh_full=True,startup_mesh_ps=.05,maxstep_ns=1)),('step_window100u_fine',dict(kind='step',stop_ns=100000,maxstep_ns=1))]:
        c=m.case('shunt150_board100n_'+name,**opts);c.update(package='stress',comp_n2_pf=150,candidate=True,filter_location='board',filter_c_nf=100,driver_r_ohm=10,step_rail='ref',edge_ns=10);out.append(c)
    for kind in ['dc','step','startup','fault','pwm','ac']:
        c=m.case('pcb150_board100n_'+kind,kind=kind,stop_ns={'dc':0,'step':100000,'startup':40000,'fault':66125,'pwm':540000,'ac':0}[kind]);c.update(package='stress',comp_n2_pf=150,comp_return='0',candidate=True,filter_location='board',filter_c_nf=100,driver_r_ohm=10,step_rail='ref',edge_ns=10,dc_reference_case='pcb150_board100n_dc');out.append(c)
    for suffix,opts in [('fullmesh',dict(startup_mesh_full=True)),('fullmesh_fine',dict(startup_mesh_full=True,startup_mesh_ps=.05,maxstep_ns=1)),('shortmesh_trap',dict(method='trap',maxstep_ns=1))]:
        c=m.case('pcb150_board100n_startup_'+suffix,kind='startup',stop_ns=40000,**opts);c.update(package='stress',comp_n2_pf=150,comp_return='0',candidate=True,filter_location='board',filter_c_nf=100,driver_r_ohm=10);out.append(c)
    for suffix,opts in [('fine',dict(maxstep_ns=1)),('allrails',dict(step_rail='all'))]:
        c=m.case('pcb150_board100n_step_'+suffix,kind='step',stop_ns=100000,**opts);c.update(package='stress',comp_n2_pf=150,comp_return='0',candidate=True,filter_location='board',filter_c_nf=100,driver_r_ohm=10,edge_ns=10);c.setdefault('step_rail','ref');out.append(c)
    for kind in ['dc','step','startup','fault','pwm','ac']:
        c=m.case('n2rl_'+kind,kind=kind,stop_ns={'dc':0,'step':100000,'startup':40000,'fault':66125,'pwm':540000,'ac':0}[kind]);c.update(package='stress',comp_n2_pf=150,comp_return='0',comp_pin_package=True,candidate=True,filter_location='board',filter_c_nf=100,driver_r_ohm=10,step_rail='ref',edge_ns=10,dc_reference_case='n2rl_dc');out.append(c)
    for name,opts in [('startup_fullmesh',dict(kind='startup',stop_ns=40000,startup_mesh_full=True)),('startup_fullmesh_fine',dict(kind='startup',stop_ns=40000,startup_mesh_full=True,startup_mesh_ps=.05,maxstep_ns=1)),('startup_shortmesh_trap',dict(kind='startup',stop_ns=40000,method='trap',maxstep_ns=1)),('step_fine',dict(kind='step',stop_ns=100000,maxstep_ns=1)),('step_allrails',dict(kind='step',stop_ns=100000,step_rail='all'))]:
        c=m.case('n2rl_'+name,**opts);c.update(package='stress',comp_n2_pf=150,comp_return='0',comp_pin_package=True,candidate=True,filter_location='board',filter_c_nf=100,driver_r_ohm=10,edge_ns=10);c.setdefault('step_rail','ref');out.append(c)
    for c in out:
        if c['name'] in ['n2rl_step','n2rl_step_fine','n2rl_fault','n2rl_startup_fullmesh_fine']:c['terminal_stress']=True
    damp=[]
    for orig in out:
        if orig['name'] in ['n2rl_dc','n2rl_step','n2rl_step_fine','n2rl_fault','n2rl_pwm','n2rl_ac','n2rl_startup_fullmesh','n2rl_startup_fullmesh_fine','n2rl_startup_shortmesh_trap']:
            c=json.loads(json.dumps(orig));c['name']=c['name'].replace('n2rl_','damped_');c['comp_damp_ohm']=10
            if 'dc_reference_case' in c:c['dc_reference_case']='damped_dc'
            if c['kind']=='startup':c.pop('terminal_stress',None)
            damp.append(c)
    c=m.case('damped_startup_fullmesh_trap',kind='startup',stop_ns=40000,startup_mesh_full=True,method='trap',maxstep_ns=1);c.update(package='stress',comp_n2_pf=150,comp_return='0',comp_pin_package=True,comp_damp_ohm=10,candidate=True,filter_location='board',filter_c_nf=100,driver_r_ohm=10);damp.append(c)
    faster=[]
    for orig in damp:
        c=json.loads(json.dumps(orig));c['name']=c['name'].replace('damped_','c47_');c['filter_c_nf']*=.47
        if 'dc_reference_case' in c:c['dc_reference_case']='c47_dc'
        if c['name']=='c47_pwm':c['maxstep_ns']=5
        faster.append(c)
    allrails=next(json.loads(json.dumps(c)) for c in faster if c['name']=='c47_step');allrails['name']='c47_step_allrails';allrails['step_rail']='all';faster.append(allrails)
    return out+damp+faster

def matrix_cases(m):
    import itertools
    out=[]
    for co,v,lv in [('typical',3.3,5),('ss',2.97,4.5),('ff',3.63,5.5)]:
        for temp in [0,27,85]:
            for bits in itertools.product([-1,1],repeat=4):
                name=f'pcb_dc_{co}_{temp}_'+''.join('p' if b>0 else 'm' for b in bits)
                c=m.case(name);c.update(corner=co,temp_c=temp,logic_v=v,led_v=lv,package='stress',comp_n2_pf=150,comp_return='0',candidate=True,filter_location='board',filter_c_nf=100,driver_r_ohm=10)
                for rr,tol,tc,sgn in zip(['RSET','RBIAS','RRELEASE','RBLEED'],[.01,.05,.05,.05],[100,200,200,200],bits):
                    c['r_factors'][rr]=1+sgn*tol;c['r_tc_ppm'][rr]=sgn*tc*(1 if temp>=27 else -1)
                out.append(c)
    for co,temp,v,lv in [('typical',27,3.3,5),('ss',85,2.97,4.5),('ff',0,3.63,5.5)]:
        for sgn in [-1,1]:
            c=m.case(f'pcb_dc_extref_{co}_{sgn:+d}');c.update(corner=co,temp_c=temp,logic_v=v,led_v=lv,package='stress',comp_n2_pf=150,comp_return='0',candidate=True,filter_location='board',filter_c_nf=100,driver_r_ohm=10,vset_r_ohm=100,vset_v=.5*(1+.002*sgn));out.append(c)
    final=[]
    for orig in out:
        c=json.loads(json.dumps(orig));c['name']=c['name'].replace('pcb_dc_','n2rl_dc_');c['comp_pin_package']=True;final.append(c)
    return out+final

def dynamic_cases(m):
    import itertools
    out=[]
    for co,temp,v,lv in [('typical',27,3.3,5),('ss',85,2.97,4.5),('ff',0,3.63,5.5)]:
        for rs,cs,ns in itertools.product([-1,1],repeat=3):
            tag=''.join('p' if x>0 else 'm' for x in [rs,cs,ns]);c=m.case(f'n2rl_dyn_{co}_{tag}',kind='step',stop_ns=100000)
            c.update(corner=co,temp_c=temp,logic_v=v,led_v=lv,package='stress',comp_n2_pf=150*(1+.1*ns),comp_return='0',comp_pin_package=True,candidate=True,filter_location='board',filter_c_nf=100*(1+.1*cs),filter_r_ohm=100*(1+.05*rs),driver_r_ohm=10,step_rail='ref',edge_ns=10);out.append(c)
        if co!='typical':
            for tag,rs,cs,ns in [('fast',-1,-1,-1),('slow',1,1,1)]:
                c=m.case(f'n2rl_startup_{co}_{tag}',kind='startup',stop_ns=40000)
                c.update(corner=co,temp_c=temp,logic_v=v,led_v=lv,package='stress',comp_n2_pf=150*(1+.1*ns),comp_return='0',comp_pin_package=True,candidate=True,filter_location='board',filter_c_nf=100*(1+.1*cs),filter_r_ohm=100*(1+.05*rs),driver_r_ohm=10,startup_mesh_full=True);out.append(c)
    return out

def damped_cases(m):
    out=[]
    for orig in dynamic_cases(m):
        n=orig['name'];keep=(n.startswith('n2rl_dyn_') and (orig['corner']=='typical' or n.endswith(('mmm','ppp')))) or n in ['n2rl_startup_ss_slow','n2rl_startup_ff_fast']
        if keep:
            c=json.loads(json.dumps(orig));c['name']=n.replace('n2rl_','damped_');c['comp_damp_ohm']=10;out.append(c)
    for tag,base in [('min','pcb_dc_ss_85_pmmm'),('max','pcb_dc_ff_85_mmmp')]:
        c=json.loads((WORK/base/'result.json').read_text())['case'];c['name']='damped_dc_equiv_'+tag;c.update(comp_pin_package=True,comp_damp_ohm=10,equivalence_baseline_case=base);out.append(c)
        d=json.loads(json.dumps(c));d['name']='damped_dc_extref_'+tag;d.update(vset_r_ohm=100,vset_v=.499 if tag=='min' else .501);out.append(d)
    faster=[]
    for orig in out:
        c=json.loads(json.dumps(orig));c['name']=c['name'].replace('damped_','c47_');c['filter_c_nf']*=.47;faster.append(c)
    return out+faster

def make_deck(c,p,m):
    legacy_kind=c['kind'];dc=dict(c)
    if legacy_kind=='ac':dc['kind']='dc'
    devices=[x.split() for x in (INPUT/'dut.spice').read_text().splitlines() if re.match(r'^X\d+ ',x)]
    src=m.deck(dc,p,devices);c.update({k:v for k,v in dc.items() if k in ['actual_resistance_ohm','fault_clear_ns','rtl_assertions_passed']})
    # Circuit additions and driver-model changes are explicit separate factors.
    r=c.get('driver_r_ohm',0)
    if r:
        for name,node in [('VRAW','raw_pwm'),('VFAULT','fault'),('VPERMIT','permit')]:
            src=re.sub(r'(?m)^'+name+' '+node+r' 0 ',name+' '+node+'_driver 0 ',src)
            src=src.replace('.control',f'RDRV_{node} {node}_driver {node} {r}\n.control')
    if c.get('cff_pf',0):src=src.replace('.control',f'CFF_REFERENCE refrail ctrl {c["cff_pf"]}p\n.control')
    if c.get('softstart'):
        src=src.replace('VLINK_ref refrail_pre refrail 0', 'VLINK_ref refrail_pre ref_input 0')
        start='PWL(0 0 2u 0 2.01u '+str(c['logic_v'])+')' if legacy_kind=='startup' else str(c['logic_v'])
        extra=f'.include "{INPUT}/softstart_v1.spice"\nXSTART diegnd ref_input refrail start gsoft ndrain pwm_ref_softstart\nRUP ref_input gsoft 1Meg\nRDOWN gsoft ndrain 100k\nCBOOT ref_input gsoft 33p\nVSTART start_driver 0 {start}\nRSTART start_driver start 10\n'
        src=src.replace('.control',extra+'.control')
    # Use compact observables, never the legacy all-node save or195/234 post-measures.
    prefix=src.split('.control')[0]
    if 'comp_n2_pf' in c:prefix=prefix.replace('CCOMP n2 ctrl 30p',f'CCOMP n2 {c.get("comp_return","diegnd")} {c["comp_n2_pf"]}p')
    if c.get('comp_pin_package'):
        prefix=prefix.replace(f'CCOMP n2 0 {c["comp_n2_pf"]}p',f'RPK_N2 n2 n2_pin_r 1\nLPK_N2 n2_pin_r n2_board 5n\nRESR_N2 n2_board n2_cap {c.get("comp_esr_ohm",.5)}\nCCOMP n2_cap 0 {c["comp_n2_pf"]}p')
    if c.get('comp_damp_ohm'):
        prefix=prefix.replace(f'RESR_N2 n2_board n2_cap {c.get("comp_esr_ohm",.5)}',f'RESR_N2 n2_board n2_damp {c.get("comp_esr_ohm",.5)}\nRDAMP_N2 n2_damp n2_cap {c["comp_damp_ohm"]}')
    if c.get('method'):prefix=prefix.replace('method=gear',f'method={c["method"]}')
    if c.get('vset_r_ohm'):
        prefix=prefix.replace('VSET vset 0 .5',f'VSET vset_source 0 {c.get("vset_v",.5)}\nRVSET vset_source vset {c["vset_r_ohm"]}')
    vec=VEC+(['v(ref_input,diegnd)','v(start,diegnd)','v(gsoft,diegnd)','v(ndrain,diegnd)'] if c.get('softstart') else [])
    if legacy_kind=='ac':
        prefix=re.sub(r'(?m)^(VREFRAIL refrail_board 0 [^\n]+)$',r'\1 AC 1',prefix)
        ctl='op\nwrdata op.dat '+' '.join(VEC[:17])+'\nac dec 80 10 100Meg\nwrdata ac.dat i(VLEDLOAD) v(refrail,diegnd) v(ctrl,diegnd) v(sense,diegnd) v(n2,diegnd) v(diegnd)'
    else:ctl=('op' if legacy_kind=='dc' else f'tran {".001n" if legacy_kind=="startup" else "10n"} {c["stop_ns"]}n 0 {c.get("maxstep_ns",2)}n')+'\nwrdata waveform.dat '+' '.join(vec)
    saved=set()
    for v in vec:
        if v.startswith('v('):saved.update('v('+n+')' for n in v[2:-1].split(','))
        else:saved.add(v)
    if c.get('terminal_stress'):
        for dev in devices:
            saved.update('v(xdut.'+node.lower()+')' for node in dev[1:5])
            for tag,i,j in [('gs',2,3),('gd',2,1),('gb',2,4),('ds',1,3),('bs',4,3),('bd',4,1)]:
                label='s_'+dev[0].lower()+'_'+tag;ctl+=f'\nlet {label}=vecmax(abs(v(xdut.{dev[i].lower()})-v(xdut.{dev[j].lower()})))\nprint {label}'
    return prefix+'.control\nset numdgt=15\nset wr_vecnames\nset wr_singlescale\nsave '+' '.join(sorted(saved))+'\n'+ctl+'\nquit\n.endc\n.end\n'

def run(c,m,reuse=False):
    enforce_budget();p=WORK/c['name'];existing=p/'result.json'
    with tempfile.TemporaryDirectory(prefix='deck-staging-',dir=WORK) as td:
        staging=Path(td);deck=make_deck(c,staging,m);events={x.name:x.read_bytes() for x in staging.iterdir() if x.is_file()}
    h=hashlib.sha256(deck.encode()).hexdigest()
    if existing.exists():
        previous=json.loads(existing.read_text())
        if reuse and previous['deck_sha256']==h:print('REUSE',c['name'],flush=True);return previous
        raise RuntimeError('Immutable identity already exists; use new case: '+c['name'])
    p.mkdir(exist_ok=True);(p/'testbench.spice').write_text(deck)
    for n,b in events.items():(p/n).write_bytes(b)
    r=dict(case=c,deck_sha256=h,executed_runner_sha256=SOURCE_SHA,source_manifest_sha256=sha(m.frozen_manifest_path),completed=False)
    start=time.time()
    with open(LOCK,'a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        try:
            sim_started=time.time()
            proc=subprocess.run(['ngspice','-b','testbench.spice'],cwd=p,text=True,capture_output=True,timeout=360);log=proc.stdout+proc.stderr;code=proc.returncode
        except subprocess.TimeoutExpired as e:
            def decoded(v):return v.decode(errors='replace') if isinstance(v,bytes) else (v or '')
            log='RUN_TIMEOUT\n'+str(e)+'\n'+decoded(e.stdout)+decoded(e.stderr);code=124
    (p/'ngspice.log').write_text(log);r.update(exit_code=code,elapsed_s=time.time()-start,elapsed_ngspice_s=time.time()-sim_started,lock_wait_s=sim_started-start,log_sha256=sha(p/'ngspice.log'))
    fail=re.search(r'(?im)^Error:.*|.*timestep too small.*|simulation interrupted|RUN_TIMEOUT',log)
    datafile=p/('ac.dat' if c['kind']=='ac' else 'waveform.dat')
    if code or fail or not datafile.exists():r['failure']=fail.group() if fail else 'Nonzero exit or missing data'
    else:
        a=np.atleast_2d(np.loadtxt(datafile,skiprows=1));assert np.isfinite(a).all();r['completed']=True;r['rows']=len(a);checks=[]
        if c.get('terminal_stress'):
            peaks={k:float(v) for k,v in re.findall(r'(s_x\d+_(?:gs|gd|gb|ds|bs|bd))\s*=\s*([+\-\deE.]+)',log)};assert len(peaks)==234
            r['terminal_abs_peak_v']=peaks;r['terminal_pairs_logged']=['gs','gd','gb','ds','bs','bd'];r['terminal_note']='Actual39MOS PEX terminal maxima only; no foundry lifetime or absolute-maximum qualification claim.'
        def ck(n,value):checks.append({'name':n,'passed':bool(value)})
        if c['kind']=='ac':
            op=np.loadtxt(p/'op.dat',skiprows=1);i0=float(op[1]);f=a[:,0];cur=a[:,1]+1j*a[:,2];vref=a[:,3]+1j*a[:,4];ctrl=a[:,5]+1j*a[:,6];sense=a[:,7]+1j*a[:,8]
            r['dc_current_a']=i0;r['transfer_samples']=[{'frequency_hz':float(f[k]),'current_a_per_v':float(abs(cur[k])),'current_relative_per_v':float(abs(cur[k])/abs(i0)),'ctrl_over_ref_abs':float(abs(ctrl[k]/vref[k])),'gate_rail_error_abs':float(abs(ctrl[k]-vref[k])),'sense_a_per_v':float(abs(sense[k]))} for k in [int(np.argmin(abs(np.log10(f)-np.log10(x)))) for x in [1e3,1e4,1e5,1e6,1e7,1e8]]];ck('ac_finite',True)
        elif c['kind']=='dc':r.update(current_a=float(a[0,1]),error_pct=float((a[0,1]/100e-6-1)*100));ck('dc_5pct',abs(r['error_pct'])<=5)
        else:
            t=a[:,0];i=a[:,1];assert np.all(np.diff(t)>0) and abs(t[-1]-c['stop_ns']*1e-9)<1e-12
            r.update(current_min_a=float(i.min()),current_max_a=float(i.max()))
            if c['kind']=='step':
                before=m.M.integral(t,i,5e-6,9e-6)/4e-6;after=m.M.integral(t,i,t[-1]-5e-6,t[-1])/5e-6;bad=np.flatnonzero((t>=25.01e-6)&(abs(i-after)>.005*abs(after)));settle=0 if not len(bad) else None if bad[-1]==len(t)-1 else float(t[bad[-1]+1]-25.01e-6)
                r.update(baseline_current_a=before,final_current_a=after,excursion_pct=float(np.max(abs(i/before-1))*100),settle_s=settle,ctrl_rail_error_peak_v=float(np.max(abs(a[:,4]-a[:,2]))))
                ck('research_excursion_20pct',r['excursion_pct']<=20);ck('research_restore_5us',settle is not None and settle<=5e-6)
            elif c['kind']=='startup':
                cond=a[:,18]-a[:,19];held=t<=20e-6;late=m.M.integral(t,i,30e-6,40e-6)/10e-6
                r.update(held_peak_a=float(np.max(abs(i[held]))),held_conduction_peak_a=float(np.max(abs(cond[held]))),held_displacement_peak_a=float(np.max(abs(a[held,19]))),held_diegnd_peak_v=float(np.max(abs(a[held,11]))),held_charge=m.M.split_charge(t,i,0,20e-6),recovered_a=late,permit_pre_release_max_v=float(np.max(abs(a[t<20e-6,14]))))
                r['prepermit_conduction_peak_a']=float(np.max(np.abs(m.M.clip(t,cond,20e-6,21.5e-6)[1])))
                ck('held_1nA',r['held_peak_a']<=1e-9);ck('prepermit_conduction_1nA',r['prepermit_conduction_peak_a']<1e-9);ck('recovered_5pct',abs(late/100e-6-1)<=.05)
            elif c['kind']=='fault':
                f=50.125e-6;safe=m.M.stable_below_time(t,i,f,f+3e-6,1e-9);charge=m.M.split_charge(t,i,f,f+1e-6);held=float(np.max(np.abs(m.M.clip(t,i,f+1e-6,f+2e-6)[1])));cond=a[:,18]-a[:,19];rel=float(np.max(np.abs(m.M.clip(t,cond,f+3e-6,f+5e-6)[1])));late=m.M.integral(t,i,t[-1]-3e-6,t[-1])/3e-6
                r.update(fault_to_safe_s=None if safe is None else safe-f,fault_charge=charge,held_fault_peak_a=held,stopped_clock_release_conduction_peak_a=rel,recovered_a=late)
                ck('fault_shutdown_1us',safe is not None and safe-f<1e-6);ck('fault_Qpositive_10pC',charge['positive_c']<10e-12);ck('fault_Qnegative_20pC',abs(charge['negative_c'])<20e-12);ck('fault_held_1nA',held<1e-9);ck('fault_stopped_clock_release_1nA',rel<1e-9);ck('fault_recovered_5pct',abs(late/100e-6-1)<.05)
            elif c['kind']=='pwm':
                refcase=c['dc_reference_case'];reference=json.loads((WORK/refcase/'result.json').read_text())['current_a'];left=258.5e-6;right=514.5e-6;q=m.M.integral(t,i,left,right);err=(q/((right-left)*reference/256)-1)*100
                r.update(d1_charge_c=q,d1_charge_error_pct=err,matched_dc_reference=refcase,matched_dc_current_a=reference,pwm_integration_window_s=[left,right]);ck('duty1_charge_error_2pct',abs(err)<2)
        r['checks']=checks;r['passed']=all(x['passed'] for x in checks)
        if c['kind'] not in ['dc','ac']:
            ix=set(np.linspace(0,len(a)-1,min(1000,len(a)),dtype=int))
            for k in range(1,a.shape[1]):ix.update([int(a[:,k].argmin()),int(a[:,k].argmax())])
            np.savetxt(EVID/(c['name']+'.csv'),a[sorted(ix)],delimiter=',',header='time_s,'+','.join(re.sub(r'[^A-Za-z0-9]+','_',v).strip('_') for v in VEC+(['v(ref_input,diegnd)','v(start,diegnd)','v(gsoft,diegnd)','v(ndrain,diegnd)'] if c.get('softstart') else [])),comments='',fmt='%.12e')
        r['raw_sha256']=sha(datafile);r['raw_bytes']=datafile.stat().st_size
        with datafile.open('rb') as sf,gzip.open(str(datafile)+'.gz','wb',compresslevel=6) as df:shutil.copyfileobj(sf,df)
        hh=hashlib.sha256()
        with gzip.open(str(datafile)+'.gz','rb') as rf:
            while b:=rf.read(1024*1024):hh.update(b)
        assert hh.hexdigest()==r['raw_sha256'];r['gzip_sha256']=sha(Path(str(datafile)+'.gz'));datafile.unlink()
    save(p/'result.json',r);save(EVID/(c['name']+'.json'),r)
    print(c['name'],'PASS' if r.get('passed') else 'FAIL',r.get('failure',r.get('excursion_pct',r.get('held_peak_a',r.get('error_pct','')))),flush=True)
    return r

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--suite',choices=['pilot','startup-diagnostic','dc-matrix','pcb','final-dc','final-core','final-dynamic','startup-corners','damped-core','damped-dynamic','damped-corners','damped-dc','c47-core','c47-dynamic','c47-dc','c15-core','c15-dynamic','c15-dc','summarize'],default='pilot');ap.add_argument('--only');ap.add_argument('--reuse',action='store_true');a=ap.parse_args();m=freeze();allcases=cases(m)+matrix_cases(m)+dynamic_cases(m)+damped_cases(m)
    c15=[]
    for old in allcases:
        if old['name'].startswith('c47_'):
            c=json.loads(json.dumps(old));c['name']=c['name'].replace('c47_','c15_');c['filter_c_nf']*=15/47
            if 'dc_reference_case' in c:c['dc_reference_case']='c15_dc'
            c15.append(c)
    allcases+=c15
    chosen=[c for c in allcases if c['name']==a.only] if a.only else [c for c in allcases if c['name'].startswith('pilot_')] if a.suite=='pilot' else [c for c in allcases if c['name'].startswith('startup_diagnostic_')] if a.suite=='startup-diagnostic' else [c for c in allcases if c['name'].startswith('pcb_dc_')] if a.suite=='dc-matrix' else [c for c in allcases if c['name'] in ['pcb150_board100n_dc','pcb150_board100n_step','pcb150_board100n_fault','pcb150_board100n_pwm','pcb150_board100n_ac']] if a.suite=='pcb' else [c for c in allcases if c['name'].startswith('n2rl_dc_')] if a.suite=='final-dc' else [c for c in allcases if c['name'] in ['n2rl_dc','n2rl_step','n2rl_fault','n2rl_pwm','n2rl_ac']] if a.suite=='final-core' else [c for c in allcases if c['name'].startswith('n2rl_dyn_')] if a.suite=='final-dynamic' else [c for c in allcases if c['name'].startswith(('n2rl_startup_ss_','n2rl_startup_ff_'))] if a.suite=='startup-corners' else [c for c in allcases if c['name'] in ['damped_dc','damped_step','damped_step_fine','damped_fault','damped_pwm','damped_ac']] if a.suite=='damped-core' else [c for c in allcases if c['name'].startswith('damped_dyn_')] if a.suite=='damped-dynamic' else [c for c in allcases if c['name'] in ['damped_startup_ss_slow','damped_startup_ff_fast']] if a.suite=='damped-corners' else [c for c in allcases if c['name'].startswith(('damped_dc_equiv_','damped_dc_extref_'))] if a.suite=='damped-dc' else [c for c in allcases if c['name'] in ['c47_dc','c47_step','c47_step_fine','c47_fault','c47_pwm','c47_ac']] if a.suite=='c47-core' else [c for c in allcases if c['name'].startswith('c47_dyn_')] if a.suite=='c47-dynamic' else [c for c in allcases if c['name'].startswith(('c47_dc_equiv_','c47_dc_extref_'))] if a.suite=='c47-dc' else [c for c in allcases if c['name'] in ['c15_dc','c15_step','c15_step_fine','c15_fault','c15_pwm','c15_ac','c15_step_allrails']] if a.suite=='c15-core' else [c for c in allcases if c['name'].startswith('c15_dyn_')] if a.suite=='c15-dynamic' else [c for c in allcases if c['name'].startswith(('c15_dc_equiv_','c15_dc_extref_'))] if a.suite=='c15-dc' else []
    if a.only and not chosen:raise ValueError(a.only)
    for c in chosen:run(c,m,a.reuse)
    result=[x for p in sorted(WORK.glob('*/result.json')) if 'case' in (x:=json.loads(p.read_text()))]
    save(EVID/'summary.json',dict(date='2026-10-24',baseline_commit='112ba95969ac6a2141c305324ea694e7b96c0765',count=len(result),completed_count=sum(x['completed'] for x in result),passed_count=sum(x.get('passed',False) for x in result),results=result,scope='New diagnostics only. No selected circuit, new PEX or autonomous POR qualification yet.'))
if __name__=='__main__':main()
