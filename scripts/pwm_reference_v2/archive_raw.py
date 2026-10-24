#!/usr/bin/env python3
"""Lossless raw archival for ended cases; never touches a running case."""
from pathlib import Path
import gzip,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[2];W=ROOT/'build/pwm-reference-v2/20261024';E=ROOT/'evidence/pwm-reference-v2/20261024'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for p in sorted(W.rglob('*.dat')):
 if 'inputs' in p.parts:continue
 ended=(p.parent/'result.json').exists() or (p.parent.parent/'result.json').exists()
 if not ended:continue
 h=sha(p);gz=Path(str(p)+'.gz')
 if not gz.exists():
  with p.open('rb') as sf,gzip.open(gz,'wb',compresslevel=6) as df:shutil.copyfileobj(sf,df)
 check=hashlib.sha256()
 with gzip.open(gz,'rb') as f:
  while b:=f.read(1024*1024):check.update(b)
 assert check.hexdigest()==h
 keep=p.stat().st_size<1024*1024
 rows.append(dict(original=str(p.relative_to(ROOT)),gzip=str(gz.relative_to(ROOT)),raw_sha256=h,gzip_sha256=sha(gz),raw_bytes=p.stat().st_size,original_small_table_retained=keep))
 if not keep:p.unlink()
old=E/'raw-archive-inventory.json';past=json.loads(old.read_text())['files'] if old.exists() else [];byname={r['original']:r for r in past}
for r in rows:byname[r['original']]=r
old.write_text(json.dumps({'script_sha256':sha(Path(__file__)),'files':list(byname.values()),'note':'gzip roundtrip SHA verified; original smallAC/OP tables retained. Large partial raw recovered exactly from gzip; no result identity rewritten.'},indent=2)+'\n');print(len(rows),'raw files verified')
