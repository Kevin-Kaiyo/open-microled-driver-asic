#!/usr/bin/env python3
"""Run FF alongside the already-running SS simulator without duplicate cases.

The sequential orchestrator is paused only while waiting for its SS child;
ngspice is not paused. Once FF has a compressed result, the orchestrator resumes
and reuses it. This coordination changes no simulation input or output.
"""
import argparse, os, signal, subprocess
from run_continuous_restored_r10 import BUILD, run


def main():
    p=argparse.ArgumentParser();p.add_argument('--waiting-orchestrator-pid',type=int,required=True);a=p.parse_args()
    command=subprocess.check_output(['ps','-p',str(a.waiting_orchestrator_pid),'-o','command='],text=True)
    assert 'complete_continuous_r10.py' in command,command
    assert (BUILD/'continuous-SS-r10-restored'/'manifest.json').exists()
    assert not (BUILD/'continuous-SS-r10-restored'/'result.json').exists()
    assert not (BUILD/'continuous-FF-r10-restored').exists()
    def terminate(_signum,_frame):raise SystemExit('Terminated; resume sequential orchestrator')
    signal.signal(signal.SIGTERM,terminate)
    os.kill(a.waiting_orchestrator_pid,signal.SIGSTOP)
    try:
        r=run('continuous-FF-r10-restored',variant='regulated',mode='startup_frame',level=1,
              corner='ff',temp=-40,voltage=3.63,steps=.27)
        assert r['simulation_ok'],'FF recovery requires diagnosis; original result preserved'
    finally:
        os.kill(a.waiting_orchestrator_pid,signal.SIGCONT)


if __name__=='__main__':main()
