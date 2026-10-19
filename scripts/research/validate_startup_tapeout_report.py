"""Report/source/arithmetic/render audit. Success never erases experiment failure."""
from pathlib import Path
import argparse, hashlib,json,math,re,subprocess,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/research/startup-tapeout-20261014'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads((ROOT/p).read_text())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--pdf-pages-reviewed',type=int,required=True);a=ap.parse_args();checks=[];hashes={}
 def ck(name,ok,detail=None):
  checks.append({'name':name,'passed':bool(ok),'detail':detail})
  if not ok:raise ValueError(name+': '+str(detail))
 s=read('evidence/startup-v2/summary.json');audit=read('evidence/startup-v2/validation.json')
 ck('audit matches summary and retains strict failure',audit['passed'] and audit['summary_sha256']==sha(ROOT/'evidence/startup-v2/summary.json')
    and s['functional_contract_passed'] and not s['legacy_startup_relative_convergence_passed'] and not s['passed'])
 ck('run counts',s['transient_runs']==len(s['results'])==21 and s['dc_runs']==len(s['dc_results'])==12 and len(s['checks'])==134)
 for p,h in s['source_sha256'].items():ck('new as-run source '+p,sha(ROOT/p)==h);hashes[p]=h
 lookup={r['name']:r for r in s['results']}
 for r in s['results']:
  p=ROOT/r['csvpath'];ck('waveform hash '+r['name'],sha(p)==r['csv_sha256']);hashes[r['csvpath']]=sha(p)
  # Case physical failure controls are labelled expected failure; not functional successes.
  if r['name'].startswith('baseline_'):ck('baseline captures failed original startup '+r['name'],r['startup']['branch_max_abs_a']>1e-9)
  elif r['name'].startswith('startup_'):ck('selected startup still uses branch peak '+r['name'],r['startup']['branch_max_abs_a']<1e-9)
 for key in ['tt','ss','ff']:
  r=lookup['fault_'+key];ck('fault deadline and directional charge '+key,r['fault_to_safe_s']<1e-6
    and r['held_fault']['branch_max_abs_a']<1e-9 and r['fault']['branch_charge']['positive_c']<10e-12
    and abs(r['fault']['branch_charge']['negative_c'])<20e-12)
  current=lookup['startup_'+key+'_ramp100ns']['dc_full_a'];ck('selected coupled DC '+key,abs(current/100e-6-1)<.05)
 c=next(x for x in s['convergence'] if x['name']=='startup');ind=abs(c['fine_charge_c']-c['coarse_charge_c'])/abs(c['coarse_charge_c'])*100
 ck('strict numerical failure independently calculated',abs(ind-c['change_pct'])<1e-12 and ind>.2 and not c['passed'])
 trial=read('evidence/startup-v2/4mos-trial/summary.json');ss=next(x for x in trial['dc_results'] if x['name']=='dc_ss_True_True_1')
 ck('single-N candidate failure retained',not trial['functional_contract_passed'] and abs(ss['current_a']*1e6-68.04684875429436)<1e-9)
 b=read('docs/research/startup-tapeout-20261014/report-blocks.json');ck('derived prose frozen to summary',b['_source_summary_sha256']==sha(ROOT/'evidence/startup-v2/summary.json'))
 # Actual schematic terminal metadata, not a pictorial approximation.
 text=(ROOT/'analog/startup_v2/reference_isolator_tg.spice').read_text();spec={}
 for line in text.splitlines():
  t=line.split()
  if t and t[0].startswith('X'):spec[t[0]]=t[1:5]
 diagram=ET.parse(BASE/'figures/reference-isolator.svg')
 parts={e.attrib['data-device']:e.attrib['data-nets'].split() for e in diagram.iter() if 'data-device' in e.attrib}
 ck('five MOS drawing matches final D G S B',len(spec)==len(parts)==5 and spec==parts,{'netlist':spec,'drawing':parts})
 area=read('docs/research/startup-tapeout-20261014/area-baseline.json')
 for r in area['layouts']:
  ck('actual archived GDS hash '+r['path'],sha(ROOT/r['path'])==r['sha256']);x0,y0,x1,y1=r['bbox_um']
  ck('independent bbox arithmetic '+r['topcell'],math.isclose((x1-x0)*(y1-y0),r['bbox_span_area_um2'],rel_tol=1e-14))
 ck('independent pad/MIM/EM unit calculations',780**2/1e6==.6084 and 3e3/1.5==2000 and 3e3/1==3000
   and math.isclose(7/.67,10.447761194029852) and math.ceil(7/.18)==39 and (80+80+2+2+2+4)==170)
 sources=read('docs/research/startup-tapeout-20261014/fabrication-sources.json')
 ck('primary source ledger',len(sources['sources'])==16 and all(x['url'].startswith('https://') and x['locator'] for x in sources['sources']))
 for r in sources['local_evidence']:ck('fabrication local identity '+r['path'],sha(ROOT/r['path'])==r['sha256']);hashes[r['path']]=r['sha256']
 for p in [BASE/'report.md',BASE/'README.md',BASE/'fabrication-chapter.md',ROOT/'evidence/startup-v2/README.md']:
  text=p.read_text();ck('no placeholder '+p.name,not re.search(r'@@[A-Z_]+@@',text));missing=[]
  links=re.findall(r'\]\(([^)]+)\)',text)+re.findall(r'href="([^"]+)"',text)
  for link in links:
   if '://' in link or link.startswith('#'):continue
   target=(p.parent/link.split('#')[0]).resolve()
   if target.name not in ['evidence-ledger.json','validation.json'] and not target.exists():missing.append(link)
  ck('local links '+str(p.relative_to(ROOT)),not missing,missing)
 peer_path=ROOT/'evidence/startup-v2/peer-audit.json';peer=json.loads(peer_path.read_text())
 ck('independent peer audit is durable and current',peer['data_integrity_passed'] and peer['checked_summary_sha256']==sha(ROOT/'evidence/startup-v2/summary.json'))
 layout=read('build/research-startup-tapeout-20261014/layout-check.json');pdf=PdfReader(str(BASE/'report.pdf'))
 ck('18 pages, loaded figures, no overflow',len(pdf.pages)==len(layout['sections'])==18 and not layout['overflow'] and all(x['loaded'] for x in layout['images']) and all(x['height']<970 for x in layout['sections']))
 ck('readable text each page',all(len(p.extract_text())>250 for p in pdf.pages));ck('all final pages inspected',a.pdf_pages_reviewed==18)
 for folder in [ROOT/'evidence/startup-v2',BASE]:
  for p in folder.glob('*.json'):
   if folder==BASE and p.name in ['evidence-ledger.json','validation.json']:continue
   hashes[str(p.relative_to(ROOT))]=sha(p)
 for p in (ROOT/'scripts/research').glob('*startup*tapeout*'):hashes[str(p.relative_to(ROOT))]=sha(p)
 for p in (ROOT/'scripts/startup_v2').glob('*.py'):hashes[str(p.relative_to(ROOT))]=sha(p)
 old=ROOT/'docs/research/reference-safety-20261013';old_validation=json.loads((old/'validation.json').read_text())
 ck('prior report PDF unchanged',sha(old/'report.pdf')==old_validation['outputs_sha256']['report.pdf'])
 ledger={'checked_on':'2026-10-14 Asia/Tokyo','engineering_baseline':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
  'new_evidence':'schematic GF180 reference isolation + actual RTL safety replay + old selected signal PEX',
  'functional_contract_passed':True,'legacy_relative_charge_passed':False,'whole_experiment_passed':False,
  'not_established':['new layout/DRC/LVS/PEX','POR/brownout/arbitrary rail order','foundry acceptance','silicon/optical measurement'],
  'source_sha256':hashes,'figures_sha256':{str(p.relative_to(BASE)):sha(p) for p in (BASE/'figures').glob('*.svg')}}
 (BASE/'evidence-ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n')
 out={'passed':True,'checked_at_UTC':datetime.now(timezone.utc).isoformat(),'check_count':len(checks),'checks':checks,'report_pages':18,
  'visually_inspected_pages':list(range(1,19)),'experiment_passed':False,'audit_does_not_upgrade_experiment':True,
  'output_sha256':{p.name:sha(p) for p in BASE.iterdir() if p.is_file() and p.name!='validation.json'}}
 (BASE/'validation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'passed':True,'checks':len(checks),'pages':18,'experiment_passed':False,'source_entries':len(hashes)}))
if __name__=='__main__':main()
