#!/usr/bin/env python3
"""Three fixed final local-loop points with complete helper/manifests identities."""
from pathlib import Path
import subprocess,sys
HERE=Path(__file__).resolve().parent
for args in [
 ['--n2c','150','--cf','15','--rf','100','--corner','typical','--temp','27','--voltage','3.3','--led','5'],
 ['--n2c','165','--cf','16.5','--rf','105','--corner','ss','--temp','85','--voltage','2.97','--led','4.5'],
 ['--n2c','135','--cf','13.5','--rf','95','--corner','ff','--temp','0','--voltage','3.63','--led','5.5'],
]:
 subprocess.run([sys.executable,str(HERE/'loop.py'),'--cff','0','--pcb','--n2rl','--damp','10','--revision','frozen2',*args],check=True)
