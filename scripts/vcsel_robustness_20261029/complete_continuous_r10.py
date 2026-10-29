#!/usr/bin/env python3
"""Resume r10 startup-to-data checks without overwriting the timed-out trial.

The restored runner differs from the frozen runner only in its subprocess
wall-clock timeout (360 -> 900 s); circuit, solver and data timing are unchanged.
"""
import json
from pathlib import Path
import run_continuous_restored_r10 as runner
from extract_frame_r10 import extract
from analyze_continuous import analyze


def main():
    original=Path(runner.__file__).with_name('run_continuous_r10.py')
    assert Path(runner.__file__).read_text()==original.read_text().replace('timeout=360','timeout=900')
    rows=[]
    for label,corner,temp,voltage in [('TT','typical',25,3.3),('SS','ss',125,2.97),('FF','ff',-40,3.63)]:
        name=f'continuous-{label}-r10-restored'
        r=runner.run(name,variant='regulated',mode='startup_frame',level=1,
                     corner=corner,temp=temp,voltage=voltage,steps=.27)
        assert r['simulation_ok'],name
        frame=extract(name)
        a=analyze(frame,grid_ps=2.5,label='continuous-v3-r1')
        rows.append(dict(case=name,frame=frame,analysis='continuous-v3-r1',
                         simulation_ok=r['simulation_ok'],passed=a['combined_screen_passed']))
        runner.emit(runner.BUILD/'continuous-r10-restored-progress.json',{'cases':rows})
    print(json.dumps({'completed':rows},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
