"""Reproduce independent generation, GDS readback DRC/LVS/RC and KLayout DRC.
Raw runs are timestamp-isolated. Use publish.py only after electrical review.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,os,re,subprocess
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--run');a=p.parse_args();run=ROOT/'build/layout-v3'/(a.run or datetime.datetime.now().strftime('run-%Y%m%d-%H%M%S'));run.mkdir(parents=True,exist_ok=False);pdk=ROOT/'build/layout/pdk';tools=ROOT/'build/layout/tools/install/bin';py=ROOT/'build/layout/venv/bin/python';src=ROOT/'layout/startup_v3';env=os.environ|{'PDK_ROOT':str(pdk)};lock=json.loads((ROOT/'layout/pdk-lock.json').read_text())
 for f,want in lock['files'].items():
  if hashlib.sha256((pdk/'gf180mcuD'/f).read_bytes()).hexdigest()!=want:raise RuntimeError('PDK hash mismatch '+f)
 def command(args,cwd,name):
  r=subprocess.run([str(x)for x in args],cwd=cwd,env=env,capture_output=True,text=True);(run/(name+'.log')).write_text(r.stdout+r.stderr);(run/(name+'.command.json')).write_text(json.dumps(dict(argv=[str(x)for x in args],cwd=str(cwd),exit_code=r.returncode),indent=2)+'\n');
  if r.returncode:raise RuntimeError(f'{name} exit={r.returncode}')
  return r.stdout+r.stderr
 command([py,ROOT/'scripts/layout_v3/generate.py'],ROOT,'generator')
 rc=pdk/'gf180mcuD/libs.tech/magic/gf180mcuD.magicrc';setup=pdk/'gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl'
 for x in ['generate','roundtrip']:(run/x).mkdir()
 text=command([tools/'magic','-dnull','-noconsole','-rcfile',rc,src/'generate.tcl'],run/'generate','magic-generate')
 if 'V3_DRC_COUNT 0'not in text:raise RuntimeError('Generated DRC failed')
 def lvs(folder,label):
  command([tools/'netgen','-batch','lvs',f'{run/folder}/startup_test_macro.spice startup_test_macro',f'{src}/startup_test_macro.spice startup_test_macro',setup,run/(label+'.log')],src,label+'-stdout');t=(run/(label+'.log')).read_text()
  if re.findall(r'^Final result:\s*(.+)$',t,re.M)!=['Circuits match uniquely.']or re.search(r'property errors|do not match|not equivalent',t,re.I):raise RuntimeError('LVS failed '+label)
 lvs('generate','netgen-lvs');env['V3_GDS']=str(run/'generate/startup_test_macro.gds')
 text=command([tools/'magic','-dnull','-noconsole','-rcfile',rc,ROOT/'scripts/layout_v3/extract.tcl'],run/'roundtrip','magic-roundtrip-pex')
 if 'ROUNDTRIP_DRC_COUNT 0'not in text or 'Nets extracted: 29 (1.000000)'not in text:raise RuntimeError('Readback DRC/PEX failed')
 lvs('roundtrip','netgen-roundtrip-lvs');command([py,ROOT/'scripts/layout_v3/run_klayout.py',run.relative_to(ROOT)],ROOT,'independent-drc')
 print(run)
if __name__=='__main__':main()
