#!/usr/bin/env python3
"""Check report identity, local navigation and independent unit arithmetic."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse,unquote
import ast,hashlib,json,math,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
EV=ROOT/'evidence/architecture-review-20261025'
OUT=ROOT/'docs/research/architecture-decision-review-20261025'
class Page(HTMLParser):
 def __init__(self):super().__init__();self.urls=[];self.ids=set()
 def handle_starttag(self,tag,attrs):
  self.urls += [v for k,v in attrs if k in ['href','src']]
  self.ids.update(v for k,v in attrs if k=='id')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 proof=json.loads((EV/'report-provenance.json').read_text());checks=[]
 for group in ['inputs','outputs']:
  for p,digest in proof[group].items():assert sha(ROOT/p)==digest,p;checks.append(group+':'+p)
 assert sha(ROOT/'scripts/architecture_review_20261025.py')==proof['generator_sha256']
 page=Page();page.feed((OUT/'index.html').read_text())
 assert '{{' not in (OUT/'index.html').read_text() and '{{' not in (OUT/'report-complete.md').read_text()
 for u in page.urls:
  parsed=urlparse(u)
  if parsed.scheme or parsed.netloc:continue
  p=(OUT/unquote(parsed.path)).resolve() if parsed.path else OUT/'index.html';assert p.exists(),u
  if parsed.fragment and p.suffix=='.html':
   target=Page();target.feed(p.read_text());assert unquote(parsed.fragment) in target.ids,u
  if p.suffix=='.svg':ET.parse(p)
 cal=json.loads((EV/'calculations.json').read_text())
 assert cal['PWM']['repetition_Hz']==3906.25 and cal['PWM']['duty_levels']==257
 assert math.isclose(cal['NRZ']['power_mW'],2.68827141845595*.5)
 assert math.isclose(cal['NRZ']['random_measurement_zero_errors_511_upper_95'],1-.05**(1/511),rel_tol=1e-10)
 s=next(x for x in cal['array_scenarios'] if x['lanes']==16)
 assert math.isclose(s['ideal_shared_control_local_output_total_port_positive_power_mW'],12.86271722452218,rel_tol=1e-8)
 assert math.isclose(s['ideal_shared_control_local_output_gross_pJ_per_bit'],s['ideal_shared_control_local_output_total_port_positive_power_mW']/8)
 assert cal['interfaces']['RGB_3840x2160_8bit_60Hz_payload_bps']==11943936000
 assert cal['power_scaling']['delta_1pJ_at_1Tbps_W']==1
 comparison=json.loads((EV/'route-comparison-reviewed.json').read_text())
 assert comparison['route_decision']['status']=='undecided'
 assert len(comparison['same_rate_rows'])==6
 assert comparison['independent_validation']['gzip_raw_files_checked']==6
 assert comparison['independent_validation']['all_ports_positive_returned_net_and_total_match']
 available_source_locks=[];missing_source_locks=[]
 for lock in comparison['source_locks']:
  archived=ROOT/lock['path']
  if archived.exists():
   assert sha(archived)==lock['sha256'];available_source_locks.append(lock['path'])
  else:missing_source_locks.append(lock['path'])
 assert '暂不把A或B列为默认优先架构' in (OUT/'report-complete.md').read_text()
 for file in [ROOT/'scripts/architecture_review_20261025.py',Path(__file__)]:ast.parse(file.read_text())
 data={'passed':True,'as_of':'2026-10-25','scope':'Existing evidence hashes, local links/anchors/SVG and independent arithmetic. No new EDA, optical test, market survey or price quote.','hashed_files':len(checks)+1,'archived_source_locks_checked':available_source_locks,'archived_source_locks_not_restored':missing_source_locks,'local_links':sum(not urlparse(x).scheme and not urlparse(x).netloc for x in page.urls),'external_links':sum(bool(urlparse(x).scheme or urlparse(x).netloc) for x in page.urls),'html_sha256':sha(OUT/'index.html'),'validator_sha256':sha(Path(__file__))}
 (EV/'validation.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print(json.dumps(data,ensure_ascii=False))
if __name__=='__main__':main()
