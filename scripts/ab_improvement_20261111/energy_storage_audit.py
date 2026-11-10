#!/usr/bin/env python3
"""Explicit capacitor stored-energy audit; not a complete energy balance."""
from pathlib import Path
import gzip,hashlib,json,re
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'evidence/ab-improvement-20261111'
CASES={'baseline':ROOT/'build/blue-emitter-speed-review-20261110/vcsel/net6.4-edge20-s40',
       'modified':ROOT/'build/ab-improvement-20261111/VCSEL/vc-atten50-steer20/net6.4-edge20-s40'}
CAPS=[('Lout',10e-9,'xdrv.lcap',None),('Dout',1e-9,'xdrv.dcap',None),('rawLaser',1e-9,'laser_c',None),('rawDriver',1e-9,'vdd_c',None),('Bcomp',5e-12,'xdrv.bn2','xdrv.bctrl'),('Tcomp',5e-12,'xdrv.tn2','xdrv.tctrl'),('Lcomp',30e-12,'xdrv.lzc','xdrv.lctrl'),('Dcomp',30e-12,'xdrv.dzc','xdrv.dctrl')]
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 rows={}
 for name,folder in CASES.items():
  m=json.loads((folder/'manifest.json').read_text());r=json.loads((folder/'result.json').read_text());wave=folder/'waveform.dat.gz'
  assert sha(wave)==r['waveform']['sha256']
  driver=(folder/'driver.spice').read_text().lower();deck=(folder/'testbench.spice').read_text().lower()
  for line in ['clout lcap vss 10n','cdout dcap vss 1n','clmiller lzc lctrl {cldo}','cdmiller dzc dctrl {cldo}','cbmiller bn2 bctrl {cc}','ctmiller tn2 tctrl {cc}']:assert line in driver
  assert 'claser laser_c 0 1n' in deck and 'cvdd vdd_c 0 1n' in deck
  inst=next(line for line in deck.splitlines() if line.startswith('xdrv '));values=dict(re.findall(r'(\w+)=([^ ]+)',inst));assert float(values['cc'])==5e-12 and float(values['cldo'])==30e-12
  with gzip.open(wave,'rb') as f:
   digest=hashlib.sha256();header=next(f);digest.update(header);first=next(f);digest.update(first);last=first
   for line in f:digest.update(line);last=line
  assert digest.hexdigest()==r['waveform']['raw_sha256']
  a=np.array([np.fromstring(first,sep=' '),np.fromstring(last,sep=' ')]);ix={e:k+1 for k,e in enumerate(m['expressions'])}
  caps={}
  for label,c,p,n in CAPS:
   v=a[:,ix['v('+p+')']]-(a[:,ix['v('+n+')']] if n else 0);e=.5*c*v*v
   caps[label]={'C_F':c,'positive_node':p,'negative_node':n or '0','initial_voltage_V':float(v[0]),'final_voltage_V':float(v[1]),'initial_J':float(e[0]),'final_J':float(e[1]),'delta_J':float(e[1]-e[0])}
  dU=sum(c['delta_J'] for c in caps.values());energy=r['total_energy']
  rows[name]={'source_case':str(folder.relative_to(ROOT)),'net_Gbps':6.4,'frame_s':float(a[-1,0]),'attempted_payload_bits':4096,'caps':caps,'explicit_cap_delta_J':dU,'source_positive_J':energy['positive_J'],'source_returned_J':energy['returned_J'],'source_net_J':energy['net_J'],
              'source_net_minus_explicit_delta_J':energy['net_J']-dU,'actual_eight_capacitor_connections_and_values_checked':True,'driver_sha256':sha(folder/'driver.spice'),'deck_sha256':sha(folder/'testbench.spice'),'result_sha256':sha(folder/'result.json'),'manifest_sha256':sha(folder/'manifest.json'),'waveform_gzip_sha256':sha(wave),'waveform_raw_sha256':digest.hexdigest()}
 b,n=rows['baseline'],rows['modified'];positive_saving=b['source_positive_J']-n['source_positive_J'];net_saving=b['source_net_J']-n['source_net_J'];delta_difference=n['explicit_cap_delta_J']-b['explicit_cap_delta_J']
 out={'schema':'vcsel-explicit-storage-audit-v1','method':'Same eight supply/compensation capacitors as original r10 runner. Native first/last voltages; U=0.5*C*V^2, delta=final-initial. Full native waveform hashes independently rechecked.',
      'cases':rows,'comparison':{'source_positive_saving_J':positive_saving,'source_net_saving_J':net_saving,'modified_minus_baseline_explicit_delta_J':delta_difference,'absolute_storage_difference_over_positive_saving':abs(delta_difference)/abs(positive_saving),
      'net_minus_explicit_storage_saving_J':(b['source_net_J']-b['explicit_cap_delta_J'])-(n['source_net_J']-n['explicit_cap_delta_J'])},
      'limits':['Only listed explicit supply and compensation capacitors. MOS intrinsic charge, VCSEL junction capacitor, package inductors and other storage are excluded.','Positive source energy is not net energy; capacitor correction uses signed net source energy. Do not present adjusted positive energy as complete dissipation.','A finite-frame difference is not steady-state efficiency. Full energy closure or repeated periodic/long-frame accounting is still needed.'],
      'script_sha256':sha(Path(__file__))}
 (EV/'energy-storage-audit.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({k:v for k,v in out['comparison'].items()},indent=2))
if __name__=='__main__':main()
