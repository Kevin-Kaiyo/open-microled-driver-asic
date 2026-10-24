#!/usr/bin/env python3
"""Explain frozen training objective and asymmetric validation timing; no retuning."""
import json
from pathlib import Path
import run as r
folders=[r.ROOT/'build/highspeed-nrz-robustness'/n for n in ['final-hv-a8-b58-r2','selected-a8-b58-r4']]
rows=[]
for w in folders:
 for p in sorted((w/'cases').glob('*/analysis.json')):
  x=json.loads(p.read_text());c=x['case']
  if c['route']!='A' or c['corner']!='ss' or c['vdd_V']!=2.95 or not x.get('analysis_ok') or 'transient' not in x:continue
  if c['rate_Gbps'] not in [.25,.4,.5]:continue
  s=x['transient']['sampler'];v=x['transient']['validation'];ps=v['phase_sweep'];ui=s['ui_s']
  indices=[min(range(len(ps['delta_ui'])),key=lambda i:abs(ps['delta_ui'][i]-target)) for target in [-.25,0,v['timing_right_ui'],v['timing_right_ui']+v['timing_sweep_step_ui']]]
  rows.append({'analysis_json':r.rel(p),'analysis_sha256':r.sha(p),'rate_Gbps':c['rate_Gbps'],'kind':c['kind'],'sample_delay_ns':s['sample_delay_s']*1e9,'sample_delay_ui':s['sample_delay_ui'],'threshold_margin_normalized':v['threshold_margin_normalized'],'timing_left_ui':v['timing_left_ui'],'timing_right_ui':v['timing_right_ui'],'timing_left_ns':v['timing_left_ui']*ui*1e9,'timing_right_ns':v['timing_right_ui']*ui*1e9,'left_lower_bound':v['timing_left_is_lower_bound'],'right_lower_bound':v['timing_right_is_lower_bound'],'diagnostic_offsets':[{'offset_ui':ps['delta_ui'][i],'offset_ns':ps['delta_ui'][i]*ui*1e9,'errors':ps['errors'][i],'threshold_margin_normalized':ps['threshold_margin_normalized'][i]} for i in indices],'sampling_reoptimized_on_validation':v['sampling_reoptimized_on_validation']})
report={'scope':'Diagnostic only, frozen original training/RX/threshold and original pass/fail unchanged. No new sampler is selected from validation.','algorithm':'Training minimizes deterministic errors then maximizes worst fixed-threshold vertical margin; near-best tolerance1e-6 of75uA=75pA. It centers only that near-best plateau, not the full horizontal zero-error interval.','interpretation':'A lower rate can improve vertical margin yet the selected phase can lie near the right edge of the zero-error interval, failing normalized timing margin. This is the frozen TX+proxy+sampler comparison result, not proof that the circuit has a conventional low-frequency bandwidth failure or that a modified receiver passes.','rows':rows}
r.emit(r.EVIDENCE/'sampler-diagnostic.json',report);print(json.dumps(report,ensure_ascii=False))
