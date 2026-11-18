"""Reconcile per-capacitor stored energy against each run's actual CFF, independently of source-port E+."""
from pathlib import Path
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[2]
TAG='driver-ab-20261118'
def main():
    rows=[]
    for lane in ['b','b_review','b_final']:
        for p in sorted((ROOT/'build'/TAG/lane).rglob('result.json')):
            r=json.loads(p.read_text())
            if not r.get('frames'):continue
            inputs=p.parent.parent/'inputs/route_b.spice'
            route=inputs.read_text()
            cap=float(re.search(r'^CFF GB OUT ([0-9.]+)f$',route,re.M)[1])*1e-15
            for f in r['frames']:
                old=f['explicit_storage_caps']['CFF']
                stored=lambda v:.5*cap*v*v*1e12
                correct=stored(old['final_V'])-stored(old['initial_V'])
                if abs(old['C_F']-cap)>1e-27:
                    rows.append(dict(result=str(p.relative_to(ROOT)),frame=f['frame'],
                                    result_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),actual_C_F=cap,
                                    previous_C_F=old['C_F'],correct_delta_pJ=correct,
                                    original_delta_pJ=old['delta_pJ']))
    out=ROOT/'evidence'/TAG/'storage-ledger.json'
    out.write_text(json.dumps(dict(replacements=rows,scope='Per-frame diagnostic capacitor endpoint energy only. Authoritative positive/returned/net energy are integrated from seven original source-port traces; independent of the diagnostic ledger.'),indent=2)+'\n')
    print(len(rows),'endpoint energy adjustments')

if __name__=='__main__':main()
