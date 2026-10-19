"""Publish compact actual physical evidence; does not certify circuit operation."""
from pathlib import Path
import json,hashlib,re,shutil,xml.etree.ElementTree as ET,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];run=ROOT/(sys.argv[1] if len(sys.argv)>1 else 'build/layout-v3/r5');out=ROOT/(sys.argv[2] if len(sys.argv)>2 else 'evidence/layout-v3/r5');out.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def ck(name,passed):checks.append(dict(name=name,passed=bool(passed)));assert passed,name
for name,token in [('magic-generate.log','V3_DRC_COUNT 0'),('magic-roundtrip-pex.log','ROUNDTRIP_DRC_COUNT 0')]:ck(name,token in (run/name).read_text() and 'DRC style is now "drc(full)"' in (run/name).read_text())
for name in ['netgen-lvs.log','netgen-roundtrip-lvs.log']:
 text=(run/name).read_text();ck(name,re.findall(r'^Final result:\s*(.+)$',text,re.M)==['Circuits match uniquely.']and not re.search(r'property errors|do not match|not equivalent',text,re.I))
text=(run/'magic-roundtrip-pex.log').read_text();ck('all nets include PG', 'Nets extracted: 29 (1.000000)'in text)
ck('KLayout independent main deck',json.loads((run/'klayout-result.json').read_text())['item_count']==0)
controls=json.loads((run/'negative-controls.json').read_text());ck('Actual physical open and PG short rejected',len(controls)==2 and all(x['rejected']for x in controls))
rc=(run/'roundtrip/startup_test_macro_rc.spice').read_text();counts={key:sum(line.startswith(prefix)for line in rc.splitlines())for key,prefix in [('mos','X'),('resistors','R'),('capacitors','C')]};ck('39 MOS extracted',counts['mos']==39)
for name in ['magic-generate.log','magic-roundtrip-pex.log','netgen-lvs.log','netgen-roundtrip-lvs.log','klayout-linux.log','klayout-command.json','klayout-result.json','negative-controls.json']:shutil.copyfile(run/name,out/name)
for mode in ['raw-open','vref-ground-short']:
 dest=out/'negative-controls'/mode;dest.mkdir(parents=True,exist_ok=True)
 for name in ['netgen-lvs.log','magic.log']:shutil.copyfile(run/mode/name,dest/name)
for folder,name in [('generate','startup_test_macro.gds'),('roundtrip','startup_test_macro.spice'),('roundtrip','startup_test_macro_rc.spice')]:shutil.copyfile(run/folder/name,out/name)
shutil.copyfile(run/'generate/startup_test_macro.mag',ROOT/'layout/startup_v3/startup_test_macro.mag')
pdk=ROOT/'build/layout/pdk/gf180mcuD';tool=ROOT/'build/layout/tools/install/bin';versions=dict(magic=subprocess.check_output([str(tool/'magic'),'--version'],text=True).strip(),netgen=subprocess.check_output([str(tool/'netgen'),'-batch','quit'],stderr=subprocess.STDOUT,text=True).splitlines()[0],klayout='0.30.7 (pinned LibreLane Linux image; see command manifest)')
files=[p for folder in ['scripts/layout_v3','layout/startup_v3']for p in (ROOT/folder).glob('*')if p.is_file()];files += [ROOT/'layout/pdk-lock.json',pdk/'libs.tech/magic/gf180mcuD.tech',pdk/'libs.tech/netgen/gf180mcuD_setup.tcl',pdk/'libs.tech/klayout/tech/drc/gf180mcu.drc',pdk/'libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice',pdk/'libs.ref/gf180mcu_fd_sc_mcu7t5v0/gds/gf180mcu_fd_sc_mcu7t5v0.gds']
snapshot=run/'source-snapshot'
for p in files:
 dest=snapshot/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
summary=dict(source_snapshot=str(snapshot.relative_to(ROOT)),schema=1,scope='New 39-MOS external-passive test macro, no pad ring/ESD/package/POR',physical_checks_passed=all(x['passed']for x in checks),electrical_checks_passed='separate analog-v3 report required',external_signoff=False,run_directory=str(run.relative_to(ROOT)),tools=versions,checks=checks,extracted_counts=counts,rc_nets_extracted=29,rc_nets_total=29,negative_controls=controls,source_sha256={str(p.relative_to(ROOT)):sha(p)for p in files},output_sha256={str(p.relative_to(ROOT)):sha(p)for p in out.iterdir()if p.is_file()and p.name!='summary.json'},failures_preserved=[dict(run='build/layout-v3/r1',reason='official buffer M2 power/output columns too close; spaced columns'),dict(run='build/layout-v3/r2',reason='official buffer isolated N-well: no body tap, LVS rejected; adjacent official filltie restores VBUF bulk')],lvs_scope='Connectivity, MOS classes and W/L with PDK property tolerance; AD/AS/PD/PS excluded by pinned Netgen setup; extracted geometry used in PEX',boundary='External VSET, RSET, RBIAS, CCOMP and RRELEASE. Full extracted local power/ground. No off-chip pad/ESD/bond/PCB RC or internal POR. DRC KLayout main deck alone does not establish density/antenna/manufacturing acceptance.')
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(dict(checks=len(checks),physical_passed=True,counts=counts)))
