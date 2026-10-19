"""Read-only independent recomputation; does not import either simulation runner."""
from pathlib import Path
import argparse, bisect, csv, hashlib, json, math
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'evidence/reference'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def integral(t,y,a,b):
    if t[0]>a or t[-1]<b-1e-16 or np.any(np.diff(t)<=0):raise AssertionError('Incomplete waveform')
    # Scalar piecewise-linear integration, independently from NumPy runner path.
    first=max(0,bisect.bisect_right(t,a)-1);last=min(len(t)-1,bisect.bisect_left(t,b))
    total=0.
    for k in range(first,last):
        x0=max(a,t[k]);x1=min(b,t[k+1])
        slope=(y[k+1]-y[k])/(t[k+1]-t[k])
        total+=(x1-x0)*(y[k]+slope*(x0-t[k])+y[k]+slope*(x1-t[k]))/2
    return total
def near(a,b):assert math.isclose(a,b,rel_tol=2e-9,abs_tol=1e-20),(a,b)
def run(candidate):
    s=json.loads((E/(candidate+'-summary.json')).read_text());w=ROOT/s['workdir'];checks=[]
    for name,h in s['source_hashes'].items():
        path=w/'inputs'/'pdk'/name.removeprefix('PDK/') if name.startswith('PDK/') else w/'inputs'/name
        assert sha(path)==h,name
        if not name.startswith('PDK/'):assert sha(ROOT/name)==h,name+' current changed'
    for name,h in s['result_files_sha256'].items():assert sha(E/name)==h,name
    csvname='pvt.csv' if candidate=='beta' else 'servo-pvt.csv'
    with (E/csvname).open() as f:pvt=list(csv.DictReader(f))
    values=[float(r['iref_a']) for r in pvt]
    assert len(values)==s['pvt']['n'];near(min(values),s['pvt']['min_iref_a']);near(max(values),s['pvt']['max_iref_a'])
    failed=sum(abs(v/100e-6-1)>.05 for v in values);assert failed==s['pvt']['failed_absolute_budget']
    checks.append('All input and result hashes, PVT count/extrema/absolute ±5% failures recomputed')
    pwm=[]
    for r in s['pwm']:
        path=ROOT/r['raw_waveform'] if 'raw_waveform' in r else w/f'pwm-{r["envelope"]}-{r["duty"]}{"-fine" if r["maxstep_s"]<10e-9 else ""}'/'data.dat'
        a=np.loadtxt(path,skiprows=1);t=a[:,0];y=a[:,1]
        q=[integral(t,y,514.5e-6+k*256e-6,514.5e-6+(k+1)*256e-6) for k in range(2)]
        for x,z in zip(q,r['frame_charge_c']):near(x,z)
        avg=sum(q)/512e-6;near(avg,r['average_current_a'])
        if r['duty']:
            errors=[100*(x/(r['dc_full_a']*r['duty']*1e-6)-1) for x in q]
            for x,z in zip(errors,r['charge_error_pct']):assert abs(x-z)<1e-7
        else:errors=None
        pwm.append(dict(envelope=r['envelope'],duty=r['duty'],maxstep_s=r['maxstep_s'],charge_error_pct=errors,off_guard_pass=bool(abs(avg)<1e-9) if r['duty']==0 else None))
    checks.append('15 PWM raw traces: both full-frame integrals independently recomputed; DC-based charge denominator retained')
    # External terminal differences for the new reference only. Does not certify SOA.
    names=(['pg','nb','rs','su','vdd','bias'] if candidate=='beta' else ['pb','ctrl','n1','n2','tail','vdd','sense','bias','vset'])
    indices=([6,7,8,9,10,5] if candidate=='beta' else [11,9,7,8,10,12,6,5,13])
    pins=([('p1','pg','pg','vdd','vdd'),('p2','nb','pg','vdd','vdd'),('n1','nb','nb','0','0'),('n2','pg','nb','rs','0'),
           ('pout','bias','pg','vdd','vdd'),('pup','su','0','vdd','vdd'),('nsense','su','nb','0','0'),('nkick','pg','su','0','0')]
          if candidate=='beta' else [('pbias','pb','pb','vdd','vdd'),('ptail','tail','pb','vdd','vdd'),('pd1','n1','vset','tail','vdd'),('pd2','n2','sense','tail','vdd'),
          ('nd1','n1','n1','0','0'),('nd2','n2','n1','0','0'),('nstage','ctrl','n2','0','0'),('pload','ctrl','ctrl','vdd','vdd'),('preg','sense','ctrl','vdd','vdd'),('pout','bias','ctrl','vdd','vdd')])
    maxima={};startup=[]
    for r in s['startup']:
        a=np.loadtxt(ROOT/r['raw_waveform'],skiprows=1);v={n:a[:,i] for n,i in zip(names,indices)};v['0']=np.zeros(len(a))
        terminal={}
        for name,d,g,source,b in pins:
            terminal[name]={k:float(np.max(np.abs(v[x]-v[y]))) for k,x,y in [('vgs',g,source),('vgd',g,d),('vgb',g,b),('vds',d,source),('vsb',source,b),('vdb',d,b)]}
            for k,value in terminal[name].items():
                key=name+'.'+k
                if key not in maxima or value>maxima[key]['max_abs_v']:maxima[key]=dict(max_abs_v=value,case=r['raw_waveform'])
        if r['kind']!='step':
            final=integral(a[:,0],a[:,1],a[-1,0]-10e-6,a[-1,0])/10e-6;near(final,r['last_10us_mean_a'])
            last=a[a[:,0]>=a[-1,0]-10e-6,1];ripple=100*float(np.ptp(last))/max(abs(final),1e-30)
            enabled=r.get('startup_enabled',True)
            # Explicitly require the actual final current to be nonzero when enabled.
            good=(ripple<2 and final>1e-6 and r['settles_within_20us']) if enabled else final<1e-9
            startup.append(dict(envelope=r['envelope'],kind=r['kind'],enabled=enabled,initial_state=r.get('initial_state'),rise_s=r.get('rise_s'),
                                final_current_a=float(final),ripple_pp_pct=ripple,observed_startup_or_negative_control_pass=bool(good)))
    checks.append('Startup endpoint averages, ripple and nonzero/disabled negative-control status independently checked; terminal differences reported')
    result=dict(status='validation_pass',candidate=candidate,summary_sha256=sha(E/(candidate+'-summary.json')),validator_sha256=sha(Path(__file__)),checks=checks,pvt_fail_count=failed,
                pwm=pwm,startup=startup,reference_terminal_maxima=maxima,scope='Finite schematic waveforms; external-terminal extrema are not foundry reliability/ESD qualification.')
    (E/(candidate+'-validation.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(candidate, 'validated',len(pwm),'PWM',len(startup),'startup cases, PVT gate fails',failed)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('candidate',choices=['beta','servo']);run(parser.parse_args().candidate)
