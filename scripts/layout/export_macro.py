"""Export the verified analog macro's real LEF, with explicit port contract."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import klayout.db as kdb

ROOT=Path(__file__).resolve().parents[2]


def main():
    summary=json.loads((ROOT/'evidence/layout/summary.json').read_text())
    if not summary['passed'] or summary['physical_checks']['lvs_property_errors']:
        raise RuntimeError('Verified physical evidence is required before macro export')
    raw=ROOT/'build/layout';raw.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='macro-',dir=raw))
    source=ROOT/'layout/pixel_driver_layout.mag'
    shutil.copyfile(source,work/source.name)
    magic=ROOT/'build/layout/tools/install/bin/magic'
    tech=ROOT/'build/layout/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc'
    script=ROOT/'scripts/layout/export_macro.tcl'
    gds=ROOT/'evidence/layout/pixel_driver_layout.gds'
    layout=kdb.Layout();layout.read(str(gds));bbox=layout.top_cell().bbox()
    bbox_um=[x*layout.dbu for x in [bbox.left,bbox.bottom,bbox.right,bbox.top]]
    # Pinned Magic technology uses 0.005um internal coordinates. Its GDS well
    # bias can enlarge the painted bbox; the routing abstract must enclose it.
    fixed=[round(x/.005) for x in bbox_um]
    if any(abs(x*.005-y)>1e-9 for x,y in zip(fixed,bbox_um)):
        raise RuntimeError('GDS bbox does not align with pinned Magic grid')
    command=[str(magic),'-dnull','-noconsole','-rcfile',str(tech),str(script)]
    p=subprocess.run(command,cwd=work,env=os.environ|{'PDK_ROOT':str(ROOT/'build/layout/pdk'),
                     'MACRO_BBOX':' '.join(f'{x:.6f}um' for x in bbox_um)},
                     capture_output=True,text=True)
    (work/'magic-export.log').write_text(p.stdout+p.stderr)
    lef=work/'pixel_driver_layout.lef'
    if p.returncode or not lef.exists() or 'END pixel_driver_layout' not in lef.read_text():
        raise RuntimeError(f'Macro export failed: {work}')
    text=lef.read_text()
    size=list(map(float,re.search(r'SIZE ([\d.]+) BY ([\d.]+)',text).groups()))
    if any(abs(a-b)>1e-6 for a,b in zip(size,[bbox_um[2]-bbox_um[0],bbox_um[3]-bbox_um[1]])):
        raise RuntimeError('LEF and actual GDS dimensions disagree')
    expected={'VSS':'INOUT','vlogic':'INOUT','pwm':'INPUT','bias':'INOUT',
              'gate':'OUTPUT','pwm_b':'OUTPUT','led_k':'INOUT'}
    for pin,direction in expected.items():
        if f'PIN {pin}\n' not in text:raise RuntimeError('Missing real macro pin: '+pin)
        section=text.split(f'PIN {pin}\n')[1].split(f'END {pin}')[0]
        if f'DIRECTION {direction} ;' not in section:
            raise RuntimeError('Missing macro pin direction: '+pin)
    dest=ROOT/'evidence/layout/pixel_driver_layout.lef'
    shutil.copyfile(lef,dest)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    data=dict(evidence_level='routing abstract derived from verified standalone analog layout',
              independent_signoff=False,raw_directory=str(work.relative_to(ROOT)),
              gds_bbox_um=bbox_um,lef_size_um=size,
              ports=dict(VSS='ground',vlogic='3.3 V analog-control supply',pwm='registered digital control input',
                         bias='external reference-current injection',led_k='external LED cathode',
                         gate='analog gate monitor',pwm_b='inverted PWM monitor'),
              source_hashes={str(p.relative_to(ROOT)):digest(p) for p in [source,gds,script,Path(__file__),ROOT/'evidence/layout/summary.json']},
              output_hashes={str(dest.relative_to(ROOT)):digest(dest)})
    (ROOT/'evidence/layout/macro-views.json').write_text(json.dumps(data,indent=2)+'\n')
    print(f'Exported actual LEF with 7 ports: {dest}')


if __name__=='__main__':main()
