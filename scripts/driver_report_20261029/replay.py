#!/usr/bin/env python3
"""Regenerate a selected saved experiment in a new directory on this computer."""
from pathlib import Path
import argparse,hashlib,importlib.util,json
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('case');p.add_argument('--prefix',default='replay');a=p.parse_args()
 assert '/' not in a.case and '/' not in a.prefix
 saved=ROOT/'build/vcsel-robustness-20261029'/a.case
 manifest=json.loads((saved/'manifest.json').read_text());cfg=manifest['config']
 assert cfg.get('mode') in ['dc','frame','startup'],'Special startup-frame/AC cases use their dedicated entrypoint; see reproduce.md'
 rev=cfg.get('revision');script='run.py' if rev is None else 'run_'+rev+'.py'
 path=ROOT/'scripts/vcsel_robustness_20261029'/script
 spec=importlib.util.spec_from_file_location('replay_runner',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 assert m.circuit(cfg['variant'])==(saved/'inputs/driver.spice').read_text(),'Source differs from the saved circuit'
 name=a.prefix+'-'+a.case
 assert not (m.BUILD/name).exists(),'Use a new prefix; existing evidence is immutable'
 m.run(name,**cfg)
 if cfg['mode']=='frame':print('Next: python scripts/vcsel_robustness_20261029/analyze.py '+name+' --label fixed-v3-r2 --grid-ps 2.5')
if __name__=='__main__':main()
