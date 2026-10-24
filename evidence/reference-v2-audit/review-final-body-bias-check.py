"""Signed body-junction diagnostic on existing frozen startup waves only."""
from pathlib import Path
import gzip,hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'build/nrz-reference-v2/selected-final-r2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def main():
    contract=read(WORK/'inputs/physical/integrated-contract.json')
    mapping={r['extracted_instance'].lower():r for r in contract['extracted_device_mapping']}
    rows=[]
    for case in read(WORK/'plan-startup.json')['cases']:
        folder=WORK/'cases'/case['name'];q=read(folder/'result.json');wave=ROOT/q['waveform']
        assert sha(wave)==q['waveform_sha256']
        with gzip.open(wave,'rt') as f:trace=np.loadtxt(f,skiprows=1)
        t=trace[:,0];v=q['vectors'];devices=[]
        for dev in q['devices']:
            nodes=dev['nodes'];body=trace[:,v[nodes[3]]] if nodes[3]!='0' else np.zeros(len(t))
            sign=1 if 'pfet' in dev['model'] else -1
            for index,terminal in [(0,'drain'),(2,'source')]:
                diff=trace[:,v[nodes[index]]] if nodes[index]!='0' else np.zeros(len(t))
                forward=sign*(diff-body);j=int(forward.argmax());original=mapping[dev['instance']]
                thresholds={}
                for threshold in [.5,.7]:
                    ids=np.flatnonzero(forward>threshold)
                    thresholds[str(threshold)]={'saved_samples':int(len(ids)),'first_sample_s':float(t[ids[0]]) if len(ids) else None,'last_sample_s':float(t[ids[-1]]) if len(ids) else None}
                devices.append(dict(extracted_instance=dev['instance'],original_instance=original['original_instance'],model=dev['model'],extracted_terminal=terminal,drain_source_swapped=original['drain_source_swapped'],original_terminal=('source' if terminal=='drain' else 'drain') if original['drain_source_swapped'] else terminal,positive_forward_V=float(forward[j]),at_s=float(t[j]),diffusion_V=float(diff[j]),body_V=float(body[j]),diagnostic_thresholds=thresholds))
        worst=max(devices,key=lambda d:d['positive_forward_V'])
        rows.append(dict(name=case['name'],result_sha256=sha(folder/'result.json'),waveform_sha256=q['waveform_sha256'],worst=worst,above_0p5V=[d for d in devices if d['positive_forward_V']>.5]))
    out=dict(script_sha256=sha(__file__),scope='Read-only signed diffusion-to-body voltage diagnostic. PMOS: diffusion minus body; NMOS: body minus diffusion. 0.5/0.7V are descriptive probes, not new acceptance or foundry limits. No body current, latch-up, substrate injection, SOA or reliability closure is inferred. Existing functional and absolute six-pair guards remain reported separately.',no_ngspice_invocation=True,rows=rows)
    Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps([dict(name=r['name'],worst=r['worst']) for r in rows if r['worst']['positive_forward_V']>.5],indent=2))
if __name__=='__main__':main()
