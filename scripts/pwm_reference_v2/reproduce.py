#!/usr/bin/env python3
"""Replay one frozen case into a new empty directory, no old-round dependency.
Only this round's inputs/, immutable case directory and result.json are needed.
Absolute .include/.lib paths are relocated; all electrical bytes stay unchanged.
"""
from pathlib import Path
import argparse,fcntl,gzip,hashlib,json,re,shutil,subprocess,time
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
DEFAULT=ROOT/'build/pwm-reference-v2/20261024'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--case',default='n2rl_dc');ap.add_argument('--source',type=Path,default=DEFAULT);ap.add_argument('--destination',type=Path,required=True);a=ap.parse_args();src=a.source.resolve();old=src/a.case;result=json.loads((old/'result.json').read_text());assert result['completed'];c=result['case'];manifest=src/'inputs/manifests'/(result['source_manifest_sha256']+'.json');assert sha(manifest)==result['source_manifest_sha256'];m=json.loads(manifest.read_text());assert m['executed_runner_sha256']==result['executed_runner_sha256'],'Do not replay an identity-exception case as selected evidence'
 dest=a.destination.resolve();assert not dest.exists(),'Destination must not already exist';dest.mkdir(parents=True);inp=dest/'inputs';inp.mkdir();verified={}
 for n,rec in m['files'].items():
  p=src/'inputs'/n;assert sha(p)==rec['sha256'],n;shutil.copy2(p,inp/n);verified[n]=sha(inp/n)
 sid=result['executed_runner_sha256'];runner=src/'inputs/executed_sources'/sid/'run.py';assert sha(runner)==sid;shutil.copy2(runner,inp/'executed-runner.py');shutil.copy2(manifest,inp/'source-manifest.json')
 deck=(old/'testbench.spice').read_text();assert sha(old/'testbench.spice')==result['deck_sha256']
 # The frozen input directory is determined from verified original includes.
 oldinputs=re.search(r'\.include "([^\n"]+)/design.ngspice"',deck).group(1)
 restored=deck.replace(oldinputs+'/',str(inp)+'/')
 for path in re.findall(r'(?im)^\.(?:include|lib)\s+"([^\n"]+)"',restored):assert Path(path).is_file() and Path(path).parent==inp,path
 (dest/'testbench.spice').write_text(restored)
 compiler=subprocess.run(['iverilog','-g2012','-s','tb_safety','-o',str(dest/'safety.vvp'),str(inp/'pixel_pwm.v'),str(inp/'pixel_safety.v'),str(inp/'tb_safety.v')],text=True,capture_output=True);(dest/'rtl-compile.log').write_text(compiler.stdout+compiler.stderr);assert compiler.returncode==0
 rtl_match=None
 if c['kind'] in ['startup','fault','pwm']:
  fn=50125 if c['kind']=='fault' else -1;stop=47700 if c['kind']=='fault' else -1;clear=c.get('startup_fault_clear_ns',20000) if c['kind']=='startup' else 100;duty=1 if c['kind']=='pwm' else 256
  p=subprocess.run(['vvp',str(dest/'safety.vvp'),f'+DUTY={duty}',f'+FAULT_NS={fn}',f'+STOP_NS={stop}',f'+STOP_TIME_NS={c["stop_ns"]}',f'+INITIAL_FAULT_CLEAR_NS={clear}',f'+OUT={dest/"rtl-events.csv"}'],text=True,capture_output=True);(dest/'rtl.log').write_text(p.stdout+p.stderr);assert p.returncode==0 and 'SAFETY_CASE_PASS' in p.stdout;rtl_match=(dest/'rtl-events.csv').read_bytes()==(old/'rtl-events.csv').read_bytes();assert rtl_match
 t=time.time()
 with open('/tmp/open-microled-pwm-reference-v2-ngspice.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);sim_started=time.time();p=subprocess.run(['ngspice','-b','testbench.spice'],cwd=dest,text=True,capture_output=True,timeout=420);sim_finished=time.time()
 log=p.stdout+p.stderr;(dest/'ngspice.log').write_text(log);assert p.returncode==0 and not re.search(r'(?im)^Error:|timestep too small|simulation interrupted',log)
 dat=dest/('ac.dat' if c['kind']=='ac' else 'waveform.dat');d=np.atleast_2d(np.loadtxt(dat,skiprows=1));assert np.isfinite(d).all();h=sha(dat)
 with dat.open('rb') as sf,gzip.open(str(dat)+'.gz','wb',compresslevel=6) as df:shutil.copyfileobj(sf,df)
 with gzip.open(str(dat)+'.gz','rb') as f:assert hashlib.sha256(f.read()).hexdigest()==h
 dat.unlink();out=dict(case=a.case,original_deck_sha256=result['deck_sha256'],relocated_deck_sha256=sha(dest/'testbench.spice'),source_manifest_sha256=sha(manifest),executed_runner_sha256=sid,verified_inputs=verified,ngspice_version=subprocess.check_output(['ngspice','--version'],text=True),elapsed_s=time.time()-t,elapsed_ngspice_s=sim_finished-sim_started,lock_wait_s=sim_started-t,reproducer_sha256=sha(Path(__file__)),rtl_recompiled=True,rtl_event_bytes_match=rtl_match,raw_sha256=h,raw_byte_identity_to_original=h==result['raw_sha256'],gzip_sha256=sha(Path(str(dat)+'.gz')),log_sha256=sha(dest/'ngspice.log'),rows=len(d),boundary='Includes relocated only; no previous-round files read. Cross-platform numerical equivalence may need metrics comparison even when byte identity differs.')
 if c['kind']=='dc':out.update(current_a=float(d[0,1]),dc_error_pct=float((d[0,1]/1e-4-1)*100),current_delta_from_original_a=float(d[0,1]-result['current_a']));assert abs(out['dc_error_pct'])<=5
 save(dest/'reproduction.json',out);print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
