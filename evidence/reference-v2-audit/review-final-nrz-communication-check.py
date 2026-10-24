"""Read-only independent NRZ/energy/power audit; does not import producer code."""
from pathlib import Path
import datetime,difflib,gzip,hashlib,json
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'build/nrz-reference-v2/selected-final-r2'
OUT=Path(__file__).with_suffix('.json')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def same(a,b,atol=1e-18):assert np.isclose(a,b,rtol=2e-9,atol=atol),(a,b)
def lowpass(t,x,tau):
    h=np.diff(t)/tau;a=np.exp(-h);b=-np.expm1(-h);c=1-b/h
    small=h<1e-4;z=h[small];c[small]=z/2-z*z/6+z**3/24-z**4/120
    y=np.empty_like(x);y[0]=x[0]
    for j in range(len(h)):y[j+1]=a[j]*y[j]+b[j]*x[j]+c[j]*(x[j+1]-x[j])
    return y
def decisions(t,y,starts,bits,delay,ui):
    when=starts+delay*ui;assert when[0]>=t[0] and when[-1]<=t[-1]
    v=np.interp(when,t,y);errors=int(np.count_nonzero((v>=62.5e-6)!=bits))
    margin=min(v[bits==1].min()-62.5e-6,62.5e-6-v[bits==0].max())
    return errors,float(margin/75e-6)
