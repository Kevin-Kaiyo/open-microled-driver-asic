"""Read-only independent audit; no project runner imports and no SPICE calls."""
from pathlib import Path
import gzip,hashlib,io,itertools,json
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'build/nrz-reference-v2/selected-final-r2'
OUT=Path(__file__).with_name('review-final-nrz-check.json')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def same(a,b):assert np.isclose(a,b,rtol=1e-9,atol=1e-14),(a,b)
def node(tr,vec,n):return np.zeros(len(tr)) if n=='0' else tr[:,vec[n]]
def stress(tr,q):
    records=[]
    for d in q['devices']:
        ns=[node(tr,q['vectors'],n) for n in d['nodes']]
        pairs=[(name,float(np.max(abs(ns[i]-ns[j])))) for name,i,j in
               [('VDS',0,2),('VGS',1,2),('VGD',1,0),('VGB',1,3),('VDB',0,3),('VSB',2,3)]]
        pair,maximum=max(pairs,key=lambda x:x[1]);limit=6 if '06v0' in d['model'] else 3.63
        records.append(dict(instance=d['instance'],model=d['model'],pair=pair,max_V=maximum,margin_V=limit-maximum))
    return min(records,key=lambda x:x['margin_V'])

m=json.loads((WORK/'manifest.json').read_text());hmanifest=sha(WORK/'manifest.json')
for path,h in m['source_hashes'].items():assert sha(WORK/'inputs'/path)==h
assert sha(WORK/'stimulus.json')==m['stimulus_sha256']
assert m['variants']['B']['REFERENCE']['sha256']=='925b0e98ede116b7d3dc0c0f326aa1704fd08b84dd8cabe39cf03ae4ac4f3d6a'
records=[];counts={};dcfails=[];startupfails=[]
for stage,analysisfile in [('dc','analysis.json'),('startup','startup-analysis.json'),('slow','slow-analysis.json')]:
    plan=WORK/f'plan-{stage}.json';p=json.loads(plan.read_text())
    assert p['source_sha256']==m['source_hashes']['pipeline/final_v2.py']
    counts[stage]=dict(planned=len(p['cases']),checked=0,current_failures=0,device_failures=0,contract_failures=0)
    for case in p['cases']:
        folder=WORK/'cases'/case['name'];rp=folder/'result.json';q=json.loads(rp.read_text());a=json.loads((folder/analysisfile).read_text());row=a['row']
        assert case==q['case']==json.loads((folder/'case.json').read_text())
        assert q['simulation_ok'] and q['exit_code']==0
        assert q['runner_source_sha256']==m['source_hashes']['pipeline/run.py']==sha(ROOT/q['runner_source'])
        assert q['candidate_definition']==m['variants']['B']['REFERENCE']
        assert q['candidate_definition_sha256']==hashlib.sha256(json.dumps(q['candidate_definition'],sort_keys=True).encode()).hexdigest()
        assert sha(folder/'testbench.spice')==q['deck_sha256'] and sha(ROOT/q['log'])==q['log_sha256']
        assert q['stimulus_sha256']==m['stimulus_sha256']
        for path,h in q['input_identity'].items():assert sha(WORK/'inputs'/path)==h==m['source_hashes'][path]
        ident=a['analysis_identity'];assert ident['result_sha256']==sha(rp)
        if stage=='dc':
            assert ident['custom_analyzer_sha256']==sha(ROOT/ident['analyzer_source'])==m['source_hashes']['pipeline/validate.py']
            for key in ('legacy_metrics_sha256','legacy_analyze_sha256'):
                name='metrics' if 'metrics' in key else 'analyze'
                assert ident[key]==m['source_hashes'][f'legacy/{name}.py']
        else:
            assert ident['source_sha256']==m['source_hashes']['pipeline/vi_startup.py']
            assert sha(WORK/'execution-sources'/('vi-startup-'+ident['source_sha256']+'.py'))==ident['source_sha256']
        wave=ROOT/q['waveform'];assert sha(wave)==q['waveform_sha256']
        raw=gzip.decompress(wave.read_bytes());assert len(raw)==q['uncompressed_bytes'] and hashlib.sha256(raw).hexdigest()==q['uncompressed_sha256']
        tr=np.atleast_2d(np.loadtxt(io.BytesIO(raw),skiprows=1));del raw
        assert len(tr)==q['rows'] and np.isfinite(tr).all()
        t=tr[:,0];vec=q['vectors'];current=tr[:,vec['iled_cond']];worst=stress(tr,q)
        key='minimum_device_specific_margin_V' if stage=='dc' else 'minimum_device_margin_V'
        same(worst['margin_V'],row[key]);devicepass=worst['margin_V']>=0
        assert devicepass==row['device_specific_screen_passed' if stage=='dc' else 'device_screen_passed']
        result=dict(name=case['name'],stage=stage,result_sha256=sha(rp),analysis_sha256=sha(folder/analysisfile),
                    raw_roundtrip_verified=True,runner_matches_manifest=True,worst_device=worst,device_passed=devicepass)
        if stage=='dc':
            target=100e-6 if case['dc_bit'] else 25e-6
            error=(current[-1]/target-1)*100;same(error,row['LED_current_error_percent'])
            result.update(current_A=float(current[-1]),error_percent=float(error),current_target_passed=bool(abs(error)<=5))
            if abs(error)>5:dcfails.append(result);counts[stage]['current_failures']+=1
        else:
            assert np.all(np.diff(t)>0);same(t[-1],case['startup']['stop_s']);last=t>case['startup']['stop_s']-10e-6
            if stage=='startup':
                s=case['startup'];release=s['disable_release_s'];hold=np.zeros(len(t),dtype=bool)
                for lo,hi in s.get('hold_windows_s',[[0,release]]):hold|=(t>=lo)&(t<hi)
                outside=np.flatnonzero((t>=release)&(abs(current-100e-6)>5e-6))
                settled=t[outside[-1]] if len(outside) else release
                holdpeak=float(current[hold].max());peak=float(current.max());pp=float(np.ptp(current[last]))
                for key,value in [('hold_peak_A',holdpeak),('current_peak_A',peak),('last10us_pp_A',pp),('last_outside_5pct_s',settled)]:same(value,row[key])
                ready=settled<=release+2e-6 and abs(current[-1]-100e-6)<=5e-6
                passed=peak<=125e-6 and pp<1e-6 and holdpeak<=2e-6 and ready and devicepass
                assert bool(passed)==row['startup_passed']
                result.update(peak_A=peak,hold_peak_A=holdpeak,release_to_last_outside_s=float(max(0,settled-release)),ready_passed=bool(ready),contract_passed=bool(passed))
                if not passed:startupfails.append(result)
            else:
                target=np.where(tr[:,vec['data']]>case['vdd_V']/2,100e-6,25e-6);mask=t>2e-6
                edges=[20e-6,40e-6,60e-6,80e-6,100e-6] if case['startup']['kind']=='loadstep' else [20e-6,40e-6]
                for edge in edges:mask&=~((t>=edge-1e-12)&(t<edge+2e-6))
                error=float(np.max(abs(current[mask]-target[mask])/target[mask]));pp=float(np.ptp(tr[last,vec['iset_current']]))
                same(error,row['max_current_error_fraction_after_2us']);same(pp,row['iset_last10us_pp_A'])
                passed=devicepass and current.max()<=125e-6 and error<=.05 and pp<=1e-6
                assert bool(passed)==row['slow_passed'];result.update(error_fraction_after_blanking=error,contract_passed=bool(passed))
            counts[stage]['contract_failures']+=not passed
        counts[stage]['device_failures']+=not devicepass;counts[stage]['checked']+=1;records.append(result)

