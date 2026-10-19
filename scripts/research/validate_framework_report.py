"""Check framework evidence, units, references and final PDF; never promotes EDA status."""
from pathlib import Path
import argparse,hashlib,json,re,math
from urllib.parse import unquote,urlsplit
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/research/product-framework-20261014'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pdf-pages-reviewed',type=int,required=True);args=ap.parse_args()
    checks=[]
    def ck(name,ok):checks.append({'name':name,'passed':bool(ok)})
    led=read(BASE/'evidence-ledger.json')
    for p,h in led['sources'].items():ck('frozen source '+p,(ROOT/p).exists() and sha(ROOT/p)==h)
    ck('report source hash',sha(BASE/'report.md')==led['report_source_sha256'])
    audit=read(BASE/'current-evidence.json')
    for p,h in audit['sources_sha256'].items():ck('independent audit input '+p,sha(ROOT/p)==h)
    startup=read(ROOT/'evidence/startup-v2/summary.json')
    ck('original overall failure preserved',startup['passed'] is False and audit['experiment_passed'] is False and led['experiment_passed'] is False)
    ck('startup run scope',startup['transient_runs']==21 and startup['dc_runs']==12 and audit['startup']['checks']==134)
    ck('no new chip physical integration',audit['physical']['new_reference_safety_isolation_integrated'] is False)
    ck('no full PG or manufacturing',not audit['physical']['full_PG_PEX'] and not led['manufacturing_acceptance'])
    plan=read(BASE/'verification-plan.json');packet=read(BASE/'tapeout-package-template.json')
    ck('gate IDs unique',len(set(g['id'] for g in plan['gates']))==14)
    ck('legacy gate still failed',next(g for g in plan['gates'] if g['id']=='G2')['current_status']=='failed')
    ck('handoff explicitly unready',packet['ready_for_submission'] is False and packet['layout']['final_file'] is None and packet['submission']['acceptance_record'] is None)
    gds=read(BASE/'layout/manifest.json')
    for g in gds['geometry_sources']:
        ck('GDS unmodified '+g['id'],sha(ROOT/g['path'])==g['sha256'])
        b=g['cell_bbox_um'];ck('GDS bbox calculation '+g['id'],math.isclose((b[2]-b[0])*(b[3]-b[1]),g['span_area_um2'],rel_tol=1e-10))
        ck('GDS physical grid '+g['id'],g['dbu_um']==.001)
        ck('label geometry excluded '+g['id'],all(not r['displayed'] for r in g['layer_statistics'] if r['datatype']==10))
    browser=read(BASE/'layout/browser-validation.json')
    ck('browser controls tested',browser['passed'] and len(browser['checks'])==8)
    ck('browser hash current',browser['checked_viewer_sha256']==sha(BASE/'layout/viewer.html'))
    geom=read(BASE/'layout/geometry-validation.json');ck('independent geometry validation',geom['passed'])
    hival=read(BASE/'highspeed-validation.json');ck('highspeed numerical check',hival['passed'] and hival['checks_count']==25)
    hi=read(BASE/'highspeed-calculations.json')
    ck('highspeed source script',sha(ROOT/hi['generated_from_script'])==hi['script_sha256'])
    for s in hi['scenarios']:
        w=2*math.pi*s['f3dB_Hz'];gain2=1/((1+(w*s['electrical_tau_s'])**2)*(1+(w*s['carrier_tau_s'])**2))
        ck('two pole cutoff '+s['label'],math.isclose(gain2,.5,rel_tol=1e-10))
        ck('two pole numerical agreement '+s['label'],s['repeated_substep_max_difference']<3e-15)
    cal=read(BASE/'calculations.json');pwm=cal['pwm'];edge=cal['driver_scale'];bond=cal['bondwire_scale']
    ck('PWM frequency',math.isclose(pwm['clock_hz']/pwm['slots'],pwm['frame_hz']))
    ck('minimum ideal charge',math.isclose(pwm['nominal_current_a']*pwm['d1_high_s'],pwm['d1_ideal_charge_c']))
    ck('gate displacement current',math.isclose(edge['assumed_C_F']*edge['assumed_delta_v_V']/edge['assumed_edge_s'],edge['average_edge_current_A']))
    ck('bond voltage teaching',math.isclose(bond['assumed_L_H']*bond['delta_I_A']/bond['edge_s'],bond['Ldi_dt_V']))
    for md in [BASE/'report.md',BASE/'README.md',BASE/'highspeed-chapter.md',BASE/'layout-chapter.md']:
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',md.read_text()):
            u=urlsplit(target)
            if u.scheme or not u.path:continue
            q=(md.parent/unquote(u.path)).resolve()
            ck('local link '+str(md.relative_to(BASE))+': '+target,q.exists() or q==BASE/'validation.json')
    layout=read(ROOT/'build/product-framework-20261014/report/layout-check.json')
    ck('all report figures load',all(i['loaded'] for i in layout['images']) and len(layout['images'])==16)
    ck('no report horizontal overflow',layout['overflow']==[])
    ck('content fits A4',all(p['height']<980 for p in layout['sections']))
    pdf=PdfReader(BASE/'report.pdf');ck('28 PDF pages',len(pdf.pages)==28)
    ck('28 pages visually reviewed',args.pdf_pages_reviewed==28)
    for i,p in enumerate(pdf.pages,1):
        t=p.extract_text();ck('text preserved page '+str(i),len(t)>150)
        ck('no replacement glyph page '+str(i),'\ufffd' not in t)
        ck('A4 page '+str(i),abs(float(p.mediabox.width)-595.28)<1 and abs(float(p.mediabox.height)-841.89)<1)
    md=(BASE/'report.md').read_text()
    for term in ['passed=false','5-V MOS','6-V模型','不是最终die','不是最终芯片的三维物理仿真','不是GF180','ready_for_submission=false']:
        ck('boundary stated '+term,term in md or (term=='不是GF180' and '不代表GF180' in md))
    outputs=['report.md','report.html','report.pdf','verification-plan.json','tapeout-package-template.json','evidence-ledger.json','README.md']
    out={'date':'2026-10-14','passed':all(c['passed'] for c in checks),'checks_count':len(checks),'checks':checks,'pdf_pages':len(pdf.pages),'pdf_pages_visually_reviewed':args.pdf_pages_reviewed,
      'report_integrity_only':True,'new_transistor_or_physical_signoff_runs':False,'experiment_passed':False,'manufacturing_acceptance':False,'source_entries':len(led['sources']),
      'output_sha256':{p:sha(BASE/p) for p in outputs},'validator_sha256':sha(Path(__file__))}
    (BASE/'validation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ['passed','checks_count','pdf_pages','experiment_passed','source_entries']}))
    if not out['passed']:
        print(json.dumps([c for c in checks if not c['passed']],ensure_ascii=False,indent=2));raise SystemExit(1)
if __name__=='__main__':main()
