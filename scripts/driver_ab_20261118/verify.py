"""Independently reconcile original stimulus, model, source, current and seven-port energy identities."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
TAG='driver-ab-20261118'
BUILD=ROOT/'build'/TAG
EV=ROOT/'evidence'/TAG
spec=importlib.util.spec_from_file_location('pvt_audit',ROOT/'scripts/driver_pvt_20261117/validate.py')
prior=importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
read,sha=prior.read,prior.sha
PORTS=['VIN','VREF','VLED','VDD','VD0','VD1','VDISABLE']


def experiment(folder, deep):
    r=read(folder/'result.json')
    m=read(folder/'manifest.json')
    if 'window_source_offset_s' in m:
        edspec=importlib.util.spec_from_file_location('edge_audit', Path(__file__).parent/'a/verify_edge.py')
        edge=importlib.util.module_from_spec(edspec)
        edspec.loader.exec_module(edge)
        return edge.verify(folder)
    deck=(folder/'testbench.spice').read_text()
    lane=folder.relative_to(BUILD).parts[0]
    assert r['manifest_sha256']==sha(folder/'manifest.json')
    assert r['deck_sha256']==m['deck_sha256']==sha(folder/'testbench.spice')
    assert sha(folder/'stimulus.json')==m['stimulus_sha256']==sha(ROOT/m['source_case']/'stimulus.json')
    assert sha(folder/'ngspice.log')==r['log_sha256']
    model=folder.parent/'inputs/led.spice'
    assert sha(model)==prior.MICRO_LED==m['inputs']['led.spice']
    assert re.search(r'^RPKG led_k pk 1$',deck,re.M)
    assert re.search(r'^LPKG pk (?:mon|out) \.5n$',deck,re.M)
    assert re.search(r'^CLED led_a led_k 2e-13$',deck,re.M)
    if lane=='a':
        assert sha(folder/'route_a.spice')==m['route_sha256']==r['route_sha256']
        _,section,temp,scale=m['pvt']
        assert f'.temp {temp}\n' in deck and f'ngspice" {section}\n' in deck
        for supply,nom in [('VIN',5),('VLED',5),('VDD',3.3)]:
            assert prior.near(prior.deck_voltage(deck,supply),nom*scale)
        assert prior.near(prior.deck_voltage(deck,'VREF'),2.5)
        for path in (folder.parent/'inputs').rglob('*'):
            if path.is_file() and path.name!='route_a.spice':assert sha(path)==m['inputs'][path.name]
        assert sha(ROOT/m['analysis_path'])==m['analysis_sha256']
    else:
        prior.conditions('b',m,deck)
        assert sha(folder/'execution-source.py')==m['execution_sha256']
        for name,identity in m['inputs'].items():assert sha(folder.parent/'inputs'/name)==identity
        for helper in m['execution_helpers'].values():assert sha(folder/helper['path'])==helper['sha256']
    prior.stimulus(lane,m,deck,read(folder/'stimulus.json'))
    wave=folder/'waveform.dat.gz'
    assert sha(wave)==r.get('compressed_sha256',r.get('gzip_sha256'))
    if deep or 'current_uA' in r:
        with gzip.open(wave,'rb') as stream:
            if deep:assert hashlib.file_digest(stream,'sha256').hexdigest()==r.get('native_sha256',r.get('raw_sha256'))
            if 'current_uA' in r:
                stream.seek(0)
                header,values=stream.read().splitlines()
                assert header.split()[1].lower()==b'i(vsense)'
                assert abs(float(values.split()[1])*1e6-r['current_uA'])<1e-8
    for frame in r.get('frames',[]):
        prior.energy_ledger(frame['source_energy_J'],frame['energy_pJ_per_attempted_payload_bit'],4096,PORTS)
    return dict(path=str(folder.relative_to(ROOT)),result_sha256=sha(folder/'result.json'),
                class_name='DC' if 'current_uA' in r else ('full_frame' if r.get('frames') else 'short_window'))


def grid():
    checks=[]
    for p in sorted(EV.glob('b-grid-*.json'))+[EV/'b-unit-screen.json']:
        data=read(p)
        rows=data['runs'] if isinstance(data,dict) else [row for spec in data for row in spec['points']]
        for row in rows:
            deck=ROOT/row['deck']
            assert sha(deck)==row['deck_sha256'] and sha(ROOT/row['source'])==row['source_sha256']
            assert row['dependencies'] and all(sha(ROOT/f)==h for f,h in row['dependencies'].items())
            raw=deck.parent/'waveform.dat'
            assert sha(raw)==row['raw_sha256']
            value=float(raw.read_text().splitlines()[1].split()[1])*1e6
            assert abs(value-row['ILED_uA'])<1e-8
            assert abs(100*(value/row['target_uA']-1)-row['error_percent'])<1e-8
        checks.append(dict(study=p.name,rows=len(rows),sha256=sha(p)))
    return checks


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deep',action='store_true',help='Also decompress and hash native bytes')
    parser.add_argument('--final',action='store_true',help='Require all prepared runnable cases to have results')
    args=parser.parse_args()
    paths=sorted({p.parent for lane in ('a','b','b_final','b_review') for p in (BUILD/lane).rglob('result.json')})
    if args.final:
        waiting=[m for lane in ('a','b','b_final','b_review') for m in (BUILD/lane).rglob('manifest.json')
                 if '_templates' not in m.parts and not (m.parent/'result.json').is_file()]
        assert not waiting, waiting
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda path:experiment(path,args.deep),paths))
    grids=grid()
    summary=dict(experiments=len(results),types=dict(Counter(r['class_name'] for r in results)),
                 additional_DC=sum(s['rows'] for s in grids),decompressed_verified=args.deep,
                 complete_prepared_cases=args.final, grids=grids,
                 meaning='Case and evidence integrity. Circuit pass is scored separately per metric.',results=results)
    print({k:v for k,v in summary.items() if k not in ('results','grids')})
    if args.final:(EV/'validation.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':main()
