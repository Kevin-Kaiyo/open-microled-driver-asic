#!/usr/bin/env python3
"""Matched6.4G node/geometry comparison from checked VCSEL experiment records."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'evidence/ab-improvement-20261111'
BASE=ROOT/'evidence/blue-emitter-speed-review-20261110/speed-sweep-all.json'
BUILD=ROOT/'build/ab-improvement-20261111/VCSEL'


def main():
    original=json.loads(BASE.read_text())
    base=next(r['full_analysis'] for r in original['rows'] if r['family']=='VCSEL' and r['net_Gbps']==6.4 and r['steps_per_symbol']==40)
    names=['vc-atten50','vc-steer20','vc-atten50-steer20']
    sources=[BASE,Path(__file__).resolve()]+[BUILD/n/'net6.4-edge20-s40/analysis.json' for n in names]
    data=[('r10-baseline',base)]+[(n,json.loads((BUILD/n/'net6.4-edge20-s40/analysis.json').read_text())) for n in names]
    rows=[]
    for name,r in data:
        full=r['pathways']['actual_graph_5GHzRX'];gate=r['stages']['steering_gate_polarity'];electrical=r['pathways']['actual_electrical'];e=r['source_energy_pJ_per_attempted_net_bit']['positive']
        rows.append(dict(candidate=name,net_Gbps=6.4,positive_pJ_per_attempted_bit=e,power_mW=e*6.4,
            input_differential_peak_V=r['observed']['predriver_input_differential_peak_V'],gate_margin_UI=gate['one_sided_margin_UI'],
            gate_selected_sampling_delay_ps=gate['delay_ps'],electrical_margin_UI=electrical['one_sided_margin_UI'],
            full_margin_UI=full['one_sided_margin_UI'],full_margin_ps=full['one_sided_margin_ps'],full_amplitude_uAeq=full['worst_signed_margin_uAeq']))
    out=dict(scope='Matched6.4G causal node comparison; receiver-selected delays are sampling phases, not standalone propagation delays.',rows=rows,
        geometry=dict(steering_instances=['XSTEER_0','XDUMP_0'],length_um=.28,width_um_before=40,width_um_after=20,
            gate_drawn_area_um2_per_device_before=11.2,gate_drawn_area_um2_per_device_after=5.6,
            diffusion_area_um2_each_terminal_before=17.6,diffusion_area_um2_each_terminal_after=8.8,
            diffusion_perimeter_um_each_terminal_before=80.88,diffusion_perimeter_um_each_terminal_after=40.88,
            note='Estimated geometry parameters; actual nonlinear Cgg/Cgd/Cdb not measured or extracted. ReducedW trades less capacitive loading against increased on-resistance/current-compliance demand. Total chip area is not inferred.'),
        input_divider=dict(RD_external_ohm=50,ATTEN_before_ohm=200,ATTEN_after_ohm=50,RADI_to_ground_ohm=2500,
            high_level_before_V=3.3*2500/(2500+50+200),high_level_after_V=3.3*2500/(2500+50+50),
            note='Single resistor change affects both input RC and input high-level attenuation. Two identical complementary input branches.'),
        source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    coarse=BUILD/'vc-atten50-steer20/net6.4-edge20-s40/analysis.json'
    fine=BUILD/'vc-atten50-steer20/net6.4-edge20-s80/analysis.json'
    if fine.exists():
        a,b=json.loads(coarse.read_text()),json.loads(fine.read_text())
        ra,rb=a['pathways']['actual_graph_5GHzRX'],b['pathways']['actual_graph_5GHzRX']
        ep_a=a['source_energy_pJ_per_attempted_net_bit']['positive'];ep_b=b['source_energy_pJ_per_attempted_net_bit']['positive']
        out['halfstep_control']=dict(net_Gbps=6.4,steps_before=40,steps_after=80,
            identical_pass=a['combined_screen_pass']==b['combined_screen_pass'],
            identical_errors=ra['errors']==rb['errors'],amplitude_delta_uAeq=rb['worst_signed_margin_uAeq']-ra['worst_signed_margin_uAeq'],
            timing_delta_ps=rb['one_sided_margin_ps']-ra['one_sided_margin_ps'],energy_relative_delta_percent=100*(ep_b/ep_a-1),
            source_coarse=str(coarse.relative_to(ROOT)),source_fine=str(fine.relative_to(ROOT)))
        out['source_hashes'][str(fine.relative_to(ROOT))]=hashlib.sha256(fine.read_bytes()).hexdigest()
    stage=EV/'vcsel-improvement.json'
    if stage.exists():
        records=json.loads(stage.read_text())['rows']
        values=sorted([r for r in records if r['candidate']=='vc-atten50-steer20' and r['steps_per_UI']==40],key=lambda r:r['net_Gbps'])
        passed=[r['net_Gbps'] for r in values if r['combined_screen_pass']]
        highest=max(passed) if passed else None
        fail=[r['net_Gbps'] for r in values if highest is not None and r['net_Gbps']>highest and not r['combined_screen_pass']]
        out['tested_envelope']=dict(candidate='vc-atten50-steer20',tested_rates_Gbps=[r['net_Gbps'] for r in values],highest_passing_tested_Gbps=highest,next_failing_tested_Gbps=min(fail) if fail else None,
            previous_highest_passing_tested_Gbps=4.8,ratio_of_highest_passing_tested_points=highest/4.8 if highest else None,
            scope='Discrete sampled nominal points, not an exact maximum or proof of monotonicity. The ratio compares highest tested passing points, not measured physical bandwidth improvement. No PVT/startup/PEX/BER closure.')
        out['source_hashes'][str(stage.relative_to(ROOT))]=hashlib.sha256(stage.read_bytes()).hexdigest()
    EV.mkdir(parents=True,exist_ok=True)
    (EV/'vcsel-causal-comparison.json').write_text(json.dumps(out,indent=2)+'\n')
    print('Wrote vcsel-causal-comparison.json')

if __name__=='__main__':main()
