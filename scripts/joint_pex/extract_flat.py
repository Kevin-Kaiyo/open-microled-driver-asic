"""Flat physical extraction removes hierarchical capacitance corrections.
Only labels/probes are added to the frozen geometry; there are no new wires.
"""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--rc-style',choices=['nominal','hrhc','lrhc','hrlc','lrlc'],default='nominal');p.add_argument('--timeout',type=int,default=300);a=p.parse_args()
 out=ROOT/'build/joint-pex'/a.run
 if out.exists()and any(out.iterdir()):raise RuntimeError('Use fresh --run')
 out.mkdir(parents=True,exist_ok=True);pdk=ROOT/'build/layout/pdk/gf180mcuD';magic=ROOT/'build/layout/tools/install/bin/magic';gds=ROOT/'evidence/integration/pixel_integrated.gds'
 for path,want in json.loads((ROOT/'scripts/physical/pdk-lock.json').read_text())['files'].items():
  if sha(pdk/path)!=want:raise RuntimeError('PDK hash mismatch '+path)
 if sha(gds)!=json.loads((ROOT/'evidence/integration/summary.json').read_text())['output_hashes']['pixel_integrated.gds']:raise RuntimeError('GDS identity changed')
 shutil.copyfile(gds,out/'input.gds');routes=json.loads((ROOT/'evidence/integration/routing.json').read_text());ports=routes['ports']
 ports=ports|{'DRIVER_I':dict(layer='Metal1',rect_um=[161.47,109.83,161.49,109.85]),'DRIVER_Z':dict(layer='Metal1',rect_um=[159.23,108.71,159.25,108.73]),'ANALOG_PWM':dict(layer='Metal3',rect_um=[119.98,111.51,120.0,111.53])}
 script=['random seed 20261005','gds read $env(JOINT_GDS)','load pixel_integrated','select top cell','flatten -nolabels pixel_flat','load pixel_flat','select top cell']
 for name,d in ports.items():script+=['box values '+' '.join(f'{x:.3f}um'for x in d['rect_um']),f'label {{{name}}} center {d["layer"].lower()}','port make']
 style='ngspice()'if a.rc_style=='nominal'else' ngspice('+a.rc_style+')'
 script+=['drc style drc(full)','drc check','drc catchup','puts "FLAT_DRC_COUNT [drc list count total]"','save pixel_flat',f'extract style {style}','extract do capacitance','extract do coupling','extresist threshold 0','extresist minres 0','extresist mindelay 0','extract do resistance','extract all','ext2spice lvs','ext2spice cthresh 0','ext2spice rthresh 0','ext2spice extresist on','ext2spice -o pixel_flat_rc.spice','quit -noprompt']
 (out/'extract.tcl').write_text('\n'.join(script)+'\n');(out/'probes.json').write_text(json.dumps(ports,indent=2)+'\n')
 sources=[Path(__file__),gds,ROOT/'evidence/integration/routing.json',ROOT/'scripts/physical/pdk-lock.json',pdk/'libs.tech/magic/gf180mcuD.magicrc',pdk/'libs.tech/magic/gf180mcuD.tech'];env=dict(os.environ,PDK_ROOT=str(pdk.parent),JOINT_GDS=str(out/'input.gds'))
 argv=[str(magic),'-dnull','-noconsole','-rcfile',str(pdk/'libs.tech/magic/gf180mcuD.magicrc'),str(out/'extract.tcl')]
 record=dict(argv=argv,inputs_sha256={str(f.relative_to(ROOT)):sha(f)for f in sources},tool_version=subprocess.check_output([str(magic),'--version'],text=True).strip(),tool_binary_sha256=sha(magic),rc_style=a.rc_style,timeout_seconds=a.timeout)
 start=time.monotonic()
 with(out/'magic.log').open('w')as h:
  try:ret=subprocess.run(argv,cwd=out,env=env,stdout=h,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=a.timeout);record['exit_code']=ret.returncode
  except subprocess.TimeoutExpired:record['timed_out']=True;record['exit_code']=None
 record['elapsed_seconds']=time.monotonic()-start;text=(out/'magic.log').read_text();record['drc_count']=re.findall(r'FLAT_DRC_COUNT (\d+)',text);record['style_confirmations']=re.findall(r'Extraction style is now "([^"]+)"',text);record['nets_summaries']=re.findall(r'Total Nets: \d+\nNets extracted:.*?\nNets output:.*?(?=\n)',text)
 dest=out/'pixel_flat_rc.spice';record['passed']=record['exit_code']==0 and dest.exists()and'exttospice finished.'in text
 record['outputs_sha256']={f.name:sha(f)for f in out.glob('*.spice')};(out/'extraction.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k]for k in['passed','exit_code','elapsed_seconds','drc_count']},indent=2));print(out)
 if not record['passed']:raise RuntimeError('Flat extraction failed, raw preserved')
if __name__=='__main__':main()
