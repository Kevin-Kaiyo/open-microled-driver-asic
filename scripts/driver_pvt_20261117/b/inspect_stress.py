#!/usr/bin/env python3
from pathlib import Path
import argparse,gzip,hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
p=argparse.ArgumentParser();p.add_argument('case');arg=p.parse_args();f=ROOT/arg.case;r=json.loads((f/'result.json').read_text());m=json.loads((f/'manifest.json').read_text());a=np.loadtxt(gzip.open(f/'waveform.dat.gz','rt'),skiprows=1,ndmin=2);ix=m['vectors'];v=lambda n:np.zeros(len(a)) if n=='0' else a[:,ix[n]];rows=[]
for d in r['stress']:
 if d['terminal_pass'] and d['body_pass']:continue
 pairs=[]
 for i in range(4):
  for j in range(i+1,4):
   dv=v(d['nodes'][i])-v(d['nodes'][j]);k=int(np.argmax(abs(dv)));pairs.append((float(abs(dv[k])),float(dv[k]),k,i,j))
 peak,signed,k,i,j=max(pairs)
 nodes=['d0','data_gate','nand_o','nand_s','data_safe','iso_g','iso_p','led_a','led_k','out','disable','vdd']
 rows.append({'device':d['instance'],'pair_nodes':[d['nodes'][i],d['nodes'][j]],'signed_voltage_V':signed,'absolute_V':peak,'time_s':float(a[k,0]),'time_from_diagnostic_command_ns':float((a[k,0]-m.get('diagnostic',{}).get('edge_s',0))*1e9),'nodes_V':{n:float(v(n)[k]) for n in nodes}})
out={'source_case':arg.case,'result_sha256':sha(f/'result.json'),'raw_sha256':r['raw_sha256'],'generator_sha256':sha(Path(__file__)),'failures':rows};(f/'stress-positions.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2))
