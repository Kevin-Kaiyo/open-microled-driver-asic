#!/usr/bin/env python3
"""Compact CSVs and same-condition historical comparison, no simulation."""
from pathlib import Path
import csv,json
import run as r
import final_v2 as f
def write_csv(path,rows,columns):
 with path.open('w',newline='') as out:
  writer=csv.DictWriter(out,columns,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
def main():
 source=f.WORK/'summary-verified.json';j=json.loads(source.read_text());out=r.EVIDENCE/'final-tables';out.mkdir(exist_ok=True);rows=j['rows']
 cols=['name','stage','corner','temp_C','vdd_V','dc_bit','LED_current_A','LED_current_error_percent','current_target_passed','errors','validation_bits','threshold_margin_normalized','timing_min_margin_ui','rail_plus_DATA_positive_draw_fJ_per_gross_bit','rail_plus_DATA_net_fJ_per_gross_bit','minimum_device_specific_margin_V','minimum_device_margin_V','device_specific_screen_passed','device_screen_passed','startup_passed','slow_passed','current_peak_A','hold_peak_A','hold_mean_A','release_to_settled_s','result_json','analysis_json']
 write_csv(out/'final-cases.csv',rows,cols)
 oldsum=r.ROOT/'build/highspeed-nrz-robustness/selected-a8-b58-r4/summary.json';old=json.loads(oldsum.read_text())['rows'];comparisons=[]
 for label,oldkind in [('TT','TT'),('SS','SSminus50'),('FF','FFplus50')]:
  prior=next(x for x in old if x['route']=='B' and x['kind']==oldkind and x['rate_Gbps']==.5 and x.get('variant')=='AFTER')
  new=next(x for x in rows if x['stage']=='nrz' and x['kind']=='NRZ_'+label)
  for design,x in [('old_ideal_VDUMMY_RREF',prior),('selected_21MOS_reference',new)]:comparisons.append({'PVT':label,'design':design,'positive_pJ_per_bit':x['rail_plus_DATA_positive_draw_fJ_per_gross_bit']/1000,'net_pJ_per_bit':(x['rail_net_fJ_per_gross_bit']+x['ideal_DATA_net_fJ_per_gross_bit'])/1000,'errors':x['errors'],'validation_bits':x['validation_bits'],'threshold_margin':x['threshold_margin_normalized'],'timing_margin_UI':x['timing_min_margin_ui'],'analysis_json':x['analysis_json'],'analysis_sha256':r.sha(r.ROOT/x['analysis_json'])})
 write_csv(out/'nominal-energy-comparison.csv',comparisons,list(comparisons[0]))
 dc=[]
 for label in ['TT','SS','FF']:
  for bit in [0,1]:
   op=next(p for p in (r.BUILD/'selected-r1/cases').glob('BASELINE*/analysis.json') if (lambda x:x['kind']=='old_'+label and x['dc_bit']==bit)(json.loads(p.read_text())['row']))
   oldrow=json.loads(op.read_text())['row'];newrow=next(x for x in rows if x['stage']=='dc' and x['kind']=='DC_'+label and x['dc_bit']==bit)
   for design,x,p in [('old_ideal_VDUMMY_RREF',oldrow,op),('selected_21MOS_reference',newrow,r.ROOT/newrow['analysis_json'])]:dc.append({'PVT':label,'bit':bit,'design':design,'current_uA':x['LED_current_A']*1e6,'target_error_percent':x['LED_current_error_percent'],'analysis_json':r.rel(p),'analysis_sha256':r.sha(p)})
 write_csv(out/'nominal-DC-comparison.csv',dc,list(dc[0]));rails=[]
 for x in rows:
  if x['stage']!='nrz':continue
  a=json.loads((r.ROOT/x['analysis_json']).read_text());en=a['transient']['energy']
  for name,part in (en['rails']|{'DATA':en['ideal_DATA']}).items():rails.append({'case':x['name'],'source':name,'positive_pJ_per_bit':part['positive_draw_J_per_gross_bit']*1e12,'returned_pJ_per_bit':part['returned_J_per_gross_bit']*1e12,'net_pJ_per_bit':part['net_J_per_gross_bit']*1e12,'net_mean_W':part['net_mean_W']})
 write_csv(out/'nrz-source-energy.csv',rails,list(rails[0]))
 r.emit(out/'sources.json',{'summary_sha256':r.sha(source),'historical_summary_sha256':r.sha(oldsum),'script_sha256':r.sha(__file__),'csvs':{p.name:r.sha(p) for p in out.glob('*.csv')},'scope':'Same0.5G nominalPVT/LED/RX/DATA conditions; powerarchitecturechanged asdeclared. DynamicRAWpulse100nFcharging energy isseparatefromnominalcommunicationenergy. ExternalanchorinternalIq notincludedinSPICE.'})
 print(json.dumps({'tables':r.rel(out),'nominal_energy':comparisons},indent=2))
if __name__=='__main__':main()
