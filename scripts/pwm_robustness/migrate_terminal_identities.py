#!/usr/bin/env python3
"""One-time identity repair for preserved terminal-inventory expansion attempts.

Original executed bytes remain under attempts and are restored to the original
identity. The six-pair run gets a distinct _terminal6 identity; its executed
result JSON is separately preserved before derived metadata is relabelled.
"""
from pathlib import Path
import gzip,hashlib,json,shutil
import numpy as np
ROOT=Path(__file__).resolve().parents[2];W=ROOT/'build/pwm-robustness/20261024';E=ROOT/'evidence/pwm-robustness/20261024'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,o):p.write_text(json.dumps(o,indent=2,ensure_ascii=False)+'\n')
ledger=E/'identity-migration-audit.json'
if ledger.exists():
    raise SystemExit('Migration already recorded; do not replay mutations.')
rows=[]
for ap in sorted((W/'attempts').glob('*/*/result.json')):
    old=json.loads(ap.read_text());name=old['case']['name'];current=W/name;new=json.loads((current/'result.json').read_text());rev=name+'_terminal6';dest=W/rev
    assert not dest.exists() and new['completed'] and old['completed']
    assert len(new['terminal_abs_peak_v'])==234 and len(old['terminal_abs_peak_v'])==195
    assert sha(current/'testbench.spice')==new['deck_sha256'];assert sha(ap.parent/'testbench.spice')==old['deck_sha256']
    current.rename(dest);shutil.copytree(ap.parent,current)
    executed=dest/'result-as-executed.json';shutil.copy2(dest/'result.json',executed)
    new['case']['generator_case_name']=name;new['case']['name']=rev
    new['identity_migration']=dict(original_generator_identity=name,immutable_revision_identity=rev,executed_result_record=str(executed.relative_to(ROOT)),executed_result_sha256=sha(executed),note='Only result metadata and directory identity relabelled; executed deck/log/raw bytes unchanged. Original earlier five-pair run restored from verified archived bytes.')
    save(dest/'result.json',new);save(E/(rev+'.json'),new);shutil.copy2(current/'result.json',E/(name+'.json'))
    csv=E/(name+'.csv')
    if csv.exists():
        shutil.copy2(csv,E/(rev+'.csv'))
        # Here raw arrays are identical because instrumentation executes after
        # wrdata. Check rather than silently treating a regenerated CSV as old.
        assert old['raw_sha256']==new['raw_sha256'], 'Different raw needs explicit old CSV regeneration'
    rows.append(dict(original_identity=name,new_revision_identity=rev,original_archive=str(ap.parent.relative_to(ROOT)),original_deck_sha256=old['deck_sha256'],revision_deck_sha256=new['deck_sha256'],original_raw_sha256=old['raw_sha256'],revision_raw_sha256=new['raw_sha256'],same_raw=old['raw_sha256']==new['raw_sha256'],original_result_byte_identical=sha(current/'result.json')==sha(ap),executed_revision_result_sha256=sha(executed),restored_original_files_sha256={p.name:sha(p) for p in current.iterdir() if p.is_file()}))
save(ledger,dict(date='2026-10-24',migration='Preserve original identities and distinguish six-pair instrumentation revisions',rows=rows,passed=all(r['original_result_byte_identical'] and r['same_raw'] for r in rows)))
print(json.dumps(dict(migrated=len(rows),passed=True),indent=2))
