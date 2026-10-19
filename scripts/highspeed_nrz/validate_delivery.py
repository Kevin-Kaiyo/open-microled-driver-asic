#!/usr/bin/env python3
"""Evidence/relationship checks for the delivered NRZ report, not optical sign-off."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib,json,math
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/highspeed-nrz-20261019'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.ids=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if 'id' in a:self.ids.append(a['id'])
  for k in ['src','href']:
   if k in a:self.links.append(a[k])
def main():
 checks=[]
 def check(name,ok):
  if not ok:raise AssertionError(name)
  checks.append(name)
 summary=json.loads((ROOT/'evidence/highspeed-nrz/summary.json').read_text());work=ROOT/summary['identity']['work'];full=json.loads((work/'analysis.json').read_text())
 check('96 formal cases completed',summary['counts']['case_results_found']==96 and summary['counts']['simulation_failures']==0 and summary['counts']['analysis_failures']==0)
 check('36 DC and 60 transient',summary['counts']['analyzed_DC']==36 and summary['counts']['analyzed_transient']==60)
 check('full analysis hash',sha(work/'analysis.json')==summary['analysis_sha256'])
 check('independent numerical controls pass',summary['metrics_self_checks']['count']==15 and summary['metrics_self_checks']['status']=='passed')
 for rec in full['cases']:
  if 'transient' not in rec:continue
  tx=rec['transient'];name=rec['case']['name'];guard=tx['sampler']['training_guard']
  check('training isolation '+name,guard['latest_training_candidate_sample_s']<guard['validation_starts_s'])
  check('511 validation bits '+name,tx['validation']['sample_count']==511 and not tx['validation']['sampling_reoptimized_on_validation'])
  en=tx['energy']
  for rail,p in en['rails'].items():check('energy identity '+name+' '+rail,math.isclose(p['net_J'],p['positive_draw_J']-p['returned_J'],rel_tol=1e-10,abs_tol=1e-22))
  check('all electrical rails and input recorded '+name,len(en['rails'])==(4 if rec['case']['route']=='A' else 3) and 'ideal_DATA' in en)
 rows=summary['rows'];nom=[r for r in rows if r['kind']=='nominal']
 check('matched seven nominal rates',len(nom)==14 and sorted(r['rate_Gbps'] for r in nom if r['route']=='A')==sorted(r['rate_Gbps'] for r in nom if r['route']=='B'))
 for route in 'AB':
  for bit,target in [(0,25e-6),(1,100e-6)]:
   r=next(r for r in rows if r['kind']=='dc' and r['route']==route and r['corner']=='typical' and r['temp_C']==27 and r['vdd_V']==3.3 and r['dc_bit']==bit)
   check(f'{route} nominal DC match bit{bit}',abs(r['LED_current_A']/target-1)<1e-5)
 for c in json.loads((ROOT/'evidence/highspeed-nrz/numerical-comparison.json').read_text()):
  check(f"numerical class stable {c['route']}/{c['rate_Gbps']}/{c['control']}",not c['errors_changed'] and not c['screen_changed'])
  check(f"numerical energy within 0.5 percent {c['route']}/{c['rate_Gbps']}/{c['control']}",abs(c['energy_positive_change_percent'])<.5)
 for name in ['voltage_driver.spice','steering_driver.spice']:
  check('report netlist exact frozen '+name,sha(OUT/'netlists'/name)==sha(work/'inputs/analog/highspeed_nrz'/name))
 p=Links();p.feed((OUT/'index.html').read_text());check('unique anchor IDs',len(p.ids)==len(set(p.ids)))
 for link in p.links:
  if link.startswith(('http:','https:','mailto:','data:')):continue
  if link.startswith('#'):check('anchor '+link,link[1:] in p.ids)
  else:check('local report link '+link,(OUT/link.split('#')[0]).exists())
 for name in ['summary.json','summary.csv','window-check.json','receiver-sensitivity.json','numerical-diagnosis.json','numerical-comparison.json']:
  check('published local evidence exact '+name,sha(OUT/name)==sha(ROOT/'evidence/highspeed-nrz'/name))
 source_files=[Path(__file__),ROOT/'scripts/highspeed_nrz/analyze.py',ROOT/'scripts/highspeed_nrz/metrics.py',ROOT/'scripts/highspeed_nrz/report.py',ROOT/'scripts/highspeed_nrz/receiver_sensitivity.py']
 evidence={'status':'passed','count':len(checks),'checks':checks,'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in source_files},'report_sha256':sha(OUT/'index.html'),'scope':'evidence coherence, calibrated comparison and numerical controls; no measured BER or tape-out qualification'}
 (ROOT/'evidence/highspeed-nrz/delivery-validation.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':'passed','count':len(checks)}))
if __name__=='__main__':main()
