"""Run frozen physical inputs in the project-local Lima/container environment."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'build/physical-flow'
IMAGE = 'ghcr.io/librelane/librelane@sha256:f91b21d75f79871f9ccf37451020b5d2f7b3236881a997ff709c561e8280a30f'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['tools', 'digital', 'klayout', 'sta-reg', 'macro-read'])
    parser.add_argument('--run-name', default='pwm-v0.2')
    parser.add_argument('--gds', type=Path)
    parser.add_argument('--topcell', default='pixel_driver_layout')
    args = parser.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True)
    lock_path = ROOT / 'scripts/physical/pdk-lock.json'
    if lock_path.exists():
        lock = json.loads(lock_path.read_text())
        for name, expected in lock['files'].items():
            if sha(ROOT / 'build/layout/pdk/gf180mcuD' / name) != expected:
                raise RuntimeError(f'Physical PDK input hash mismatch: {name}')
    task_env = dict(os.environ, LIMA_HOME=str(BUILD / 'lima'))
    base = ['limactl', 'shell', 'asic', 'nerdctl', 'run', '--rm',
            '-v', f'{ROOT}:{ROOT}', '-w', str(ROOT), '-e', 'QT_QPA_PLATFORM=offscreen',
            '-e', f'PYTHONPATH={BUILD / "linux-python"}', IMAGE]

    def run(argv, log):
        runner_hash = sha(Path(__file__))
        with log.open('w') as handle:
            result = subprocess.run(argv, cwd=ROOT, env=task_env, stdout=handle,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        (log.with_suffix(log.suffix + '.command.json')).write_text(json.dumps(
            dict(argv=argv, exit_code=result.returncode, image=IMAGE, runner_sha256=runner_hash), indent=2) + '\n')
        if result.returncode:
            raise RuntimeError(f'exit={result.returncode}; see {log}')

    if args.mode == 'tools':
        probe = '''import json,subprocess,sys,platform,hashlib,shutil,pathlib
tools={}
for name,argv in [('librelane',['librelane','--version']),('openroad',['openroad','-version']),('yosys',['yosys','-V']),('klayout',['klayout','-v']),('magic',['magic','--version']),('netgen',['netgen','-batch'])]:
 try:
  p=subprocess.run(argv,capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=15)
  binary=pathlib.Path(shutil.which(argv[0])).resolve()
  tools[name]={'argv':argv,'exit_code':p.returncode,'output':p.stdout+p.stderr,'launcher_path':str(binary),'launcher_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}
 except subprocess.TimeoutExpired:
  tools[name]={'argv':argv,'timed_out':True}
try:
 import docopt,klayout.db
 tools['drc_python_imports']={'passed':True,'klayout_version':klayout.db.__version__}
except ImportError as e:
 tools['drc_python_imports']={'passed':False,'error':str(e)}
print(json.dumps({'python':sys.version,'platform':platform.platform(),'tools':tools},indent=2))'''
        raw = BUILD / 'tool-versions.log'
        run(base + ['python3', '-c', probe], raw)
        value, end = json.JSONDecoder().raw_decode(raw.read_text().lstrip())
        value['transport_log_tail'] = raw.read_text().lstrip()[end:].strip()
        (BUILD / 'tool-versions.json').write_text(json.dumps(value, indent=2) + '\n')
    elif args.mode == 'digital':
        inputs = BUILD / 'frozen-inputs' / args.run_name
        if not (inputs / 'config.json').exists():
            (inputs / 'rtl').mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / 'rtl/pixel_pwm.v', inputs / 'rtl/pixel_pwm.v')
            config = json.loads((ROOT / 'layout/digital/config.json').read_text())
            config['VERILOG_FILES'] = [str(inputs / 'rtl/pixel_pwm.v')]
            if 'PNR_EXCLUDED_CELL_FILE' in config:
                excluded = ROOT / 'scripts/physical/no-pnr.cells'
                shutil.copyfile(excluded, inputs / excluded.name)
                config['PNR_EXCLUDED_CELL_FILE'] = str(inputs / excluded.name)
            (inputs / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
            originals = ['rtl/pixel_pwm.v', 'layout/digital/config.json',
                         'layout/pdk-lock.json', 'scripts/digital/library-lock.json']
            if 'PNR_EXCLUDED_CELL_FILE' in config:
                originals.append('scripts/physical/no-pnr.cells')
            (inputs / 'provenance.json').write_text(json.dumps({
                'source_sha256': {p: sha(ROOT / p) for p in originals},
                'snapshot_sha256': {str(p.relative_to(inputs)): sha(p)
                                    for p in [inputs / 'rtl/pixel_pwm.v', inputs / 'config.json']},
                'image': IMAGE,
            }, indent=2) + '\n')
        run_dir = BUILD / args.run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        run(base + ['librelane', '--manual-pdk', '--pdk-root', str(ROOT / 'build/layout/pdk'),
                    '--pdk', 'gf180mcuD', '--scl', 'gf180mcu_fd_sc_mcu7t5v0',
                    '--force-run-dir', str(run_dir), '-j', '4', '--hide-progress-bar',
                    str(inputs / 'config.json')], BUILD / (args.run_name + '.log'))
    elif args.mode == 'macro-read':
        run_dir = BUILD / args.run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        source = ROOT / 'evidence/layout/pixel_driver_layout.lef'
        snapshot = run_dir / 'input.lef'
        if snapshot.exists() and sha(snapshot) != sha(source):
            raise RuntimeError('Existing frozen LEF differs; choose a new --run-name')
        shutil.copyfile(source, snapshot)
        env_base = base[:-1] + ['-e', f'ASICFLOW_ROOT={ROOT}', '-e', f'ASICFLOW_OUTPUT={run_dir}', IMAGE]
        result_file = run_dir / 'macro-read.json'
        result_file.unlink(missing_ok=True)
        run(env_base + ['openroad', '-python', '-exit', str(ROOT / 'scripts/physical/read_macro.py')],
            run_dir / 'macro-read.log')
        if not result_file.exists() or not json.loads(result_file.read_text())['passed']:
            raise RuntimeError(f'OpenDB macro read did not succeed: {run_dir}')
    elif args.mode == 'sta-reg':
        run_dir = BUILD / args.run_name
        config = json.loads((BUILD / 'frozen-inputs' / args.run_name / 'config.json').read_text())
        output = run_dir / 'register-sta'
        output.mkdir(parents=True, exist_ok=True)
        for corner in config['STA_CORNERS']:
            env_base = base[:-1] + ['-e', f'ASICFLOW_ROOT={ROOT}', '-e', f'ASICFLOW_RUN={run_dir}',
                                   '-e', f'ASICFLOW_CORNER={corner}', IMAGE]
            run(env_base + ['openroad', '-no_init', '-exit', str(ROOT / 'scripts/physical/register_sta.tcl')],
                output / (corner + '.log'))
            content = (output / (corner + '.log')).read_text()
            if f'R2R_END_HOLD {corner}' not in content or '[ERROR' in content or '\nError:' in content:
                raise RuntimeError(f'STA script failed despite CLI status; inspect {output / (corner + ".log")}')
    else:
        if args.gds is None:
            parser.error('--gds is required for klayout')
        source = args.gds.resolve()
        run_dir = BUILD / args.run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        snapshot = run_dir / 'input.gds'
        if snapshot.exists() and sha(snapshot) != sha(source):
            raise RuntimeError('Existing frozen GDS differs; choose a new --run-name')
        shutil.copyfile(source, snapshot)
        deck = ROOT / 'build/layout/pdk/gf180mcuD/libs.tech/klayout/tech/drc/run_drc.py'
        (run_dir / 'input-hashes.json').write_text(json.dumps(
            dict(source=str(source), topcell=args.topcell, gds_sha256=sha(snapshot), runner_sha256=sha(deck),
                 main_deck_sha256=sha(deck.parent / 'gf180mcu.drc'), image=IMAGE), indent=2) + '\n')
        run(base + ['python3', str(deck), f'--path={snapshot}', '--variant=D',
                    f'--topcell={args.topcell}', '--mp=1', '--thr=4',
                    f'--run_dir={run_dir / "drc"}'], run_dir / 'klayout-drc.log')
    print(f'Completed {args.mode}; inspect raw results in {BUILD}')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
