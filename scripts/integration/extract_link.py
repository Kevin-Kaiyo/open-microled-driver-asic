"""Extract only new PWM Metal3 span; macro-internal RC is excluded.
Includes the new neighboring power routes as electrostatic conductors. The
span boundaries are the actual GDS macro edges x=120 and x=150 um.
"""
from pathlib import Path
import argparse,json
import klayout.db as k
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--run',default='r2');a=p.parse_args()
folder=ROOT/'build/integration'/a.run
j=json.loads((folder/'routing.json').read_text());l=k.Layout();l.dbu=.001;c=l.create_cell('pwm_link_rc')
levels={'Metal3':42,'Metal4':46,'Metal5':81,'Via3':40,'Via4':41}
for r in j['routes']:
 if r['net'] not in ('VDD','VSS','pwm_link'):continue
 coords=r['rect_um']
 if r['net']=='pwm_link':coords=[120,coords[1],150,coords[3]]
 c.shapes(l.layer(levels[r['layer']],0)).insert(k.DBox(*coords))
l.write(str(folder/'pwm_link_only.gds'))
script=['gds read $env(INTEGRATION_RUN)/pwm_link_only.gds','load pwm_link_rc']
for n,layer,b in [('A','metal3',[120,111.24,120.02,111.8]),('Y','metal3',[149.98,111.24,150,111.8]),('VDD','metal4',[139.65,116.5,140.35,117.52]),('VSS','metal5',[134.65,104.5,135.35,105.52])]:
 script += ['box values '+' '.join(f'{v}um' for v in b),f'label {n} center {layer}','port make']
script+=['extract style ngspice()','extract do capacitance','extract do coupling','extresist threshold 0','extresist minres 0','extresist mindelay 0','extract do resistance','extract all','ext2spice lvs','ext2spice cthresh 0','ext2spice rthresh 0','ext2spice extresist on','ext2spice -o pwm_link_rc.spice','quit -noprompt']
(folder/'extract_link.tcl').write_text('\n'.join(script)+'\n')
print(folder)
# Preserve the raw extractor's substrate node; map it only after verifying the
# complete top's analog NMOS bulk and substrate node are tied to VSS.
import hashlib,os,re,shutil,subprocess
magic=ROOT/'build/layout/tools/install/bin/magic'
env=dict(os.environ,PDK_ROOT=str(ROOT/'build/layout/pdk'),INTEGRATION_RUN=str(folder))
command=[str(magic),'-dnull','-noconsole','-rcfile',str(ROOT/'build/layout/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc'),str(folder/'extract_link.tcl')]
ret=subprocess.run(command,cwd=folder,env=env,capture_output=True,text=True)
(folder/'magic-link.log').write_text(ret.stdout+ret.stderr)
if ret.returncode:raise RuntimeError('Metal RC extraction failed')
raw=(folder/'pwm_link_rc.spice').read_text()
full=(folder/'pixel_integrated.spice').read_text()
if not re.search(r'Xpixel_driver_layout_0 VSS bias gate pwm_monitor pwm_b led_k VDD pixel_driver_layout',full):raise RuntimeError('Full-top substrate binding not confirmed')
# Verify the real hierarchical substrate merges, rather than just model pins.
full_ext=(folder/'pixel_integrated.ext').read_text()
merges=re.findall(r'^merge \"([^\"]+)\" \"([^\"]+)\"',full_ext,re.M)
parents={}
def find(n):
 parents.setdefault(n,n)
 if parents[n]!=n:parents[n]=find(parents[n])
 return parents[n]
