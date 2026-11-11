#!/usr/bin/env python3
"""Check compact evidence against frozen inputs and numerical pass conditions."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'evidence/driver-methods-20261111'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())

def main():
    summary=read(OUT/'micro-summary.json');checked=[];manifests=set()
    for row in summary['records']:
        path=ROOT/row['result'];r=read(path)
        assert sha(path)==row['result_sha256']
        assert sha(path.parent/'testbench.spice')==r['deck_sha256']
        if row['baseline']:continue
        work=path.parents[2];manifest=work/'manifest.json';m=read(manifest)
        assert sha(manifest)==r['manifest_sha256']
        if manifest not in manifests:
            for p,h in m['inputs'].items():assert sha(work/'inputs'/p)==h,p
            for p,h in m['execution_sources'].items():assert sha(work/'execution-sources'/p)==h,p
            assert sha(work/'stimulus.json')==m['stimulus_sha256']
            manifests.add(manifest)
        assert sha(path.parent/'execution-source.py')==r['engine_sha256']
        assert sha(path.parent/'waveform.dat.gz')==r['gzip_sha256']
        assert len(r['metadata']['devices'])=={'A':20,'B':21}[r['case']['route']]
        assert r['simulation_ok'] and not r.get('analysis_error')
        if row['kind']=='transient':
            a=r['analysis'];f=a['full_receiver'];e=a['energy_pJ_per_attempted_payload_bit']
            expected=f['errors']==f['train_errors']==0 and f['worst_signed_margin_uAeq']>=7.5 and f['one_sided_margin_bit_UI']>=.37
            assert expected==f['research_margin_pass']
            assert row['pass_screen']==bool(expected and a['terminal_screen_pass'] and a['body_screen_pass'] and a['static_IV_domain_pass'])
            for key in ['positive','returned','net']:
                summed=sum(x[key+'_J'] for x in r['metrics']['energy'].values())*1e12/4096
                assert abs(summed-e[key])<1e-12
            assert abs(e['positive']-e['returned']-e['net'])<1e-12
            assert abs(f['one_sided_margin_bit_UI']*(32/37)/(r['case']['net_rate_Gbps']*1e9)*1e12-f['one_sided_margin_ps'])<1e-9
        checked.append(dict(result=row['result'],result_sha256=row['result_sha256'],checks_passed=True))
    protocol=summary['protocol']
    windows=[protocol['development_window'],protocol['prior_holdout_window'],protocol['holdout_window_in_reference_cycle']]
    for a,b in zip(sorted(windows),sorted(windows)[1:]):assert a[1]<=b[0]
    assert all(0<=a<b<=32767 and b-a==4736 for a,b in windows)
    record=dict(schema='micro-methods-evidence-validation-v1',script_sha256=sha(Path(__file__)),summary_sha256=sha(OUT/'micro-summary.json'),checked=checked,manifest_count=len(manifests),all_checks_passed=True,scope='Frozen input/deck/code/wave hashes, device inventory, receiver gate, source-energy sum and PRBS window bounds. Does not rerun SPICE or claim hardware validation.')
    (OUT/'micro-validation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    print(f"Validated {len(checked)} new cases, {len(manifests)} frozen candidates/holdouts")

if __name__=='__main__':main()
