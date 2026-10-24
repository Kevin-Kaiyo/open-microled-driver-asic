"""Independent read-only PWM final audit; no producer imports or simulator calls."""
from pathlib import Path
import gzip,hashlib,itertools,json,re
import numpy as np
ROOT=Path(__file__).resolve().parents[2];W=ROOT/'build/pwm-reference-v2/20261024';E=ROOT/'evidence/pwm-reference-v2/20261024'
OUT=Path(__file__).with_suffix('.json')
def read(p):return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def same(a,b,atol=1e-23):assert np.isclose(a,b,rtol=2e-9,atol=atol),(a,b)
def clip(t,y,lo,hi):
    assert t[0]<=lo+1e-18 and t[-1]>=hi-1e-18
    use=(t>lo)&(t<hi);return np.r_[lo,t[use],hi],np.r_[np.interp(lo,t,y),y[use],np.interp(hi,t,y)]
def integral(t,y,lo,hi):
    x,v=clip(t,y,lo,hi);return float(np.trapezoid(v,x))
def charges(t,y,lo,hi):
    x,v=clip(t,y,lo,hi);dt=np.diff(x);a=v[:-1];b=v[1:];pos=(a>=0)&(b>=0);neg=(a<=0)&(b<=0);cross=~(pos|neg)
    positive=np.sum(dt[pos]*(a[pos]+b[pos])/2)+np.sum(dt[cross]*np.maximum(a[cross],b[cross])**2/(2*abs(a[cross]-b[cross])))
    negative=np.sum(dt[neg]*(a[neg]+b[neg])/2)-np.sum(dt[cross]*np.minimum(a[cross],b[cross])**2/(2*abs(a[cross]-b[cross])))
    return dict(signed_c=float(np.trapezoid(v,x)),positive_c=float(positive),negative_c=float(negative))
def spnum(s):
    x=re.fullmatch(r'([+\-\d.eE]+)([a-zA-Z]*)',s);return float(x[1])*{'':1,'n':1e-9,'u':1e-6,'p':1e-12}[x[2]]
manifests={}
def identity(q,folder,allow_exception=False):
    sid=q['executed_runner_sha256'];assert sha(W/'inputs/executed_sources'/sid/'run.py')==sid
    mh=q['source_manifest_sha256'];mp=W/'inputs/manifests'/(mh+'.json');assert sha(mp)==mh
    if mh not in manifests:
        m=read(mp)
        for n,r in m['files'].items():assert sha(W/'inputs'/n)==r['sha256']
        manifests[mh]=m
    m=manifests[mh];matched=m['executed_runner_sha256']==sid
    assert matched or allow_exception
    assert sha(folder/'testbench.spice')==q['deck_sha256'] and sha(folder/'ngspice.log')==q['log_sha256']
    assert m['files']['dut.spice']['sha256']=='d6ebc340c5f2096c43e1358b851d68590fefddbf47b5cc6e746ffc3c12851424'
    return matched
