#!/usr/bin/env python3
"""Bounded proof that the affected assert cases have identical decks and scoring code."""
from pathlib import Path
import ast,difflib,hashlib,json,types
ROOT=Path(__file__).resolve().parents[3];B=ROOT/'build/driver-pvt-20261117/b';E=ROOT/'evidence/driver-pvt-20261117/b'
p1=B/'clamp5v_buffer/tt-assert-s40/execution-source.py';p2=B/'clamp5v_buffer/tt_high-assert-s40/execution-source.py';a=p1.read_text();b=p2.read_text()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fn(s,n):return ast.dump(next(v for v in ast.parse(s).body if isinstance(v,ast.FunctionDef) and v.name==n),include_attributes=False)
assert fn(a,'diagnostic')==fn(b,'diagnostic');assert fn(a,'pwl_window')==fn(b,'pwl_window')
modules=[]
for label,source in [('loaded',a),('later_snapshot',b)]:
 m=types.ModuleType(label);m.__file__=str(ROOT/'scripts/driver_pvt_20261117/b/run.py');exec(compile(source,m.__file__,'exec'),m.__dict__);m.BUILD=B/'source-equivalence'/label;modules.append(m)
rows=[]
for grid in ['tt_high','ss_hot_low','sf_hot_low','fs_cold_high']:
 folders=[m.prepare('clamp5v_buffer',grid,'assert')[0] for m in modules]
 hashes=[sha(f/'testbench.spice') for f in folders];assert len(set(hashes))==1
 original=B/f'clamp5v_buffer/{grid}-assert-s40/testbench.spice';assert hashes[0]==sha(original)
 rows.append({'grid':grid,'decks_identical':True,'deck_sha256':hashes[0],'original_case':str(original.parent.relative_to(ROOT))})
(E/'source-equivalence.diff').write_text(''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='actual-loaded-source',tofile='later-disk-snapshot')))
r={'schema':'b-assert-source-equivalence-v1','actual_source_sha256':sha(p1),'later_snapshot_sha256':sha(p2),'assert_diagnostic_AST_identical':True,'PWL_crop_AST_identical':True,'regenerated_decks':rows,'prior_analyzer_sha256':sha(ROOT/'scripts/driver_interface_20261115/micro/run.py'),'generator_sha256':sha(Path(__file__)),'scope':'Proves affected assert-mode decks and numerical scoring are identical. Normal1/full-only analysis additions and optional preview SHA metadata are not claimed equivalent for all modes. Original files remain unchanged.'};(E/'source-equivalence.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('4 original decks reproduced byte-for-byte; diagnostic/PWL AST equal')
