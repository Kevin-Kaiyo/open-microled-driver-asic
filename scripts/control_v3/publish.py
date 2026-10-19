from pathlib import Path
from run import ROOT,B,E,sha
import json,shutil,re
F=B/'physical/final';m=json.loads((F/'metrics.json').read_text());st=json.loads((E/'sta.json').read_text());sdf=json.loads((E/'sdf.json').read_text())
keys=['magic__drc_error__count','design__lvs_error__count','design__xor_difference__count','design__max_slew_violation__count','design__max_cap_violation__count','design__max_fanout_violation__count','timing__setup_vio__count','timing__hold_vio__count']
for k in keys:assert m[k]==0,(k,m[k])
assert st['passed'] and sdf['passed']
files=['gds/pixel_control_v3.gds','lef/pixel_control_v3.lef','nl/pixel_control_v3.nl.v','pnl/pixel_control_v3.pnl.v','sdc/pixel_control_v3.sdc','metrics.json']
for name in files:shutil.copyfile(F/name,E/Path(name).name)
# Keep compact raw STA and SDF reports; full implementation remains in build.
from pathlib import Path

logs=E/'logs';logs.mkdir(exist_ok=True)
for p in (B/'verification').glob('*.log'):shutil.copyfile(p,logs/p.name)
for p in (B/'sdf').glob('*/run.log'):shutil.copyfile(p,logs/(p.parent.name+'-sdf.log'))
metrics={k:m[k] for k in keys}
summary={'schema_version':1,'date':'2026-10-15','passed':True,'top':'pixel_control_v3','die_um':[200,200],
'rtl_cases':len(json.loads((E/'rtl.json').read_text())['cases']),'gate_cases':len(json.loads((E/'gate.json').read_text())['cases']),
'sdf_corners':9,'sdf_checks_per_corner':4108,'sdf_fault_monitor_off_ns':[min(c['fault_to_monitor_off_ns'] for c in sdf['corners']),max(c['fault_to_monitor_off_ns'] for c in sdf['corners'])],
'r2r_setup_min_ns':min(c['r2r_setup_min_ns'] for c in st['corners']),'r2r_hold_min_ns':min(c['r2r_hold_min_ns'] for c in st['corners']),
'metrics':metrics,'artifacts':{n:sha(F/n) for n in files},
'implemented_sources':{p.name:sha(p) for p in (B/'inputs').glob('*.v')},
'validation_sources':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'scripts/control_v3').glob('*') if p.is_file()},
'physical_scope':'Digital PWM and recovery macro with routed nets, 9-corner extracted STA and SDF. No pads, ESD or whole-chip power-up proof.',
'limitations':['KLayout DRC skipped by LibreLane; independent common-top KLayout planned separately.','Fault release recovery/removal STA uses 200 ns SDC input-arrival assumption. Arbitrary asynchronous release and metastability remain unresolved.','Icarus conditional XOR ModPath arcs and timing checks unsupported; static checks retained.','Power/IR estimates lack actual package source locations and are not signoff.','External fault must start asserted while safety supply is valid.','Output load72.91fF assumed; common-top intermacro RC not back-annotated into this STA.']}
(E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
