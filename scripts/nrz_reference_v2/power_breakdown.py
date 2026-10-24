#!/usr/bin/env python3
"""Same six nominal DC conditions, additional read-only device current probes."""
from pathlib import Path
import datetime,fcntl,json,re,subprocess
import numpy as np
import run as r
import final_v2 as f
def main():
 top=r.BUILD/'power-dc-r2';assert not top.exists();top.mkdir();(top/'executed-power_breakdown.py').write_bytes(Path(__file__).read_bytes());contract=json.loads((f.WORK/'inputs/physical/integrated-contract.json').read_text());mapping={x['original_instance']:x for x in contract['extracted_device_mapping']}
 originals=['XR_IPBIAS','XR_IPTAIL','XR_IPLOAD','XR_IPREG','XR_IPOUT'];mos=[mapping[x]['extracted_instance'].lower() for x in originals];assert all(mapping[x]['drain_source_swapped'] for x in originals)
 cs=[c for c in f.plan('dc') if c['kind'] in ['DC_TT','DC_SS','DC_FF']];r.emit(top/'plan.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs,'source_sha256':r.sha(__file__),'purpose':'Additionalcurrentobservations atsame6nominalDCpoints; nochangeincircuitorOP','map':{a:b for a,b in zip(originals,mos)}});rows=[]
 for c in cs:
  folder=top/c['name'];folder.mkdir();base=r.build_deck(f.WORK,c)[0].split('.control')[0]
  expr=['v(vin)','v(dummy)','i(VRAW)','i(VSENSE)','i(VRSETMON)']+['@m.xdrv.'+x+'.m0[id]' for x in mos]
  deck=base+'.control\nset numdgt=15\nset wr_vecnames\nset wr_singlescale\nsave all\nop\nwrdata power.dat '+' '.join(expr)+'\nquit\n.endc\n.end\n';(folder/'testbench.spice').write_text(deck)
  with open('/tmp/open-microled-nrz-ngspice.lock','a') as lock,(folder/'ngspice.log').open('w') as log:
   fcntl.flock(lock,fcntl.LOCK_EX);p=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,stdout=log,stderr=subprocess.STDOUT,timeout=60)
  assert p.returncode==0;assert not re.search(r'(?im)^Error:',(folder/'ngspice.log').read_text());a=np.loadtxt(folder/'power.dat',skiprows=1);vin,dummy,raw,led,iset=a[1:6];curr=a[6:];idummy=(vin-dummy)/50000;closure=-raw-idummy-sum(curr)
  reference=json.loads((f.WORK/'cases'/c['name']/'analysis.json').read_text())['row'];difference=led-reference['LED_current_A'];assert abs(difference)<1e-12
  row={'name':c['name'],'bit':c['dc_bit'],'corner':c['corner'],'LED_current_A':float(led),'LED_difference_from_original_A':float(difference),'raw_source_current_A':float(-raw),'dummy_current_A':float(idummy),'OTA_control_current_A':float(sum(curr[:3])),'sense_reference_current_A':float(curr[3]),'output_reference_current_A':float(curr[4]),'DC_current_closure_residual_A':float(closure),'source5V_allocated_power_W':{'dummy':float(5*idummy),'OTA_control':float(5*sum(curr[:3])),'sense_reference':float(5*curr[3]),'output_reference':float(5*curr[4]),'closure':float(5*closure)},'instrumentation':'Modelm0draincurrent atactualVIN-side drain, mappingconfirmsD/Sswap; sameoriginalOP/LEDcurrentchecked','deck_sha256':r.sha(folder/'testbench.spice'),'raw_sha256':r.sha(folder/'power.dat'),'log_sha256':r.sha(folder/'ngspice.log')};r.emit(folder/'result.json',row);rows.append(row);print(json.dumps(row),flush=True)
 r.emit(r.EVIDENCE/'power-dc-r2.json',{'rows':rows,'plan_sha256':r.sha(top/'plan.json'),'scope':'DCsourcepowerallocation includescurrentfeedingbranches; notinternalheat orhighspeedtransientbranchenergy. Allrails+DATAtransientenergy remainsprimary. VIaggregate isexactRAWterminal minusexternalRDUMMY; modelm0channelcurrent bucketsleaveexplicitbody/leakage/modelportresidual.','retained_diagnostic':'power-dc-r1 assumedm0[id] channelsum equalscompleteRAIL to10nA; TTresidual25.57nA invalidatedthatmeasurementassumption,notcircuitOP. Originaldeck/raw/log/scriptpreserved; nofunctionalacceptancelimit changed.'})
if __name__=='__main__':main()
