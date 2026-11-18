"""Verify six complete B frames from native data, including failing versions."""
import argparse
import json
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'b_review'))
import check
ROOT=HERE.parents[1]
STAGE=ROOT/'build/driver-ab-20261118/b_final'
OUT=ROOT/'evidence/driver-ab-20261118/b_final'
MATRIX=[(name,case) for name in ('unit6-r260','unit6-r260-ff36','unit6-r260-n4ff36')
        for case in ('tt-normal1-s40','ss_hot_low-full-s40','ff_cold_high-full-s40')]+[('unit6-r260-n4ff36','ss_hot_low-full-s80')]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wait',action='store_true')
    args=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    pending=MATRIX.copy()
    deadline=time.monotonic()+5400
    while pending:
        for name,case in pending.copy():
            folder=STAGE/name/case
            result=folder/'result.json'
            if not result.is_file():continue
            out=OUT/f'{name}-{case}.json'
            if not out.is_file() or json.loads(out.read_text())['result_sha256']!=check.digest(result):
                audit=check.review(folder)
                out.write_text(json.dumps(audit,indent=2)+'\n')
                print(name,case,flush=True)
            pending.remove((name,case))
        if pending:
            if not args.wait or time.monotonic()>deadline:raise RuntimeError(f'Pending {pending}')
            time.sleep(10)

if __name__=='__main__':main()
