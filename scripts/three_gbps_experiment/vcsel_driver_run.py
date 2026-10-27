#!/usr/bin/env python3
"""Frozen, bounded transistor-level VCSEL research runs; no PEX qualification."""
from pathlib import Path
import argparse, datetime, gzip, hashlib, importlib.util, json, math, shutil, subprocess, time
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'build/three-gbps-experiment-20261027/vcsel-driver'
CIRCUIT = ROOT / 'analog/circuits/vcsel_research_20261027/vcsel_bias_mod.spice'
MODEL = ROOT / 'analog/models/vcsel_research_20261027/vcsel_research.spice'
RX = ROOT / 'scripts/fair_driver_v1/receiver_equal_latency_v2.py'
PORTS = ['VLASER', 'VDD', 'VREF', 'VD', 'VDB']
PINS = dict(D='d', DB='db', OUT='out', VLASER='vlaser', VDD='vdd', VREF='vref', VSS='0')


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576), b''): h.update(b)
    return h.hexdigest()


def emit(p, x):
    Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def module(p, name):
    s=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def seeded_stimulus(seed,rx):
    """Same PRBS15 recurrence/frame as v2; only an explicit nonzero15bit seed varies."""
    assert 0<seed<32768
    stimulus=rx.make_stimulus()
    if seed==0x5ACE:return stimulus
    state=seed;bits=[]
    for _ in range(4736):
        bits.append((state>>14)&1);state=((state<<1)&0x7fff)|(((state>>14)^(state>>13))&1)
    mapping={(0,0):0,(0,1):1,(1,1):2,(1,0):3};symbols=[mapping[tuple(bits[k:k+2])] for k in range(0,len(bits),2)]
    validation=symbols[288:2336]
    stimulus.update(seed=seed,bits=bits,symbols_N=list(bits),symbols_C=symbols,
        validation_PAM4_symbol_counts={str(k):validation.count(k) for k in range(4)},
        validation_PAM4_directed_transition_counts={f'{a}->{b}':sum((x,y)==(a,b) for x,y in zip(validation[:-1],validation[1:])) for a in range(4) for b in range(4) if a!=b},
        provenance='Explicit seed override only; PRBS15x15+x14+1 recurrence,frame ranges,training/guard/payload/tail unchanged')
    return stimulus


def devices(text):
    out=[]
    for line in text.splitlines():
        w=line.split()
        if len(w)<6 or w[5] not in ['nmos_3p3','pmos_3p3']: continue
        out.append(dict(instance=w[0], model=w[5], nodes=[PINS.get(n,'xdrv.'+n.lower()) for n in w[1:5]], parameters=w[6:]))
    assert len(out)==13
    return out


def pwl(bits,ui,vdd,edge=20e-12):
    entries=[(0,bits[0]*vdd)]
    for k in range(1,len(bits)):
        if bits[k]!=bits[k-1]: entries += [(k*ui,bits[k-1]*vdd),(k*ui+edge,bits[k]*vdd)]
    entries.append((len(bits)*ui,bits[-1]*vdd))
    return 'PWL(\n+'+'\n+'.join(' '.join(f'{t:.15g} {v:.15g}' for t,v in entries[j:j+4]) for j in range(0,len(entries),4))+')'


def stress(data, ix, devs):
    def v(n): return np.zeros(len(data)) if n=='0' else data[:,ix['v('+n+')']]
    rows=[]
    for d in devs:
        vs=[v(n) for n in d['nodes']]
        pairs={p:float(np.max(np.abs(vs[a]-vs[b]))) for p,a,b in [('VDS',0,2),('VGS',1,2),('VGD',1,0),('VGB',1,3),('VDB',0,3),('VSB',2,3)]}
        forward=max(float(np.max(vs[3]-vs[0])),float(np.max(vs[3]-vs[2])),0.) if d['model'].startswith('n') else max(float(np.max(vs[0]-vs[3])),float(np.max(vs[2]-vs[3])),0.)
        rows.append(dict(d, max_abs_terminal_V=pairs,max_body_forward_V=forward,screen_pass=max(pairs.values())<=3.63 and forward<=.3))
    return rows


