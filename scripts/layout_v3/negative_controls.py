"""Actual GDS gap and rail bridge controls; baseline/golden preserved."""
from pathlib import Path
import json,os,subprocess,re,hashlib,sys
import klayout.db as k
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/(sys.argv[1] if len(sys.argv)>1 else 'build/layout-v3/r5');pdk=ROOT/'build/layout/pdk';tools=ROOT/'build/layout/tools/install/bin';rc=pdk/'gf180mcuD/libs.tech/magic/gf180mcuD.magicrc';setup=pdk/'gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl';env=os.environ|{'PDK_ROOT':str(pdk)}
results=[]
for mode in ['raw-open','vref-ground-short']:
 out=BASE/mode;out.mkdir(exist_ok=True);l=k.Layout();l.read(str(BASE/'generate/startup_test_macro.gds'));c=l.cell('startup_test_macro');idx=l.layer(42,0);region=k.Region(c.shapes(idx))
 contract=json.loads((ROOT/'layout/startup_v3/contract.json').read_text()); buses=contract['buses_um']; spans=contract['bus_spans_um']
 if mode=='raw-open':
  x=sum(spans['RAW_PWM'])/2;y=buses['RAW_PWM'];region-=k.Region(k.DBox(x-1,y-.5,x+1,y+.5).to_itype(l.dbu))
 else:
  x=sum(spans['VREF'])/2;region+=k.Region(k.DBox(x-.3,-.3,x+.3,buses['VREF']+.3).to_itype(l.dbu))
 c.shapes(idx).clear();c.shapes(idx).insert(region);l.write(str(out/'startup_test_macro.gds'))
 script=out/'extract.tcl';script.write_text('gds read startup_test_macro.gds\nload startup_test_macro\nselect top cell\ndrc style drc(full)\ndrc check\ndrc catchup\nputs "CONTROL_DRC_COUNT [drc list count total]"\nextract all\next2spice lvs\next2spice\nquit -noprompt\n')
 r=subprocess.run([str(tools/'magic'),'-dnull','-noconsole','-rcfile',str(rc),str(script)],cwd=out,env=env,capture_output=True,text=True);(out/'magic.log').write_text(r.stdout+r.stderr)
 cmd=[str(tools/'netgen'),'-batch','lvs',f'{out}/startup_test_macro.spice startup_test_macro',f'{ROOT}/layout/startup_v3/startup_test_macro.spice startup_test_macro',str(setup),str(out/'netgen-lvs.log')]
 n=subprocess.run(cmd,cwd=ROOT/'layout/startup_v3',env=env,capture_output=True,text=True);(out/'netgen-stdout.log').write_text(n.stdout+n.stderr)
 text=(out/'netgen-lvs.log').read_text();result=dict(control=mode,description='Real Metal3 gap on RAW_PWM bus, fixed original top port' if mode=='raw-open' else 'Real Metal3 bridge from VREF to VSS',magic_exit=r.returncode,netgen_exit=n.returncode,final_result=re.findall(r'^Final result:\s*(.+)$',text,re.M),rejected=any(x in text for x in ['Netlists do not match','Circuits do not match','Top level cell failed pin matching.']),negative_gds_sha256=hashlib.sha256((out/'startup_test_macro.gds').read_bytes()).hexdigest());results.append(result)
(BASE/'negative-controls.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
assert all(x['rejected'] for x in results)
