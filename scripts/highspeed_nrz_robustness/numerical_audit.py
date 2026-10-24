#!/usr/bin/env python3
import json
from pathlib import Path
import run as r
w=r.ROOT/'build/highspeed-nrz-robustness/selected-a8-b58-r4';rows=[json.loads(p.read_text()) for p in (w/'cases').glob('*/analysis.json')];pairs=[]
for x in rows:
 c=x['case']
 if not x.get('analysis_ok') or c['kind'] not in ['SSminus50_gear80','FFplus50_gear80','FFplus50_trap']:continue
 def match(y):
  yc=y['case']
  return y.get('analysis_ok') and yc.get('steps_per_ui')==40 and yc.get('method')=='gear' and not yc.get('rail_offsets_V') and not yc.get('rail_profiles') and not yc.get('supply_package') and all(yc.get(k)==c.get(k) for k in ['route','rate_Gbps','corner','temp_C','vdd_V','res_corner','r_pkg','l_pkg']) and 'dc_bit' not in yc
 candidates=[y for y in rows if match(y)]
 if not candidates:raise ValueError('missing baseline for '+c['name'])
 y=candidates[0];a=x['row'];b=y['row'];diff={k:abs(a[k]-b[k]) for k in ['max_abs_terminal_V','threshold_margin_normalized','timing_min_margin_ui']};diff['energy_relative']=abs(a['rail_plus_DATA_positive_draw_fJ_per_gross_bit']/b['rail_plus_DATA_positive_draw_fJ_per_gross_bit']-1)
 ok=diff['max_abs_terminal_V']<=.005 and diff['threshold_margin_normalized']<=.02 and diff['timing_min_margin_ui']<=.02 and diff['energy_relative']<=.05 and a['errors']==b['errors']
 pairs.append({'control':a['analysis_json'],'baseline':b['analysis_json'],'differences':diff,'error_counts':[b['errors'],a['errors']],'passed':ok})
out={'acceptance':'evidence/highspeed-nrz-robustness/numerical-acceptance.json','pairs':pairs,'all_passed':bool(pairs) and all(p['passed'] for p in pairs),'complete_six_controls':len(pairs)==6};r.emit(r.EVIDENCE/'numerical-audit.json',out);print(json.dumps(out))