def compress(p):
    original=sha(p); gz=p.with_suffix(p.suffix+'.gz')
    with p.open('rb') as fi,gzip.open(gz,'wb',compresslevel=5) as fo: shutil.copyfileobj(fi,fo)
    h=hashlib.sha256()
    with gzip.open(gz,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    assert h.hexdigest()==original
    p.unlink() # Only newly generated scratch, after lossless read-back verification.
    return dict(path=str(gz.relative_to(ROOT)),sha256=sha(gz),raw_sha256=original,bytes=gz.stat().st_size,roundtrip_verified=True)


def run(args):
    work=BUILD/args.name
    if args.recover:
        assert work.exists() and not (work/'result.json').exists()
        log=(work/'ngspice.log').read_text()
        assert 'No. of Data Rows' in log and 'ngspice-' in log and 'done' in log and 'Error:' not in log
        stored=json.loads((work/'manifest.json').read_text())
        return summarize(work,argparse.Namespace(**stored['args']),0,None,recovery=True)
    assert not work.exists(), 'Use a new immutable run name'
    assert shutil.disk_usage(ROOT).free>2*1024**3
    lock=json.loads((ROOT/'analog/models/pdk-lock.json').read_text())
    for name,digest in lock['files'].items():
        assert sha(ROOT/'.cache/pdk/gf180mcu'/Path(name).name)==digest, 'Pinned model subset hash drift'
    inp=work/'inputs'; inp.mkdir(parents=True)
    sources={'driver.spice':CIRCUIT,'vcsel.spice':MODEL,'receiver.py':RX,'runner.py':Path(__file__),
             'design.ngspice':ROOT/'.cache/pdk/gf180mcu/design.ngspice','sm141064.ngspice':ROOT/'.cache/pdk/gf180mcu/sm141064.ngspice'}
    for name,src in sources.items(): shutil.copy2(src,inp/name)
    rx=module(inp/'receiver.py','vcsel_receiver_'+args.name.replace('-','_'))
    stim=seeded_stimulus(args.seed,rx); emit(work/'stimulus.json',stim)
    devs=devices((inp/'driver.spice').read_text())
    nodes=sorted({n for d in devs for n in d['nodes']} - {'0'})
    expr=['v(jmon)']+['v('+n+')' for n in nodes]+['v('+n+')' for n in ['laser_src','vdd_src','ref_src','d_src','db_src','vc_a','vc_k']]+['i('+p+')' for p in PORTS]+['i(v.xdrv.vibase)','i(v.xdrv.vitail)']
    ix={e:i+1 for i,e in enumerate(expr)}
    ui=32/37/(args.rate*1e9); end=4736*ui
    pvt={'TT':('typical',25,3.3),'SS':('ss',125,2.97),'FF':('ff',-40,3.63)}[args.pvt]
    co,temp,vdd=pvt
    # Sources, supply R/L/decoupling, package R/L are explicit engineering assumptions.
    plan=dict(created=datetime.datetime.now().astimezone().isoformat(),args=vars(args),corner=co,temp_C=temp,supply_V=vdd,
              sources={n:sha(inp/n) for n in sources},stimulus_sha256=sha(work/'stimulus.json'),devices=devs,expressions=expr,
              ngspice_version=subprocess.check_output(['ngspice','--version'],text=True),
              fixed_receiver_contract=dict(frame_bits=4736,payload_bits=4096,training_scored_bits=448,training_guard_bits=64,
                  electrical_targets_mA=[3,7],normalization_uAeq=[25,100],threshold_uAeq=62.5,min_signed_margin_uAeq=7.5,
                  min_time_margin_ps=100,delay_budget_ns=8,delay_step_ps=5,
                  optical_response=args.optical_response,rx_pole_GHz=args.rx_ghz,
                  optical_curve='model-card provided lookup; specified separately by vcsel_driver_analyze.py',
                  boundary='Equivalent-current affine optical-power proxy only; no calibrated coupling, photodiode, TIA or RX power'),
              power_scope='All five ideal source terminal ports incl complementary input, references, dummy, buffers, VCSEL and RLC; upstream source losses, serializer, CDR, receiver excluded',
              evidence='Public GF180 BSIM schematic simulation + graph-constrained VCSEL research proxy. No physical PDK, layout, PEX, silicon, optical or BER qualification',
              thermal_boundary='GF180 circuit corner temperature varies; VCSEL graph remains25C and has no validated temperature model',
              supply_model=dict(series_R_ohm=.25,series_L_H=.2e-9,decoupling_F=1e-9,decoupling_ESR_ohm=.1,reference_R_ohm=.2,data_R_ohm=50,package_R_ohm=.5,package_L_H=.2e-9),
              stress_screen=dict(max_abs_terminal_V=3.63,max_body_forward_V=.3,boundary='Conservative engineering screen; not full reliability qualification'))
    emit(work/'manifest.json',plan)
    data0=f'{args.level*vdd}' if args.mode=='dc' else pwl(stim['bits'],ui,vdd)
    data1=f'{(1-args.level)*vdd}' if args.mode=='dc' else pwl([1-b for b in stim['bits']],ui,vdd)
    action='op' if args.mode=='dc' else f'tran {ui/args.steps:.15g} {end:.15g} 0 {ui/args.steps:.15g}'
    deck=f'''Independent VCSEL driver research {args.name}
.include "{inp/'design.ngspice'}"
.param sw_stat_global=0 sw_stat_mismatch=0
.lib "{inp/'sm141064.ngspice'}" {co}
.include "{inp/'driver.spice'}"
.include "{inp/'vcsel.spice'}"
.temp {temp}
VLASER laser_src 0 {vdd}
RLASER laser_src laser_r .25
LLASER laser_r vlaser .2n
RCLASER vlaser laser_c .1
CLASER laser_c 0 1n
VDD vdd_src 0 {vdd}
RVDD vdd_src vdd_r .25
LVDD vdd_r vdd .2n
RCVDD vdd vdd_c .1
CVDD vdd_c 0 1n
VREF ref_src 0 {vdd}
RREFSRC ref_src vref .2
VD d_src 0 {data0}
VDB db_src 0 {data1}
RD d_src d 50
RDB db_src db 50
XDRV d db out vlaser vdd vref 0 vcsel_bias_mod RREF={args.rref} WBASE={args.wbase} WTAIL={args.wtail}
XVCSEL vlaser vc_k jmon vcsel_research CJ={args.cj}
RPKG vc_k vc_a .5
LPKG vc_a out .2n
.options reltol=1e-5 abstol=1e-12 vntol=1e-7 chgtol=1e-16
.control
set numdgt=12
set wr_singlescale
set wr_vecnames
save {' '.join(expr)}
{action}
wrdata waveform.dat {' '.join(expr)}
quit
.endc
.end
'''
    (work/'testbench.spice').write_text(deck)
    start=time.time()
    try:
        with (work/'ngspice.log').open('w') as log:
            result=subprocess.run(['ngspice','-b','testbench.spice'],cwd=work,stdout=log,stderr=subprocess.STDOUT,timeout=240)
        code=result.returncode
    except subprocess.TimeoutExpired: code='timeout'
    return summarize(work,args,code,time.time()-start)


def summarize(work,args,code,elapsed,recovery=False):
    manifest=json.loads((work/'manifest.json').read_text()); expr=manifest['expressions']; ix={e:i+1 for i,e in enumerate(expr)}; devs=manifest['devices']
    nodes=sorted({n for d in devs for n in d['nodes']} - {'0'})
    end=4736*32/37/(args.rate*1e9)
    result=dict(case=args.name,exit_code=code,elapsed_s=elapsed,manifest_sha256=sha(work/'manifest.json'),deck_sha256=sha(work/'testbench.spice'),log_sha256=sha(work/'ngspice.log'))
    if recovery: result['recovery']=dict(reason='Post-simulation result summarization failure; completed ngspice log verified, no circuit rerun or waveform changes',script_sha256=sha(Path(__file__)))
    waveform=work/'waveform.dat'
    if not waveform.exists() and (work/'waveform.dat.gz').exists(): waveform=work/'waveform.dat.gz'
    if code==0 and waveform.exists():
        a=np.atleast_2d(np.loadtxt(waveform,skiprows=1)); t=a[:,0]
        result.update(sample_count=len(a),simulation_ok=bool(args.mode=='dc' or (t[-1]>=end-1e-15 and np.all(np.diff(t)>0))),current_range_mA=[float(a[:,1].min()*1e3),float(a[:,1].max()*1e3)],
                      stress=stress(a,ix,devs))
        result['device_screen_passed']=all(d['screen_pass'] for d in result['stress'])
        port_nodes=dict(VLASER='laser_src',VDD='vdd_src',VREF='ref_src',VD='d_src',VDB='db_src')
        powers={p:-a[:,ix['v('+port_nodes[p]+')']]*a[:,ix['i('+p+')']] for p in PORTS}
        if args.mode=='dc':
            result.update(current_mA=float(a[-1,1]*1e3),reference_current_mA=float(-a[-1,ix['i(VREF)']]*1e3),base_current_mA=float(a[-1,ix['i(v.xdrv.vibase)']]*1e3),tail_current_mA=float(a[-1,ix['i(v.xdrv.vitail)']]*1e3),nodes_V={n:float(a[-1,ix['v('+n+')']]) for n in nodes},source_power_W={p:float(v[-1]) for p,v in powers.items()})
        else:
            ledger={p:dict(positive_J=float(np.trapezoid(np.maximum(v,0),t)),returned_J=float(np.trapezoid(np.maximum(-v,0),t)),net_J=float(np.trapezoid(v,t))) for p,v in powers.items()}
            sums={k:sum(v[k] for v in ledger.values()) for k in ['positive_J','returned_J','net_J']}
            result.update(energy_by_port=ledger,total_energy=dict(sums,positive_pJ_per_offered_payload_bit=sums['positive_J']/4096*1e12,net_pJ_per_offered_payload_bit=sums['net_J']/4096*1e12),max_timestep_ps=float(np.diff(t).max()*1e12))
        if waveform.suffix=='.gz':
            result['waveform']=dict(path=str(waveform.relative_to(ROOT)),sha256=sha(waveform),raw_sha256=hashlib.sha256(gzip.open(waveform,'rb').read()).hexdigest(),bytes=waveform.stat().st_size,roundtrip_verified=True)
        else: result['waveform']=compress(waveform)
    else: result['simulation_ok']=False
    emit(work/'result.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['stress','nodes_V']},ensure_ascii=False),flush=True)
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--name',required=True); ap.add_argument('--mode',choices=['dc','frame'],default='dc')
    ap.add_argument('--recover',action='store_true')
    ap.add_argument('--seed',type=lambda s:int(s,0),default=0x5ACE)
    ap.add_argument('--level',type=int,choices=[0,1],default=0); ap.add_argument('--pvt',choices=['TT','SS','FF'],default='TT')
    ap.add_argument('--rate',type=float,default=3.2); ap.add_argument('--steps',type=int,default=40)
    ap.add_argument('--rref',type=float,default=6900.); ap.add_argument('--wbase',type=float,default=60e-6); ap.add_argument('--wtail',type=float,default=84e-6)
    ap.add_argument('--cj',type=float,default=150e-15); ap.add_argument('--optical-response',default='figure3mA_proxy'); ap.add_argument('--rx-ghz',type=float,default=5.)
    run(ap.parse_args())
