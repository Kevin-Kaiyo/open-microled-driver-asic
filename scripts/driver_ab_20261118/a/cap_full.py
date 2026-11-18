"""Full SS 5.12 us regression for the ISO_G capacitor chosen in the edge test."""
from pathlib import Path
import run as a
import numpy as np
import sys
original_netlist=a.netlist

def cap_netlist(point,codes,level,mode,rs,variant):
    assert variant=='sensecap150' and level is None
    base,deck,route,m=original_netlist(point,codes,level,mode,rs,'sense')
    old='RGATE iso_g iso_p 100k'
    assert deck.count(old)==1
    deck=deck.replace(old,old+'\nCISOEDGE iso_g 0 150f')
    m['extra_caps'].append(['CISOEDGE',150e-15,'iso_g','0'])
    m['variant_source_sha256']=a.sha(__file__)
    m['variant_source_path']=str(Path(__file__).resolve().relative_to(a.ROOT))
    return base,deck,route,m

if __name__=='__main__':
    a.netlist=cap_netlist
    codes=tuple(a.read(a.EV/'SShotlow-ideal.json')['codes'])
    r=a.run('SShotlow',codes,None,'fault',variant='sensecap150')
    print(r['body_forward_V'],r['shutdown']['max_abs_current_uA'],r['frames'][-1]['full_receiver'],flush=True)
