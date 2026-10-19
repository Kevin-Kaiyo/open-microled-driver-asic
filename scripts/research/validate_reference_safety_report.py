"""Independent source/arithmetic/render audit; failed experiments remain failed."""
from pathlib import Path
import argparse, csv, hashlib, json, math, re, subprocess
from datetime import datetime, timezone
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/research/reference-safety-20261013'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads((ROOT/p).read_text())
def integral(rows,key,lo,hi,mode='signed'):
    pairs=[(float(r['time_s']),float(r[key])) for r in rows]
    assert pairs[0][0]<=lo and pairs[-1][0]>=hi
    assert all(math.isfinite(t) and math.isfinite(v) for t,v in pairs)
    assert all(a[0]<b[0] for a,b in zip(pairs,pairs[1:]))
    terms=[]
    for (t0,v0),(t1,v1) in zip(pairs,pairs[1:]):
        a,b=max(lo,t0),min(hi,t1)
        if b<=a:continue
        va=v0+(v1-v0)*(a-t0)/(t1-t0);vb=v0+(v1-v0)*(b-t0)/(t1-t0)
        if mode=='signed':terms.append((b-a)*(va+vb)/2);continue
        if va*vb<0:
            zero=a-va*(b-a)/(vb-va)
            pieces=[(a,zero,va,0),(zero,b,0,vb)]
        else:pieces=[(a,b,va,vb)]
        for x,y,u,v in pieces:
            if mode=='positive' and u+v>=0 or mode=='negative' and u+v<=0:terms.append((y-x)*(u+v)/2)
    return math.fsum(terms)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pdf-pages-reviewed',type=int,required=True);a=parser.parse_args()
    checks=[];source_hashes={};classes=[]
    def check(name,ok,detail=None):
        checks.append(dict(name=name,passed=bool(ok),detail=detail))
        if not ok:raise ValueError(name+': '+str(detail))
    for name in ['reference/beta','reference/servo']:
        s=read('evidence/'+name+'-summary.json');paths=s['source_hashes']
        for p,h in paths.items():
            path=ROOT/('build/layout/pdk/gf180mcuD/libs.tech/ngspice/'+p.split('/',1)[1] if p.startswith('PDK/') else p)
            check('as-run source '+p+name,sha(path)==h)
            source_hashes[str(path.relative_to(ROOT))]=h
        classes.append(dict(path='evidence/'+name+'-summary.json',evidence='new schematic transistor simulation',
                            established='conditions and current/startup outcomes',not_established='new layout/physical/full-chip/optics'))
    beta=read('evidence/reference/beta-summary.json');servo=read('evidence/reference/servo-summary.json')
    check('beta failure is not erased',beta['pvt']['failed_absolute_budget']==126 and beta['pvt']['n']==135)
    check('servo discrete precision scope',servo['pvt']['failed_absolute_budget']==0 and servo['pvt']['n']==180)
    conditions=read('evidence/reference/servo-coupled-conditions.json')
    check('18 coupled DC deck conditions preserved',len(conditions)==18 and all('rset_ohm' in r and 'vset_v' in r for r in conditions))
    nominal=next(r for r in conditions if r['case']=='coupled-tt-1')
    check('reported analog-RC coupled nominal',abs(nominal['iout_a']*1e6-99.96729969410715)<1e-9)
    core=read('evidence/safety/summary.json');joint=read('evidence/safety/servo-summary.json')
    for s in [core,joint]:
        for p,h in s['source_sha256'].items():
            check('safety source identity '+p,sha(ROOT/p)==h);source_hashes[p]=h
    check('core validated, extended suite stays false',core['passed'] and core['check_count']==141 and not joint['passed']
          and joint['core_contract_passed'] and joint['extra_startup_guard_failed'] and joint['extra_startup_charge_convergence_failed'])
    for row in core['results']:
        if row.get('fault_to_safe_current_s') is None:continue
        origin=row['conditions']['fault_ns']*1e-9
        check('fault origin is PWL start '+row['name'],abs(row['stable_safe_current_time_s']-origin-row['fault_to_safe_current_s'])<1e-14)
    blocks=read('docs/research/reference-safety-20261013/safety-report-blocks.json')
    check('safety prose uses exact summaries',blocks['summary_source_sha256']==sha(ROOT/'evidence/safety/summary.json')
          and blocks['servo_source_sha256']==sha(ROOT/'evidence/safety/servo-summary.json'))
    ab=read('evidence/safety-clamp-ab/summary.json')
    for row in ab['results']:
        path=ROOT/row['waveform_path'];check('AB waveform hash '+row['name'],sha(path)==row['waveform_sha256'])
        rows=list(csv.DictReader(path.open()));lo=20125e-9
        for mode,key in [('positive','Qpositive_first_us_C'),('negative','Qnegative_first_us_C')]:
            q=integral(rows,'LED_branch_A',lo,lo+1e-6,mode)
            check('independent directional Q '+row['name']+mode,abs(q-row[key])<1e-20)
        check('matched control physical outcome '+row['name'],row['input_slew_ns']==10 and row['original_fault_contract_passed']==row['clamp_action_enabled'])
    rv=read('evidence/current-range/validation.json');range_s=read('evidence/current-range/summary.json')
    check('range independent validation has matching summary',rv['passed'] and rv['summary_sha256']==sha(ROOT/'evidence/current-range/summary.json'))
    check('7mA static and minimum-code limitations retained',not range_s['qualified_entire_0p1_to_7mA_range']
          and next(x for x in range_s['DC'] if x['load']=='measured_static' and x['led_v']==5 and x['units']==70)['error_pct']<-40
          and next(x for x in range_s['PWM'] if x['name']=='pwm_n70_d1_step5')['area_error_pct']<-15)
    curves=list(csv.DictReader((ROOT/'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv').open()))
    for i,value in range_s['dc_calibration']['measured_static_V_by_current_A'].items():
        target=float(i)
        for x,y in zip(curves,curves[1:]):
            i0,i1=float(x['current_A']),float(y['current_A'])
            if i0<=target<=i1:
                v0,v1=float(x['voltage_V']),float(y['voltage_V']);calc=v0+(v1-v0)*(target-i0)/(i1-i0);break
        check('independent static VF '+i,abs(calc-value)<1e-12)
    check('hand calculations with units',abs(.5/5000-100e-6)<1e-20 and abs(.007**2*100-.0049)<1e-15
          and abs(70*20*4*2.3e-15-12.88e-12)<1e-25 and abs(.007/(20e-4)**2-1750)<1e-12)
    for p in [BASE/'report.md',BASE/'README.md',BASE/'architecture-notes.md']:
        text=p.read_text();missing=[]
        check('no unresolved report placeholder '+p.name,not re.search(r'@@[A-Z_]+@@',text))
        for link in re.findall(r'\]\(([^)]+)\)',text):
            if '://' in link or link.startswith('#'):continue
            target=(p.parent/link.split('#')[0]).resolve()
            if target.name not in ['validation.json','evidence-ledger.json'] and not target.exists():missing.append(link)
        check('local links '+p.name,not missing,missing)
    layout=read('build/research-reference-safety-20261013/layout-check.json')
    pdf=PdfReader(str(BASE/'report.pdf'))
    check('19A4 pages and all images',len(layout['sections'])==len(pdf.pages)==19 and not layout['overflow']
          and all(x['height']<970 for x in layout['sections']) and all(x['loaded'] for x in layout['images']))
    check('PDF contains readable text every page',all(len(p.extract_text())>180 for p in pdf.pages))
    check('all final pages visually reviewed',a.pdf_pages_reviewed==19)
    for p in [ROOT/'evidence/current-range/summary.json',ROOT/'evidence/safety-clamp-ab/summary.json']:
        source_hashes[str(p.relative_to(ROOT))]=sha(p)
    for folder in [ROOT/'evidence/reference',ROOT/'evidence/safety']:
        for p in folder.glob('*.json'):source_hashes[str(p.relative_to(ROOT))]=sha(p)
    for p in (ROOT/'scripts/research').glob('*reference*safety*'):source_hashes[str(p.relative_to(ROOT))]=sha(p)
    for name in ['scripts/research/prepare_safety_report.py','scripts/research/check_clamp_ab.py','scripts/research/highspeed_architecture_figures.py',
                 'scripts/research/reference_architecture_figures.py','analog/current_range/pixel_bank.spice','scripts/current_range/run.py','scripts/current_range/validate.py',
                 'evidence/robustness/main-summary.json','evidence/interface/dc.csv','evidence/characterization/actual-w20-l4-summary.json',
                 'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv','evidence/joint-pex/nominal/summary.json']:
        source_hashes[name]=sha(ROOT/name)
    classes += [dict(path='evidence/safety/summary.json',evidence='new pre-layout gate/clamp + existing selected PEX',
                     established='declared powered fault contract',not_established='POR/new layout/full PG/optics'),
                dict(path='evidence/safety/servo-summary.json',evidence='new coupled fixture with explicit failure',
                     established='normal and fault original contracts',not_established='extra all-startup branch/charge guards'),
                dict(path='evidence/current-range/summary.json',evidence='new geometry/compliance simulation and static public curve replay',
                     established='reported DC/PWM and failures',not_established='implemented current DAC/real LED dynamics'),
                dict(path='evidence/safety-clamp-ab/summary.json',evidence='new matched 10ns controlled simulation',
                     established='same-load clamp action contribution',not_established='optical/SOA/full-chip claims')]
    ledger=dict(report_completed_on='2026-10-14',study_started_on='2026-10-13',
                engineering_baseline=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                new_modules_are_pre_layout=True,new_silicon_or_optical_measurements=False,
                evidence=classes,sources_sha256=source_hashes,
                figures={str(p.relative_to(BASE)):sha(p) for p in (BASE/'figures').glob('*.svg')})
    (BASE/'evidence-ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n')
    out=dict(passed=True,validated_at_UTC=datetime.now(timezone.utc).isoformat(),checks=checks,
             report_pages=19,direct_visual_pages=list(range(1,20)),engineering_failures_preserved=True,
             audit_success_is_not_experiment_success=True,outputs_sha256={p.name:sha(p) for p in BASE.iterdir() if p.is_file() and p.name!='validation.json'})
    (BASE/'validation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=True,checks=len(checks),pages=19,source_entries=len(source_hashes),failures_preserved=True)))
if __name__=='__main__':main()
