"""Bind final compact producer summaries to independently checked raw records."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
DIR=Path(__file__).parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    frozen=read(DIR/'review-final-nrz-check.json');comm=read(DIR/'review-final-nrz-communication-check.json')
    identities={r['name']:(r['result_sha256'],r['analysis_sha256']) for r in frozen['records']}
    identities.update({r['name']:(r['fingerprints']['result_sha256'],r['fingerprints']['analysis_sha256']) for r in comm['records']})
    sp=ROOT/'evidence/nrz-reference-v2/selected-final-r2-summary-verified.json';s=read(sp)
    assert len(identities)==len(s['rows'])==138 and s['manifest_sha256']==frozen['manifest_sha256']==comm['manifest_sha256']
    assert s['coverage']['missing']==s['coverage']['unplanned']==[]
    assert s['coverage']['stage_counts']=={'dc':112,'nrz':10,'startup':11,'slow':5}
    assert {r['name'] for r in s['rows']}==set(identities)
    for row in s['rows']:
        rp=ROOT/row['result_json'];ap=ROOT/row['analysis_json'];q=read(rp);a=read(ap)
        assert (sha(rp),sha(ap))==identities[row['name']]
        assert row['case']==q['case']
        for k,v in a['row'].items():assert row[k]==v,(row['name'],k)
        assert row['maximum_recorded_body_forward_V']==a['stress']['maximum_recorded_body_forward_V']
        if row['stage']=='dc':assert row['current_target_passed']==(abs(row['LED_current_error_percent'])<=5)
    counts=dict(planned=138,results=138,analyzed=138,simulation_failures=0,analysis_failures=0,DC_current_target_failures=4,NRZ_receiver_failures=0,device_screen_failures=1,startup_contract_failures=1,slow_response_failures=0,administrative_interruptions=1)
    assert s['counts']==counts
    assert s['qualification_limits']['maximum_recorded_body_forward_V']==.746648764813482
    hashes={str(sp.relative_to(ROOT)):sha(sp)}
    for stage,n in [('dc',112),('startup',11),('slow',5),('nrz',10)]:
        path=sp.with_name(f'selected-final-r2-{stage}.json');q=read(path);assert len(q['rows'])==n
        for row in q['rows']:
            full=next(r for r in s['rows'] if r['name']==row['name'])
            for k,v in row.items():assert full[k]==v
        hashes[str(path.relative_to(ROOT))]=sha(path)
    out=dict(script_sha256=sha(__file__),bound_records=138,counts=counts,producer_summary_hashes=hashes,independent_audit_hashes={p.name:sha(p) for p in [DIR/'review-final-nrz-check.json',DIR/'review-final-nrz-communication-check.json',DIR/'review-final-body-bias-check.json']},scope='Final compact data match independently checked raw identities; this does not mark retained functional/precision/body-bias failures as accepted.')
    Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
