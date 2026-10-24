#!/usr/bin/env python3
"""Replay a frozen case using only this milestone's small input bundle.

No build/analog-v3 or build/layout-v3 history is required. The target must be a
new empty directory. Original case directories are never modified.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[2]
DEFAULT_INPUT=ROOT/'build/pwm-robustness/20261024/inputs'
DEFAULT_EVID=ROOT/'evidence/pwm-robustness/20261024'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,default=DEFAULT_INPUT);ap.add_argument('--manifest',type=Path,default=DEFAULT_EVID/'input-manifest.json');ap.add_argument('--case-file',type=Path,default=DEFAULT_EVID/'dc_board100n.json');ap.add_argument('--work',type=Path);a=ap.parse_args()
    source=a.inputs.resolve();manifest=json.loads(a.manifest.read_text());reference=json.loads(a.case_file.read_text())
    required=['design.ngspice','sm141064.ngspice','dut.spice','microled.spice','pixel_pwm.v','pixel_safety.v','tb_safety.v','math.py']
    expected={}
    for name in required:
        suffix='scripts/safety/run.py' if name=='math.py' else '/'+name
        matches=[v for k,v in manifest['inputs'].items() if k.endswith(suffix)]
        if len(matches)!=1:raise RuntimeError('Missing/ambiguous frozen manifest entry '+name)
        expected[name]=matches[0]
        if sha(source/name)!=expected[name]:raise RuntimeError('Frozen source checksum mismatch '+name)
    if a.work:
        work=a.work.resolve()
        if work.exists() and any(work.iterdir()):raise RuntimeError('Replay work directory must be empty: '+str(work))
        work.mkdir(parents=True,exist_ok=True)
    else:
        parent=ROOT/'build/pwm-robustness';parent.mkdir(parents=True,exist_ok=True);work=Path(tempfile.mkdtemp(prefix='replay-',dir=parent))
    inp=work/'inputs';inp.mkdir();evid=work/'evidence';evid.mkdir()
    for name in required:
        shutil.copy2(source/name,inp/name)
        if sha(inp/name)!=expected[name]:raise RuntimeError('Copied input checksum mismatch '+name)
    spec=importlib.util.spec_from_file_location('pwm_replay',Path(__file__).with_name('run.py'));runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    runner.WORK=work;runner.INPUT=inp;runner.EVID=evid
    spec=importlib.util.spec_from_file_location('frozen_math',inp/'math.py');math=importlib.util.module_from_spec(spec);spec.loader.exec_module(math);runner.M=math
    runner.command(['iverilog','-g2012','-s','tb_safety','-o',work/'safety.vvp',inp/'pixel_pwm.v',inp/'pixel_safety.v',inp/'tb_safety.v'],work,'rtl-compile.log')
    devices=[line.split() for line in (inp/'dut.spice').read_text().splitlines() if runner.re.match(r'^X\d+ ',line)]
    assert len(devices)==39
    c=dict(reference['case']);c['source_case_identity']=c['name'];c['name']='replay_'+c['name'];c.pop('generator_case_name',None)
    result=runner.run(c,devices,reuse=False)
    current_delta=None if 'current_a' not in result else result['current_a']-reference['current_a']
    summary=dict(date='2026-10-24',work_directory=str(work),original_case_file=str(a.case_file.resolve()),original_case_file_sha256=sha(a.case_file),original_input_manifest_sha256=sha(a.manifest),frozen_file_sha256=expected,required_historical_build_directories=[],ngspice_version=subprocess.check_output(['ngspice','--version'],text=True),python=sys.version,runner_sha256=sha(Path(__file__).with_name('run.py')),reproducer_sha256=sha(Path(__file__)),result=result,current_difference_a=current_delta,reproduction_passed=result['completed'] and (abs(current_delta)<=1e-12 if current_delta is not None else result.get('passed',False)),note='Fresh empty directory, regenerated absolute includes, copied and hash-verified frozen models/RTL/math only. No historical Oct15 raw directory or layout PDK tree accessed by replay.')
    runner.save(work/'reproduction-summary.json',summary)
    print(json.dumps({k:summary[k] for k in ['work_directory','required_historical_build_directories','current_difference_a','reproduction_passed']},indent=2))
    return 0 if summary['reproduction_passed'] else 2
if __name__=='__main__':raise SystemExit(main())
