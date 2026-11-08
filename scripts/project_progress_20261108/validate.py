#!/usr/bin/env python3
"""Validate report evidence, numeric bindings, PDF integrity and local links."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import ast,base64,hashlib,io,json,math,re,sys
import xml.etree.ElementTree as ET
from pypdf import PdfReader
import pdfplumber
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'docs/research/project-progress-review-20261108';EV=ROOT/'evidence/project-progress-review-20261108';WORK=ROOT/'build/project-progress-review-20261108'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
class Page(HTMLParser):
 def __init__(self):super().__init__();self.ids=set();self.links=[];self.images=[];self.tables=0
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  if a.get('id'):self.ids.add(a['id'])
  if t=='a':self.links.append(a.get('href',''))
  if t=='img':self.images.append(a)
  if t=='table':self.tables+=1

def main():
 checks=[]
 def ck(name,passed,detail=None):checks.append({'name':name,'passed':bool(passed),'detail':detail})
 src=read(EV/'sources.json');content=read(DOC/'content.json');gen=read(EV/'generation.json')
 ck('23_named_sources_current',len(src['sources'])==23 and all(sha(ROOT/s['path'])==s['sha256'] for s in src['sources']))
 ck('all_scoped_audit_source_identities',all(sha(ROOT/p)==h for p,h in src['audited_source_hashes'].items()),{'source_count':len(src['audited_source_hashes'])})
 fk=read(EV/'figure-ledger.json')['figures'];bad=[]
 for f in fk:
  for p,h in [(f['source_path'],f['source_sha256']),(f['rendered_path'],f['rendered_sha256'])]+[(q['path'],q['sha256']) for q in f.get('basis_sources',[])]:
   if sha(ROOT/p)!=h:bad.append(p)
  if (ROOT/f['source_path']).suffix=='.svg':ET.parse(ROOT/f['source_path'])
  Image.open(ROOT/f['rendered_path']).verify()
 ck('9_original_or_traceable_figures',len(fk)==9 and not bad,bad)
 page=Page();page.feed((DOC/'index.html').read_text());broken=[]
 for link in page.links:
  u=urlsplit(link)
  if u.scheme or u.netloc:continue
  if not u.path and u.fragment and u.fragment not in page.ids:broken.append(link)
  if u.path and not (DOC/unquote(u.path)).resolve().exists():broken.append(link)
 ck('HTML_links_and_anchors',not broken,broken)
 imgs=[]
 for i in page.images:
  try:
   assert i['src'].startswith('data:image/png;base64,') and i.get('alt')
   Image.open(io.BytesIO(base64.b64decode(i['src'].split(',',1)[1]))).verify();imgs.append(True)
  except Exception:imgs.append(False)
 ck('9_self_contained_readable_images',len(imgs)==9 and all(imgs))
 ck('17_sections_and_source_anchors',all('section-'+str(i).zfill(2) in page.ids for i in range(1,18)) and all('source-S'+str(i).zfill(2) in page.ids for i in range(1,24)))
 r=PdfReader(DOC/'project-progress-report.pdf');texts=[p.extract_text() for p in r.pages]
 norm=lambda x:re.sub(r'\s+','',x)
 ck('PDF_17_pages_all_sections_present',len(r.pages)==len(content['pages'])==gen['expected_PDF_pages']==17 and all(norm(q['title']) in norm(texts[i]) for i,q in enumerate(content['pages'])))
 ck('PDF_real_text_each_page',all(len(t)>300 for t in texts),{'character_counts':[len(t) for t in texts]})
 ck('PDF_A4_dimensions',all(abs(float(p.mediabox.width)-595.276)<.1 and abs(float(p.mediabox.height)-841.89)<.1 for p in r.pages))
 fonts=set();embedded=[]
 for p in r.pages:
  for ref in p['/Resources'].get('/Font',{}).values():
   f=ref.get_object();fonts.add(str(f.get('/BaseFont','')));fd=f.get('/FontDescriptor')
   if fd:embedded.append(any(k in fd.get_object() for k in ['/FontFile','/FontFile2','/FontFile3']))
 ck('PDF_fonts_embedded',bool(embedded) and all(embedded),{'fonts':sorted(fonts)})
 out=[]
 with pdfplumber.open(DOC/'project-progress-report.pdf') as pdf:
  for i,p in enumerate(pdf.pages,1):
   for x in p.chars:
    if x['text'].strip() and (x['x0']<0 or x['x1']>p.width+.5 or x['top']<0 or x['bottom']>p.height+.5):out.append([i,x['text']])
 ck('PDF_no_text_outside_page',not out,out[:10])
 pdftext='\n'.join(texts);ck('PDF_preparation_and_evidence_dates','2026-11-09' in texts[0] and '2026-11-08' in texts[0])
 pwm=read(ROOT/'evidence/pwm-reference-v2/20261024/final-summary.json')
 nominal=pwm['key_results']['c15_dc']['current_a']*1e6
 ck('PWM_numeric_binding',f'{nominal:.4f}' in pdftext and math.isclose(1e6/256,3906.25) and '3.90625kHz' in norm(pdftext))
 ee=read(ROOT/'evidence/microled-dynamic-v1/electrical-summary.json');rr=read(ROOT/'evidence/microled-dynamic-v1/rx-summary.json')
 full=[x for x in rr['records'] if x['stage']=='full'];ck('MicroLED_counts_bound_to_evidence',ee['completed']==49 and len(full)==132 and sum(x['combined_electrical_and_RX_screen_pass'] for x in full)==0)
 chosen=lambda route,cap,tau:next(x for x in full if x['route']==route and x['corner']=='typical' and x['steps_per_symbol']==40 and abs(x['capacitance_fF']-cap)<1e-6 and x['optical_tau_ps']==tau)
 expected=[['200fF / τ200ps',*[str(chosen(x,200,200)['bit_errors']) for x in 'ABC']],['10fF / τ25ps',*[str(chosen(x,10,25)['bit_errors']) for x in 'ABC']]]
 tables=[b for p in content['pages'] for b in p['blocks'] if b['type']=='table']
 ck('MicroLED_report_error_table_matches',any(t['rows']==expected for t in tables))
 vc=read(ROOT/'evidence/vcsel-robustness-20261029/final-r10-index.json')['frame_records'];vctable=next(t for t in tables if '正向pJ/尝试净位' in t['head'])
 vcok=True
 for corner,row in zip(['TT','SS','FF'],vctable['rows']):
  x=next(x for x in vc if x['case']=='frame-'+corner+'-r10' and x['label']=='fixed-v3-r2')
  vcok &= row[1]==x['errors'] and row[2]==f"{x['margin_uAeq']:.2f}" and row[3]==f"{x['time_margin_ps']:.2f}" and row[4]==f"{x['positive_pJ_per_offered_payload_bit']:.3f}"
 ck('VCSEL_report_table_matches_native_index',vcok)
 for name in ['数字SDF事件曾回放到r5的30pF','TT名义保持窗','73MOS候选尚无匹配的新layout/PEX','器件代理不随.temp更新','5波形卷缺失','HTTP408']:
  ck('scope_statement_'+name,name in norm(pdftext),{'statement':name})
 guard=read(WORK/'workspace-before.json');changed=[x['path'] for x in guard['unrelated_files'] if not (ROOT/x['path']).exists() or sha(ROOT/x['path'])!=x['sha256']]
 ck('35_unrelated_files_preserved',len(guard['unrelated_files'])==35 and not changed,changed)
 for p in (ROOT/'scripts/project_progress_20261108').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
 ck('generator_AST',True)
 manifest={}
 for d in [DOC,ROOT/'scripts/project_progress_20261108',EV]:
  for p in sorted(d.rglob('*')):
   if p.is_file() and '__pycache__' not in p.parts and p.name not in ['manifest.json','validation.json','delivery-check.json']:
    manifest[str(p.relative_to(ROOT))]={'sha256':sha(p),'bytes':p.stat().st_size}
 (EV/'manifest.json').write_text(json.dumps({'files':manifest},ensure_ascii=False,indent=2)+'\n')
 result={'prepared_date':'2026-11-09','evidence_as_of':'2026-11-08','passed':all(x['passed'] for x in checks),'checks':checks,'PDF_pages':len(r.pages),'HTML_tables':page.tables,'HTML_images':len(page.images),'public_files':len(manifest),'public_bytes':sum(v['bytes'] for v in manifest.values()),'scope':'Report/data/identity/layout integrity, not new EDA/silicon/optical validation. Visual QA is a separate receipt.'}
 (EV/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'passed':result['passed'],'checks':len(checks),'failed':[x for x in checks if not x['passed']],'PDF_pages':len(r.pages),'figures':len(page.images)},ensure_ascii=False))
 raise SystemExit(0 if result['passed'] else 1)
if __name__=='__main__':main()
