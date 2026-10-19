"""Run pinned independent GF180D DRC in the existing Linux tool container."""
from pathlib import Path
import os,sys,json,subprocess,hashlib,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];out=ROOT/sys.argv[1];gds=out/'generate/startup_test_macro.gds';pdk=ROOT/'build/layout/pdk';deck=pdk/'gf180mcuD/libs.tech/klayout/tech/drc/run_drc.py'
IMAGE='ghcr.io/librelane/librelane@sha256:f91b21d75f79871f9ccf37451020b5d2f7b3236881a997ff709c561e8280a30f'
cmd=['limactl','shell','asic','nerdctl','run','--rm','-v',f'{ROOT}:{ROOT}','-w',str(out),'-e','QT_QPA_PLATFORM=offscreen','-e',f'PYTHONPATH={ROOT}/build/physical-flow/linux-python','-e',f'PDK_ROOT={pdk}',IMAGE,'python3',str(deck),f'--path={gds}','--variant=D','--topcell=startup_test_macro','--mp=1','--thr=4',f'--run_dir={out}/klayout']
with (out/'klayout-linux.log').open('w') as f:r=subprocess.run(cmd,env=os.environ|{'LIMA_HOME':str(ROOT/'build/physical-flow/lima')},stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
(out/'klayout-command.json').write_text(json.dumps(dict(argv=cmd,exit_code=r.returncode,image=IMAGE,sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),gds,deck,deck.parent/'gf180mcu.drc']}),indent=2)+'\n')
if r.returncode:raise RuntimeError(f'KLayout failed {out}')
xml=out/'klayout/startup_test_macro_main.lyrdb';doc=ET.parse(xml);items=doc.findall('.//item');cats={}
for x in items:cats[x.findtext('category')]=cats.get(x.findtext('category'),0)+1
result=dict(item_count=len(items),categories=cats,passed=len(items)==0)
(out/'klayout-result.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
if items:sys.exit(2)
