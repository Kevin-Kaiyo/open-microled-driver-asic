#!/usr/bin/env python3
"""Refresh final r10 summaries and verify the immutable records they reference.

This verifies completion/integrity and stated numerical gates, not hardware
validity. Independent native-waveform recomputation is a separate audit.
"""
from pathlib import Path
import json
from run import ROOT, EV, CIR, sha, emit
import summarize
import engineer_notes_r10


def bound(path,digest):
    p=Path(path);assert p.is_file() and sha(p)==digest,str(p)


def main():
    summarize.main();engineer_notes_r10.main()
    index=json.loads((EV/'final-r10-index.json').read_text())
    assert not index['missing_checks'],index['missing_checks']
    assert not index['failed_checks'],index['failed_checks']
    freeze=json.loads((CIR/'frozen-r10.json').read_text())
    for p,h in freeze['circuits'].items():bound(ROOT/p,h)
    for p,h in freeze['additional_sources'].items():bound(ROOT/p,h)
    bound(ROOT/'scripts/vcsel_robustness_20261029/run_r10.py',freeze['runner_sha256'])
    bound(ROOT/'scripts/three_gbps_experiment/vcsel_driver_receiver_v3.py',freeze['receiver_sha256'])
    bound(ROOT/'scripts/three_gbps_experiment/vcsel_model.py',freeze['optical_sha256'])
    for x in json.loads((EV/'baseline-lock.json').read_text())['files']:bound(ROOT/x['path'],x['sha256'])
    checked=set()
    for row in index['frame_records']:
        rp=ROOT/row['result'];bound(rp,row['result_sha256']);r=json.loads(rp.read_text())
        bound(ROOT/row['analysis'],row['analysis_sha256']);ap=(ROOT/row['analysis']).parent
        a=json.loads((ap/'result.json').read_text());plan=json.loads((ap/'plan.json').read_text())
        bound(ap/'plan.json',a['plan_sha256']);bound(ap/'plot-data.npz',a['plot_data_sha256'])
        for p,h in plan['sources'].items():bound(ap/'inputs'/p,h)
        if row['case'] not in checked:
            bound(rp.parent/'manifest.json',r['manifest_sha256'])
            m=json.loads((rp.parent/'manifest.json').read_text())
            for p,h in m['source_hashes'].items():bound(ROOT/p,h)
            bound(ROOT/r['waveform']['path'],r['waveform']['sha256'])
            if 'continuous_run' in r:
                parent=rp.parent.parent/r['continuous_run']['parent_case'];pr=json.loads((parent/'result.json').read_text())
                bound(parent/'result.json',r['continuous_run']['parent_result_sha256'])
                bound(ROOT/pr['waveform']['path'],pr['waveform']['sha256'])
                bound(parent/'testbench.spice',pr['deck_sha256']);bound(parent/'ngspice.log',pr['log_sha256'])
            else:
                bound(rp.parent/'testbench.spice',r['deck_sha256']);bound(rp.parent/'ngspice.log',r['log_sha256'])
            assert abs(sum(x['positive_J'] for x in r['energy_by_port'].values())-r['total_energy']['positive_J'])<1e-18
            checked.add(row['case'])
        assert a['combined_screen_passed'] and a['errors']==0 and a['time_margin_ps']>=100 and a['min_signed_margin_uAeq']>=7.5
    fast=[x for x in index['unresolved_startup_terminal_screen_cases'] if x['case']=='startup-FF-peak-fast-r10']
    assert len(fast)==1 and fast[0]['max_terminal_V']>3.63,'Known rapid-start failure must remain visible'
    summary=json.loads((EV/'summary.json').read_text())
    assert all(x['use_for_stability_signoff'] is False for x in summary['approximate_ldo_loop_ac'])
    paths=[EV/n for n in ['summary.json','final-r10-index.json','engineer-notes.md','recovery-runtime-contract.json','ac-r10-reproduction-check.json']]
    paths+=list((ROOT/'scripts/vcsel_robustness_20261029').glob('*.py'))
    receipt=dict(status='PASS_BOUNDED_COMPLETION_AND_INTEGRITY',unique_frames_checked=len(checked),analysis_records_checked=len(index['frame_records']),
                 files=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in sorted(paths)],
                 unresolved_fast_start=fast,scope='All listed final r10 frame checks completed and passed their finite numerical gates; rapid20ns FF startup still fails terminal screen, AC ratio is not stability proof, no physical PVT/BER/PEX or silicon qualification.')
    emit(EV/'implementation-closeout.json',receipt)
    print(json.dumps(dict(status=receipt['status'],unique_frames_checked=len(checked),analysis_records_checked=len(index['frame_records']),
                          summary_sha256=sha(EV/'summary.json'),closeout_sha256=sha(EV/'implementation-closeout.json')),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
