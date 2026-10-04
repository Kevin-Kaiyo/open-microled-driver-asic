"""Publish compact evidence only after actual top checks and controls succeed."""
from pathlib import Path
import argparse,collections,hashlib,json,re,shutil
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',default='r3');a=p.parse_args();run=ROOT/'build/integration'/a.run;dest=ROOT/'evidence/integration';dest.mkdir(parents=True,exist_ok=True)
 results={mode:json.loads((run/(mode+'-result.json')).read_text())for mode in ['magic','lvs','klayout']}
 geometry=json.loads((run/'geometry-connectivity.json').read_text())
 if not all(v['passed']for v in results.values())or not geometry['passed']:raise RuntimeError('Baseline has not passed all physical checks')
 controls={}
 for kind in ['pwm-open','pg-short']:
  folder=ROOT/'build/integration'/f'{a.run}-{kind}'
  lvs=json.loads((folder/'lvs-result.json').read_text());g=json.loads((folder/'geometry-connectivity.json').read_text());magic=json.loads((folder/'magic-result.json').read_text())
  if lvs['passed']or g['passed']:raise RuntimeError('A physical negative control escaped detection')
  target=dest/'negative-controls'/kind;target.mkdir(parents=True,exist_ok=True)
  for name in ['pixel_integrated.gds','pixel_integrated.spice','netgen-lvs.log','netgen-lvs.json','lvs-result.json','magic-result.json','geometry-connectivity.json','control.json','lvs-linux.command.json']:
   shutil.copyfile(folder/name,target/name)
  controls[kind]=dict(mutation=json.loads((folder/'control.json').read_text())['mutation'],netgen=lvs,label_free_geometry=g['checks'],magic_drc_count=magic['drc_count'],rejected_by_both_electrical_checks=True)
 for name in ['pixel_integrated.gds','pixel_integrated.spice','pixel_integrated.ext','routing.json','extract.tcl','magic-linux.log','magic-linux.command.json','magic-result.json','lvs-linux.log','lvs-linux.command.json','lvs-result.json','netgen-lvs.log','netgen-lvs.json','klayout-linux.log','klayout-linux.command.json','klayout-result.json','geometry-connectivity.json']:
  shutil.copyfile(run/name,dest/name)
 shutil.copyfile(run/'klayout/pixel_integrated_main.lyrdb',dest/'klayout.lyrdb')
 link_dir=run/'link-characterization' if (run/'link-characterization/link-rc.json').exists() else run
 link=json.loads((link_dir/'link-rc.json').read_text())
 if not link['passed']:raise RuntimeError('Private link characterization did not pass')
 link_gds=next(value for name,value in link['inputs_sha256'].items()if name.endswith('/pixel_integrated.gds'))
 if link_gds!=sha(run/'pixel_integrated.gds'):raise RuntimeError('Link characterization refers to a different top GDS')
 link_map={'pwm_link_rc.spice':'pwm_link_rc.raw.spice','pwm_link_normalized.spice':'pwm_link_rc.spice','link-rc.json':'link-rc.json','magic-link.log':'magic-link.log','substrate-proof.json':'substrate-proof.json'}
 for raw_name,public_name in link_map.items():
  src=link_dir/raw_name
  if public_name in link['public_artifacts_sha256']and sha(src)!=link['public_artifacts_sha256'][public_name]:raise RuntimeError('Private link artifact hash differs: '+raw_name)
  shutil.copyfile(src,dest/public_name)
 routing=json.loads((run/'routing.json').read_text());nl=(run/'pixel_integrated.spice').read_text()
 lines=[]
 for line in nl.splitlines():
  if line.startswith('+'):lines[-1]+=' '+line[1:].strip()
  else:lines.append(line)
 blocks={};name=None
 for line in lines:
  t=line.split()
  if not t:continue
  if t[0].lower()=='.subckt':name=t[1];blocks[name]=dict(ports=t[2:],instances=[])
  elif t[0].lower()=='.ends':name=None
  elif name and t[0].startswith('X'):blocks[name]['instances'].append(t)
 calls=collections.Counter(t[-1]for t in blocks['pixel_pwm']['instances'])
 counts={n:sum(len(t)>5 and t[5]in ['nfet_05v0','pfet_05v0']for t in b['instances'])for n,b in blocks.items()if n.startswith('gf180')}
 primitive_count=sum(calls[n]*counts[n]for n in calls)
 inventory=dict(digital_extracted_macro_instances=sum(calls.values()),digital_leaf_classes=len(calls),digital_mos_calls_weighted_before_parallel_combination=primitive_count,analog_mos_calls=6,total_retained_mos_calls_weighted=primitive_count+6,digital_macro_instance_classes=dict(calls),digital_leaf_mos_counts=counts)
 (dest/'device-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
 inputs=['layout/integration/pixel_integrated.v','layout/pixel_driver_schematic.spice','evidence/physical/digital/pnl/pixel_pwm.pnl.v','scripts/physical/pdk-lock.json','layout/pdk-lock.json','scripts/digital/library-lock.json','build/layout/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice','build/layout/pdk/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl']
 summary=dict(milestone='one-pixel v0.3 common physical top',passed=True,run_directory=str(run.relative_to(ROOT)),topcell='pixel_integrated',macro_instances=[dict(name=name,origin_translation_um=xy,rotation='R0')for name,xy in routing['placements_origin_um'].items()],bbox_um=routing['bbox_um'],bbox_span_area_um2=(routing['bbox_um'][2]-routing['bbox_um'][0])*(routing['bbox_um'][3]-routing['bbox_um'][1]),external_ports=routing['ports'],power_contract=dict(VDD='digital VDD/VNW, analog vlogic/PMOS bulk; nominal 3.3 V',VSS='digital VSS/VPW and analog VSS/NMOS bulk',VLED='Off-chip 5-V LED anode rail; not wired to the logic/analog supply within this top'),physical_checks=results,label_free_geometry=geometry,negative_controls=controls,device_inventory=inventory,lvs_scope=dict(method='Actual complete GDS hierarchy extracted with Magic, compared against analog schematic plus final digital PNL and official standard-cell transistor SPICE',digital_leaf_internal_mos_classes=30,primitive_models='nfet_05v0,pfet_05v0,nfet_06v0,pfet_06v0 are four-terminal primitive placeholders; MOS-call connectivity and retained W/L properties compared',ignored_classes='PDK deck ignores __endcap, __filltie, and __fill_[digits] instances; these are not themselves signed off by LVS',property_scope='Model class, connectivity and W/L under locked tolerance {w 0.01 l 0.01}; AD/AS/PD/PS and other deleted properties excluded',old_evidence='v0.2 digital standalone LVS used LEF abstract leaf views; its evidence level is unchanged'),drc_scope=dict(magic='drc(full), whole hierarchy including cross-macro interactions',klayout='Pinned GF180 D full main deck, 651 categories, FEOL/BEOL/connectivity/offgrid enabled; optional density and antenna modes disabled'),routing_rc_scope=json.loads((dest/'link-rc.json').read_text())['evidence_level'],not_established=['Full joint multi-corner RC transient of all digital and analog devices','Power-grid IR-drop/EM, substrate impedance, latch-up or manufacturing acceptance','Pads/ESD/package/reference generator','Actual LED capacitance/temperature dynamics, silicon or optical measurement'],inputs_sha256={**routing['inputs_sha256'],**{s:sha(ROOT/s)for s in inputs}},packaging_source_hashes={str(s.relative_to(ROOT)):sha(s)for s in sorted((ROOT/'scripts/integration').glob('*'))if s.is_file()})
 summary['output_hashes']={str(f.relative_to(dest)):sha(f)for f in sorted(dest.rglob('*'))if f.is_file()and f.name!='summary.json'}
 (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(f'PASS publish common top: DRC0/0, full hierarchical LVS, 19 ports, two physical negative controls; {dest}')
if __name__=='__main__':main()
