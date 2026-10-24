"""Publish a complete small physical run with byte verification; never replace evidence."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
from validate import validate

ROOT=Path(__file__).resolve().parents[2]
ALLOWED={'.py','.gds','.mag','.spice','.ext','.json','.log','.tcl','.lyrdb','.cir','.md','.txt','.drc'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    raw=ROOT/a.run;out=ROOT/a.out
    check=validate(raw)
    files=[]
    for p in sorted(raw.rglob('*')):
        if not p.is_file():continue
        assert p.suffix in ALLOWED,p
        dest=out/p.relative_to(raw);dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert sha(dest)==sha(p),f'Refusing overwrite: {dest}'
        else:shutil.copyfile(p,dest)
        assert sha(dest)==sha(p)
        files.append(dict(path=str(dest.relative_to(out)),source=str(p.relative_to(ROOT)),sha256=sha(dest),size=dest.stat().st_size))
    summary=dict(schema_version=1,physical_validation=check,source_run=a.run,
       scope='Actual experimental transistor-core GDS, DRC, LVS, PEX and fault controls; electrical performance validated separately.',
       exclusions=['Full PDK','Tool binaries','Transient waveform data','Package/EM/IR/ESD/pad/full-chip/silicon signoff'],
       copied_files=files)
    p=out/'publication.json';data=(json.dumps(summary,indent=2)+'\n').encode()
    if p.exists():assert p.read_bytes()==data
    else:p.write_bytes(data)
    print(json.dumps(dict(out=a.out,files=len(files),bytes=sum(x['size'] for x in files),passed=True)))
if __name__=='__main__':main()
