"""Safely characterize new top routing into a private run-specific directory.

The historical extract_link.py remains byte-frozen. This replacement stages
results under build/, never directly publishes or overwrites the v0.3 baseline.
"""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess
import klayout.db as k
ROOT=Path(__file__).resolve().parents[2]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def make_helper(run,out):
 data=json.loads((run/'routing.json').read_text());lay=k.Layout();lay.dbu=.001;cell=lay.create_cell('pwm_link_rc')
 levels={'Metal3':42,'Metal4':46,'Metal5':81,'Via3':40,'Via4':41}
 for route in data['routes']:
  if route['net']not in ['VDD','VSS','pwm_link']:continue
  rect=route['rect_um']
  if route['net']=='pwm_link':rect=[120,rect[1],150,rect[3]]
  cell.shapes(lay.layer(levels[route['layer']],0)).insert(k.DBox(*rect))
 lay.write(str(out/'pwm_link_only.gds'))
 script=['random seed 20261004','gds read $env(INTEGRATION_LINK_OUTPUT)/pwm_link_only.gds','load pwm_link_rc']
 for name,layer,box in [('A','metal3',[120,111.24,120.02,111.8]),('Y','metal3',[149.98,111.24,150,111.8]),('VDD','metal4',[139.65,116.5,140.35,117.52]),('VSS','metal5',[134.65,104.5,135.35,105.52])]:
  script+=['box values '+' '.join(f'{x}um'for x in box),f'label {name} center {layer}','port make']
 script+=['extract style ngspice()','extract do capacitance','extract do coupling','extresist threshold 0','extresist minres 0','extresist mindelay 0','extract do resistance','extract all','ext2spice lvs','ext2spice cthresh 0','ext2spice rthresh 0','ext2spice extresist on','ext2spice -o pwm_link_rc.spice','quit -noprompt']
 (out/'extract_link.tcl').write_text('\n'.join(script)+'\n')
