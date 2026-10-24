#!/usr/bin/env python3
"""Independent readback using one import-time frozen analyzer; retains previous analyses."""
import argparse,datetime,json
import validate as v
import run as r
p=argparse.ArgumentParser();p.add_argument('--work',required=True);a=p.parse_args();w=r.ROOT/a.work
v.verify(w);paths=sorted((w/'cases').glob('*/result.json'))
for path in paths:
 row=v.analyze(w,json.loads(path.read_text()),out_name='analysis-verified.json');print(row['name'],row['analysis_ok'],flush=True)
r.emit(w/'analysis-provenance-readback.json',{'at':datetime.datetime.now().isoformat(),'scope':'Independent retained-raw readback. Original analysis.json retained. Early scripts took file hash at per-case time while process could hold earlier imported implementation; this readback pins actual imported analyzer bytes. Numerical findings now derive from this recorded source.','analyzer_sha256':v.ANALYZER_SHA256,'case_count':len(paths),'all_original_results_retained':True})
v.summarize(w)
