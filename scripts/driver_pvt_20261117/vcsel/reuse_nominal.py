#!/usr/bin/env python3
"""Record explicit reuse of the exact previously verified TT25 complete frame."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import run

def main():
 p=run.BASE;m=run.read(p/'manifest.json');a=run.read(p/'analysis.json');r=run.read(p/'result.json');short=run.read(run.BUILD/'frozen/tt25/short-net8.8-s40/manifest.json')
 assert m['interface_config']['candidate']=='single-phy12' and m['net_Gbps']==8.8 and m['steps_per_UI']==40 and len(m['devices'])==73
 assert m['ports']==short['ports'] and m['devices']==short['devices']
 assert all(run.sha(p/n)==h for n,h in m['source_sha256'].items() if n in run.FILES)
 assert all(m['source_sha256'][n]==short['source_sha256'][n] for n in run.FILES)
 assert run.sha(p/'testbench.spice')==m['deck_sha256'] and run.sha(p/'stimulus.json')==m['stimulus_sha256']
 assert run.read(p/'stimulus.json')['bits'][:1024]==run.read(run.BUILD/'frozen/tt25/short-net8.8-s40/stimulus.json')['bits']
 assert a['combined_screen_pass'] and r['simulation_ok']
 record=dict(schema='vcsel-pvt-reused-nominal-v1',kind='historical_verified_full_frame_reuse_not_new_SPICE',case=str(p.relative_to(run.ROOT)),conditions=dict(process='typical',temp_C=25,rail_scale=1,net_Gbps=8.8,steps_per_UI=40,line_bits=4736,payload_bits=4096,source_edge_ps=20,variant='frozen'),manifest_sha256=run.sha(p/'manifest.json'),result_sha256=run.sha(p/'result.json'),analysis_sha256=run.sha(p/'analysis.json'),deck_sha256=run.sha(p/'testbench.spice'),stimulus_sha256=run.sha(p/'stimulus.json'),source_sha256={n:run.sha(p/n) for n in run.FILES},waveform=r['waveform'],prior_freeze=str((run.EV.parent.parent/'driver-interface-20261115/vcsel-interface-freeze.json').relative_to(run.ROOT)),scope='Device inventory,source files,ports and first1024 actual bits match new frozen TT25 short probe. Exact previous nominal full result is reused with its original raw hashes, not silently rebranded a new PVT run.')
 run.emit(run.EV/'nominal-reuse.json',record)
if __name__=='__main__':main()