def normalize(run,out):
 raw=(out/'pwm_link_rc.spice').read_text();full=(run/'pixel_integrated.spice').read_text();ext=(run/'pixel_integrated.ext').read_text()
 if not re.search(r'Xpixel_driver_layout_0 VSS bias gate pwm_monitor pwm_b led_k VDD pixel_driver_layout',full):raise RuntimeError('Analog full-top supply binding unconfirmed')
 parents={}
 def find(name):
  parents.setdefault(name,name)
  if parents[name]!=name:parents[name]=find(parents[name])
  return parents[name]
 for x,y in re.findall(r'^merge "([^"]+)" "([^"]+)"',ext,re.M):parents[find(x)]=find(y)
 if not find('VSUBS')==find('VSS')==find('pixel_driver_layout_0/VSS'):raise RuntimeError('Actual hierarchical substrate merge is not bound to VSS')
 proof=dict(passed=True,source=str((run/'pixel_integrated.ext').relative_to(ROOT)),basis='Actual full-top Magic hierarchical merge records',relevant_records=[line for line in ext.splitlines()if line.startswith('substrate ')or(line.startswith('merge ')and all(find(n)==find('VSS')for n in re.findall(r'"([^"]+)"',line)[:2]))],helper_substrate_records=[line for line in(out/'pwm_link_rc.ext').read_text().splitlines()if line.startswith('substrate ')])
 nodes=set(re.findall(r'\bw_\d+_\d+#',raw))
 if len(nodes)!=1 or not all(' pw 'in line for line in proof['helper_substrate_records']):raise RuntimeError('Expected one actual pw substrate boundary')
 text=raw
 for node in nodes:text=text.replace(node,'VSS')
 text='* Isolated new M3 span only; full-top pwell substrate boundary mapped to VSS.\n* Macro-internal RC excluded; VDD/VSS ideal in the downstream interface probe.\n'+text
 lines=[]
 for line in text.splitlines():
  cols=line.split()
  lines.append('* omitted self-cap after proven substrate mapping: '+line if cols and cols[0].startswith('C')and cols[1]==cols[2]else line)
 (out/'pwm_link_normalized.spice').write_text('\n'.join(lines)+'\n');(out/'substrate-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
 return nodes

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);p.add_argument('--output',type=Path);p.add_argument('--reuse-raw',type=Path,help='Validate/re-normalize frozen raw files without invoking Magic');a=p.parse_args()
 run=ROOT/'build/integration'/a.run;out=(a.output or run/'link-characterization').resolve()
 if not out.is_relative_to(ROOT/'build/integration'):raise RuntimeError('Output must be inside build/integration')
 if out==run.resolve()or(out.exists()and any(out.iterdir())):raise RuntimeError('Use a fresh private output directory; frozen inputs are never overwritten')
 for name in ['magic-result.json','lvs-result.json','klayout-result.json','geometry-connectivity.json']:
  if not json.loads((run/name).read_text())['passed']:raise RuntimeError('Baseline physical checks must pass first: '+name)
 out.mkdir(parents=True,exist_ok=True);magic=ROOT/'build/layout/tools/install/bin/magic';pdk=ROOT/'build/layout/pdk/gf180mcuD'
 for path,want in json.loads((ROOT/'scripts/physical/pdk-lock.json').read_text())['files'].items():
  if sha(pdk/path)!=want:raise RuntimeError('PDK lock mismatch '+path)
 reuse=None
 if a.reuse_raw:
  reuse=a.reuse_raw.resolve();record=json.loads((reuse/'link-rc.json').read_text())
  prior_gds=next(v for key,v in record['inputs_sha256'].items()if key.endswith('/pixel_integrated.gds'))
  if prior_gds!=sha(run/'pixel_integrated.gds'):raise RuntimeError('Frozen raw geometry does not match this full-top GDS')
  for name in ['pwm_link_only.gds','pwm_link_rc.spice','pwm_link_rc.ext','magic-link.log']:shutil.copyfile(reuse/name,out/name)
  if sha(out/'pwm_link_rc.spice')!=record['outputs_sha256']['pwm_link_rc.spice']:raise RuntimeError('Frozen raw netlist hash differs')
  tool_version=record['tool_version'];tool_hash=record['tool_binary_sha256'];invocation=dict(mode='frozen-raw verification and normalization; no Magic run',source_run=str(reuse.relative_to(ROOT)))
 else:
  make_helper(run,out)
  env=dict(os.environ,PDK_ROOT=str(pdk.parent),INTEGRATION_LINK_OUTPUT=str(out))
  argv=[str(magic),'-dnull','-noconsole','-rcfile',str(pdk/'libs.tech/magic/gf180mcuD.magicrc'),str(out/'extract_link.tcl')]
  ret=subprocess.run(argv,cwd=out,env=env,capture_output=True,text=True);(out/'magic-link.log').write_text(ret.stdout+ret.stderr)
  if ret.returncode or 'Nets extracted: 3 (0.600000)'not in ret.stdout+ret.stderr:raise RuntimeError('Actual metal-only extraction failed')
  tool_version=subprocess.check_output([str(magic),'--version'],text=True).strip();tool_hash=sha(magic);invocation=dict(mode='actual native Magic metal-only extraction',argv=argv,exit_code=ret.returncode,random_seed=20261004)
 nodes=normalize(run,out);raw=(out/'pwm_link_rc.spice').read_text()
 data=dict(evidence_level='Actual PDK Magic metal-only R/C extraction of the new top-level M3 PWM span, not full joint PEX',ports_order=['A','Y','VDD','VSS'],port_binding={'A':'analog macro edge x=120 um','Y':'digital macro edge x=150 um','VDD':'3.3-V common ideal rail in interface replay','VSS':'common ground and pwell substrate'},span_um=30,width_um=.56,series_r_ohm=float(re.search(r'^R0 A Y (\S+)',raw,re.M).group(1)),pwm_total_c_f=sum(float(t[3][:-1])*1e-15 for line in raw.splitlines()if(t:=line.split())and t[0].startswith('C')and any(n in['A','Y']for n in t[1:3])),substrate_raw_nodes=sorted(nodes),substrate_mapping_basis='Actual full-top hierarchical merge graph binds VSUBS, digital VPW/VSS and analog VSS to common VSS; helper has no substrate contacts',excludes=['macro-internal metal/device R/C already present in their own macro evidence','global chip multi-corner PEX','substrate impedance or realistic power-grid transient','added monitor/package/pad probe load'],tool_version=tool_version,tool_binary_sha256=tool_hash,invocation=invocation,inputs_sha256={str(f.relative_to(ROOT)):sha(f)for f in[run/'pixel_integrated.gds',run/'pixel_integrated.ext',run/'pixel_integrated.spice',run/'routing.json',out/'pwm_link_only.gds',Path(__file__),pdk/'libs.tech/magic/gf180mcuD.magicrc',pdk/'libs.tech/magic/gf180mcuD.tech']},outputs_sha256={name:sha(out/name)for name in['pwm_link_rc.spice','pwm_link_normalized.spice','magic-link.log']},outputs_sha256_scope='Private output-directory names, not the renamed public files',public_artifacts_sha256={'pwm_link_rc.raw.spice':sha(out/'pwm_link_rc.spice'),'pwm_link_rc.spice':sha(out/'pwm_link_normalized.spice'),'magic-link.log':sha(out/'magic-link.log'),'substrate-proof.json':sha(out/'substrate-proof.json')},passed=True)
 (out/'link-rc.json').write_text(json.dumps(data,indent=2)+'\n');print('PASS private link characterization: '+str(out))
if __name__=='__main__':main()
