"""Check current deliverable links, pinned sources and report/evidence identity.

Historical run inventories are deliberately preserved. This index records the
current tree and explains revisions rather than rewriting as-run hashes.
"""
from pathlib import Path
from datetime import datetime
import argparse
import hashlib
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pdf-pages-reviewed',type=int,required=True)
    args=parser.parse_args()
    checks=[]
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)})
        if not value:raise RuntimeError(name)
    report=(ROOT/'docs/research/research-report.md').read_text()
    check('No draft placeholders',not any(w in report for w in ['待补录','待从成功证据','作者工作占位','报告发布前根据']))
    files=[ROOT/'README.md']+list((ROOT/'docs').rglob('*.md'))+list((ROOT/'evidence/research').glob('*.md'))
    links=[]
    for p in files:
        for href in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            href=href.strip('<>')
            if '://' in href or href.startswith('#') or ' ' in href:continue
            target=(p.parent/href.split('#')[0]).resolve()
            # This manifest is written only after all other checks pass.
            if target==ROOT/'evidence/research/current-manifest.json':continue
            if not target.exists():links.append([str(p.relative_to(ROOT)),href])
    check('Repository document local links exist',not links)
    layout=json.loads((ROOT/'evidence/layout/summary.json').read_text())
    for n,h in layout['output_hashes'].items():
        p=(ROOT/'layout'/n) if n.endswith('.mag') else ROOT/'evidence/layout'/n
        check('Analog generated output '+n,digest(p)==h)
    for name in ['actual-w20-l4-summary.json','measured-load-summary.json']:
        data=json.loads((ROOT/'evidence/characterization'/name).read_text())
        rc_hash=data.get('actual_rc_sha256') or data['source_hashes']['evidence/layout/pixel_driver_rc.spice']
        check('Current RC used by '+name,rc_hash==digest(ROOT/'evidence/layout/pixel_driver_rc.spice'))
    macro=json.loads((ROOT/'evidence/layout/macro-views.json').read_text())
    check('LEF dimensions match GDS',[round(x,6) for x in macro['lef_size_um']]==[95,37.66])
    for n,h in macro['output_hashes'].items():check('Macro view '+n,digest(ROOT/n)==h)
    mapping=json.loads((ROOT/'evidence/research/input-mapping.json').read_text())
    check('Input mapping complete',mapping.get('passed') is True)
    for lock,base in [('layout/pdk-lock.json','build/layout/pdk/gf180mcuD'),
                      ('scripts/digital/library-lock.json','build/layout/pdk/gf180mcuD'),
                      ('scripts/physical/pdk-lock.json','build/layout/pdk/gf180mcuD')]:
        data=json.loads((ROOT/lock).read_text())
        for n,h in data['files'].items():check('Pinned input '+n,digest(ROOT/base/n)==h)
    physical=json.loads((ROOT/'evidence/physical/summary.json').read_text())
    check('Physical completed under unchanged timing targets',physical.get('passed') is True)
    for name,h in physical['evidence_files_sha256'].items():
        check('Physical output '+name,digest(ROOT/'evidence/physical'/name)==h)
    for name,h in physical['actual_frozen_input_provenance']['source_sha256'].items():
        check('Implemented digital input '+name,digest(ROOT/name)==h)
    for name,h in physical['packaging_source_sha256'].items():
        check('Physical packaging input '+name,digest(ROOT/name)==h)
    check('Nine STA corners',len(physical['corners'])==9)
    for name,corner in physical['corners'].items():
        check('Timing and electrical rules '+name,
              all(corner[k]==0 for k in ['setup_violation_count','hold_violation_count',
                  'max_slew_violation_count','max_cap_violation_count']) and
              corner['r2r_setup']['endpoint_count']==19 and corner['r2r_hold']['endpoint_count']==19)
    for domain in ['analog','digital']:
        check('Independent DRC '+domain,physical['independent_klayout'][domain]['item_count']==0)
    check('Independent analog GDS identity',physical['independent_klayout']['analog']['input_hashes']['gds_sha256']==digest(ROOT/'evidence/layout/pixel_driver_layout.gds'))
    check('Independent digital GDS identity',physical['independent_klayout']['digital']['input_hashes']['gds_sha256']==digest(ROOT/'evidence/physical/digital/gds/pixel_pwm.gds'))
    version=re.search(r'研究报告\s+(v\d+\.\d+)',report).group(1)
    if version in ('v0.3','v0.4'):
        joint=json.loads((ROOT/'evidence/integration/summary.json').read_text())
        check('Joint top completed',joint['passed'] is True)
        check('Nineteen explicit joint ports',len(joint['external_ports'])==19)
        for mode,result in joint['physical_checks'].items():check('Actual joint '+mode,result['passed'] is True)
        for name,h in joint['inputs_sha256'].items():check('Joint source '+name,digest(ROOT/name)==h)
        for name,h in joint['packaging_source_hashes'].items():check('Joint packaging '+name,digest(ROOT/name)==h)
        for name,h in joint['output_hashes'].items():check('Joint output '+name,digest(ROOT/'evidence/integration'/name)==h)
        for kind,control in joint['negative_controls'].items():
            check('Physical mutation rejected '+kind,control['rejected_by_both_electrical_checks'] is True and control['netgen']['passed'] is False)
        identity=json.loads((ROOT/'evidence/research/macro-identity.json').read_text())
        check('Both frozen macro polygon sets preserved',identity['passed'] is True and len(identity['macros'])==2)
        check('Macro identity belongs to actual joint GDS',identity['integrated_gds_sha256']==digest(ROOT/'evidence/integration/pixel_integrated.gds'))
        for name,h in identity['source_hashes'].items():check('Macro identity source '+name,digest(ROOT/name)==h)
        interface=json.loads((ROOT/'evidence/interface/summary.json').read_text())
        link_map=json.loads((ROOT/'evidence/interface/input-mapping.json').read_text())
        check('As-run link mapping passed',link_map['passed'] is True and link_map['electrical_graph_equal'] is True)
        for name,item in link_map['paths'].items():
            check('Mapped current input '+name,digest(ROOT/name)==item['current_sha256'])
            check('Original executed input retained '+name,digest(ROOT/item['snapshot_path'])==item['as_run_sha256']==item['snapshot_sha256'])
        for name,h in interface['source_hashes'].items():
            actual=digest(ROOT/name)
            if actual!=h and name in link_map['paths']:
                check('Original interface input '+name,h==link_map['paths'][name]['as_run_sha256'])
            else:check('Interface executed source '+name,actual==h)
        check('Interface actual RC identity',interface['actual_analog_rc_sha256']==digest(ROOT/'evidence/layout/pixel_driver_rc.spice'))
        check('Executed joint-link snapshot identity',interface['joint_link_sha256']==link_map['paths']['evidence/integration/pwm_link_rc.spice']['as_run_sha256'])
        check('Interface 54 executed transients',interface['passed'] is True and interface['transient_runs']==54 and all(c['passed'] for c in interface['checks']))
        check('Actual Liberty transition definition',interface['conditions']['actual_liberty_slew_thresholds_pct']==[30,70])
        manifest=json.loads((ROOT/'evidence/interface/manifest.json').read_text())
        for name,h in manifest['files_sha256'].items():check('Interface public output '+name,digest(ROOT/name)==h)
        stress=json.loads((ROOT/'evidence/interface/slew-budget-summary.json').read_text())
        check('Six input-slew stress cases',stress['passed'] is True and stress['transient_runs']==6 and all(c['passed'] for c in stress['checks']))
        check('Stress uses exact main summary',stress['base_summary_sha256']==digest(ROOT/'evidence/interface/summary.json'))
        for name,h in stress['sources_sha256'].items():check('Stress executed source '+name,digest(ROOT/name)==h)
        for name in ['validation.json','slew-budget-validation.json']:
            check('Independent numerical validation '+name,json.loads((ROOT/'evidence/interface'/name).read_text())['passed'] is True)
        for name in ['integration-review.json','interface-review.json']:
            review=json.loads((ROOT/'evidence/research'/name).read_text())
            check('Independent final review '+name,review['passed'] is True)
            for p,h in review.get('input_hashes',{}).items():check('Independent review input '+p,digest(ROOT/p)==h)
            for p,h in review.get('output_hashes',{}).items():check('Independent review output '+p,digest(ROOT/p)==h)
        figure=json.loads((ROOT/'evidence/research/integration-figure.json').read_text())
        for p,h in figure['source_sha256'].items():check('Current geometry figure source '+p,digest(ROOT/p)==h)
        check('Current geometry figure output',digest(ROOT/figure['output'])==figure['output_sha256'])
    if version=='v0.4':
        from verify_v04_assets import verify
        verify(check,report)
    # PDF page count and visual inspection are distinct from electrical checks.
    result=subprocess.run(['pdfinfo',ROOT/'docs/research/research-report.pdf'],capture_output=True,text=True,check=True)
    count=int(re.search(r'^Pages:\s+(\d+)',result.stdout,re.M).group(1))
    check('All final PDF pages reviewed',count==args.pdf_pages_reviewed)
    public=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    selected=[]
    prefixes=('analog/driver/','analog/models/measured-led/','rtl/','sim/rtl/','layout/',
              'scripts/characterization/','scripts/digital/','scripts/physical/','scripts/led/',
              'scripts/layout/','scripts/research/','docs/research/','docs/digital/','docs/specifications/',
              'scripts/integration/','scripts/interface/','evidence/integration/','evidence/interface/',
              'scripts/joint_pex/','scripts/robustness/','scripts/strategy/',
              'evidence/joint-pex/','evidence/robustness/','evidence/strategy/','evidence/teaching/',
              'evidence/characterization/','evidence/digital/','evidence/layout/','evidence/led-fit/',
              'evidence/physical/','evidence/research/','evidence/automotive/')
    for name in public:
        if name=='evidence/research/current-manifest.json':continue
        if name.startswith(prefixes) or name in ['README.md','docs/design.md','docs/environment.md','docs/pwm.md','docs/verification.md','docs/roadmap.md']:
            selected.append(name)
    data={'date':datetime.now().astimezone().isoformat(),'stage':'one-pixel '+version+' research milestone',
          'passed':True,'checks':checks,'pdf_pages':count,'pdf_visual_pages_reviewed':list(range(1,count+1)),
          'current_file_hashes':{n:digest(ROOT/n) for n in sorted(set(selected))},
          'historical_identity_note':'As-run hashes in older evidence are preserved. Old TB snapshot and default-trace equivalence are public in input-mapping.json. Broad historical source inventories also include subsequently changed presentation/export scripts and independent digital config; these do not rewrite the analog run identity.',
          'project_not_complete_at_chip_level':['complete PG/body/substrate model and full-chip multi-corner electrical and supply sign-off','pads/ESD/package','actual reference generator and startup','real LED dynamic/thermal/optical calibration','provider acceptance','silicon/optical measurements']}
    (ROOT/'evidence/research/current-manifest.json').write_text(json.dumps(data,indent=2)+'\n')
    print(f'PASS {len(checks)} artifact checks; {len(selected)} current files indexed; {count} PDF pages reviewed')
if __name__=='__main__':main()
