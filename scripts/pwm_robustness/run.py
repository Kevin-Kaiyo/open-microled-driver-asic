#!/usr/bin/env python3
"""Independent external-component and rail/package experiments on frozen r5 39MOS.

One ngspice at a time via /tmp/open-microled-ngspice.lock. No previous source
or selected evidence is modified. All PWM results retain the 100uA/2.8V synthetic
load; no communication receiver/eye criterion is applicable here.
"""
from pathlib import Path
import argparse, csv, fcntl, gzip, hashlib, importlib.util, itertools, json
import math, re, shutil, subprocess, time, tempfile
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT/'build/pwm-robustness/20261024'
EVID = ROOT/'evidence/pwm-robustness/20261024'
INPUT = WORK/'inputs'
OLD = ROOT/'evidence/analog-v3/final/summary.json'
SPEC = importlib.util.spec_from_file_location('safety_math',ROOT/'scripts/safety/run.py')
M = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(M)
VEC = ['i(VLEDLOAD)','v(led_k)','v(bias)','v(refout)','v(sense)',
       'v(n2)','v(ctrl)','v(refrail)','v(saferail)','v(bufrail)','v(rail)',
       'v(diegnd)','v(raw_pwm)','v(fault)','v(permit)','v(safe_out)',
       'v(pwm_drive)','v(gate)','v(pb)','v(fault_hb)',
       'i(VREFRAIL)','i(VSAFE)','i(VBUF)','i(VLED)',
       '@d.xled.dled[id]','@d.xled.dled[capcur]']
IDX = {v:k+1 for k,v in enumerate(VEC)}
RES = {'RSET':5000.,'RBIAS':100000.,'RRELEASE':100000.,'RBLEED':10000000.}
NODES = {'RSET':'sense 0','RBIAS':'pb 0','RRELEASE':'rail fault_hb','RBLEED':'refout 0'}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,data): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def command(args,cwd,log):
    r=subprocess.run([str(a) for a in args],cwd=cwd,text=True,capture_output=True)
    (cwd/log).write_text(r.stdout+r.stderr)
    if r.returncode: raise RuntimeError(str(cwd/log))
    return r.stdout+r.stderr

def freeze():
    INPUT.mkdir(parents=True,exist_ok=True); EVID.mkdir(parents=True,exist_ok=True)
    old=json.loads(OLD.read_text()); source=ROOT/old['raw_directory']/'inputs'
    assert sha(source/'dut.spice')==old['dut_sha256']
    files={n:source/n for n in ['design.ngspice','sm141064.ngspice','dut.spice','microled.spice']}
    files.update({'pixel_pwm.v':ROOT/'rtl/pixel_pwm.v','pixel_safety.v':ROOT/'rtl/safety/pixel_safety.v','tb_safety.v':ROOT/'sim/safety/tb_safety.v','math.py':ROOT/'scripts/safety/run.py'})
    manifest={}
    for n,p in files.items():
        q=INPUT/n
        if q.exists(): assert sha(q)==sha(p), 'Frozen input changed: '+n
        else: shutil.copyfile(p,q)
        manifest[str(p.relative_to(ROOT))]=sha(p)
    devices=[x.split() for x in (INPUT/'dut.spice').read_text().splitlines() if re.match(r'^X\d+ ',x)]
    assert len(devices)==39 and sum(x[5].endswith('05v0') for x in devices)==6
    save(EVID/'input-manifest.json',dict(date='2026-10-24',selected_old_summary=str(OLD.relative_to(ROOT)),selected_old_summary_sha256=sha(OLD),inputs=manifest,devices=[dict(name=x[0],terminals_DGSB=x[1:5],model=x[5]) for x in devices],old_evidence_reused_only_as_provenance=True,script_sha256=sha(Path(__file__))))
    (WORK/'ngspice-version.log').write_text(subprocess.check_output(['ngspice','--version'],text=True))
    command(['iverilog','-g2012','-s','tb_safety','-o',WORK/'safety.vvp',INPUT/'pixel_pwm.v',INPUT/'pixel_safety.v',INPUT/'tb_safety.v'],WORK,'rtl-compile.log')
    return devices