def load(q,folder):
    wave=folder/('ac.dat.gz' if q['case']['kind']=='ac' else 'waveform.dat.gz');assert sha(wave)==q['gzip_sha256']
    h=hashlib.sha256();size=0
    with gzip.open(wave,'rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b);size+=len(b)
    assert h.hexdigest()==q['raw_sha256'] and size==q['raw_bytes']
    with gzip.open(wave,'rt') as f:a=np.atleast_2d(np.loadtxt(f,skiprows=1))
    assert len(a)==q['rows'] and np.isfinite(a).all();return a
def metrics(q,a):
    c=q['case'];kind=c['kind'];t=a[:,0];i=a[:,1];r={}
    if kind=='dc':r=dict(current_a=float(i[0]),error_pct=float((i[0]/100e-6-1)*100));passed=abs(r['error_pct'])<=5
    elif kind=='ac':passed=True
    else:
        assert np.all(np.diff(t)>0);same(t[-1],c['stop_ns']*1e-9,atol=1e-18)
        r.update(current_min_a=float(i.min()),current_max_a=float(i.max()))
        if kind=='step':
            before=integral(t,i,5e-6,9e-6)/4e-6;after=integral(t,i,t[-1]-5e-6,t[-1])/5e-6
            bad=np.flatnonzero((t>=25.01e-6)&(abs(i-after)>.005*abs(after)))
            settle=0. if not len(bad) else None if bad[-1]==len(t)-1 else float(t[bad[-1]+1]-25.01e-6)
            r.update(baseline_current_a=before,final_current_a=after,excursion_pct=float(np.max(abs(i/before-1))*100),settle_s=settle,ctrl_rail_error_peak_v=float(np.max(abs(a[:,4]-a[:,2]))))
            passed=r['excursion_pct']<=20 and settle is not None and settle<=5e-6
        elif kind=='startup':
            cond=a[:,18]-a[:,19];held=t<=20e-6;late=integral(t,i,30e-6,40e-6)/10e-6
            r.update(held_peak_a=float(abs(i[held]).max()),held_conduction_peak_a=float(abs(cond[held]).max()),held_displacement_peak_a=float(abs(a[held,19]).max()),held_diegnd_peak_v=float(abs(a[held,11]).max()),held_charge=charges(t,i,0,20e-6),recovered_a=late,permit_pre_release_max_v=float(abs(a[t<20e-6,14]).max()),prepermit_conduction_peak_a=float(abs(clip(t,cond,20e-6,21.5e-6)[1]).max()))
            passed=r['held_peak_a']<=1e-9 and r['prepermit_conduction_peak_a']<1e-9 and abs(late/100e-6-1)<=.05
        elif kind=='fault':
            f=50.125e-6;x,v=clip(t,abs(i),f,f+3e-6);bad=np.flatnonzero(v>1e-9)
            if not len(bad):safe=f
            elif bad[-1]==len(v)-1:safe=None
            else:
                k=bad[-1];safe=float(x[k]+(1e-9-v[k])/(v[k+1]-v[k])*(x[k+1]-x[k]))
            charge=charges(t,i,f,f+1e-6);held=float(abs(clip(t,i,f+1e-6,f+2e-6)[1]).max());rel=float(abs(clip(t,a[:,18]-a[:,19],f+3e-6,f+5e-6)[1]).max());late=integral(t,i,t[-1]-3e-6,t[-1])/3e-6
            r.update(fault_to_safe_s=None if safe is None else safe-f,fault_charge=charge,held_fault_peak_a=held,stopped_clock_release_conduction_peak_a=rel,recovered_a=late)
            passed=safe is not None and safe-f<1e-6 and charge['positive_c']<10e-12 and abs(charge['negative_c'])<20e-12 and held<1e-9 and rel<1e-9 and abs(late/100e-6-1)<.05
        elif kind=='pwm':
            ref=read(W/c['dc_reference_case']/'result.json')['current_a'];value=integral(t,i,258.5e-6,514.5e-6);err=(value/(256e-6*ref/256)-1)*100
            r.update(d1_charge_c=value,d1_charge_error_pct=err,matched_dc_current_a=ref);assert q['pwm_integration_window_s']==[258.5e-6,514.5e-6];passed=abs(err)<2
        else:raise ValueError(kind)
    for k,value in r.items():
        if isinstance(value,dict):
            for sub,val in value.items():same(val,q[k][sub])
        elif value is None:assert q[k] is None
        else:same(value,q[k],atol=1e-17 if k.endswith('pct') else 1e-23)
    assert bool(passed)==q['passed'];r['passed']=bool(passed);return r
def main():
    s=read(E/'final-summary.json');v=read(E/'validation.json');assert s['selected_prefix']==v['selected_prefix']=='c15' and s['selected_filter_c_nf']==v['selected_filter_c_nf']==15
    expected={'c15_'+n for n in ['dc','step','step_fine','step_allrails','fault','pwm','ac','startup_fullmesh','startup_fullmesh_trap','startup_ss_slow','startup_ff_fast','dc_equiv_min','dc_equiv_max','dc_extref_min','dc_extref_max']}
    expected|={'c15_dyn_typical_'+''.join(x) for x in itertools.product('mp',repeat=3)}
    expected|={'c15_dyn_'+c+'_'+x for c in ['ss','ff'] for x in ['mmm','ppp']}
    assert expected=={p.parent.name for p in W.glob('c15_*/result.json')} and len(expected)==27
    baseline={'n2rl_dc_'+c+'_'+str(temp)+'_'+''.join(bits) for c in ['typical','ss','ff'] for temp in [0,27,85] for bits in itertools.product('mp',repeat=4)}
    histories={'damped_startup_ss_slow','c47_startup_ss_slow','c47_dyn_ss_mmm','c47_dyn_ss_ppp'}
    names=expected|baseline|histories|{'n2rl_dc','pcb_dc_ff_85_mmmp','pcb_dc_ss_85_pmmm'}
    records=[];data={};objects={}
    for n in sorted(names):
        folder=W/n;rp=folder/'result.json';q=read(rp);objects[n]=q;assert q['case']['name']==n and q['completed'] and q['exit_code']==0;identity(q,folder)
        if n in expected:assert read(E/(n+'.json'))==q
        a=load(q,folder);r=metrics(q,a);r.update(name=n,result_sha256=sha(rp),raw_sha256=q['raw_sha256'],gzip_sha256=q['gzip_sha256'],manifest_sha256=q['source_manifest_sha256'],runner_sha256=q['executed_runner_sha256'],raw_bytes=q['raw_bytes'],window_stop_s=float(a[-1,0]),deep_raw_identity=True)
        deck=(folder/'testbench.spice').read_text()
        if n in expected:
            assert re.search(r'^RDAMP_N2 n2_damp n2_cap 10(?:\.0)?$',deck,re.M)
            assert 'RPK_N2 n2 n2_pin_r 1' in deck and 'LPK_N2 n2_pin_r n2_board 5n' in deck and 'CSENSE sense 0 30p' in deck
            for port in ['raw_pwm','fault','permit']:assert f'RDRV_{port} {port}_driver {port} 10' in deck
            if q['case']['kind'] not in ['ac','dc']:assert '.options reltol=1e-7 abstol=1e-14 vntol=1e-9' in deck
            if q['case']['kind'] in ['startup','fault','pwm']:assert q['case']['rtl_assertions_passed'] and 'SAFETY_CASE_PASS' in (folder/'rtl.log').read_text()
        if 'terminal_abs_peak_v' in q:
            logged={k:float(x) for k,x in re.findall(r'(s_x\d+_(?:gs|gd|gb|ds|bs|bd))\s*=\s*([+\-\deE.]+)',(folder/'ngspice.log').read_text())};assert logged==q['terminal_abs_peak_v'] and len(logged)==234
            devices=[l.split() for l in (W/'inputs/dut.spice').read_text().splitlines() if re.match(r'^X\d+ ',l)]
            for dev in devices:
                for tag,i,j in [('gs',2,3),('gd',2,1),('gb',2,4),('ds',1,3),('bs',4,3),('bd',4,1)]:assert f'let s_{dev[0].lower()}_{tag}=vecmax(abs(v(xdut.{dev[i].lower()})-v(xdut.{dev[j].lower()})))' in deck
            r['logged_terminal_maxima_checked']=234
        if n in ['c15_step','c15_step_fine']:data[n]=a[:,:2].copy()
        if n in ['c15_startup_fullmesh','c15_startup_fullmesh_trap']:
            pwl=re.search(r'^VREFRAIL refrail_board 0 PWL\((.*?)\)',deck,re.M|re.S)[1];tokens=pwl.replace('+','').split();points=np.array([[spnum(tokens[j]),spnum(tokens[j+1])] for j in range(0,len(tokens),2)])
            for lo,hi in [(0,1e-9),(99e-9,102e-9)]:
                x=points[(points[:,0]>=lo-1e-18)&(points[:,0]<=hi+1e-18),0];assert np.diff(x).max()<=1.00001e-13
            r['source_edge_knots_full_0p1ps_verified']=True
        records.append(r);del a
        if n in expected or n in histories:print(n+' independently recomputed',flush=True)
    by={r['name']:r for r in records};dynamic=[by[n] for n in expected if n.startswith('c15_dyn_')]
    same(max(r['excursion_pct'] for r in dynamic),s['dynamic_matrix']['max_excursion_pct']);same(max(r['settle_s'] for r in dynamic),s['dynamic_matrix']['max_restore_s'])
    assert all(by[n]['passed'] for n in expected|baseline)
    same(min(by[n]['error_pct'] for n in baseline),s['dc_matrix']['min_error_pct']);same(max(by[n]['error_pct'] for n in baseline),s['dc_matrix']['max_error_pct'])
    for n,q in s['key_results'].items():assert q==objects[n]
    def dc_remainder(n):
        lines=(W/n/'testbench.spice').read_text().split('.control')[0].splitlines()[1:]
        return [l for l in lines if not l.startswith(('CFILTER ','CCOMP ','RPK_N2 ','LPK_N2 ','RESR_N2 ','RDAMP_N2 '))]
    equiv=[]
    for n,b in [('c15_dc','n2rl_dc'),('c15_dc_equiv_max','pcb_dc_ff_85_mmmp'),('c15_dc_equiv_min','pcb_dc_ss_85_pmmm')]:
        assert dc_remainder(n)==dc_remainder(b);equiv.append(dict(final=n,baseline=b,rest_of_DC_deck_identical=True,current_delta_A=by[n]['current_a']-by[b]['current_a']))
    an,bn='c15_startup_fullmesh','c15_startup_fullmesh_trap';a,b=by[an],by[bn]
    numerics=[dict(pair=[an,bn],held_peak_delta_a=abs(a['held_peak_a']-b['held_peak_a']),held_charge_max_delta_c=max(abs(a['held_charge'][k]-b['held_charge'][k]) for k in a['held_charge']),recovered_current_relative_delta=abs(a['recovered_a']/b['recovered_a']-1))]
    an,bn='c15_step','c15_step_fine';a,b=by[an],by[bn];charge=[]
    for n in [an,bn]:
        d=data[n];use=d[:,0]>=10e-6;t=d[use,0];di=d[use,1]-by[n]['baseline_current_a'];charge.append([float(np.trapezoid(np.maximum(di,0),t)),float(np.trapezoid(np.minimum(di,0),t))])
    numerics.append(dict(pair=[an,bn],peak_relative_delta=max(abs(a[k]/b[k]-1) for k in ['current_min_a','current_max_a']),disturbance_positive_negative_charge_c=charge,disturbance_charge_relative_delta=max(abs(charge[0][k]/charge[1][k]-1) for k in [0,1]),settle_delta_s=abs(a['settle_s']-b['settle_s'])))
    for x,y in zip(numerics,v['numerical_comparisons']):
        assert x['pair']==y['pair'] and y['passed']
        for key,value in x.items():
            if key=='pair':continue
            assert np.allclose(value,y[key],rtol=2e-8,atol=1e-20),(key,value,y[key])
    exception=[]
    for q in v['identity_exceptions']:
        n=q['case'];assert n not in expected and q['excluded_from_final_acceptance'];r=read(W/n/'result.json');assert not identity(r,W/n,True);exception.append(q)
    assert {r['case'] for r in exception}=={'pcb150_board100n_ac','startup_diagnostic_strict_r10_gear1_fullmesh'}
    loops=[]
    for q in s['final_local_loops']:
        folder=W/q['name'];assert read(folder/'result.json')==q and q['complete_source_identity']
        assert sha(W/'inputs/executed_sources'/q['executed_source_sha256']/'loop.py')==q['executed_source_sha256']
        mh=q['source_manifest_sha256'];assert sha(W/'inputs/manifests'/(mh+'.json'))==mh;assert read(W/'inputs/manifests'/(mh+'.json'))['executed_runner_sha256']==q['helper_runner_sha256']
        assert sha(W/'inputs/executed_sources'/q['helper_runner_sha256']/'run.py')==q['helper_runner_sha256']
        for rec in q['records']:
            for f,k in [('testbench.spice','deck_sha256'),('dut.spice','dut_sha256'),('ngspice.log','log_sha256')]:assert sha(folder/rec['method']/f)==rec[k]
        norm=lambda t:'\n'.join(l.strip() for l in t.splitlines() if l.strip())
        assert norm((folder/'closed/dut.spice').read_text())==norm((W/'inputs/dut.spice').read_text())
        a=np.loadtxt(folder/'voltage/ac.dat',skiprows=1);b=np.loadtxt(folder/'current/ac.dat',skiprows=1);assert np.array_equal(a[:,0],b[:,0]);f=a[:,0]
        tv=-(a[:,1]+1j*a[:,2])/(a[:,3]+1j*a[:,4]);ti=(b[:,1]+1j*b[:,2])/(b[:,3]+1j*b[:,4]);ratio=(tv*ti-1)/(tv+ti+2);g=20*np.log10(abs(ratio));phase=np.unwrap(np.angle(ratio))*180/np.pi
        assert np.allclose(np.loadtxt(E/(q['name']+'.csv'),delimiter=',',skiprows=1),np.c_[f,g,phase],rtol=1e-12,atol=1e-11)
        crossing=[]
        for j in np.flatnonzero(((g[:-1]>=0)&(g[1:]<0))|((g[:-1]<0)&(g[1:]>=0))):
            fraction=-g[j]/(g[j+1]-g[j]);crossing.append(dict(direction='down' if g[j]>=0 else 'up',frequency_hz=float(np.exp(np.log(f[j])+fraction*np.log(f[j+1]/f[j]))),phase_margin_deg=float(180+phase[j]+fraction*(phase[j+1]-phase[j]))))
        assert len(crossing)==len(q['crossings'])==1 and crossing[0]['direction']=='down'
        same(crossing[0]['frequency_hz'],q['crossings'][0]['frequency_hz']);same(crossing[0]['phase_margin_deg'],q['crossings'][0]['phase_margin_deg'])
        ops=[np.loadtxt(folder/k/'op.dat',skiprows=1) for k in ['voltage','current','closed']];delta=max(float(abs(x-ops[-1]).max()) for x in ops[:-1]);same(delta,q['closed_injected_op_max_delta_v'])
        loops.append(dict(name=q['name'],all_crossings=crossing,op_delta_V=delta,result_sha256=sha(folder/'result.json')))
    output=dict(script_sha256=sha(__file__),summary_sha256=sha(E/'final-summary.json'),validation_sha256=sha(E/'validation.json'),selected_count=27,selected_passed=27,raw_records=len(records),reused_DC_count=144,DC_reuse_scope='Full old DC rows independently reread; capacitors open and isolated series branch draws zero in DC, unchanged remainder proven for nominal/extrema. This is not 144 new15nF transient tests.',DC_equivalence=equiv,records=records,numerical_comparisons=numerics,identity_exceptions_preserved=exception,loops=loops,terminal_scope='234 simulator-logged peak expressions verified against frozen39MOS terminals at requested cases; compact raw does not retain every internal node for independent terminal-peak waveform recomputation. These are observations, not foundry lifetime/absolute-max acceptance.',no_ngspice_invocation=True,no_engineering_source_mutation=True)
    OUT.write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(dict(selected=27,reused_DC=144,raw_records=len(records),loops=loops,numerics=numerics),indent=2))
if __name__=='__main__':main()
