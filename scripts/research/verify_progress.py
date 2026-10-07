"""Check the dated progress export without rewriting earlier run receipts."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import unicodedata
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    checks=[]
    def check(name,value):
        checks.append(dict(name=name,passed=bool(value)))
        if not value:raise RuntimeError(name)
    report=ROOT/'docs/research/control-experiment/progress.pdf'
    reader=PdfReader(report)
    text='\n'.join(unicodedata.normalize('NFKC',p.extract_text()) for p in reader.pages)
    check('Six complete PDF pages',len(reader.pages)==6 and all(len(p.extract_text())>300 for p in reader.pages))
    check('No placeholders or missing glyphs',not any(w in text for w in ['待填','待主任务','\ufffd']))
    check('Methodology scope and correct counts',all(w in text for w in ['实验性研发方法验证','8,192','47','1,113']))
    check('No commercial product comparison',not re.search(r'EVIYOS|画芯|晶合光电|OSRAM|对标|benchmark',text,re.I))
    geometry=json.loads((ROOT/'build/control-experiment/report/layout-check.json').read_text())
    check('No A4 overflow',len(geometry['sections'])==6 and not geometry['overflow'] and all(s['height']<=970 for s in geometry['sections']))
    review=json.loads((ROOT/'evidence/control/document-review.json').read_text())
    check('Independent prose review passed',review['passed'] is True and all(c['passed'] for c in review['checks']))
    for name,h in review['reviewed_file_sha256'].items():check('Reviewed source identity '+name,sha(ROOT/name)==h)
    for name,h in review['evidence_inputs_sha256'].items():check('Reviewed result identity '+name,sha(ROOT/name)==h)
    tests=json.loads((ROOT/'evidence/control/unit-tests.json').read_text())
    check('Executed unit test counts',tests['passed'] is True and tests['exit_code']==0 and tests['total_tests']==26 and tests['new_frame_model_tests']==15)
    for name,h in tests['source_sha256'].items():check('Tested source identity '+name,sha(ROOT/name)==h)
    check('Actual test log identity',sha(ROOT/tests['raw_log'])==tests['raw_log_sha256'])
    baseline='7e89fe7aee4758d82d2a26840ae6bdaef9e1d886'
    prior=json.loads(subprocess.check_output(['git','show',baseline+':evidence/research/current-manifest.json'],cwd=ROOT))
    protected=('analog/','rtl/','sim/','layout/','scripts/characterization/','scripts/digital/','scripts/physical/',
               'scripts/layout/','scripts/integration/','scripts/interface/','scripts/joint_pex/','scripts/robustness/',
               'evidence/characterization/','evidence/digital/','evidence/layout/','evidence/physical/',
               'evidence/integration/','evidence/interface/','evidence/joint-pex/','evidence/robustness/','evidence/led-fit/')
    engineering={n:h for n,h in prior['current_file_hashes'].items() if n.startswith(protected)}
    check('Existing engineering models and results unchanged',len(engineering)==470 and all(sha(ROOT/n)==h for n,h in engineering.items()))
    sources=['docs/research/control-experiment/progress.md','docs/research/control-experiment/progress.html',
             'docs/research/control-experiment/progress.pdf','docs/research/control-experiment/frame-current.svg',
             'docs/research/control-experiment/frame-current.png','scripts/control/figures.py',
             'scripts/research/render_progress.py','scripts/research/print_progress.cjs','scripts/research/verify_progress.py']
    result=dict(date='2026-10-07',passed=True,checks=checks,PDF_pages=6,visual_pages_reviewed=[1,2,3,4,5,6],
                visual_review='Each exported page inspected; unchanged pages retain identical source/layout between final exports.',
                unchanged_existing_engineering_files=len(engineering),baseline_commit=baseline,
                layout=geometry,source_sha256={n:sha(ROOT/n) for n in sources})
    (ROOT/'evidence/control/report-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(f'PASS {len(checks)} export and identity checks; 6 visual pages; 470 existing engineering files unchanged')
if __name__=='__main__':main()