def case(name,kind='dc',**kw):
    return dict(name=name,kind=kind,corner='typical',temp_c=27,logic_v=3.3,led_v=5.,r_factors={},r_tc_ppm={},package='ideal',candidate=False,**kw)

def dc_cases():
    rows=[case('dc_nominal')]
    for r in RES:
        for sign in [-1,1]:
            c=case(f'dc_{r.lower()}_{"lo" if sign<0 else "hi"}');c['r_factors']={r:1+sign*(.01 if r=='RSET' else .05)};rows.append(c)
    # Full independent 2^4 passive vertices at fixed TT/85C; external-resistor
    # engineering assumptions, not PDK resistor process distributions.
    for k,signs in enumerate(itertools.product([-1,1],repeat=4)):
        c=case(f'dc_passive_vertex_{k:02}');c['temp_c']=85
        c['r_factors']={r:1+s*(.01 if r=='RSET' else .05) for r,s in zip(RES,signs)}
        c['r_tc_ppm']={r:s*(100 if r=='RSET' else 200) for r,s in zip(RES,signs)};rows.append(c)
    # RSET process-like tolerance and temperature coefficients crossed independently
    # with MOS model corner and temperature (supplies held fixed, no bundled PVT).
    for co,t,s in itertools.product(['typical','ss','ff'],[0,27,85],[-1,1]):
        c=case(f'dc_cross_{co}_{t}_{"lo" if s<0 else "hi"}');c.update(corner=co,temp_c=t,r_factors={'RSET':1+s*.01},r_tc_ppm={'RSET':s*100});rows.append(c)
    for co,sign in itertools.product(['typical','ss','ff'],[-1,1]):
        c=case(f'dc_cold_tc_independent_{co}_{"lo" if sign<0 else "hi"}');c.update(corner=co,temp_c=0,r_factors={'RSET':1+sign*.01},r_tc_ppm={'RSET':-sign*100});rows.append(c)
    for co,t,lv,led,sign in [('ss',85,2.97,4.5,1),('ff',0,3.63,5.5,-1)]:
        c=case('dc_guard_'+co);c.update(corner=co,temp_c=t,logic_v=lv,led_v=led,r_factors={r:1+sign*(.01 if r=='RSET' else .05) for r in RES},r_tc_ppm={r:sign*(100 if r=='RSET' else 200) for r in RES},package='stress');rows.append(c)
    for s in [-1,1]:
        c=case(f'dc_rset5pct_{"lo" if s<0 else "hi"}');c.update(corner='ss',temp_c=85,r_factors={'RSET':1+s*.05},r_tc_ppm={'RSET':s*200});rows.append(c)
    for pk in ['nominal','stress']:
        c=case('dc_package_'+pk);c['package']=pk;rows.append(c)
    c=case('dc_filtered');c['candidate']=True;c['package']='stress';rows.append(c)
    c=case('dc_filtered10n');c.update(candidate=True,package='stress',filter_c_nf=10);rows.append(c)
    c=case('dc_filtered8p2n');c.update(candidate=True,package='stress',filter_c_nf=8.2);rows.append(c)
    return rows

def trans_cases():
    rows=[]
    for src in ['ref','led','all']:
        for edge in [10,100]:
            c=case(f'step_{src}_{edge}ns',kind='step',step_rail=src,edge_ns=edge,stop_ns=50000);rows.append(c)
    for pk in ['nominal','stress']:
        c=case('step_all_10ns_package_'+pk,kind='step',step_rail='all',edge_ns=10,stop_ns=50000);c['package']=pk;rows.append(c)
    for kind in ['startup','fault','pwm']:
        c=case(kind+'_package_stress',kind=kind,stop_ns={'startup':80000,'fault':66125,'pwm':1070000}[kind]);c['package']='stress';rows.append(c)
    c=case('step_ref_10ns_fine',kind='step',step_rail='ref',edge_ns=10,stop_ns=50000,maxstep_ns=1);rows.append(c)
    c=case('step_all_10ns_package_stress_fine',kind='step',step_rail='all',edge_ns=10,stop_ns=50000,maxstep_ns=1);c['package']='stress';rows.append(c)
    return rows

