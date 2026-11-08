#!/usr/bin/env python3
"""Cross-check recorded experiment coverage and evidence, without upgrading physical status."""
from pathlib import Path
import argparse, gzip, hashlib, json, math, subprocess, sys
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'evidence/microled-dynamic-v1'
DOC=ROOT/'docs/research/microled-dynamic-validation-20261108'
WORK=ROOT/'build/microled-dynamic-v1/electrical/run-r1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
class Page(HTMLParser):
 def __init__(self):super().__init__();self.ids=set();self.links=[];self.images=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if a.get('id'):self.ids.add(a['id'])
  if tag=='a' and a.get('href'):self.links.append(a['href'])
  if tag=='img':self.images.append(a)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--partial',action='store_true');ap.add_argument('--raw-readback',action='store_true');args=ap.parse_args()
 checks=[]
 def ck(name,v,detail=None):checks.append({'name':name,'passed':bool(v),'detail':detail})
 e=read(EV/'electrical-summary.json');rx=read(EV/'rx-summary.json');fit=read(EV/'fit-summary.json');card=read(ROOT/'analog/models/microled_dynamic_v1/model-card.json')
 plan=read(WORK/'plan.json');m=read(WORK/'manifest.json')
 planned={c['name']:c for c in plan};rows={r['name']:r for r in e['records']}
 ck('49_unique_cases_planned',len(planned)==49 and len(plan)==49)
 ck('record_names_are_planned',set(rows)<=set(planned))
 ck('complete_coverage_or_explicit_partial',args.partial or set(rows)==set(planned),{'recorded':len(rows),'missing':sorted(set(planned)-set(rows))})
 ck('record_counts_consistent',e['completed']==len(rows) and e['planned']==len(plan))
 transient={n for n,c in planned.items() if c.get('kind','transient')!='dc'};dc=set(planned)-transient
 ck('33_transients_16_dc',len(transient)==33 and len(dc)==16)
 ck('new_fit_not_used_as_physical_transient',fit['usable_transient_family'] is False and card['usable_transient_family'] is False)
 ck('fit_holdouts_coverage',len(fit['fit_summary'])==5 and len(fit['frequency_holdouts'])==15 and len(fit['bias_holdouts'])==5)
 sources=fit['source_hashes'];ck('source_hashes_match',all(sha(ROOT/x['path'])==x['sha256'] for x in sources))
 ck('fit_math_stable_normalized',all(x['all_poles_strictly_LHP'] and x['strictly_proper'] and abs(x['normalization_at30MHz_dB'])<1e-10 for x in fit['numerical_checks'].values()))
 coeff=read(ROOT/'analog/models/microled_dynamic_v1/coefficients.json')['coefficients']
 data=np.genfromtxt(EV/'fit-residuals.csv',delimiter=',',names=True);coeff_errors=[]
 for bias,model in coeff.items():
  q=data[data['bias_uA']==float(bias)];n=np.array(model['numerator_ascending_q']);d=np.array(model['denominator_ascending_q']);s=1j*q['frequency_Hz']/1e9
  h=np.polynomial.polynomial.polyval(s,n)/np.polynomial.polynomial.polyval(s,d);y=20*np.log10(abs(h))
  if np.max(abs(y-q['conditional_model_dB']))>1e-8 or not np.all(np.roots(d[::-1]).real<0):coeff_errors.append(bias)
 ck('independent_rational_response_and_poles',not coeff_errors,coeff_errors)
 inp={k:v for k,v in m['inputs'].items()} if 'inputs' in m else m.get('input_sha256',{})
 ck('frozen_semantic_inputs_match',all(sha(WORK/'inputs'/p)==h for p,h in inp.items()),{'files':len(inp),'cache_scope':'r1 PYC is a documented generated cache, not a SPICE model; see electrical-input-audit.json'})
 wrong=[];energy=[];io=[]
 for name,r in rows.items():
  path=ROOT/r['result_path'];q=read(path)
  if sha(path)!=r['result_sha256']:io.append(name+' result hash')
  if q.get('case')!=planned[name]:wrong.append(name+' plan mismatch')
  if not r.get('simulation_ok',False):continue
  metrics=q.get('metrics',{})
  stress=metrics.get('stress',[])
  if len(stress)!=dict(A=20,B=21,C=49)[r['route']]:wrong.append(name+' MOS coverage')
  if name in transient:
   en=r['total_energy'];ports=r['energy_ports']
   for field in ['positive_J','returned_J','net_J']:
    if not math.isclose(en[field],sum(v[field] for v in ports.values()),rel_tol=1e-12,abs_tol=1e-24):energy.append(name+' '+field)
   if not math.isclose(en['positive_pJ_per_payload_bit'],en['positive_J']*1e12/4096,rel_tol=1e-12):energy.append(name+' denominator')
   if set(ports)!={'VIN','VDD','VREF','VLED','VD0','VD1','VDISABLE'}:energy.append(name+' ports')
   wave=ROOT/r['waveform_path']
   if not wave.exists() or sha(wave)!=r['gzip_sha256']:io.append(name+' gzip hash')
 ck('case_identity_and_MOS_coverage',not wrong,wrong);ck('native_energy_sum_sign_and_payload',not energy,energy);ck('result_and_compressed_trace_readback',not io,io)
 dc_ok=all(math.isclose(x['error_percent'],(x['current_uA']/x['target_uA']-1)*100,abs_tol=1e-10) for x in e['dc'])
 ck('DC_reported_error_and_cap_invariance',dc_ok and (args.partial or (len(e['dc'])==16 and len(e['dc_capacitance_checks'])==8 and all(x['DC_cap_invariance_passed'] for x in e['dc_capacitance_checks']))),{'criterion':'Independent arithmetic and DC invariance; no post-hoc accuracy acceptance limit'})
 rr=rx['records'];actual={r['case_name'] for r in rr}
 successful={n for n in transient if n in rows and rows[n].get('simulation_ok') and not rows[n].get('analysis_error')}
 ck('only_successful_transients_enter_RX',actual<=successful)
 missing=sorted(successful-actual);ck('all_completed_transients_analyzed',args.partial or not missing,missing)
 rxmissing=[]
 for name in successful:
  if name not in actual:continue
  for tau in [0,25,75,200]:
   found=[r for r in rr if r['case_name']==name and r['stage']=='full' and r['optical_tau_ps']==tau]
   if len(found)!=1:rxmissing.append([name,tau])
 ck('four_tau_hypotheses_for_each_trace',not rxmissing,rxmissing)
 ck('no_unreported_analysis_failures',not rx.get('analysis_failures'),rx.get('analysis_failures'))
 ck('RX_bound_to_frozen_registry',rx['electrical_registry_sha256']==sha(EV/'electrical-registry.json'))
 baseline=rx['baseline_200ps_reproduction'];half=rx['halfstep_checks']
 ck('historical_RX_reproductions',len(baseline)==33 and all(x['passed'] for x in baseline))
 ck('native_step_controls_accounted',len(half)==24 and all(x['pass_unchanged'] and x['delay_delta_ps']==0 for x in half),{'bit_count_differences':sum(x['bit_error_delta']!=0 for x in half),'maximum_bit_count_delta':max(abs(x['bit_error_delta']) for x in half),'criterion':'Preserve numerical deltas; unchanged screening is not exact waveform equality.'})
 audit=read(EV/'rx-audit.json')
 ck('final_RX_audit_hash_binding',audit['passed'] and audit['final'] and audit['summary_sha256']==sha(EV/'rx-summary.json') and audit['analysis_source_sha256']==sha(ROOT/'scripts/microled_dynamic_v1/analyze.py') and all(c['passed'] for c in audit['checks']))
 badrx=[]
 for r in rr:
  if not 0<=r['delay_ps']<=8000 or abs(r['delay_ps']/5-round(r['delay_ps']/5))>1e-7:badrx.append(r['case_name']+' phase')
  if r['bit_count']!=4096:badrx.append(r['case_name']+' payload')
  if r['stage']=='full' and r['case_name'] in rows and not math.isclose(r['energy_positive_pJ_per_attempted_payload_bit'],rows[r['case_name']]['total_energy']['positive_pJ_per_payload_bit'],rel_tol=1e-12):badrx.append(r['case_name']+' energy')
 ck('fixed_grid_payload_and_shared_energy',not badrx,badrx)
 oldmanifest=read(ROOT/'evidence/microled-dynamic-20261029/manifest.json')['public_files']
 ck('historical_dynamic_evidence_unchanged',all(sha(ROOT/p)==v['sha256'] for p,v in oldmanifest.items()))
 page=Page();page.feed((DOC/'index.html').read_text());broken=[]
 for link in page.links+[x['src'] for x in page.images]:
  u=urlsplit(link)
  if u.scheme or u.netloc:continue
  if u.path and not (DOC/unquote(u.path)).resolve().exists():broken.append(link)
  if not u.path and u.fragment and unquote(u.fragment) not in page.ids:broken.append(link)
 ck('local_links_and_anchors',not broken,broken);ck('five_original_report_figures',len(page.images)==5 and all(x.get('alt') for x in page.images))
 for p in (DOC/'figures').glob('*.svg'):ET.parse(p)
 ck('SVG_XML_wellformed',True)
 guards=read(ROOT/'build/microled-dynamic-v1/workspace-before.json');unrelated=[]
 for g in guards['unrelated_files']:
  p=ROOT/g['path']
  if not p.exists() or sha(p)!=g['sha256']:unrelated.append(g['path'])
 ck('unrelated_workspace_files_preserved',not unrelated,unrelated)
 rawproof=[]
 if args.raw_readback:
  for name in ['TT-A-C200fF-S40','TT-B-C0fF-S40','TT-C-C10fF-S40']:
   if name not in rows:continue
   r=rows[name];p=ROOT/r['waveform_path']
   with gzip.open(p,'rb') as stream:h=hashlib.file_digest(stream,'sha256').hexdigest()
   rawproof.append({'case':name,'matches_uncompressed_source':h==r['raw_sha256']})
  ck('independent_native_trace_decompression',len(rawproof)==3 and all(q['matches_uncompressed_source'] for q in rawproof),rawproof)
 public=[]
 for d in [DOC,EV,ROOT/'scripts/microled_dynamic_v1',ROOT/'analog/models/microled_dynamic_v1']:
  public.extend(p for p in d.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ['report-validation.json','report-manifest.json','archive-manifest.json','archive-local.json','archive-remote.json','archive-restore.json','delivery-check.json'])
 public=sorted(set(public));manifest={str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in public}
 report={'date':'2026-11-08','partial':args.partial,'passed':all(x['passed'] for x in checks),'checks':checks,'expected_cases':len(plan),'recorded_cases':len(rows),'actual_RX_transients':len(actual),'public_files':len(public),'public_bytes':sum(v['bytes'] for v in manifest.values()),'electrical_failures_reported':e.get('failures',[]),'raw_readback':rawproof,'boundary':'Passing means reproducible evidence accounting, not that the driver/link or physical model passes. Pair-voltage screen excludes body/reliability qualification.'}
 (EV/'report-manifest.json').write_text(json.dumps({'files':manifest},ensure_ascii=False,indent=2)+'\n');(EV/'report-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'passed':report['passed'],'partial':args.partial,'checks':len(checks),'failed':[x for x in checks if not x['passed']],'cases':len(rows),'RX_transients':len(actual)},ensure_ascii=False))
 raise SystemExit(0 if report['passed'] else 1)
if __name__=='__main__':main()
