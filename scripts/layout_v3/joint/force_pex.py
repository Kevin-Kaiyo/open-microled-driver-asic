"""Use documented Magic res:drive attributes for otherwise unexpanded nodes.
Coordinates/types come solely from the unmodified extraction. No GDS mutation,
no device/resistor/capacitor removal, no relaxed electrical limits.
"""
from pathlib import Path
import re,shutil,json,hashlib,subprocess,os
ROOT=Path(__file__).resolve().parents[3];run=ROOT/'build/layout-v3/joint-r2';old=run/'pex';out=run/'pex-driven-final';out.mkdir(exist_ok=True)
name='startup_integrated_v3_flat';ext=(old/(name+'.ext')).read_text();done=set(re.findall(r'^Extracting (\S+)\s*$',(run/'magic-full-pex.log').read_text(),re.M));nodes=[]
for m in re.finditer(r'^node "([^"]+)" \S+ \S+ (\S+) (\S+) (\S+)',ext,re.M):
 n,x,y,t=m.groups()
 if n not in done:nodes.append(dict(node=n,x=int(x),y=int(y),layer=t))
for suffix in ['.mag'] :shutil.copyfile(old/(name+suffix),out/(name+suffix))
attrs=''.join(f'attr "{n["node"]}" {n["x"]} {n["y"]} {n["x"]+1} {n["y"]+1} {n["layer"]} "res:drive"\n'for n in nodes)
byname={n['node']:n for n in nodes};lines=[]
for line in ext.splitlines():
 lines.append(line)
 m=re.match(r'^node "([^"]+)"',line)
 if m and m[1] in byname:
  n=byname[m[1]];lines.append(f'attr "{n["node"]}" {n["x"]} {n["y"]} {n["x"]+1} {n["y"]+1} {n["layer"]} "res:drive"')
annotated='\n'.join(lines)+'\n';(out/(name+'.ext')).write_text(annotated)
manifest=dict(node_count=len(nodes),nodes=nodes,original_ext_sha256=hashlib.sha256(ext.encode()).hexdigest(),annotated_ext_sha256=hashlib.sha256(annotated.encode()).hexdigest(),source='Magic documented res:drive extraction attribute; coordinates and layer copied from original .ext node record',geometry_mutated=False);(out/'drive-attributes.json').write_text(json.dumps(manifest,indent=2)+'\n')
tcl=f'''load {name}
select top cell
extract style ngspice()
extresist threshold 0
extresist minres 0
extresist mindelay 0
extresist all
ext2spice lvs
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice -o {name}_rc.spice
quit -noprompt
''';(out/'extract-driven.tcl').write_text(tcl)
pdk=ROOT/'build/layout/pdk';cmd=[ROOT/'build/layout/tools/install/bin/magic','-dnull','-noconsole','-rcfile',pdk/'gf180mcuD/libs.tech/magic/gf180mcuD.magicrc',out/'extract-driven.tcl']
with (run/'magic-driven-final-pex.log').open('w')as f:r=subprocess.run([str(x)for x in cmd],cwd=out,env=os.environ|{'PDK_ROOT':str(pdk)},stdout=f,stderr=subprocess.STDOUT)
print('rc',r.returncode,'attributes',len(nodes));assert r.returncode==0