def candidate_cases():
    rows=[]
    for suffix,cap,res in [('lo',90,95),('hi',110,105)]:
        c=case('step_ref_10ns_filtered100n_'+suffix,kind='step',step_rail='ref',edge_ns=10,stop_ns=100000);c.update(candidate=True,package='stress',filter_c_nf=cap,filter_r_ohm=res);rows.append(c)
    for suffix,cap,res in [('lo',7.38,95),('hi',9.02,105),('fine',8.2,100)]:
        c=case('step_ref_10ns_filtered8p2n_'+suffix,kind='step',step_rail='ref',edge_ns=10,stop_ns=50000);c.update(candidate=True,package='stress',filter_c_nf=cap,filter_r_ohm=res,maxstep_ns=1 if suffix=='fine' else 2);rows.append(c)
    for src in ['ref','all']:
        c=case('step_'+src+'_10ns_filtered8p2n',kind='step',step_rail=src,edge_ns=10,stop_ns=50000);c.update(candidate=True,package='stress',filter_c_nf=8.2);rows.append(c)
    for kind in ['startup','fault','pwm']:
        c=case(kind+'_filtered8p2n',kind=kind,stop_ns={'startup':40000,'fault':66125,'pwm':1070000}[kind]);c.update(candidate=True,package='stress',filter_c_nf=8.2);rows.append(c)
    for src in ['ref','all']:
        c=case('step_'+src+'_10ns_filtered10n',kind='step',step_rail=src,edge_ns=10,stop_ns=50000);c.update(candidate=True,package='stress',filter_c_nf=10);rows.append(c)
    for kind in ['startup','fault','pwm']:
        c=case(kind+'_filtered10n',kind=kind,stop_ns={'startup':40000,'fault':66125,'pwm':1070000}[kind]);c.update(candidate=True,package='stress',filter_c_nf=10);rows.append(c)
    for src in ['ref','all']:
        c=case('step_'+src+'_10ns_filtered',kind='step',step_rail=src,edge_ns=10,stop_ns=100000);c.update(candidate=True,package='stress');rows.append(c)
    for kind in ['startup','fault','pwm']:
        c=case(kind+'_filtered',kind=kind,stop_ns={'startup':80000,'fault':66125,'pwm':1070000}[kind]);c.update(candidate=True,package='stress');rows.append(c)
    return rows

def board_cases():
    rows=[]
    for name,kind,stop in [('dc_board100n','dc',0),('step_ref_10ns_board100n','step',100000),('step_all_10ns_board100n','step',100000),('startup_board100n','startup',80000),('fault_board100n','fault',66125),('pwm_board100n','pwm',540000)]:
        c=case(name,kind=kind,stop_ns=stop);c.update(candidate=True,package='stress',filter_c_nf=100,filter_location='board')
        if kind=='step':c.update(step_rail='all' if '_all_' in name else 'ref',edge_ns=10)
        if kind=='startup':c['startup_mesh_full']=True
        if kind=='pwm':c.update(pwm_window_start_ns=258500,pwm_window_end_ns=514500)
        rows.append(c)
    for name in ['startup_package_stress_refined','startup_filtered_refined']:
        c=case(name,kind='startup',stop_ns=80000);c.update(candidate='filtered' in name,package='stress',startup_mesh_full=True);rows.append(c)
    return rows

def numerical_cases():
    rows=[]
    for suffix,order,mesh in [('wide',2,.1),('wide_mesh005',2,.05),('wide_gear1',1,.1)]:
        c=case('startup_board100n_'+suffix,kind='startup',stop_ns=80000);c.update(candidate=True,package='stress',filter_c_nf=100,filter_location='board',startup_mesh_full=True,gear_order=order,startup_mesh_ps=mesh,reltol='1e-8',abstol='1e-12',vntol='1e-7');rows.append(c)
    for suffix,order,mesh in [('gear1',1,.1),('gear1_mesh02',1,.2),('gear1_mesh005',1,.05)]:
        c=case('startup_board100n_'+suffix,kind='startup',stop_ns=80000);c.update(candidate=True,package='stress',filter_c_nf=100,filter_location='board',startup_mesh_full=True,gear_order=order,startup_mesh_ps=mesh);rows.append(c)
    return rows

