"""Retain compact real extraction logs/raw nominal data and tool conditions."""
from pathlib import Path
from collections import Counter
import gzip,json
from export import ROOT,number,sha
from publish import write_frozen

def main():
 base=ROOT/'evidence/joint-pex';rawout=base/'raw';records={};archives={}
 for style in ['hierarchical-nominal','nominal','hrhc','lrhc','hrlc','lrlc','reproduction-nominal']:
  run='full-nominal-r1'if style=='hierarchical-nominal'else'flat-nominal-r3'if style=='nominal'else'reproduce-nominal-r1'if style=='reproduction-nominal'else'flat-'+style+'-r2';directory=ROOT/'build/joint-pex'/run;q=json.loads((directory/'extraction.json').read_text());spice=directory/('pixel_integrated_rc.spice'if style=='hierarchical-nominal'else'pixel_flat_rc.spice');lines=[l.split()for l in spice.read_text().splitlines()if l.startswith(('X','R','C'))];caps=[t for t in lines if t[0][0]=='C'];neg=[t for t in caps if number(t[3])<0]
  records[style]=dict(run=str(directory.relative_to(ROOT)),extraction=q,raw_counts=dict(Counter(t[0][0]for t in lines)),negative_C_count=len(neg),negative_C_sum_f=str(sum((number(t[3])for t in neg),start=number('0'))),most_negative_C_f=str(min((number(t[3])for t in neg),default=number('0'))))
  files=['extraction.json','extract.tcl','magic.log']
  if style in ['nominal','hierarchical-nominal','reproduction-nominal']:files+=[spice.name,*[f.name for f in directory.glob('*.ext')]]
  for name in files:
   src=directory/name;dest=rawout/style/(name+'.gz');write_frozen(dest,gzip.compress(src.read_bytes(),mtime=0));archives[str(dest.relative_to(base))]=dict(public_sha256=sha(dest),decompressed_sha256=sha(src),source_path=str(src.relative_to(ROOT)))
 tech=ROOT/'build/layout/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.tech'
 report=dict(passed=all(z['extraction']['passed']and z['extraction']['drc_count']==['0']for z in records.values()),input_gds_sha256=sha(ROOT/'evidence/integration/pixel_integrated.gds'),records=records,public_archives=archives,rc_deck=dict(path=str(tech.relative_to(ROOT)),sha256=sha(tech),style_declaration='ngspice variants (),(hrhc),(lrhc),(hrlc),(lrlc)',locator_lines=[3248,3305,3357,3409,3455],meaning='Real nominal/high-R high-C/low-R high-C/high-R low-C/low-R low-C extraction variants, separate from MOS TT/SS/FF.',key_resistance_coefficients=dict(units='milli-ohm per square; contact values in milli-ohm',nominal=dict(M1_M4=90,M5=40,ndiff=6300,pdiff=7000,poly=7300,nd_contact=6300,pd_contact=5200,poly_contact=8000,via_contact=4500),high_R=dict(M1_M4=104,M5=49,ndiff=15000,pdiff=15000,poly=15000,contacts=15000),low_R=dict(M1_M4=76,M5=31,ndiff=1000,pdiff=1000,poly=1000,contacts=0))),scope='Complete frozen geometry was read, then eligible nets were extresist-resolved. Raw full hierarchy contains signed overlap correction capacitors and is not a simulation-ready full-chip model. Flat cutout removes all ideal-PG fixed-voltage-only terms, including 19 negatives, while retaining signal coupling. No full-chip transient/IR/EM/substrate signoff.',exploratory_failure=dict(run='build/joint-pex/flat-nominal-r1',reason='Complement diffusion node was incorrectly probed as Metal1; Magic moved that label to space. This probe is excluded from all frozen final runs; the raw log and initial source snapshot remain local.'),existing_LVS=dict(summary='evidence/integration/summary.json',sha256=sha(ROOT/'evidence/integration/summary.json'),condition='Frozen GDS geometry identical; v0.3 full retained standard-cell MOS LVS remains applicable. New PEX projection and A/P checked separately, no claim that original LVS checked junction A/P.'))
 (base/'extraction-method.json').write_text(json.dumps(report,indent=2)+'\n');print('archived',len(archives),'files; method passed',report['passed'])
if __name__=='__main__':main()
