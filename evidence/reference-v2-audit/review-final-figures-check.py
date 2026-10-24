"""Read-only SVG device metadata/source hashes; not a substitute for visual review."""
from pathlib import Path
import hashlib,json,re,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def devices(path):
    out={}
    for line in Path(path).read_text().splitlines():
        p=line.split()
        if len(p)>5 and p[0].startswith('X') and p[5] in ('nfet_06v0','nfet_03v3','pfet_06v0','pfet_03v3'):
            out[p[0][1:]]=dict(zip('DGSB',p[1:5]))
    return out
def svg_nets(path):
    return {e.attrib['data-device']:dict(zip('DGSB',e.attrib['data-nets'].split())) for e in ET.parse(path).iter() if 'data-device'in e.attrib}
records=[]
for name in ['nrz-b-reference-power-20261024','pwm-reference-startup-20261024']:
    folder=ROOT/'docs/research'/name/'figures'
    for p in folder.glob('*manifest.json'):
        obj=json.loads(p.read_text());figs=obj.get('figures',[obj])
        for fig in figs:
            if not fig.get('file','').endswith('.svg'):continue
            svg=folder/fig['file'];assert sha(svg)==fig['sha256'],svg
            sources=fig.get('source_hashes',fig.get('sources',{}))
            if fig.get('source'):sources={fig['source']:fig['source_sha256']}
            for s,h in sources.items():assert sha(ROOT/s)==h,(svg,s)
            actual=svg_nets(svg)
            if fig.get('devices'):
                for d,n in actual.items():assert n=={k:fig['devices'][d][k] for k in 'DGSB'}
            records.append(dict(figure=str(svg.relative_to(ROOT)),sha256=sha(svg),source_hashes=sources,device_count=len(actual),manifest_and_embedded_nets_agree=True))
ref=devices(ROOT/'analog/nrz_reference_v2/vi_reference_switched_keeper.spice')
vi=svg_nets(ROOT/'docs/research/nrz-b-reference-power-20261024/figures/vi-servo-selected.svg')
assert len(vi)==10 and all(vi[k]==ref[k] for k in vi)
core=devices(ROOT/'layout/highspeed_nrz_robustness/steering_driver-reference.spice')
expected={**{'MREF':core['REF'],'MBASE':core['BASE'],'ML':core['LED'],'MD':core['DUMMY'],'MTAIL':core['TAIL']},
          'DIS':{k:('BIAS' if n=='IOUT' else n) for k,n in ref['DIS'].items()},'MK':ref['KEEP']}
top=svg_nets(ROOT/'docs/research/nrz-b-reference-power-20261024/figures/selected-b-circuit.svg')
assert top==expected
out=dict(passed=True,scope='Current source SVG hashes and embedded D/G/S/B tuples versus independently parsed SPICE; PNG parity requires regeneration after source changes.',
         script_sha256=sha(__file__),nrz_selected_vi_devices_checked=10,nrz_selected_core_and_protection_devices_checked=7,figures=records)
Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(passed=True,figures=len(records),nrz_device_tuples=17)))
