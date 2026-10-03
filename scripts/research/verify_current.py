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
    # PDF page count and visual inspection are distinct from electrical checks.
    result=subprocess.run(['pdfinfo',ROOT/'docs/research/research-report.pdf'],capture_output=True,text=True,check=True)
    count=int(re.search(r'^Pages:\s+(\d+)',result.stdout,re.M).group(1))
    check('All final PDF pages reviewed',count==args.pdf_pages_reviewed)
    public=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    selected=[]
    prefixes=('analog/driver/','analog/models/measured-led/','rtl/','sim/rtl/','layout/',
              'scripts/characterization/','scripts/digital/','scripts/physical/','scripts/led/',
              'scripts/layout/','scripts/research/','docs/research/','docs/digital/','docs/specifications/',
              'evidence/characterization/','evidence/digital/','evidence/layout/','evidence/led-fit/',
              'evidence/physical/','evidence/research/')
    for name in public:
        if name=='evidence/research/current-manifest.json':continue
        if name.startswith(prefixes) or name in ['README.md','docs/design.md','docs/pwm.md','docs/verification.md','docs/roadmap.md']:
            selected.append(name)
    data={'date':datetime.now().astimezone().isoformat(),'stage':'one-pixel v0.2 research milestone',
          'passed':True,'checks':checks,'pdf_pages':count,'pdf_visual_pages_reviewed':list(range(1,count+1)),
          'current_file_hashes':{n:digest(ROOT/n) for n in sorted(set(selected))},
          'historical_identity_note':'As-run hashes in older evidence are preserved. Old TB snapshot and default-trace equivalence are public in input-mapping.json. Broad historical source inventories also include subsequently changed presentation/export scripts and independent digital config; these do not rewrite the analog run identity.',
          'project_not_complete_at_chip_level':['routed mixed-signal top','pads/ESD/package','actual reference generator and startup','real LED dynamic/thermal/optical calibration','provider acceptance','silicon/optical measurements']}
    (ROOT/'evidence/research/current-manifest.json').write_text(json.dumps(data,indent=2)+'\n')
    print(f'PASS {len(checks)} artifact checks; {len(selected)} current files indexed; {count} PDF pages reviewed')
if __name__=='__main__':main()
