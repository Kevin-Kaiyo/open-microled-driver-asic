#!/usr/bin/env python3
"""Append the actual module-load source for a known sequential batch; never alter original cases."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[3];B=ROOT/'build/driver-pvt-20261117/b/clamp5v_buffer'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
reference=B/'tt-assert-s40/execution-source.py';actual=reference.read_bytes();assert hashlib.sha256(actual).hexdigest().startswith('529aff8a7a0a43')
for grid in ['tt_high','ss_hot_low','sf_hot_low','fs_cold_high']:
 f=B/f'{grid}-assert-s40';m=json.loads((f/'manifest.json').read_text());assert m['execution_sha256'].startswith('2aa4ddef317bc0')
 q=f/'actual-execution-source.py';q.write_bytes(actual)
 d={'schema':'b-source-snapshot-correction-v1','scope':'Execution-source provenance only; netlist, waveform, original manifest and result unchanged.','reason':'Sequential all-grid process loaded run.py before a normal1-mode extension was edited on disk. The old prepare() copied the current file at each case creation, so later four case snapshots reflected disk text rather than already-loaded module. Correct actual source is the first TT case snapshot of the same process. All relevant assert calculations used that source. Future generator captures EXECUTION_SOURCE once at module load.','original_manifest_sha256':sha(f/'manifest.json'),'original_result_sha256':sha(f/'result.json'),'original_claimed_execution_sha256':m['execution_sha256'],'actual_execution_source':q.name,'actual_execution_sha256':sha(q),'same_process_first_case':str(reference.parent.relative_to(ROOT)),'correction_generator_sha256':sha(Path(__file__))};(f/'execution-provenance-correction.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 print(grid,d['actual_execution_sha256'])