def source_values(c,p):
    v,l=c['logic_v'],c['led_v'];sources={'ref':str(v),'safe':str(v),'buf':str(v),'led':str(l)}
    if c['kind']=='step':
        for src in sources:
            if c['step_rail']=='all' or src==c['step_rail']:
                a=l if src=='led' else v;e=c['edge_ns'];sources[src]=f'PWL(0 {a} 10u {a} {10000+e}n {a*.9:.12g} 25u {a*.9:.12g} {25000+e}n {a} {c["stop_ns"]}n {a})'
    if c['kind']=='startup':
        # Slope unchanged; explicit .1ps knots in first .02ns and ramp knee.
        mesh=c.get('startup_mesh_ps',.1);unit=5e-14 if mesh==.05 else 1e-13;div=2000000 if mesh==.05 else 1000000;step=1 if mesh==.05 else int(round(mesh/.1))
        if c.get('startup_mesh_full'):
            factor=2 if mesh==.05 else 1;ticks=sorted(set(range(0,10000*factor+1,step))|set(range(990000*factor,1020000*factor+1,step))|{div})
        else:ticks=sorted(set(range(201))|set(range(999800,1000201))|{1000000})
        points=[f'{k*unit:.16g} {v*min(k/div,1):.16g}' for k in ticks]
        sources['ref']='PWL(\n'+'\n'.join('+ '+x for x in points)+f'\n+ {c["stop_ns"]}n {v}\n+)'
    if c['kind'] in ['startup','fault','pwm']:
        fn=50125 if c['kind']=='fault' else -1;stop=47700 if c['kind']=='fault' else -1
        clear=c.get('startup_fault_clear_ns',20000) if c['kind']=='startup' else 100
        duty=1 if c['kind']=='pwm' else 256
        log=command(['vvp',WORK/'safety.vvp',f'+DUTY={duty}',f'+FAULT_NS={fn}',f'+STOP_NS={stop}',f'+STOP_TIME_NS={c["stop_ns"]}',f'+INITIAL_FAULT_CLEAR_NS={clear}',f'+OUT={p/"rtl-events.csv"}'],p,'rtl.log')
        assert 'SAFETY_CASE_PASS' in log
        rows=M.read_events(p/'rtl-events.csv');raw=M.pwl_signal(rows,'raw_pwm',v,c['stop_ns']);fault=M.pwl_signal(rows,'fault',v,c['stop_ns']);permit=M.pwl_signal(rows,'permit',v,c['stop_ns'])
        c['fault_clear_ns']=clear;c['rtl_assertions_passed']=True
    else: raw,fault,permit=str(v),'0',str(v)
    return sources,raw,fault,permit

