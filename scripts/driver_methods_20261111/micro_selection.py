#!/usr/bin/env python3
"""Separate development-grid limits from step/holdout-qualified operating points."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'evidence/driver-methods-20261111'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def emit(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
    source=OUT/'micro-summary.json';data=json.loads(source.read_text());rows=data['records'];selection=[]
    def slim(r):
        if r is None:return None
        f=r['full_receiver']
        return dict(rate_Gbps=r['case']['net_rate_Gbps'],steps=r['case']['steps_per_symbol'],joint_pass=r['pass_screen'],errors=f['errors'],train_errors=f['train_errors'],amplitude_uAeq=f['worst_signed_margin_uAeq'],timing_ps=f['one_sided_margin_ps'],timing_UI=f['one_sided_margin_bit_UI'],energy_pJ=r['energy_pJ'],result=r['result'],result_sha256=r['result_sha256'])
    for name,old in [('A_rcff31p275','a-rin1wide-core03-matched'),('B_vin3p3_dummy27p6k','B_wide_ff31p275')]:
        own=[r for r in rows if r['candidate']==name]
        nominal=sorted([r for r in own if r['kind']=='transient' and r['case']['steps_per_symbol']==40],key=lambda r:r['case']['net_rate_Gbps'])
        passed=[r for r in nominal if r['pass_screen']]
        highest=passed[-1] if passed else None
        failures=[r for r in nominal if highest and r['case']['net_rate_Gbps']>highest['case']['net_rate_Gbps'] and not r['pass_screen']]
        holdouts=sorted([r for r in rows if r['candidate']==name+'-holdout4c2d' and r['kind']=='transient'],key=lambda r:r['case']['net_rate_Gbps'])
        fine=[r for r in own if r['kind']=='transient' and r['case']['steps_per_symbol']==80]
        fully=[]
        for r in passed:
            rate=r['case']['net_rate_Gbps']
            if any(x['case']['net_rate_Gbps']==rate and x['pass_screen'] for x in fine) and any(x['case']['net_rate_Gbps']==rate and x['pass_screen'] for x in holdouts):fully.append(r)
        baseline=sorted([r for r in rows if r['candidate']==old and r['kind']=='transient' and r['case']['steps_per_symbol']==40 and r['pass_screen']],key=lambda r:r['case']['net_rate_Gbps'])
        selection.append(dict(candidate=name,DC_all_pass=all(x['pass_screen'] for x in own if x['kind']=='dc') and len([x for x in own if x['kind']=='dc'])==2,
             highest_development_grid_pass=slim(highest),next_development_grid_failure=slim(failures[0] if failures else None),
             S80=[slim(x) for x in fine],holdouts=[slim(x) for x in holdouts],
             highest_with_DC_S80_and_holdout_pass=slim(fully[-1] if fully else None),
             previous_candidate_highest_development_grid_pass=slim(baseline[-1] if baseline else None),
             target_3p2=slim(next((x for x in nominal if x['case']['net_rate_Gbps']==3.2),None))))
    emit(OUT/'micro-selection.json',dict(schema='micro-methods-working-point-selection-v1',summary_sha256=sha(source),source_script_sha256=sha(Path(__file__)),candidates=selection,
          interpretation='Sampled TT nominal schematic limits, not continuous fmax, physical BER, PVT/PEX or measured optical capacity. S80 and nonoverlapping deterministic PRBS15 window qualify only the listed operating point under this contract.',
          holdout_policy='Circuit and parameters frozen before the new sequence. If selected-rate holdout fails, preserve it and test a predefined lower rate without retuning. Highest nominal pass and highest holdout-qualified point remain separate.',
          no_global_winner='At common 1.6 Gb/s compare energy, timing/amplitude margins and peak current; low-voltage B trades maximum tested speed for energy. Retain prior 5V B when its higher-rate operating point is needed.'))

if __name__=='__main__':main()