ac=[]
for p in sorted((ROOT/'evidence/nrz-reference-v2').glob('vi-loop-shunt150-*-final-r2*.json')):
    q=json.loads(p.read_text());folder=ROOT/'build/nrz-reference-v2'/p.stem
    assert sha(folder/'executed-vi_loop.py')==q['source_sha256']==m['source_hashes']['pipeline/vi_loop.py']
    source=(WORK/'inputs/physical/B-reference-RC.spice').read_text()
    closed=(folder/'closed/core.spice').read_text()
    normalize=lambda x:'\n'.join(line.strip() for line in x.splitlines() if line.strip())
    assert normalize(closed)==normalize(source)
    for rec in q['records']:
        d=folder/rec['method']
        for file,key in [('testbench.spice','deck_sha256'),('core.spice','core_sha256'),('ngspice.log','log_sha256')]:assert sha(d/file)==rec[key]
    v=np.loadtxt(folder/'voltage/ac.dat',skiprows=1);i=np.loadtxt(folder/'current/ac.dat',skiprows=1)
    assert np.array_equal(v[:,0],i[:,0]);f=v[:,0]
    tv=-(v[:,1]+1j*v[:,2])/(v[:,3]+1j*v[:,4]);ti=(i[:,1]+1j*i[:,2])/(i[:,3]+1j*i[:,4]);T=(tv*ti-1)/(tv+ti+2)
    g=20*np.log10(abs(T));phase=np.unwrap(np.angle(T))*180/np.pi
    curve=np.loadtxt(folder/'loop.csv',delimiter=',',skiprows=1);assert np.allclose(curve,np.c_[f,g,phase],rtol=1e-10,atol=1e-10)
    crossings=[]
    for j in np.flatnonzero(((g[:-1]>=0)&(g[1:]<0))|((g[:-1]<0)&(g[1:]>=0))):
        frac=-g[j]/(g[j+1]-g[j]);crossings.append(dict(direction='down' if g[j]>=0 else 'up',frequency_Hz=float(np.exp(np.log(f[j])+frac*np.log(f[j+1]/f[j]))),phase_margin_deg=float(180+phase[j]+frac*(phase[j+1]-phase[j]))))
    down=[x for x in crossings if x['direction']=='down'];assert len(down)==len(q['crossings'])
    for x,y in zip(down,q['crossings']):same(x['frequency_Hz'],y['frequency_Hz']);same(x['phase_margin_deg'],y['phase_margin_deg'])
    ops=[np.loadtxt(folder/k/'op.dat',skiprows=1) for k in ('closed','voltage','current')]
    delta=max(float(np.max(abs(x-ops[0]))) for x in ops[1:]);same(delta,q['closed_injected_op_max_delta'])
    ac.append(dict(name=p.stem,result_sha256=sha(p),source_bound_to_final_fullRC=True,all_crossings=crossings,op_delta=delta))
assert len(ac)==7
output=dict(status='frozen_NRZ_DC_startup_slow_AC_independently_recomputed; communication_and_PWM_pending',manifest_sha256=hmanifest,
            script_sha256=sha(__file__),counts=counts,current_failures=dcfails,startup_failures=startupfails,ac=ac,records=records,
            no_ngspice_invocation=True,no_engineering_source_mutations=True)
OUT.write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(dict(counts=counts,dc_fail_names=[x['name'] for x in dcfails],startup_failures=startupfails,ac_points=len(ac)),indent=2))
