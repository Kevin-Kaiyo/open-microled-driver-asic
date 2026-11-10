#!/usr/bin/env python3
"""Check final report bindings, publication boundaries and rendered PDF structure."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse,unquote
import ast,hashlib,json,math,re
from pypdf import PdfReader
import pdfplumber

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/driver-improvement-20261111'
EV=ROOT/'evidence/ab-improvement-20261111'
WORK=ROOT/'build/ab-improvement-20261111'
checks=[]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ck(name,good,detail=None):checks.append({'check':name,'passed':bool(good),'detail':detail})
def read(p):return json.loads(Path(p).read_text())
class Links(HTMLParser):
    def __init__(self):super().__init__();self.paths=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.add(a['id'])
        for key in ['href','src']:
            if key in a:self.paths.append(a[key])

def main():
    pages=read(DOC/'content.json');pdf=PdfReader(DOC/'technical-stage-report.pdf');texts=[p.extract_text() for p in pdf.pages]
    compact=lambda x:re.sub(r'\s+','',x)
    ck('one_explicit_section_per_PDF_page',len(pages)==len(pdf.pages),{'expected':len(pages),'actual':len(pdf.pages)})
    ck('each_PDF_title_on_its_page',len(pages)==len(pdf.pages) and all(compact(p['title']) in compact(t) for p,t in zip(pages,texts)))
    ck('real_extractable_text',all(len(t)>140 for t in texts),[len(t) for t in texts])
    ck('A4',all(abs(float(p.mediabox.width)-595.276)<.1 and abs(float(p.mediabox.height)-841.89)<.1 for p in pdf.pages))
    outside=[]
    with pdfplumber.open(DOC/'technical-stage-report.pdf') as doc:
        for i,p in enumerate(doc.pages,1):
            for c in p.chars:
                if c['text'].strip() and (c['x0']<0 or c['x1']>p.width+.5 or c['top']<0 or c['bottom']>p.height+.5):outside.append([i,c['text']])
    ck('PDF_no_outside_page_text',not outside,outside[:15])
    local_bad=[];images=0
    for path in DOC.glob('*.html'):
        h=Links();h.feed(path.read_text())
        for url in h.paths:
            ref=urlparse(url)
            if ref.scheme or not ref.path:continue
            target=(path.parent/unquote(ref.path)).resolve()
            # These two files are created by this validation invocation itself.
            generated_here=target in [EV/'validation.json',EV/'report-manifest.json']
            if not target.is_file() and not generated_here:local_bad.append([path.name,url])
            if target.suffix in ['.png','.svg']:images+=1
    ck('HTML_local_links_and_images',not local_bad,local_bad)
    scientific=read(EV/'scientific-validation.json')
    ck('scientific_integrity_and_final_completion',scientific.get('integrity_pass') and scientific.get('complete'),scientific.get('pending'))
    normative='\n'.join(texts)
    for text in ['200 fF','0.37','32 Gb/s','3.2','31.275','黄光','850 nm','DISABLE','未实例化','时间步长']:
        ck('essential_scope_'+text,compact(text) in compact(normative))
    original=read(WORK/'workspace-before.json')['files']
    unrelated=[r for r in original if not r['path'].startswith(('scripts/ab_improvement_20261111/','docs/research/driver-improvement-20261111/','evidence/ab-improvement-20261111/'))]
    changes=[r['path'] for r in unrelated if not (ROOT/r['path']).is_file() or sha(ROOT/r['path'])!=r['sha256']]
    ck('preexisting_unrelated_work_preserved',not changes,{'files':len(unrelated),'changed':changes})
    for path in (ROOT/'scripts/ab_improvement_20261111').glob('*.py'):ast.parse(path.read_text(),filename=str(path))
    ck('Python_syntax',True)
    # Only independently created figures and sourced numeric summaries are public.
    ck('no_original_vendor_or_paper_PDFs_in_report',all(p.name=='technical-stage-report.pdf' for p in DOC.rglob('*.pdf')))
    manifest={str(p.relative_to(ROOT)):{'sha256':sha(p),'bytes':p.stat().st_size} for base in [DOC,EV,ROOT/'scripts/ab_improvement_20261111'] for p in sorted(base.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name not in ['validation.json','report-manifest.json','delivery.json']}
    (EV/'report-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    result={'passed':all(c['passed'] for c in checks),'checks':checks,'PDF_pages':len(pdf.pages),'html_images':images,'scope':'Numerical/source/report integrity; rendered visual review and raw archive remote verification reported separately.'}
    (EV/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'pages':len(pdf.pages),'failed':[c for c in checks if not c['passed']]},ensure_ascii=False))
    raise SystemExit(0 if result['passed'] else 1)

if __name__=='__main__':main()
