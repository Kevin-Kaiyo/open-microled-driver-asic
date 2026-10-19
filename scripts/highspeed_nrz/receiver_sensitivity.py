#!/usr/bin/env python3
"""Independent assumed-optical/Rx sensitivity, reusing identical electrical traces."""
from pathlib import Path
import argparse,hashlib,json,math
from analyze import load_trace
from metrics import receiver_proxy,train_sampler,evaluate_validation
ROOT=Path(__file__).resolve().parents[2]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--work',required=True);a=ap.parse_args();work=ROOT/a.work;st=json.loads((work/'stimulus.json').read_text());rows=[];sources=[]
 for route in 'AB':
  p=work/'cases'/f'{route}-nominal-1G-typical-27C-3.3V-C200-L0.5-e20-s40'/'result.json';r=json.loads(p.read_text());x,source=load_trace(r,p);sources.append(source);v=r['vectors'];ui=1e-9
  for tau in [50e-12,200e-12,1e-9]:
   for bw in [.5e9,1e9,2e9]:
    rx=receiver_proxy(x[:,0],x[:,v['iled_cond']],tau,bw)['receiver_proxy_A'];sam=train_sampler(x[:,0],rx,st['training_bits'][:-5],32*ui,ui,max_delay_ui=4);out=evaluate_validation(x[:,0],rx,st['validation_bits'],286*ui,ui,sam)
    rows.append({'route':route,'rate_Gbps':1,'tau_opt_ps':tau*1e12,'rx_GHz':bw/1e9,'errors':out['deterministic_errors'],'threshold_margin_normalized':out['threshold_margin_normalized'],'eye_normalized':out['eye_opening_normalized'],'timing_min_margin_ui':out['timing_min_margin_ui'],'comparison_screen_passed':out['deterministic_errors']==0 and out['threshold_margin_normalized']>=.1 and out['timing_min_margin_ui']>=.1})
 out={'scope':'Behavioral assumption sensitivity on SAME saved transistor traces; not new measured LED data, no physical BER; each condition has common A/B optical and Rx assumptions. Independent tau/C sweep does not assert physically independent device parameters.','work':a.work,'source_electrical_traces':sources,'rows':rows,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 (ROOT/'evidence/highspeed-nrz/receiver-sensitivity.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
