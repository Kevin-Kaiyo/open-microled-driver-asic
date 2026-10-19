from pathlib import Path
import json,subprocess,os,re,hashlib
import klayout.db as k
ROOT=Path(__file__).resolve().parents[3];run=ROOT/'build/layout-v3/joint-r2';pdk=ROOT/'build/layout/pdk';tools=ROOT/'build/layout/tools/install/bin';rc=pdk/'gf180mcuD/libs.tech/magic/gf180mcuD.magicrc';baseenv=os.environ|{'PDK_ROOT':str(pdk),'V3_ROOT':str(ROOT)};results=[]
for mode in ['baseline','raw-link-open','common-power-short']:
 out=run if mode=='baseline'else run/mode;out.mkdir(exist_ok=True);(out/'extract').mkdir(exist_ok=True)
 if mode!='baseline':
  l=k.Layout();l.read(str(run/'startup_integrated_v3.gds'));c=l.cell('startup_integrated_v3')
  if mode=='raw-link-open':
   i=l.layer(42,0);r=k.Region(c.shapes(i));r-=k.Region(k.DBox(695,44.5,697,45.5).to_itype(l.dbu));c.shapes(i).clear();c.shapes(i).insert(r)
  else:c.shapes(l.layer(81,0)).insert(k.DBox(760,47.49,760.6,51.89))
  l.write(str(out/'startup_integrated_v3.gds'))
 env=baseenv|{'V3_JOINT_GDS':str(out/'startup_integrated_v3.gds'),'V3_JOINT_RUN':str(out)}
 if mode!='baseline':
  with(out/'magic-extract.log').open('w')as f:r=subprocess.run([str(tools/'magic'),'-dnull','-noconsole','-rcfile',str(rc),str(run/'extract.tcl')],cwd=out/'extract',env=env,stdout=f,stderr=subprocess.STDOUT)
  assert r.returncode==0
 with(out/'netgen-stdout.log').open('w')as f:r=subprocess.run([str(tools/'netgen'),'-batch','source',str(ROOT/'scripts/layout_v3/joint/lvs.tcl')],cwd=ROOT/'layout/startup_v3',env=env,stdout=f,stderr=subprocess.STDOUT)
 text=(out/'netgen-lvs.log').read_text();final=re.findall(r'^Final result:\s*(.+)$',text,re.M);passed=final==['Circuits match uniquely.']and not re.search(r'property errors|do not match|not equivalent',text,re.I)
 record=dict(case=mode,final_result=final,netgen_exit=r.returncode,unique_match=bool(passed),expected_unique_match=mode=='baseline',passed=bool(passed)==(mode=='baseline'),gds_sha256=hashlib.sha256((out/'startup_integrated_v3.gds').read_bytes()).hexdigest());results.append(record)
(run/'negative-controls.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2));assert all(x['passed']for x in results)