for x,y in merges:parents[find(x)]=find(y)
substrate_connected=find('VSUBS')==find('VSS')==find('pixel_driver_layout_0/VSS')
if not substrate_connected:raise RuntimeError('Actual hierarchical substrate is not bound to common VSS')
proof=dict(passed=substrate_connected,source=str((folder/'pixel_integrated.ext').relative_to(ROOT)),basis='Actual full-top Magic hierarchical merge records',relevant_records=[line for line in full_ext.splitlines()if line.startswith('substrate ') or (line.startswith('merge ') and all(find(n)==find('VSS')for n in re.findall(r'\"([^\"]+)\"',line)[:2]))],helper_substrate_records=[line for line in (folder/'pwm_link_rc.ext').read_text().splitlines()if line.startswith('substrate ')])
(folder/'substrate-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
subnodes=set(re.findall(r'\bw_\d+_\d+#',raw))
if len(subnodes)!=1:raise RuntimeError('Expected one substrate boundary in isolated route')
normalized=raw
for node in subnodes:normalized=normalized.replace(node,'VSS')
normalized='* Isolated new M3 span only; full-top pwell substrate boundary mapped to VSS.\n* Macro-internal RC excluded; VDD/VSS ideal in the downstream interface probe.\n'+normalized
lines=[]
for line in normalized.splitlines():
 t=line.split()
 if t and t[0].startswith('C') and t[1]==t[2]:lines.append('* omitted self-cap after proven substrate mapping: '+line)
 else:lines.append(line)
normalized='\n'.join(lines)+'\n'
(folder/'pwm_link_normalized.spice').write_text(normalized)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record=dict(evidence_level='Actual PDK Magic metal-only R/C extraction of the new top-level M3 PWM span, not full joint PEX',ports_order=['A','Y','VDD','VSS'],port_binding={'A':'analog macro edge x=120 um','Y':'digital macro edge x=150 um','VDD':'3.3-V common ideal rail in interface replay','VSS':'common ground and pwell substrate'},span_um=30,width_um=.56,series_r_ohm=float(re.search(r'^R0 A Y (\S+)',raw,re.M).group(1)),pwm_total_c_f=sum(float(t[3][:-1])*1e-15 for line in raw.splitlines() if (t:=line.split()) and t[0].startswith('C') and any(n in ('A','Y') for n in t[1:3])),substrate_raw_nodes=sorted(subnodes),substrate_mapping_basis='Full GDS-extracted top binds analog NMOS bodies and frozen digital VPW/VSS to common VSS; helper geometry has no substrate contacts',excludes=['macro-internal metal/device R/C already present in their own macro evidence','global chip multi-corner PEX','substrate impedance or realistic power-grid transient','added monitor/package/pad probe load'],tool_version=subprocess.check_output([str(magic),'--version'],text=True).strip(),tool_binary_sha256=sha(magic),inputs_sha256={str(p.relative_to(ROOT)):sha(p) for p in [folder/'pixel_integrated.gds',folder/'pwm_link_only.gds',folder/'routing.json',folder/'pixel_integrated.ext',ROOT/'scripts/integration/extract_link.py',ROOT/'build/layout/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc',ROOT/'build/layout/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.tech']},outputs_sha256={name:sha(folder/name) for name in ['pwm_link_rc.spice','pwm_link_normalized.spice','magic-link.log']},passed=True)
record['outputs_sha256_scope']='Raw run-directory names, not the renamed public files'
record['public_artifacts_sha256']={'pwm_link_rc.raw.spice':sha(folder/'pwm_link_rc.spice'),'pwm_link_rc.spice':sha(folder/'pwm_link_normalized.spice'),'magic-link.log':sha(folder/'magic-link.log'),'substrate-proof.json':sha(folder/'substrate-proof.json')}
(folder/'link-rc.json').write_text(json.dumps(record,indent=2)+'\n')
dest=ROOT/'evidence/integration';dest.mkdir(parents=True,exist_ok=True)
shutil.copyfile(folder/'pwm_link_rc.spice',dest/'pwm_link_rc.raw.spice')
shutil.copyfile(folder/'pwm_link_normalized.spice',dest/'pwm_link_rc.spice')
shutil.copyfile(folder/'link-rc.json',dest/'link-rc.json')
shutil.copyfile(folder/'magic-link.log',dest/'magic-link.log')
shutil.copyfile(folder/'substrate-proof.json',dest/'substrate-proof.json')
print('PASS isolated route: %.8f ohm, %.8f fF'%(record['series_r_ohm'],record['pwm_total_c_f']*1e15))