def deck(c,p,devices):
    sources,raw,fault,permit=source_values(c,p)
    lines=[f'r5 39MOS robustness: {c.get("generator_case_name",c["name"])}',f'.include "{INPUT}/design.ngspice"',f'.lib "{INPUT}/sm141064.ngspice" {c["corner"]}',f'.temp {c["temp_c"]}', '.param sw_stat_global=0 sw_stat_mismatch=0 LED_IS=2.2725351141552272e-20']
    package={'ideal':(0.,0.),'nominal':(.2,2e-9),'stress':(1.,5e-9)}[c['package']]
    for src,name,node in [('ref','VREFRAIL','refrail'),('safe','VSAFE','saferail'),('buf','VBUF','bufrail'),('led','VLED','rail')]:
        upstream=node+'_board';lines.append(f'{name} {upstream} 0 {sources[src]}')
        board_filter=src=='ref' and c['candidate'] and c.get('filter_location')=='board'
        if board_filter:
            lines.extend([f'RFILTER {upstream} ref_filtered_board {c.get("filter_r_ohm",100)}',f'CFILTER ref_filtered_board 0 {c.get("filter_c_nf",100)}n']);upstream='ref_filtered_board'
        if package[1]:lines.extend([f'RPK_{src} {upstream} {node}_pkg {package[0]}',f'LPK_{src} {node}_pkg {node}_pre {package[1]:.12g}'])
        else:lines.append(f'VPK_{src} {upstream} {node}_pre 0')
        if src=='ref' and c['candidate'] and not board_filter:
            lines.extend([f'RFILTER {node}_pre {node} {c.get("filter_r_ohm",100)}',f'CFILTER refrail diegnd {c.get("filter_c_nf",100)}n'])
        else:lines.append(f'VLINK_{src} {node}_pre {node} 0')
    if package[1]:lines.extend([f'RPK_gnd 0 return_pkg {package[0]}',f'LPK_gnd return_pkg diegnd {package[1]:.12g}'])
    else:lines.append('VPK_gnd diegnd 0 0')
    lines.extend(['VLEDLOAD rail led_anode 0','VSET vset 0 .5',f'VRAW raw_pwm 0 {raw}',f'VFAULT fault 0 {fault}',f'VPERMIT permit 0 {permit}','RFAULTPULLUP saferail fault 1Meg'])
    c['actual_resistance_ohm']={}
    for r,val in RES.items():
        val*=c['r_factors'].get(r,1)*(1+c['r_tc_ppm'].get(r,0)*1e-6*(c['temp_c']-27))
        c['actual_resistance_ohm'][r]=val;lines.append(f'{r} {NODES[r]} {val:.16g}')
    lines.extend(['CCOMP n2 ctrl 30p','CSENSE sense 0 30p',f'.include "{INPUT}/dut.spice"','XDUT diegnd refrail saferail bufrail rail raw_pwm fault permit vset sense pb n2 ctrl fault_hb led_k refout bias gate pwm_b safe_out pwm_drive startup_test_macro',f'.include "{INPUT}/microled.spice"','XLED led_anode led_k microled',f'.options reltol={c.get("reltol","1e-7")} abstol={c.get("abstol","1e-14")} vntol={c.get("vntol","1e-9")} method=gear maxord={c.get("gear_order",2)}','.control','set numdgt=15','set wr_vecnames','set wr_singlescale','save all @d.xled.dled[id] @d.xled.dled[capcur]'])
    lines.append('op' if c['kind']=='dc' else f'tran {".001n" if c["kind"]=="startup" else "10n"} {c["stop_ns"]}n 0 {c.get("maxstep_ns",5 if c["kind"]=="pwm" else 2)}n')
    lines.append('wrdata waveform.dat '+' '.join(VEC))
    # All terminal metrics use actual distributed-RC terminals, not macro pins.
    for d in devices:
        for tag,i,j in [('gs',2,3),('gd',2,1),('gb',2,4),('ds',1,3),('bs',4,3),('bd',4,1)]:
            label=f's_{d[0].lower()}_{tag}'
            lines.extend([f'let {label}=vecmax(abs(v(xdut.{d[i].lower()})-v(xdut.{d[j].lower()})))',f'print {label}'])
    lines.extend(['quit','.endc','.end']);return '\n'.join(lines)+'\n'

