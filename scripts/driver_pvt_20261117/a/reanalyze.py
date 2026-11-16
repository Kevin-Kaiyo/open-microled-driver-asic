#!/usr/bin/env python3
"""Recover analysis-failed new-stage cases without altering original evidence."""
import argparse,gzip,hashlib,shutil,time
from pathlib import Path
import numpy as np
import run as a
import analyze_case as analyzer
def main(folder):
 folder=Path(folder).resolve();assert folder.is_relative_to(a.BUILD)
 r=a.read(folder/'result.json');m=a.read(folder/'manifest.json');assert r['simulation_ok'] and r.get('analysis_error')
 assert a.sha(folder/'waveform.dat.gz')==r['gzip_sha256']
 scratch=folder/'reanalysis';scratch.mkdir(exist_ok=True)
 for name in ['ngspice.log','stimulus.json']:shutil.copy2(folder/name,scratch/name)
 with gzip.open(folder/'waveform.dat.gz','rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['raw_sha256']
 raw=np.loadtxt(folder/'waveform.dat.gz',skiprows=1,ndmin=2);assert np.all(np.diff(raw[:,0])>0) and abs(raw[-1,0]-m['end_s'])<1e-14
 out=analyzer.summarize_case(scratch,m,raw)
 out.update(schema='a-pvt-append-only-reanalysis-v1',correction='Recovery empty threshold crossings now use observation boundaries, exactly as normal horizontal-margin scoring. Same waveform, thresholds, phase-training, energy and stress.',original_result_sha256=a.sha(folder/'result.json'),original_manifest_sha256=a.sha(folder/'manifest.json'),raw_sha256=r['raw_sha256'],gzip_sha256=r['gzip_sha256'],analyzer_sha256=a.sha(Path(analyzer.__file__)),original_analysis_error=r['analysis_error'])
 a.emit(folder/'reanalysis.json',out);shutil.copy2(Path(analyzer.__file__),scratch/'execution-source.py')
 print(folder.name,'errors',out['frames'][-1]['full_receiver']['errors'],'off',out['shutdown']['off_current_screen_pass'],'recovery',out['shutdown']['recovery_within_1us_verified'],flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('folder');main(p.parse_args().folder)
