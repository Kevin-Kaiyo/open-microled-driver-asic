#!/usr/bin/env python3
"""Keep final R/MOS/poly and folded C matrix; change ground-C positions only."""
import argparse,json,shutil
import explore as e
r=e.r;ROOT=e.ROOT
WORK=ROOT/'build/highspeed-nrz-pvt/cap-placement-final-r4';FINAL=ROOT/'build/highspeed-nrz-pvt/final-r4'

def prepare():
 e.create(WORK);m=json.loads((WORK/'manifest.json').read_text())
 for route in 'AB':
  src=ROOT/f'build/highspeed-nrz-pvt-layout/final-r4/{route}/rc-lumped-capacitance.spice';dst=WORK/'inputs'/f'{route}-RCLUMP.spice'
  if dst.exists():
   if r.sha(dst)!=r.sha(src):raise ValueError('Frozen RCLUMP input drift')
  else:shutil.copy2(src,dst)
  definition={'path':str(dst.relative_to(WORK/'inputs')),'sha256':r.sha(dst),'rref_source':'vdummy' if route=='B' else 'vdd','source':r.rel(src),'scope':'Ground-C placement control; allR, MOS,compactresistor andfoldednet-pairC unchanged. Not a secondfieldsolution.'}
  old=m['variants'][route].get('RCLUMP')
  if old and old!=definition:raise ValueError('Frozen definition drift')
  m['variants'][route]['RCLUMP']=definition
 r.emit(WORK/'manifest.json',m)

def summary():
 base=json.loads((FINAL/'analysis.json').read_text());out=[];model_checks=[]
 for route in 'AB':
  rc=next((ROOT/f'build/highspeed-nrz-pvt-layout/final-r4/{route}/full-rc').glob('*_rc.spice'));lump=ROOT/f'build/highspeed-nrz-pvt-layout/final-r4/{route}/rc-lumped-capacitance.spice'
  def elements(path,prefix):return sorted(' '.join(s.split()) for s in path.read_text().splitlines() if s.strip().upper().startswith(prefix))
  def folded(path):
   from collections import defaultdict
   import re
   sums=defaultdict(float)
   for line in path.read_text().splitlines():
    f=line.split()
    if len(f)==4 and f[0].lower().startswith('c'):
     nodes=tuple(sorted(re.sub(r'\.(?:t|n)\d+.*','',n.lower()) for n in f[1:3]));sums[nodes]+=float(f[3])
   return sums
  cm,cl=folded(rc),folded(lump);delta=max(abs(cm.get(k,0)-cl.get(k,0)) for k in set(cm)|set(cl))
  check={'route':route,'RC_sha256':r.sha(rc),'RCLUMP_sha256':r.sha(lump),'identical_all_R':elements(rc,'R')==elements(lump,'R'),'identical_all_MOS_and_poly':elements(rc,'X')==elements(lump,'X'),'folded_C_matrix_max_delta_F':delta}
  check['passed']=check['identical_all_R'] and check['identical_all_MOS_and_poly'] and delta<1e-26
  if not check['passed']:raise ValueError('RCLUMP changed more than groundC placement')
  model_checks.append(check)
 for ap in sorted((WORK/'cases').glob('*/analysis.json')):
  a=json.loads(ap.read_text());row=a['row'];c=row
  ref=next(x for x in base['rows'] if x['variant']=='AFTER' and x['route']==c['route'] and x['rate_Gbps']==c['rate_Gbps'] and x['kind']==c['kind'])
  key='rail_plus_DATA_positive_draw_fJ_per_gross_bit'
  out.append({'row':row,'reference':ref['name'],'reference_analysis_json':ref['analysis_json'],'energy_change_percent':100*(row[key]/ref[key]-1),'terminal_delta_V':row['max_abs_terminal_V']-ref['max_abs_terminal_V'],'margin_delta':row['threshold_margin_normalized']-ref['threshold_margin_normalized'],'errors_changed':row['errors']!=ref['errors'],'screen_changed':row['combined_screen_passed']!=ref['combined_screen_passed']})
 r.emit(r.EVIDENCE/'cap-placement-control.json',{'work':r.rel(WORK),'controls':out,'model_checks':model_checks,'reference_analysis_sha256':r.sha(FINAL/'analysis.json'),'count':len(out),'complete':len(out)==4,'scope':'Two selected SS/FF operating points perroute; groundCplacementonly; not fieldsolver validation'})
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--routes',default='AB');a=p.parse_args();prepare()
 for route in a.routes:
  for kind,corner,temp,vdd in [('slow_hot','ss',125,3.),('fast_cold','ff',-40,3.6)]:
   c=r.case_spec(WORK,route,'RCLUMP',1 if route=='A' else .5,kind=kind,corner=corner,temp_C=temp,vdd_V=vdd);row=e.metrics(WORK,r.run_case(WORK,c));print(json.dumps({k:row.get(k) for k in ['name','errors','threshold_margin_normalized','max_abs_terminal_V','combined_screen_passed']}),flush=True)
 summary()
if __name__=='__main__':main()
