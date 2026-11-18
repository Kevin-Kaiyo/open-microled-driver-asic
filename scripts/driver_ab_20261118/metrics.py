"""Build the follow-up table from each matched protocol and the model's signed source energy."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
TAG='driver-ab-20261118'
BUILD=ROOT/'build'/TAG
EV=ROOT/'evidence'/TAG
PREVIOUS=ROOT/'build/driver-pvt-20261117/b/clamp5v_buffer_soft'
BRANCHES={
    'previous':None,
    'w4-r260':BUILD/'b/merged220c10r260',
    'w6-r260':BUILD/'b_final/unit6-r260',
    'w6-n4ff36':BUILD/'b_final/unit6-r260-n4ff36',
    'w6-ff36':BUILD/'b_final/unit6-r260-ff36',
}
RUNS=['tt-normal1-s40','ss_hot_low-full-s40','ff_cold_high-full-s40']


def main():
    rows=[]
    for case in RUNS:
        for name,branch in BRANCHES.items():
            if name=='previous':
                branch=BUILD/'b_review/reference/clamp5v_buffer_soft' if case.startswith('ff_') else PREVIOUS
            path=branch/case/'result.json'
            if not path.is_file():
                raise FileNotFoundError(path)
            r=json.loads(path.read_text())
            f=r['frames'][-1]
            rx=f['first_frame_phase_receiver']
            off=r.get('shutdown',{})
            rec=off.get('recovery_screen',{})
            dev=min(r['stress'],key=lambda d:d['limit_V']-d['peak_pair_V'])
            rows.append(dict(case=case,design=name,source=str(path.relative_to(ROOT)), MOS=r['MOS'],
                      terminal_pass=r['terminal_pass'],body_pass=r['body_pass'],body_V=r['body_forward_V'],
                      tight_terminal=dev['instance'],terminal_margin_V=dev['limit_V']-dev['peak_pair_V'],
                      errors=rx['errors'],train_errors=f['full_receiver']['train_errors'],
                      rx_frozen_pass=rx['research_margin_pass'],rx_retrained_pass=f['full_receiver']['research_margin_pass'],
                      vertical_uAeq=rx['amplitude_uAeq'],timing_UI=rx['timing_UI'],timing_ps=rx['timing_ps'],
                      E_pJ_per_attempted_bit=f['energy_pJ_per_attempted_payload_bit'],
                      last_above_ns=off.get('last_above_threshold_ns'),post20_peak_uA=off.get('max_abs_current_uA'),
                      recovered=rec.get('recovery_within_1us_verified'),recovery_diagnostic_ns=rec.get('upper_bound_ns'),
                      off_Eplus_mW=off.get('total_source_positive_power_during_settled_off_mW')))
    (EV/'matched-frames.json').write_text(json.dumps(rows,indent=2)+'\n')
    for r in rows:
        print(r['design'],r['case'],round(r['timing_ps'],3),r['recovered'],r['recovery_diagnostic_ns'])

if __name__=='__main__':main()