def run(c,devices,reuse=False):
    p=WORK/c['name'];p.mkdir(exist_ok=True)
    # Generate stimulus only in staging: even a rejected changed-case replay
    # must never modify the completed case's RTL events or logs.
    with tempfile.TemporaryDirectory(prefix='deck-staging-',dir=WORK) as td:
        staging=Path(td);src=deck(c,staging,devices)
        generated_rtl={q.name:q.read_bytes() for q in staging.iterdir() if q.is_file()}
    path=p/'testbench.spice'
    previous=json.loads((p/'result.json').read_text()) if (p/'result.json').exists() else {}
    if reuse and previous.get('deck_sha256')==hashlib.sha256(src.encode()).hexdigest() :
        print('REUSE' if previous.get('completed') else 'REUSE retained incomplete result',c['name'],flush=True);return previous
    if path.exists() and previous:
        # Completed identities are immutable. A metadata-only terminal-inventory
        # expansion may reuse old electrical data, but never upgrades its scope.
        def physics(text):
            return '\n'.join(x for x in text.splitlines() if not x.startswith(('let s_x','print s_x')))
        if reuse and previous.get('completed') and physics(path.read_text())==physics(src):
            print('REUSE existing terminal inventory without upgrade',c['name'],flush=True);return previous
        raise RuntimeError('Immutable case already exists with another deck: '+c['name']+'; choose a new revision identity')
    path.write_text(src)
    for n,data in generated_rtl.items():(p/n).write_bytes(data)
    started=time.time()
    with open('/tmp/open-microled-ngspice.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:
            proc=subprocess.run(['ngspice','-b','testbench.spice'],cwd=p,text=True,capture_output=True,timeout=360)
            log=proc.stdout+proc.stderr;rc=proc.returncode
        except subprocess.TimeoutExpired as e:log='RUN_TIMEOUT\n'+str(e);rc=124
    (p/'ngspice.log').write_text(log)
    result=dict(case=c,deck_sha256=sha(path),log_sha256=sha(p/'ngspice.log'),elapsed_including_lock_s=time.time()-started,exit_code=rc,completed=False)
    error=re.search(r'(?im)^Error:.*|.*timestep too small.*|simulation interrupted|RUN_TIMEOUT',log)
    if rc or error or not (p/'waveform.dat').exists():
        result['failure']=error.group() if error else 'Missing output or nonzero exit'
    else:
        d=np.atleast_2d(np.loadtxt(p/'waveform.dat',skiprows=1));t=d[:,0];i=d[:,1]
        assert np.isfinite(d).all()
        result['completed']=True
        result['rows']=len(d)
        stress={label:float(value) for label,value in re.findall(r'(s_x\d+_(?:gs|gd|gb|ds|bs|bd))\s*=\s*([+\-\deE.]+)',log)}
        assert len(stress)==234,(len(stress),p)
        result['terminal_pairs_logged']=['gs','gd','gb','ds','bs','bd']
        groups={}
        for model in ['05v0','06v0']:
            names=[x[0].lower() for x in devices if x[5].endswith(model)]
            values={key:val for key,val in stress.items() if key.split('_')[1] in names}
            key=max(values,key=values.get);groups[model]=dict(max_abs_voltage_v=values[key],terminal=key)
        result['terminal_peak_by_model_class']=groups;result['terminal_abs_peak_v']=stress
        result['terminal_screen_note']='Actual extracted device-terminal peaks only; 05v0/06v0 are model families, not an endorsed absolute-maximum/reliability threshold.'
        checks=[]
        def ck(name,value): checks.append(dict(name=name,passed=bool(value)))
        if c['kind']=='dc':
            result['current_a']=float(i[0]);result['error_pct']=float((i[0]/100e-6-1)*100);ck('dc_accuracy_within_5pct',abs(result['error_pct'])<=5)
        else:
            assert np.all(np.diff(t)>0) and abs(t[-1]-c['stop_ns']*1e-9)<1e-12
            result.update(current_min_a=float(i.min()),current_max_a=float(i.max()))
            if c['kind']=='step':
                baseline=M.integral(t,i,5e-6,9e-6)/4e-6;final=M.integral(t,i,t[-1]-5e-6,t[-1])/5e-6
                stepstart=25e-6+c['edge_ns']*1e-9;out=np.flatnonzero((t>=stepstart)&(np.abs(i-final)>.005*abs(final)))
                settle=None if len(out) and out[-1]==len(t)-1 else 0 if not len(out) else float(t[out[-1]+1]-stepstart)
                result.update(baseline_current_a=baseline,final_current_a=final,settle_after_restore_0p5pct_s=settle,excursion_pct_of_pre_step=float(np.max(np.abs(i/baseline-1))*100),die_reference_min_v=float((d[:,IDX['v(refrail)']]-d[:,IDX['v(diegnd)']]).min()),die_reference_max_v=float((d[:,IDX['v(refrail)']]-d[:,IDX['v(diegnd)']]).max()))
                ck('research_transient_excursion_20pct',result['excursion_pct_of_pre_step']<=20);ck('research_restore_settle_5us',settle is not None and settle<=5e-6)
            elif c['kind']=='startup':
                clear=c['fault_clear_ns']*1e-9;held=np.max(np.abs(M.clip(t,i,0,clear)[1]));cond=d[:,IDX['@d.xled.dled[id]']]-d[:,IDX['@d.xled.dled[capcur]']]
                pre=np.max(np.abs(M.clip(t,cond,clear,clear+1.5e-6)[1]));recovered=M.integral(t,i,t[-1]-10e-6,t[-1])/10e-6
                result.update(held_fault_peak_a=float(held),held_fault_charge=M.split_charge(t,i,0,clear),prepermit_conduction_peak_a=float(pre),recovered_a=recovered,held_fault_conduction_peak_a=float(np.max(np.abs(M.clip(t,cond,0,clear)[1]))),held_fault_displacement_peak_a=float(np.max(np.abs(M.clip(t,d[:,IDX['@d.xled.dled[capcur]']],0,clear)[1]))),diegnd_peak_abs_v=float(np.max(np.abs(d[:,IDX['v(diegnd)']]))))
                ck('startup_held_fault_1nA',held<=1e-9);ck('startup_no_conduction_before_permit_1nA',pre<1e-9);ck('startup_recovered_within5pct',abs(recovered/100e-6-1)<=.05)
            elif c['kind']=='fault':
                f=50.125e-6;safe=M.stable_below_time(t,i,f,f+3e-6,1e-9);charge=M.split_charge(t,i,f,f+1e-6);held=float(np.max(np.abs(M.clip(t,i,f+1e-6,f+2e-6)[1])));cond=d[:,IDX['@d.xled.dled[id]']]-d[:,IDX['@d.xled.dled[capcur]']];rel=float(np.max(np.abs(M.clip(t,cond,f+3e-6,f+5e-6)[1])));recovered=M.integral(t,i,t[-1]-3e-6,t[-1])/3e-6
                result.update(fault_to_safe_s=None if safe is None else safe-f,fault_charge=charge,held_fault_peak_a=held,stopped_clock_release_conduction_peak_a=rel,recovered_a=recovered)
                ck('fault_shutdown_1us',safe is not None and safe-f<1e-6);ck('fault_Qpositive_10pC',charge['positive_c']<10e-12);ck('fault_Qnegative_20pC',abs(charge['negative_c'])<20e-12);ck('fault_held_1nA',held<1e-9);ck('fault_stopped_clock_release_1nA',rel<1e-9);ck('fault_recovered_within5pct',abs(recovered/100e-6-1)<.05)
            elif c['kind']=='pwm':
                refcase='dc_board100n' if c.get('filter_location')=='board' else ('dc_filtered8p2n' if c.get('filter_c_nf')==8.2 else 'dc_filtered10n' if c.get('filter_c_nf')==10 else 'dc_filtered') if c['candidate'] else 'dc_package_stress';reference=json.loads((WORK/refcase/'result.json').read_text())['current_a'];left=c.get('pwm_window_start_ns',514500)*1e-9;right=c.get('pwm_window_end_ns',1026500)*1e-9;q=M.integral(t,i,left,right);error=(q/((right-left)*reference/256)-1)*100
                result.update(d1_charge_c=q,d1_charge_error_pct=error,matched_dc_reference=refcase,matched_dc_current_a=reference,pwm_integration_window_s=[left,right])
                ck('duty1_charge_error_2pct',abs(error)<2)
        result['checks']=checks;result['passed']=all(x['passed'] for x in checks)
        # Compact waveforms: dense around event knees plus regular samples/extrema.
        if c['kind']!='dc':
            selected=set(np.linspace(0,len(t)-1,min(1600,len(t)),dtype=int))
            for k in range(1,d.shape[1]):selected.update([int(d[:,k].argmin()),int(d[:,k].argmax())])
            for a,b in [(9.9e-6,10.2e-6),(24.9e-6,25.2e-6),(50e-6,51e-6),(514.4e-6,516e-6)]:
                ids=np.flatnonzero((t>=a)&(t<=b));selected.update(ids[::max(1,len(ids)//300)])
            np.savetxt(EVID/(c['name']+'.csv'),d[sorted(selected)],delimiter=',',header='time_s,'+','.join(VEC),comments='',fmt='%.12e')
        raw=p/'waveform.dat';result['raw_sha256']=sha(raw);result['raw_uncompressed_bytes']=raw.stat().st_size
        with raw.open('rb') as src,gzip.open(str(raw)+'.gz','wb',compresslevel=6) as dst:shutil.copyfileobj(src,dst)
        with gzip.open(str(raw)+'.gz','rb') as f:assert hashlib.sha256(f.read()).hexdigest()==result['raw_sha256']
        result['raw_gzip_sha256']=sha(Path(str(raw)+'.gz'));raw.unlink()
    save(p/'result.json',result);save(EVID/(c['name']+'.json'),result)
    print(c['name'],'PASS' if result.get('passed') else 'FAIL',result.get('error_pct',result.get('excursion_pct_of_pre_step',result.get('failure',result.get('d1_charge_error_pct',result.get('held_fault_peak_a'))))),flush=True)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--suite',choices=['pilot','dc','cold-tc','transient','candidate','selected','strong','board','all','summarize'],default='pilot');ap.add_argument('--only');ap.add_argument('--reuse',action='store_true');args=ap.parse_args()
    devices=freeze();allcases=dc_cases()+trans_cases()+candidate_cases()+board_cases()+numerical_cases()
    rows=[]
    if args.only:
        rows=[c for c in allcases if c['name']==args.only]
        if not rows and (WORK/args.only/'result.json').exists():rows=[json.loads((WORK/args.only/'result.json').read_text())['case']]
        if not rows:raise ValueError('Unknown case '+args.only)
    elif args.suite=='pilot':rows=[c for c in allcases if c['name'] in ['dc_nominal','dc_package_stress','dc_filtered','step_ref_100ns','step_ref_10ns','step_all_10ns_package_stress']]
    elif args.suite=='dc':rows=dc_cases()
    elif args.suite=='cold-tc':rows=[c for c in dc_cases() if 'cold_tc_independent' in c['name']]
    elif args.suite=='transient':rows=trans_cases()
    elif args.suite=='candidate':rows=candidate_cases()
    elif args.suite=='selected':rows=[c for c in allcases if 'filtered8p2n' in c['name']]
    elif args.suite=='board':rows=board_cases()
    elif args.suite=='strong':rows=[c for c in allcases if c['name'].endswith('_filtered') or 'filtered100n_' in c['name']]
    elif args.suite=='all':rows=allcases
    for c in rows:run(c,devices,args.reuse)
    results=[json.loads(p.read_text()) for p in sorted(WORK.glob('*/result.json'))]
    summary=dict(schema_version=1,date='2026-10-24',scope='New external resistor tolerance/temperature coefficient, rail step and lumped package R/L experiments on old selected actual39MOS full nominalRC. No optical, full pad/ESD, reliability, statistical yield, arbitrary rail sequencing or new DRC/LVS claim.',source_dut_sha256=sha(INPUT/'dut.spice'),script_sha256=sha(Path(__file__)),assumptions=dict(target_current_a=100e-6,synthetic_led_vf_at100uA_27C_v=2.8,external_resistor_tolerance=dict(RSET=.01,RBIAS=.05,RRELEASE=.05,RBLEED=.05),external_resistor_tc_ppm=dict(RSET=100,RBIAS=200,RRELEASE=200,RBLEED=200),tolerance_reference_temp_c=27,package_each_path_nominal=dict(R_ohm=.2,L_h=2e-9),package_each_path_stress=dict(R_ohm=1,L_h=5e-9),package_paths=['VREF','VSAFE','VBUF','LED_A','VSS_return'],candidate=dict(RFILTER_ohm=100,CFILTER_f=100e-9,startup_fault_clear_us=20,locations=['Legacy die-port capacitance with shared package return; not PCB placement','board cases place both R and C before package R/L with C return at board ground'],capacitor_trial_nf=[100,10,8.2]),research_rail_excursion_budget_pct=20,research_restore_budget_us=5),count=len(results),completed_count=sum(r['completed'] for r in results),passed_count=sum(r.get('passed',False) for r in results),results=results)
    save(EVID/'summary.json',summary);save(WORK/'summary.json',summary)
    print(json.dumps({k:summary[k] for k in ['count','completed_count','passed_count']},indent=2))
if __name__=='__main__':main()
