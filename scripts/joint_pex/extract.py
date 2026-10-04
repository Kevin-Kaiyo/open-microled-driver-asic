"""Extract actual frozen common GDS R/C, preserving every raw result."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--timeout',type=int,default=300);p.add_argument('--skip-power',action='store_true');a=p.parse_args()
 out=ROOT/'build/joint-pex'/a.run
 if out.exists()and any(out.iterdir()):raise RuntimeError('Use a fresh --run; preserve earlier logs')
 out.mkdir(parents=True,exist_ok=True);pdk=ROOT/'build/layout/pdk/gf180mcuD';magic=ROOT/'build/layout/tools/install/bin/magic'
 lock=json.loads((ROOT/'scripts/physical/pdk-lock.json').read_text())
 for path,want in lock['files'].items():
  if sha(pdk/path)!=want:raise RuntimeError('PDK hash mismatch '+path)
 gds=ROOT/'evidence/integration/pixel_integrated.gds'
 if sha(gds)!=json.loads((ROOT/'evidence/integration/summary.json').read_text())['output_hashes']['pixel_integrated.gds']:raise RuntimeError('Common GDS identity differs')
 shutil.copyfile(gds,out/'input.gds')
 script=(ROOT/'evidence/integration/extract.tcl').read_text().replace('gds read $env(INTEGRATION_GDS)','random seed 20261005\ngds read $env(JOINT_GDS)')
 prefs=['extract style ngspice()','extract do capacitance','extract do coupling','extresist threshold 0','extresist minres 0','extresist mindelay 0']
 if a.skip_power:prefs += ['extresist ignore VDD','extresist ignore VSS','extresist ignore VNW','extresist ignore VPW']
 prefs+=['extract do resistance','extract all','ext2spice lvs','ext2spice cthresh 0','ext2spice rthresh 0','ext2spice extresist on','ext2spice -o pixel_integrated_rc.spice']
 script=script.replace('extract all\next2spice lvs\next2spice','\n'.join(prefs))
 (out/'extract.tcl').write_text(script)
 sources=[Path(__file__),gds,ROOT/'evidence/integration/extract.tcl',ROOT/'scripts/physical/pdk-lock.json',pdk/'libs.tech/magic/gf180mcuD.magicrc',pdk/'libs.tech/magic/gf180mcuD.tech']
 env=dict(os.environ,PDK_ROOT=str(pdk.parent),JOINT_GDS=str(out/'input.gds'))
 argv=[str(magic),'-dnull','-noconsole','-rcfile',str(pdk/'libs.tech/magic/gf180mcuD.magicrc'),str(out/'extract.tcl')]
 record=dict(argv=argv,inputs_sha256={str(f.relative_to(ROOT)):sha(f)for f in sources},tool_version=subprocess.check_output([str(magic),'--version'],text=True).strip(),tool_binary_sha256=sha(magic),skip_power=a.skip_power,timeout_seconds=a.timeout)
 start=time.monotonic()
 with(out/'magic.log').open('w')as handle:
  try:ret=subprocess.run(argv,cwd=out,env=env,stdout=handle,stderr=subprocess.STDOUT,timeout=a.timeout,stdin=subprocess.DEVNULL);record['exit_code']=ret.returncode
  except subprocess.TimeoutExpired:record['timed_out']=True;record['exit_code']=None
 record['elapsed_seconds']=time.monotonic()-start
 text=(out/'magic.log').read_text();record['net_extraction_summaries']=re.findall(r'Total Nets: \d+\nNets extracted:.*?\nNets output:.*?(?=\n)',text)
 output=out/'pixel_integrated_rc.spice';record['passed']=record['exit_code']==0 and output.exists()and'exttospice finished.'in text
 record['output_sha256']={f.name:sha(f)for f in sorted(out.glob('*.spice'))};record['drc_count']=re.findall(r'INTEGRATION_DRC_COUNT (\d+)',text)
 (out/'extraction.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k]for k in['passed','exit_code','elapsed_seconds','drc_count']},indent=2));print(out)
 if not record['passed']:raise RuntimeError('Actual extraction failed; preserve '+str(out))
if __name__=='__main__':main()