def receiver(t,current,case,st,tx):
    ui=1/(case['rate_Gbps']*1e9);assert case['rate_Gbps']==.5
    y=lowpass(t,lowpass(t,current,200e-12),1/(2*np.pi*1e9))
    train=np.array(st['training_bits'][:-5]);valid=np.array(st['validation_bits'])
    assert len(train)==249 and len(valid)==511
    starts=(st['training_start_bit']+np.arange(len(train)))*ui
    assert starts[-1]+4*ui<st['validation_start_bit']*ui
    delays=np.arange(513)/128
    scores=np.array([decisions(t,y,starts,train,d,ui) for d in delays])
    eligible=scores[:,0]==scores[:,0].min();best=scores[eligible,1].max()
    ids=np.flatnonzero(eligible&(scores[:,1]>=best-1e-6));groups=np.split(ids,np.flatnonzero(np.diff(ids)!=1)+1)
    group=max(groups,key=len);selected=delays[group[(len(group)-1)//2]]
    same(selected,tx['sampler']['sample_delay_ui'])
    starts=(st['validation_start_bit']+np.arange(511))*ui
    err,margin=decisions(t,y,starts,valid,selected,ui)
    offsets=np.linspace(-.5,.5,129);sweep=[decisions(t,y,starts,valid,selected+d,ui) for d in offsets]
    assert [s[0] for s in sweep]==tx['validation']['phase_sweep']['errors']
    assert np.allclose([s[1] for s in sweep],tx['validation']['phase_sweep']['threshold_margin_normalized'],rtol=2e-9,atol=1e-11)
    safe=[s[0]==0 and s[1]>0 for s in sweep];left=right=64
    if safe[64]:
        while left>0 and safe[left-1]:left-=1
        while right<128 and safe[right+1]:right+=1
    timing=min(-offsets[left],offsets[right]) if safe[64] else 0.
    v=tx['validation'];assert err==v['deterministic_errors'];same(margin,v['threshold_margin_normalized']);same(timing,v['timing_min_margin_ui'])
    passed=err==0 and margin>=.1 and timing>=.1
    assert passed==tx['comparison_screen']['passed']
    return dict(errors=err,bits=511,threshold_margin_normalized=margin,timing_min_margin_ui=float(timing),training_delay_ui=float(selected),receiver_passed=bool(passed))
def energy(t,p,start,end):
    inside=(t>start)&(t<end);tc=np.r_[start,t[inside],end];pc=np.r_[np.interp(start,t,p),p[inside],np.interp(end,t,p)]
    dt=np.diff(tc);a=pc[:-1];b=pc[1:];net=float(np.sum(dt*(a+b)/2))
    # Analytic trapezoid/triangle areas of each PWL segment, independent of producer's zero-insertion code.
    pos=(a>=0)&(b>=0);neg=(a<=0)&(b<=0);cross=~(pos|neg)
    draw=float(np.sum(dt[pos]*(a[pos]+b[pos])/2));returned=float(-np.sum(dt[neg]*(a[neg]+b[neg])/2))
    draw+=float(np.sum(dt[cross]*np.maximum(a[cross],b[cross])**2/(2*np.abs(b[cross]-a[cross]))))
    returned+=float(np.sum(dt[cross]*np.minimum(a[cross],b[cross])**2/(2*np.abs(b[cross]-a[cross]))))
    same(net,draw-returned)
    return dict(net_J=net,positive_draw_J=draw,returned_J=returned)
def stress(a,q):
    rows=[];vec=q['vectors'];zero=np.zeros(len(a))
    for d in q['devices']:
        v=[zero if n=='0' else a[:,vec[n]] for n in d['nodes']]
        allpairs=[float(np.max(abs(v[i]-v[j]))) for i,j in [(0,2),(1,2),(1,0),(1,3),(0,3),(2,3)]]
        maximum=max(allpairs);limit=6. if '06v0' in d['model'] else 3.63
        rows.append(dict(instance=d['instance'],margin_V=limit-maximum,max_V=maximum))
    return min(rows,key=lambda x:x['margin_V'])

def main():
    m=read(WORK/'manifest.json');p=read(WORK/'plan-nrz.json');st=read(WORK/'stimulus.json');am=read(WORK/'budget-amendment.json')
    for file,h in m['source_hashes'].items():assert sha(WORK/'inputs'/file)==h
    assert sha(WORK/'stimulus.json')==m['stimulus_sha256']
    assert p['source_sha256']==m['source_hashes']['pipeline/final_v2.py']
    old=m['source_hashes']['pipeline/run.py'];new=am['runner_after_sha256'];allowed={old,new}
    sources={q['runner_source_sha256']:ROOT/q['runner_source'] for c in p['cases'] if (WORK/'cases'/c['name']/'result.json').exists() for q in [read(WORK/'cases'/c['name']/'result.json')]}
    for h,f in sources.items():assert sha(f)==h
    before=sources[old].read_text();after=sources[new].read_text()
    assert before.replace('MAX_INCREMENTAL_BYTES=2*1024**3','MAX_INCREMENTAL_BYTES=int(3.5*1024**3)')==after
    admin=[]
    for row in am['administrative_records']:
        rp=ROOT/row['archived_directory']/'result.json';assert sha(rp)==row['result_sha256'];q=read(rp)
        assert not q['simulation_ok'] and q['exit_code'] is None
        admin.append(dict(result=str(rp.relative_to(ROOT)),sha256=sha(rp),reason=row['reason']))
    previous=read(OUT) if OUT.exists() else {};cache={x['name']:x for x in previous.get('records',[])} if previous.get('script_sha256')==sha(__file__) else {}
    records=[];missing=[]
    for case in p['cases']:
        d=WORK/'cases'/case['name'];rp=d/'result.json';ap=d/'analysis.json'
        if not rp.exists() or not ap.exists():missing.append(case['name']);continue
        q=read(rp);a=read(ap);r=a['row'];tx=a['transient'];ident=a['analysis_identity']
        assert case==q['case']==read(d/'case.json') and q['simulation_ok'] and q['exit_code']==0 and a['analysis_ok']
        assert q['runner_source_sha256'] in allowed and sha(ROOT/q['runner_source'])==q['runner_source_sha256']
        assert q['candidate_definition']==m['variants']['B']['REFERENCE'] and q['candidate_definition']['sha256']=='925b0e98ede116b7d3dc0c0f326aa1704fd08b84dd8cabe39cf03ae4ac4f3d6a'
        assert q['candidate_definition_sha256']==hashlib.sha256(json.dumps(q['candidate_definition'],sort_keys=True).encode()).hexdigest()
        assert q['stimulus_sha256']==m['stimulus_sha256'] and sha(d/'testbench.spice')==q['deck_sha256'] and sha(ROOT/q['log'])==q['log_sha256']
        for file,h in q['input_identity'].items():assert h==m['source_hashes'][file]==sha(WORK/'inputs'/file)
        assert ident['result_sha256']==sha(rp) and ident['custom_analyzer_sha256']==sha(ROOT/ident['analyzer_source'])==m['source_hashes']['pipeline/validate.py']
        for key,name in [('legacy_metrics_sha256','metrics'),('legacy_analyze_sha256','analyze')]:assert ident[key]==m['source_hashes'][f'legacy/{name}.py']
        wave=ROOT/q['waveform'];assert sha(wave)==q['waveform_sha256']
        fingerprints=dict(result_sha256=sha(rp),analysis_sha256=sha(ap),waveform_sha256=sha(wave))
        if case['name'] in cache and cache[case['name']]['fingerprints']==fingerprints:
            records.append(cache[case['name']]);print(case['kind']+' unchanged verified record',flush=True);continue
        h=hashlib.sha256();size=0
        with gzip.open(wave,'rb') as f:
            for b in iter(lambda:f.read(2**20),b''):h.update(b);size+=len(b)
        assert h.hexdigest()==q['uncompressed_sha256'] and size==q['uncompressed_bytes']
        with gzip.open(wave,'rt') as f:trace=np.loadtxt(f,skiprows=1)
        assert len(trace)==q['rows'] and np.isfinite(trace).all()
        t=trace[:,0];vec=q['vectors'];assert np.all(np.diff(t)>0)
        rx=receiver(t,trace[:,vec['iled_cond']],case,st,tx);worst=stress(trace,q)
        same(worst['margin_V'],r['minimum_device_specific_margin_V']);assert (worst['margin_V']>=0)==r['device_specific_screen_passed']
        ui=2e-9;start=st['validation_start_bit']*ui;end=st['validation_end_bit']*ui;energies={}
        for port in list(q['rails'])+['DATA']:
            vkey='data' if port=='DATA' else port.lower()+'_voltage';ikey='data_current' if port=='DATA' else port.lower()+'_current'
            value=energy(t,-trace[:,vec[vkey]]*trace[:,vec[ikey]],start,end)
            expected=tx['energy']['ideal_DATA'] if port=='DATA' else tx['energy']['rails'][port]
            for key,number in value.items():same(number,expected[key]);same(number/511,expected[key+'_per_gross_bit'])
            energies[port]=value
        total={k:sum(e[k] for e in energies.values()) for k in ['net_J','positive_draw_J','returned_J']}
        for key,num in total.items():same(num,tx['energy']['rail_plus_ideal_DATA_total'][key])
        same(total['positive_draw_J']/511*1e15,r['rail_plus_DATA_positive_draw_fJ_per_gross_bit'])
        passed=rx['receiver_passed'] and worst['margin_V']>=0;assert passed==r['combined_screen_passed']
        rec=dict(name=case['name'],kind=case['kind'],fingerprints=fingerprints,runner_sha256=q['runner_source_sha256'],deep_raw_roundtrip=True,receiver=rx,worst_device=worst,all_ports_energy_J=energies,total_energy_pJ_per_bit={k.replace('_J',''):v/511*1e12 for k,v in total.items()},combined_passed=bool(passed))
        records.append(rec);del trace
        print(case['kind']+' independently verified '+json.dumps(rec['total_energy_pJ_per_bit']),flush=True)
        OUT.write_text(json.dumps(dict(script_sha256=sha(__file__),records=records),indent=2)+'\n')
    powerdir=ROOT/'build/nrz-reference-v2/power-dc-r2';powerplan=read(powerdir/'plan.json');powersummary=read(ROOT/'evidence/nrz-reference-v2/power-dc-r2.json')
    assert sha(powerdir/'plan.json')==powersummary['plan_sha256'] and sha(powerdir/'executed-power_breakdown.py')==powerplan['source_sha256']
    contract=read(WORK/'inputs/physical/integrated-contract.json');mapping={x['original_instance']:x for x in contract['extracted_device_mapping']};powerrows=[]
    for original,extracted in powerplan['map'].items():assert mapping[original]['extracted_instance'].lower()==extracted and mapping[original]['drain_source_swapped']
    for c in powerplan['cases']:
        d=powerdir/c['name'];q=read(d/'result.json');assert q in powersummary['rows']
        for file,key in [('testbench.spice','deck_sha256'),('power.dat','raw_sha256'),('ngspice.log','log_sha256')]:assert sha(d/file)==q[key]
        original=(WORK/'cases'/c['name']/'testbench.spice').read_text().split('.control')[0]
        assert (d/'testbench.spice').read_text().split('.control')[0]==original
        a=np.loadtxt(d/'power.dat',skiprows=1);vin,dummy,raw,led,iset=a[1:6];curr=a[6:]
        value=dict(raw_source_current_A=-raw,dummy_current_A=(vin-dummy)/50000,OTA_control_current_A=sum(curr[:3]),sense_reference_current_A=curr[3],output_reference_current_A=curr[4])
        value['DC_current_closure_residual_A']=value['raw_source_current_A']-sum(value[k] for k in ['dummy_current_A','OTA_control_current_A','sense_reference_current_A','output_reference_current_A'])
        for k,v in value.items():same(v,q[k])
        oldcurrent=read(WORK/'cases'/c['name']/'analysis.json')['row']['LED_current_A'];assert led==oldcurrent and q['LED_difference_from_original_A']==0
        for source,key in [('dummy','dummy_current_A'),('OTA_control','OTA_control_current_A'),('sense_reference','sense_reference_current_A'),('output_reference','output_reference_current_A'),('closure','DC_current_closure_residual_A')]:same(5*value[key],q['source5V_allocated_power_W'][source])
        powerrows.append(dict(name=c['name'],case_sha256=sha(d/'result.json'),circuit_prefix_equals_original=True,LED_delta_A=float(led-oldcurrent),**{k:float(v) for k,v in value.items()}))
    output=dict(created=datetime.datetime.now(datetime.timezone.utc).isoformat(),script_sha256=sha(__file__),manifest_sha256=sha(WORK/'manifest.json'),plan_sha256=sha(WORK/'plan-nrz.json'),budget_amendment_sha256=sha(WORK/'budget-amendment.json'),runner_only_changed_storage_budget=True,administrative_records=admin,planned=len(p['cases']),checked=len(records),missing=missing,records=records,power_plan_sha256=sha(powerdir/'plan.json'),power_rows=powerrows,power_scope='DC source power allocation; explicit model-channel/body-current residual, not local heat or fast branch energy',no_ngspice_invocation=True,no_engineering_source_mutations=True)
    OUT.write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(dict(checked=len(records),missing=missing,power_checked=len(powerrows))))
if __name__=='__main__':main()
