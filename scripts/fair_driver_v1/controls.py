#!/usr/bin/env python3
"""Selected, predeclared one-factor controls; not a Cartesian signoff matrix."""
import argparse,concurrent.futures,json
import run as e

def plan(parameters):
 out=[]
 for route in 'ABC':
  levels=range(4 if route=='C' else 2)
  for err in [-.002,.002]:
   for level in levels:out.append({'name':f'DC-{route}-VREF{err:+g}-L{level}','kind':'dc','route':route,'level':level,'reference_error':err,'control_factor':'VREF only +/-0.2%; ideal source tolerance, not IC noise/TC'})
  for err in [-.001,.001]:
   p={k:v*(1+err) for k,v in parameters[route].items() if k in (['RH','RL'] if route=='A' else ['RSET'])}
   for level in levels:out.append({'name':f'DC-{route}-Rtol{err:+g}-L{level}','kind':'dc','route':route,'level':level,'parameters':p,'control_factor':'A both divider-bottoms same fractional perturbation; B/C RSET only. Not full independent resistor combination/TC.'})
 for route in 'ABC':
  out.append({'name':f'RX-{route}-step80-0.5G','route':route,'net_rate_Gbps':.5,'steps_per_symbol':80,'control_factor':'native max-step per symbol40->80; no receiver or export downsampling'})
  out.append({'name':f'RX-{route}-RINresSS-0.25G','route':route,'net_rate_Gbps':.25,'res_corner':'ss','control_factor':'MOS typical/27C/3.3V held; PDK RIN res_ss only; external ideal resistors fixed'})
  out.append({'name':f'RX-{route}-VDDpulse50mV-0.25G','route':route,'net_rate_Gbps':.25,'pulse_rail':'VDD','pulse_V':.05,'control_factor':'source3.3->3.35V, start200ns, rise/fall2ns,width20ns,period800ns; same finite package and100nFESR decoupling'})
 for skew in [-20e-12,20e-12]:out.append({'name':f'RX-C-skew{skew*1e12:+g}ps-0.5G','route':'C','net_rate_Gbps':.5,'skew_s':skew,'control_factor':'D1 edge relative to D0 only; fixed20ps transition duration'})
 return [dict(c,timeout_s=900) for c in out]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--jobs',type=int,default=1);a=ap.parse_args();source=e.BUILD/'matched-r2';m=e.verify(source);w=e.BUILD/'controls-r1';e.init(w,m['parameters']);assert e.verify(w)['inputs']==m['inputs'];p=plan(m['parameters']);target=w/'plan.json'
 if target.exists():assert json.loads(target.read_text())==p
 else:e.emit(target,p)
 def go(c):
  r=w/'cases'/c['name']/'result.json';return json.loads(r.read_text()) if r.exists() else e.run(w,c)
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
  fs={pool.submit(go,c):c for c in p}
  for f in concurrent.futures.as_completed(fs):
   r=f.result();x=r.get('metrics',{});rx=x.get('receiver',{});print(json.dumps({'case':r['case']['name'],'ok':r['simulation_ok'],'seconds':r['elapsed_s'],'error':r.get('analysis_error'),'I_uA':x.get('i_led_A',0)*1e6,'DC_error_percent':x.get('current_error_percent'),'E_pJ':x.get('total_energy',{}).get('positive_pJ_per_payload_bit'),'RX':rx.get('checks'),'margin_uA':rx.get('validation',{}).get('decision_distance_min_uA'),'time_ps':rx.get('horizontal_margin',{}).get('min_ps')}),flush=True)
if __name__=='__main__':main()
