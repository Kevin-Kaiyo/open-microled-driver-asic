#!/usr/bin/env python3
"""Compare only like-for-like first normal frames; preserve failed pre2."""
import difflib
from pathlib import Path
import run as a
def main():
 pairs=[]
 for v in ['trackwide4gm5pre2-fixed','trackwide4gm5buf2-fixed']:
  folder=a.BUILD/v/'TT-continuous-f1-s40';r=a.read(folder/'result.json');m=a.read(folder/'manifest.json');f=r['frames'][0];cap=sum(x['delta_pJ'] for x in f['explicit_storage_caps'].values())
  pairs.append(dict(variant=v,case_path=str(folder.relative_to(a.ROOT)),result_sha256=a.sha(folder/'result.json'),manifest_sha256=a.sha(folder/'manifest.json'),deck_sha256=m['deck_sha256'],source_inputs=m['inputs'],receiver=f['full_receiver'],frozen_phase=f['first_frame_phase_receiver'],energy_pJ_per_attempted_payload_bit=f['energy_pJ_per_attempted_payload_bit'],ports_positive_pJ_per_attempted_bit={k:e['positive_J']*1e12/4096 for k,e in f['source_energy_J'].items()},explicit_cap_delta_pJ=cap,explicit_cap_abs_delta_pJ=sum(abs(x['delta_pJ']) for x in f['explicit_storage_caps'].values()),mean_current_uA=f['mean_current_uA'],MOS=r['MOS'],terminal_pass=r['terminal_pass'],body_pass=r['body_pass']))
 x,y=pairs;assert x['deck_sha256']==y['deck_sha256'];assert {k:v for k,v in x['source_inputs'].items() if k!='route_a.spice'}=={k:v for k,v in y['source_inputs'].items() if k!='route_a.spice'}
 old=(a.BUILD/x['variant']/'inputs/route_a.spice').read_text().splitlines();new=(a.BUILD/y['variant']/'inputs/route_a.spice').read_text().splitlines();diff=[l for l in difflib.unified_diff(old,new) if l.startswith(('+','-')) and not l.startswith(('+++','---'))];assert len(diff)==4 and all(l[1:].startswith(('XN1 ','XP1 ')) for l in diff)
 e0=x['energy_pJ_per_attempted_payload_bit']['positive'];e1=y['energy_pJ_per_attempted_payload_bit']['positive'];a.emit(a.EV/'predriver-comparison.json',dict(cases=pairs,only_changed_transistor_lines=diff,Eplus_change_percent=100*(e1/e0-1),source_positive_energy_reduction_pJ=(e0-e1)*4096,explicit_cap_storage_delta_difference_pJ=y['explicit_cap_delta_pJ']-x['explicit_cap_delta_pJ'],scope='Same nominal first normal frame and PWL, same calibrated DC targets/load/RX. This is finite-record E+ per attempted payload bit; storage audit excludes MOS charge and is not a full energy balance. VDD-port reduction does not identify short-circuit current without per-device current traces.',new_version_fault_and_PVT_waveform_qualified=False))
if __name__=='__main__':main()
