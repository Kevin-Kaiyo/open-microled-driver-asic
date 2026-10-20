#!/usr/bin/env python3
"""Reproduce the six RC ground-capacitance-placement controls."""
from pathlib import Path
import argparse
import shutil
from run import ROOT, sha, rel, emit, case_spec, run_case


def placement(work, timeout=240):
    digest=sha(Path(__file__))
    source=work/'execution-sources'/f'{digest}.py'
    source.parent.mkdir(parents=True,exist_ok=True)
    if not source.exists():shutil.copy2(Path(__file__),source)
    cases=[case_spec(work,r,'RCLUMP',f,kind='cap_placement_control') for r in 'AB' for f in [.5,1,2]]
    emit(work/'planned-cap-placement.json',{'cases':cases,'helper_source':rel(source),'helper_sha256':digest,
        'scope':'ground-C placement sensitivity only; both decks place coupling C at logical nodes'})
    results=[]
    for case in cases:
        result=run_case(work,case,timeout);results.append(result)
        print(case['name'], 'OK' if result['simulation_ok'] else result.get('error','FAILED'),flush=True)
    emit(work/'run-cap-placement.json',{'cases':results,'helper_source':rel(source),'helper_sha256':digest})
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--work',required=True);parser.add_argument('--timeout',type=float,default=240)
    args=parser.parse_args();placement((ROOT/args.work).resolve(),args.timeout)
