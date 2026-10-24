#!/usr/bin/env python3
"""Locate the existing restart forward junction event; no new simulation."""
import json
import numpy as np
import run as r
import final_v2 as f
def intervals(t,y,threshold):
 segments=[]
 for k in range(len(t)-1):
  a,b=float(t[k]),float(t[k+1]);u,v=float(y[k]),float(y[k+1])
  if u>threshold and v>threshold:segments.append((a,b))
  elif (u>threshold)!=(v>threshold):
   cross=a+(threshold-u)*(b-a)/(v-u);segments.append((a,cross) if u>threshold else (cross,b))
 merged=[]
 for lo,hi in segments:
  if merged and lo<=merged[-1][1]+1e-18:merged[-1][1]=hi
  else:merged.append([lo,hi])
 return {'threshold_V':threshold,'total_duration_s':sum(hi-lo for lo,hi in merged),'intervals_s':merged,'meaning':'Descriptive threshold only, not a new foundry acceptance limit'}
def main():
 p=next((f.WORK/'cases').glob('*restart*/result.json'));q=json.loads(p.read_text());r.module(f.WORK/'inputs/legacy/metrics.py','metrics');a=r.module(f.WORK/'inputs/legacy/analyze.py','body_review');a.ROOT=r.ROOT;tr,_=a.load_trace(q,p);t=tr[:,0];vec=q['vectors'];dev=next(d for d in q['devices'] if d['instance']=='x7');d,g,s,b=dev['nodes'];diff=tr[:,vec[s]]-tr[:,vec[b]];k=int(np.argmax(diff));mapping=json.loads((f.WORK/'inputs/physical/integrated-contract.json').read_text());physical=next(x for x in mapping['extracted_device_mapping'] if x['extracted_instance']=='X7')
 signal={'SPICE_S_IN2_V':tr[:,vec[s]],'BODY_VIN_V':tr[:,vec[b]],'forward_diff_V':diff,'RAW_source_V':tr[:,vec['vraw_voltage']],'VIN_port_V':tr[:,vec['vin_die_voltage']],'ILED_cond_A':tr[:,vec['iled_cond']],'ISET_A':tr[:,vec['iset_current']],'VREF_source_V':tr[:,vec['vref_voltage']],'DISABLE_source_V':tr[:,vec['vdisable_voltage']]};sel=(t>=19e-6)&(t<=25e-6);out=r.EVIDENCE/'final-tables';out.mkdir(exist_ok=True);csv=out/'restart-body-event.csv';np.savetxt(csv,np.column_stack([t[sel]]+[x[sel] for x in signal.values()]),delimiter=',',header=','.join(['time_s']+list(signal)),comments='')
 record={'result_json':r.rel(p),'result_sha256':r.sha(p),'waveform_sha256':q['waveform_sha256'],'case':q['case'],'device':dev,'physical_mapping':physical,'peak':{'time_s':float(t[k]),'forward_voltage_V':float(diff[k]),**{key:float(value[k]) for key,value in signal.items()}},'descriptive_durations':[intervals(t,diff,x) for x in [0,.3,.6,.7]],'csv':r.rel(csv),'csv_sha256':r.sha(csv),'script_sha256':r.sha(__file__),'interpretation':'SPICE S=IN2.t1 is originalXR_IPD2 drain after documentedD/Sswap; B=VIN.t6 nwell. IN2external150pF storescharge asRAWfalls; eventconsistentwithjunctionforwardconduction. Existingwaveforms containterminalvoltages, notjunctioncurrent: noquantifiedinjectioncharge/latchup/SOAqualification. Originalstartupboolonlyfunctional+absolutesixpairs, notrestartqualification.'};r.emit(r.EVIDENCE/'restart-body-review.json',record);print(json.dumps(record['peak'],indent=2));print(json.dumps(record['descriptive_durations'],indent=2))
if __name__=='__main__':main()
