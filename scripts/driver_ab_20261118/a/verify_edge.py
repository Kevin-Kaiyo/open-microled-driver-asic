"""Read back cropped DATA and DISABLE at every original and generated breakpoint."""
import gzip
import hashlib
import json
from pathlib import Path
import re
import numpy as np

ROOT=Path(__file__).resolve().parents[3]

def sha(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file,'sha256').hexdigest()

def verify(folder):
    folder=Path(folder).resolve()
    read=lambda p:json.loads(p.read_text())
    r=read(folder/'result.json');m=read(folder/'manifest.json')
    full=ROOT/m['source_case']
    source=(full/'testbench.spice').read_text()
    dest=(folder/'testbench.spice').read_text()
    assert sha(full/'manifest.json')==m['source_manifest_sha256']
    assert sha(full/'testbench.spice')==m['source_deck_sha256']
    assert sha(folder/'manifest.json')==r['manifest_sha256']
    assert sha(folder/'testbench.spice')==r['deck_sha256']==m['deck_sha256']
    assert sha(folder/'route_a.spice')==sha(full/'route_a.spice')==r['route_sha256']==m['route_sha256']
    assert sha(folder/'ngspice.log')==r['log_sha256']
    assert sha(folder/'waveform.dat.gz')==r['compressed_sha256']
    assert m['inputs']==read(full/'manifest.json')['inputs']
    for path in (folder.parent/'inputs').rglob('*'):
        if path.is_file() and path.name!='route_a.spice':assert sha(path)==m['inputs'][path.name]
    with gzip.open(folder/'waveform.dat.gz','rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==r['native_sha256']
    assert m['end_s']==128e-9 and m['edge_at_s']==32e-9 and m['pvt']==['SShotlow','ss',85,.95]
    assert sha(ROOT/'scripts/driver_ab_20261118/a/protection.py')==m['runner_at_execution_sha256']
    assert m['steps_per_symbol']==r['steps']
    for name in ['VD0','VDISABLE']:
        def wave(deck):return np.fromstring(re.search(r'(?m)^'+name+r' \w+ 0 PWL\((.+)\)$',deck)[1],sep=' ').reshape(-1,2)
        x,v=wave(source).T
        y,w=wave(dest).T
        offset=m['window_source_offset_s'];stop=m['end_s']
        assert np.all(np.diff(y)>0) and y[0]==0 and y[-1]==stop
        # Check corners from both descriptions, including times with flat levels.
        test=np.unique(np.r_[y,x[(x>offset)&(x<offset+stop)]-offset])
        np.testing.assert_allclose(np.interp(test,y,w),np.interp(test+offset,x,v),atol=2e-10,rtol=0.)
    assert ('CISOEDGE iso_g 0 '+f"{m['cap_ff']:g}f" in dest)==bool(m['cap_ff'])
    assert re.search(r'^\.temp 85$',dest,re.M)
    assert f'RMON mon out 100\n' in dest and 'LPKG pk mon .5n' in dest and 'CLED led_a led_k 2e-13' in dest
    return dict(path=str(folder.relative_to(ROOT)),result_sha256=sha(folder/'result.json'),class_name='short_window')
