"""Independent common-top runner in the project's frozen GF180D environment."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
IMAGE='ghcr.io/librelane/librelane@sha256:f91b21d75f79871f9ccf37451020b5d2f7b3236881a997ff709c561e8280a30f'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['magic','lvs','klayout']);p.add_argument('--run',default='r1');p.add_argument('--allow-invalid',action='store_true');a=p.parse_args()
 out=ROOT/'build/integration'/a.run;out.mkdir(parents=True,exist_ok=True)
 pdk=ROOT/'build/layout/pdk'
 for name,want in json.loads((ROOT/'scripts/physical/pdk-lock.json').read_text())['files'].items():
  if sha(pdk/'gf180mcuD'/name)!=want:raise RuntimeError('PDK hash differs '+name)
 env=dict(os.environ,LIMA_HOME=str(ROOT/'build/physical-flow/lima'))
 base=['limactl','shell','asic','nerdctl','run','--rm','-v',f'{ROOT}:{ROOT}','-w',str(out),'-e','QT_QPA_PLATFORM=offscreen','-e',f'PYTHONPATH={ROOT}/build/physical-flow/linux-python','-e',f'PDK_ROOT={pdk}','-e',f'INTEGRATION_ROOT={ROOT}','-e',f'INTEGRATION_RUN={out}','-e',f'INTEGRATION_GDS={out}/pixel_integrated.gds',IMAGE]
 if a.mode=='magic':cmd=['magic','-dnull','-noconsole','-rcfile',str(pdk/'gf180mcuD/libs.tech/magic/gf180mcuD.magicrc'),str(out/'extract.tcl')]
 elif a.mode=='lvs':cmd=['netgen','-batch','source',str(ROOT/'scripts/integration/lvs.tcl')]
 else:
  deck=pdk/'gf180mcuD/libs.tech/klayout/tech/drc/run_drc.py'
  cmd=['python3',str(deck),f'--path={out}/pixel_integrated.gds','--variant=D','--topcell=pixel_integrated','--mp=1','--thr=4',f'--run_dir={out}/klayout']
 log=out/(a.mode+'-linux.log')
 used=[Path(__file__),out/'routing.json',out/'pixel_integrated.gds']
 if a.mode=='magic':used += [out/'extract.tcl',pdk/'gf180mcuD/libs.tech/magic/gf180mcuD.magicrc',pdk/'gf180mcuD/libs.tech/magic/gf180mcuD.tech']
 elif a.mode=='lvs':used += [ROOT/'scripts/integration/lvs.tcl',out/'pixel_integrated.spice',ROOT/'layout/integration/pixel_integrated.v',ROOT/'layout/pixel_driver_schematic.spice',ROOT/'evidence/physical/digital/pnl/pixel_pwm.pnl.v',pdk/'gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice',pdk/'gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl']
 else:used += [deck,deck.parent/'gf180mcu.drc']
 used_hashes={str(f.relative_to(ROOT)):sha(f)for f in used}
 with log.open('w')as f:ret=subprocess.run(base+cmd,env=env,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
 log.with_suffix('.command.json').write_text(json.dumps(dict(argv=base+cmd,exit_code=ret.returncode,image=IMAGE,source_sha256=used_hashes,inputs_sha256=json.loads((out/'routing.json').read_text())['inputs_sha256']),indent=2)+'\n')
 if ret.returncode:raise RuntimeError(f'exit={ret.returncode}: {log}')
 if a.mode=='magic':
  body=log.read_text();counts=re.findall(r'^INTEGRATION_DRC_COUNT (\d+)$',body,re.M)
  result=dict(drc_count=int(counts[0])if len(counts)==1 else None,style='drc(full)',passed=counts==['0'] and 'DRC style is now \"drc(full)\"'in body)
 elif a.mode=='lvs':
  body=(out/'netgen-lvs.log').read_text();finals=re.findall(r'^Final result:\s*(.+)$',body,re.M)
  errors=bool(re.search(r'property errors|do not match|not equivalent',body,re.I))
  result=dict(final_results=finals,property_or_connectivity_errors=errors,passed=finals==['Circuits match uniquely.']and not errors)
 else:
  xml=out/'klayout/pixel_integrated_main.lyrdb';doc=ET.parse(xml);result=dict(item_count=len(doc.findall('.//item')),category_count=len(doc.findall('.//category')),passed=len(doc.findall('.//item'))==0)
 result['tool_exit_code']=ret.returncode
 (out/(a.mode+'-result.json')).write_text(json.dumps(result,indent=2)+'\n')
 if not result['passed'] and not a.allow_invalid:raise RuntimeError(f'Semantic {a.mode} verification rejected: {log}')
 print(log)
if __name__=='__main__':main()
