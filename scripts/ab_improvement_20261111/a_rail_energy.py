#!/usr/bin/env python3
"""Approximate shunt-rail storage drift from saved native VH/VL endpoints.

Actual capacitor nodes HC/LC were not exported. VH/VL are separated from those
nodes by0.2ohm ESR, so this is a labeled approximation, not full energy balance.
"""
from pathlib import Path
import hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/ab-improvement-20261111'
OUT=ROOT/'evidence/ab-improvement-20261111/a-rail-energy-audit.json'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
records=[]
for name in ['a-base','a-rin1wide-core03-matched']:
 p=BUILD/name/'cases/TT-net1.6-C200-S40';r=json.loads((p/'result.json').read_text());v=r['metadata']['vectors'];wave=p/'waveform.dat.gz';assert sha(wave)==r['gzip_sha256']
 a=np.loadtxt(wave,skiprows=1,usecols=(0,v['xdrv.vh'],v['xdrv.vl']));rails={}
 for i,label in [(1,'VH'),(2,'VL')]:
  vv=a[:,i];rails[label]={'first_V':float(vv[0]),'last_V':float(vv[-1]),'drift_mV':float((vv[-1]-vv[0])*1e3),'minimum_V':float(vv.min()),'maximum_V':float(vv.max()),'delta_energy_pJ_approx':float(.5*10e-9*(vv[-1]**2-vv[0]**2)*1e12)}
 total=sum(x['delta_energy_pJ_approx'] for x in rails.values());energy=r['metrics']['total_energy']
 records.append({'candidate':name,'rate_Gbps':1.6,'frame_duration_s':float(a[-1,0]),'rails':rails,'total_delta_rail_storage_pJ_approx':total,'equivalent_delta_storage_pJ_per_payload_bit_approx':total/4096,'source_frame_positive_pJ':energy['positive_J']*1e12,'source_frame_net_pJ':energy['net_J']*1e12,'source_result':str((p/'result.json').relative_to(ROOT)),'source_result_sha256':sha(p/'result.json'),'waveform_raw_sha256':r['raw_sha256'],'waveform_gzip_sha256':r['gzip_sha256']})
dsource=records[1]['source_frame_positive_pJ']-records[0]['source_frame_positive_pJ'];dstore=records[1]['total_delta_rail_storage_pJ_approx']-records[0]['total_delta_rail_storage_pJ_approx']
result={'schema':'A-rail-energy-drift-audit-v1','approximation':{'expression':'deltaE=0.5*10nF*((VHend^2-VHstart^2)+(VLend^2-VLstart^2))','actual_capacitor_nodes':'HC and LC, behind0.2ohm ESR; they were not exported, so onlyVH/VL proxies are used. Error bound not established.','sign':'positive means net charging; negative means release of initially stored rail energy.','initial_condition':'Each frame starts at the DC operating point of the first data bit, not independently established periodic communication steady state.','excluded':'Energy of other C/L, MOS stored charge, ESR losses, and exact internalcapnodes; this is not totalenergybalance or corrected wall-plug energy.'},'records':records,'comparison':{'selected_minus_baseline_source_positive_pJ':dsource,'selected_minus_baseline_rail_storage_pJ_approx':dstore,'absolute_storage_difference_over_source_energy_difference':abs(dstore/dsource)},'script_path':str(Path(__file__).relative_to(ROOT)),'script_sha256':sha(Path(__file__))}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
