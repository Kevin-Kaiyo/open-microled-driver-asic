"""Reproduce both independent candidates and restore the candidate-index summary."""
from pathlib import Path
import shutil, subprocess, sys
ROOT=Path(__file__).resolve().parents[2]
def run(name,*args):subprocess.run([sys.executable,str(ROOT/'scripts/reference'/name),*args],cwd=ROOT,check=True)
run('run.py')
shutil.copyfile(ROOT/'evidence/reference/summary.json',ROOT/'evidence/reference/beta-summary.json')
run('servo.py')
run('validate.py','beta')
run('validate.py','servo')
run('servo_boundaries.py')
run('junction_sensitivity.py')
run('junction_zero_area_control.py')
run('validate_sensitivity.py')
run('index.py')
