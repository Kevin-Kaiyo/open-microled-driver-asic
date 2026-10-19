#!/usr/bin/env python3
"""Validate/recover completed NRZ traces after archive-stage storage failure.

Default is inspection only. --recover never launches ngspice: it verifies the
original deck against its frozen generator, scans every raw sample, preserves
its byte hash in standard results, and validates gzip before removing raw.
Incomplete or numerically failed traces remain untouched and unaccepted.
"""
from pathlib import Path
import argparse, gzip, hashlib, importlib.util, json, math, re, shutil, sys, zlib

ROOT=Path(__file__).resolve().parents[2]

def sha(path):
    with path.open('rb') as f:return stream_digest(f)[0]

def stream_digest(stream):
    h=hashlib.sha256();size=0
    while True:
        b=stream.read(1024*1024)
        if not b:break
        h.update(b);size+=len(b)
    return h.hexdigest(),size

def rel(path):return str(path.relative_to(ROOT))

def inspect(folder,runner,work):
    result={'case_folder':rel(folder),'recoverable':False}
    required=['case.json','testbench.spice','ngspice.log','waveform.dat']
    missing=[name for name in required if not (folder/name).exists()]
    if missing:return result|{'reason':'missing files','missing':missing}
    case=json.loads((folder/'case.json').read_text())
    if 'dc_bit' in case:return result|{'reason':'this recovery only accepts transient cases'}
    deck,vectors,devices,rails=runner.build_deck(work,case)
    if (folder/'testbench.spice').read_text()!=deck:
        return result|{'reason':'deck differs from frozen generator'}
    log=(folder/'ngspice.log').read_text()
    if re.search(r'(?im)^Error:|timestep too small|simulation interrupted|fatal error|tran simulation\(s\) aborted|doAnalyses:',log):
        return result|{'reason':'simulation error reported in original log'}
    if 'ngspice-' not in log or ' done' not in log:
        return result|{'reason':'missing normal ngspice completion text'}
    raw=folder/'waveform.dat';h=hashlib.sha256();rows=0;previous=None;cols=len(vectors)+1
    with raw.open('rb') as f:
        header=f.readline();h.update(header)
        if len(header.split())!=cols:return result|{'reason':'unexpected raw header vector count'}
        for line in f:
            h.update(line)
            try:values=list(map(float,line.split()))
            except ValueError:return result|{'reason':'unparseable raw data','line':rows+2}
            if len(values)!=cols or not all(map(math.isfinite,values)):
                return result|{'reason':'wrong vector count or nonfinite raw data','line':rows+2}
            if previous is not None and values[0]<=previous:
                return result|{'reason':'time not strictly increasing','line':rows+2}
            previous=values[0];rows+=1
    expected_stop=len(runner.stimulus()['bits'])/(case['rate_Gbps']*1e9)
    if rows<2 or previous is None or abs(previous-expected_stop)>1e-18:
        return result|{'reason':'incomplete transient','last_time_s':previous,'expected_stop_s':expected_stop,'rows':rows}
    logged=re.findall(r'No\. of Data Rows\s*:\s*(\d+)',log)
    if not logged or int(logged[-1])!=rows:
        return result|{'reason':'row count differs from original completion log','rows':rows,'logged_counts':logged}
    return result|{'recoverable':True,'case':case,'raw_sha256':h.hexdigest(),'raw_bytes':raw.stat().st_size,'rows':rows,
                   'last_time_s':previous,'expected_stop_s':expected_stop,'vectors':vectors,'devices':devices,
                   'rails':rails,'warnings':[s for s in log.splitlines() if 'warning' in s.lower()],
                   'deck_sha256':sha(folder/'testbench.spice'),'log_sha256':sha(folder/'ngspice.log')}

