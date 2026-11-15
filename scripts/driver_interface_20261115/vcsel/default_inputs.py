#!/usr/bin/env python3
"""DC open-cable/default-bias diagnostic, not upstream power-down or laser shutdown."""
from pathlib import Path
import argparse,copy,re,shutil,subprocess,time
import numpy as np
import run
def main(name):
 base=run.BUILD/name/'DC-L0';folder=run.BUILD/'_diagnostics'/('open-input-'+name)
 assert (base/'result.json').exists()
 if (folder/'result.json').exists():return
 folder.mkdir(parents=True,exist_ok=False);m=copy.deepcopy(run.read(base/'manifest.json'))
 for f in ['design.ngspice','sm141064.ngspice','vcsel.spice','driver.spice']:shutil.copy2(base/f,folder/f)
 shutil.copytree(base/'execution-sources',folder/'execution-sources')
 deck=(base/'testbench.spice').read_text();deck,n=re.subn(r'(?m)^XPHY[^\n]*\n','',deck);assert n==4
 (folder/'testbench.spice').write_text(deck);(folder/'execution-source.py').write_bytes(Path(__file__).read_bytes())
 m.update(schema='vcsel-open-input-diagnostic-v1',diagnostic_kind='physical_open_cable_DC_not_shutdown',case_source=str(base.relative_to(run.ROOT)),parent_manifest_sha256=run.sha(base/'manifest.json'),deck_sha256=run.sha(folder/'testbench.spice'),execution_source_sha256=run.sha(folder/'execution-source.py'),scope='Both upstream output inverters physically disconnected: pins have only resistor shunts. DC default only; not supply-off/backpower/ESD or safe optical shutdown. No transient release-time claim.')
 m['devices']=[x for x in m['devices'] if not x['instance'].startswith('XPHY')];run.emit(folder/'manifest.json',m)
 with (folder/'ngspice.log').open('w') as f:code=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,stdout=f,stderr=subprocess.STDOUT,timeout=120).returncode
 assert code==0;a=np.atleast_2d(np.loadtxt(folder/'waveform.dat',skiprows=1));ix={e:i+1 for i,e in enumerate(m['expressions'])};legacy=run.engine.module(run.engine.LEGACY,'open_input_stress');stress=legacy.stress(a,ix,m['devices'])
 r=dict(exit_code=code,simulation_ok=True,nodes_final_V={k:float(a[-1,ix['v('+k+')']]) for k in ['d_src','db_src','xdrv.di','xdrv.dbi','xdrv.gp','xdrv.gn']},current_mA=float(a[-1,1]*1e3),terminal_screen_pass=all(s['screen_pass'] for s in stress),max_body_forward_V=max(s['max_body_forward_V'] for s in stress),stress=stress,waveform=legacy.compress(folder/'waveform.dat'),manifest_sha256=run.sha(folder/'manifest.json'),deck_sha256=run.sha(folder/'testbench.spice'),scope=m['scope'])
 r['pins_default_low']=max(abs(r['nodes_final_V'][k]) for k in ['xdrv.di','xdrv.dbi'])<.01
 r['laser_is_not_shut_down']=r['current_mA']>1
 run.emit(folder/'result.json',r);run.emit(run.EV/('vcsel-default-input-'+name+'.json'),dict(case=str(folder.relative_to(run.ROOT)),result_sha256=run.sha(folder/'result.json'),**{k:r[k] for k in ['nodes_final_V','current_mA','terminal_screen_pass','max_body_forward_V','pins_default_low','laser_is_not_shut_down','waveform','scope']}));print(name,r['current_mA'],r['pins_default_low'],flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('candidate',choices=run.SPECS);main(p.parse_args().candidate)
