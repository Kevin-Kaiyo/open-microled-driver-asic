#!/usr/bin/env python3
"""Check report-to-evidence integrity; this does not turn simulations into hardware proof."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'evidence/vcsel-robustness-20261029'
DOC=ROOT/'docs/research/vcsel-reference-microled-dynamics-20261029'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def bound(p,h):assert Path(p).is_file() and sha(p)==h,str(p)
class Links(HTMLParser):
 def __init__(self):super().__init__();self.urls=[];self.images=0
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag in ['a','img']:
   v=d.get('href' if tag=='a' else 'src','');self.urls.append(v)
   if tag=='img':self.images+=1;assert d.get('alt'),v
def main():
 checks=[]
 for x in read(EV/'baseline-lock.json')['files']:bound(ROOT/x['path'],x['sha256'])
 checks.append('Historical model, receiver, baseline summary and experiment-plan bytes unchanged')
 s=read(EV/'summary.json');cfg=read(EV/'report-cases.json')
 names=[v for row in cfg['frames'].values() for v in row.values()]+cfg.get('controls',[])+cfg.get('continuous',[])
 cases=[]
 for identifier in names:
  name,label=identifier.split('#',1) if '#' in identifier else (identifier,'fixed-v3-r2')
  rows=[x for x in s['cases'] if x['case']==name and x['analysis_label']==label];assert len(rows)==1,identifier
  x=rows[0];w=ROOT/'build/vcsel-robustness-20261029'/name
  for k,h in [('result','result_sha256'),('analysis','analysis_sha256'),('plot_data','plot_sha256')]:
   if k in x:bound(ROOT/x[k],x[h])
  r=read(w/'result.json');m=read(w/'manifest.json');bound(w/'manifest.json',r['manifest_sha256'])
  if r.get('continuous_run'):
   cr=r['continuous_run'];parent=ROOT/'build/vcsel-robustness-20261029'/cr['parent_case'];pr=read(parent/'result.json')
   bound(parent/'result.json',cr['parent_result_sha256']);bound(parent/'testbench.spice',pr['deck_sha256']);bound(parent/'ngspice.log',pr['log_sha256']);bound(ROOT/pr['waveform']['path'],m['parent_waveform_sha256'])
   assert cr['no_operating_point_reset'] and pr['simulation_ok']
  else:
   bound(w/'testbench.spice',r['deck_sha256']);bound(w/'ngspice.log',r['log_sha256'])
  for p,h in m['source_hashes'].items():bound(ROOT/p,h)
  bound(ROOT/r['waveform']['path'],r['waveform']['sha256'])
  assert r['simulation_ok'] and m['config']['rate']==3.2 and m['config']['nbits']==4736
  assert abs(sum(p['positive_J'] for p in x['ports'].values())/4096*1e12-x['energy']['positive_pJ_per_offered_payload_bit'])<1e-8
  if x['variant']=='regulated':assert set(x['ports'])=={'VLASER','VDD','VREF','VD','VDB','VSET','VREGSET'}
  if x['passed']:assert x['errors']==0 and x['time_margin_ps']>=100 and x['min_signed_margin_uAeq']>=7.5 and x['stress_max_V']<=3.63 and x['device_screen_passed']
  cases.append(dict(case=name,analysis_label=label,conditional_screen_passed=x['passed']))
 checks.append('Selected frame inputs, raw gzip, energy-port sums, receiver label and reported screening gates agree')
 for name in list(cfg['startup_before'].values())+list(cfg['startup_after'].values()):
  w=ROOT/'build/vcsel-robustness-20261029'/name;x=read(w/'startup-review.json');r=read(w/'result.json')
  bound(w/'startup-plot.npz',x['plot_sha256']);bound(ROOT/r['waveform']['path'],x['waveform_sha256']);bound(ROOT/'build/vcsel-robustness-20261029'/x['dc_case']/'result.json',x['dc_result_sha256'])
 checks.append('Startup charts bound to native data and independent DC targets')
 for x in read(EV/'audit-r10-startup-peak-windows.json')['rows']:
  w=ROOT/'build/vcsel-robustness-20261029'/x['case'];r=read(w/'result.json')
  bound(ROOT/r['waveform']['path'],x['waveform_sha256']);bound(w/'testbench.spice',r['deck_sha256']);bound(w/'ngspice.log',r['log_sha256'])
  assert x['max_native_timestep_ns']<0.051
  if x['config']['ramp_ns']==20:assert x['stress_max']['V']>3.63 and x['stress_max']['headroom_mV']<0
 checks.append('Fine-step fast-startup failure preserved, independent of data-frame screening')
 fig=read(EV/'circuit-figures.json');bound(ROOT/fig['source'],fig['source_sha256'])
 devices={line.split()[0] for line in (ROOT/fig['source']).read_text().splitlines() if len(line.split())>5 and line.split()[5] in ['nmos_3p3','pmos_3p3']}
 represented=set()
 for f in fig['figures']:
  bound(ROOT/f['path'],f['sha256'])
  for g in f['groups']:represented.update(g['instances'])
 assert devices==represented and len(devices)==fig['mos_count']
 checks.append(f'All {len(devices)} source MOS instances represented with D/G/S/B and geometry')
 micro=read(ROOT/'evidence/microled-dynamic-20261029/manifest.json')
 for path,item in micro['public_files'].items():bound(ROOT/path,item['sha256'])
 for path,item in micro['raw_inputs'].items():
  if item.get('public_release')=='allowlisted':bound(ROOT/path,item['sha256'])
 checks.append('MicroLED public extracts, model contract, source files and licensed raw subset match their frozen manifest')
 for item in read(EV/'report-manifest.json')['files']:bound(ROOT/item['path'],item['sha256'])
 pages=[]
 for name in ['index.html','microled-dynamic-evidence.html']:
  p=DOC/name;t=p.read_text();parser=Links();parser.feed(t)
  assert '待仿真与独立复核后填入' not in t and '待验证设计冻结后填入' not in t
  assert not re.search(r'<!-- ([A-Z_]+) -->\s*<!-- END \1 -->',t)
  for url in parser.urls:
   u=urlsplit(url)
   if u.scheme or not u.path:continue
   dest=(p.parent/unquote(u.path)).resolve();assert dest.exists(),(name,url)
  pages.append(dict(page=name,local_references=len(parser.urls),images=parser.images))
 checks.append('Report hash, images, local links and completed narrative sections checked')
 result=dict(status='PASS',checks=checks,cases=cases,pages=pages,boundary='Integrity and bounded experiment checks only; independent numerical audit and visual inspection are separate. No optical BER, PEX or silicon qualification.')
 (EV/'report-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