def recover(folder,check,runner_hash):
    assert check['recoverable'] and not (folder/'result.json').exists()
    raw=folder/'waveform.dat';archive=folder/'waveform.dat.gz'
    archive_info={'existing_archive':archive.exists()}
    usable=False
    if archive.exists():
        archive_info.update(previous_archive_sha256=sha(archive),previous_archive_bytes=archive.stat().st_size)
        try:
            with gzip.open(archive,'rb') as f:h,size=stream_digest(f)
            usable=h==check['raw_sha256'] and size==check['raw_bytes']
            archive_info['previous_archive_validation']='matches raw' if usable else 'decoded content differs from raw'
        except (OSError,EOFError,zlib.error) as exc:
            archive_info['previous_archive_validation']=type(exc).__name__+': '+str(exc)
    if not usable:
        temp=folder/'waveform.dat.gz.recovery.partial'
        if temp.exists():raise RuntimeError(f'Preserve and inspect existing temporary archive before retry: {temp}')
        with raw.open('rb') as f,gzip.open(temp,'wb',compresslevel=6) as g:
            shutil.copyfileobj(f,g,1024*1024)
        with gzip.open(temp,'rb') as f:h,size=stream_digest(f)
        assert h==check['raw_sha256'] and size==check['raw_bytes'],'gzip round-trip mismatch'
        # Only replace a known-invalid archive after the new one is verified.
        temp.replace(archive)
    archive_info['action']='reused existing verified gzip' if usable else 'created and verified replacement gzip'
    gzsha=sha(archive)
    result={'case':check['case'],'simulation_ok':True,'exit_code':None,'elapsed_s':None,
            'waveform':rel(archive),'uncompressed_sha256':check['raw_sha256'],'waveform_sha256':gzsha,
            'deck_sha256':check['deck_sha256'],'vectors':{key:i+1 for i,(key,_) in enumerate(check['vectors'])},
            'devices':check['devices'],'rails':{k:{'node':pin,'voltage_V':v} for k,(pin,v) in check['rails'].items()},
            'rows':check['rows'],'warnings':check['warnings'],
            'storage_recovery':{'reason':'original run finished but archive/result stage was interrupted by disk exhaustion',
               'validation':'every original raw row finite, ordered, correct vector count; exact stop; row count matches log; deck equals frozen generator; no logged solver errors',
               'original_log':rel(folder/'ngspice.log'),'original_log_sha256':check['log_sha256'],
               'last_time_s':check['last_time_s'],'expected_stop_s':check['expected_stop_s'],
               'uncompressed_bytes':check['raw_bytes'],'archive_bytes':archive.stat().st_size,
               'round_trip_sha256_verified':True,'ngspice_rerun':False,
               'original_exit_code_and_elapsed':'not persisted; null rather than invented',
               'frozen_runner_sha256':runner_hash,'recovery_script_sha256':sha(Path(__file__)),
               'archive':archive_info}}
    temp_result=folder/'result.json.recovery.tmp'
    temp_result.write_text(json.dumps(result,indent=2)+'\n');temp_result.replace(folder/'result.json')
    assert json.loads((folder/'result.json').read_text())['uncompressed_sha256']==check['raw_sha256']
    raw.unlink()
    return {'case':check['case']['name'],'status':'recovered','archive_action':archive_info['action'],
            'rows':check['rows'],'freed_raw_bytes':check['raw_bytes'],'result':rel(folder/'result.json')}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',default='build/highspeed-nrz/run-0xqxvspp')
    ap.add_argument('--recover',action='store_true');args=ap.parse_args()
    work=(ROOT/args.work).resolve();manifest=json.loads((work/'manifest.json').read_text())
    runner_path=work/'inputs/scripts/highspeed_nrz/run.py';runner_hash=sha(runner_path)
    assert runner_hash==manifest['inputs']['scripts/highspeed_nrz/run.py']
    for name in ['analog/highspeed_nrz/voltage_driver.spice','analog/highspeed_nrz/steering_driver.spice',
                 'analog/models/measured-led/lin2026-yellow20-dc.spice']:
        assert sha(work/'inputs'/name)==manifest['inputs'][name]
    for name in ['design.ngspice','sm141064.ngspice']:
        assert sha(work/'inputs/pdk'/name)==manifest['inputs']['build/layout/pdk/gf180mcuD/libs.tech/ngspice/'+name]
    spec=importlib.util.spec_from_file_location('frozen_storage_recovery_runner',runner_path)
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner);runner.ROOT=ROOT
    outputs=[]
    for folder in sorted((work/'cases').iterdir()):
        if not folder.is_dir() or (folder/'result.json').exists():continue
        check=inspect(folder,runner,work)
        if check['recoverable'] and args.recover:record=recover(folder,check,runner_hash)
        else:record={k:v for k,v in check.items() if k not in ['vectors','devices','rails','case','warnings']}
        outputs.append(record);print(json.dumps(record),flush=True)
    if args.recover:
        receipt={'mode':'storage recovery without ngspice execution','work':rel(work),'script_sha256':sha(Path(__file__)),
                 'python':sys.version,'cases':outputs}
        (work/'storage-recovery.json').write_text(json.dumps(receipt,indent=2)+'\n')
    if any(r.get('recoverable') is False for r in outputs):raise SystemExit(2)

if __name__=='__main__':main()
