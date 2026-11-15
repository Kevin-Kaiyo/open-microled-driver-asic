#!/usr/bin/env python3
"""Append missing case explanations; original per-case outputs remain byte-for-byte unchanged."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[3];E=ROOT/'evidence/driver-interface-20261115'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
s=json.loads((E/'micro-summary.json').read_text());dest=E/'micro-failures.json'
old=json.loads(dest.read_text());keep={r['case']:r for r in old}
explanations={
 ('A','baseline'):('off_current_failure','DISABLE has no actual optical-path switch; continued DATA still drives LED.','Add real high-side isolation and across-LED clamp.'),
 ('B','baseline'):('off_current_failure','Reference-bias clamp does not stop CFF edge injection.','Separate optical-path shutdown from reference generation and gate internal DATA while external input keeps toggling.'),
 ('A','protected_v2'):('transition_body_stress_failure','Release recharges CLED too rapidly; large displacement/package current with small simultaneous LED conduction current.','Limit actual high-side gate slew using 100 kohm and a finite-source controlled turn-off path.'),
 ('B','protected_v2'):('terminal_and_body_stress_failure','Release overshoot and negative excursions; continued off-state CFF injection; original metadata for two reference gates was corrected append-only.','Separate slew control, DATA gating, logic damping, and turn-off slew experiments; use corrected actual-deck native stress.'),
 ('A','protected_v3'):('incomplete_transient','ngspice exited zero after Timestep too small; output trace did not reach required end time.','Use an explicit 100 ohm protection source boundary, retain old trace, compare common prefix, then verify full duration and half step.'),
 ('B','protected_v3'):('body_stress_failure','Slow reconnection reduces positive release overshoot, but W20 fast-off boosts LED_A and continued CFF creates off-state negative body excursions.','Add real internal DATA allow delay; independently limit turn-off gate slew.'),
 ('B','protected_v4'):('logic_and_body_stress_failure','New NAND output overshoots from input-edge coupling; PISO turn-off boost remains. NAND intermediate node is not the violating node.','Add two-square PDK poly only before new logic DATA gates; preserve original core XRIN.'),
 ('B','protected_v5'):('diagnostic_body_stress_failure','One-frame diagnostic proves logic damping fixes logic stress; W20 high-side turn-off body boost remains. It has no complete post-recovery frame.','Reduce only fast-off PMOS W20 to W4, then rerun full matrix.'),
 ('B','protected_v6'):('incomplete_transient','ngspice exits zero but transient stops at 0.743243 us at vdisable#branch.','Add physical 100 ohm protection source resistance as distinct v6r; preserve all other candidate parameters and compare common prefix.')}
for row in s['rows']:
 if row['combined_research_screen_pass'] or row['source_case'] in keep:continue
 r=row.get('corrected_effective_result',row['result']);k=(row['route'],row['variant'])
 if k not in explanations:raise ValueError(k)
 typ,reason,fix=explanations[k]
 rec={'case':row['source_case'],'simulation_ok':r.get('simulation_ok',False),'failure_type':typ,'message':reason,'correction':fix,'result_sha256':row['result_sha256'],'manifest_sha256':row['manifest_sha256'],'deck_sha256':r.get('deck_sha256'),'log_sha256':r.get('log_sha256'),'waveform_gzip_sha256':row.get('waveform_gzip_sha256'),'body_forward_V':r.get('body_forward_V'),'terminal_pass':r.get('terminal_pass'),'body_pass':r.get('body_pass')}
 if row.get('correction'):rec['append_only_correction']=row['correction']['path']
 if row.get('completion_diagnostic'):rec['append_only_diagnostic']=row['completion_diagnostic']['path']
 keep[row['source_case']]=rec
out=list(keep.values());dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('failure/diagnostic records',len(out))
