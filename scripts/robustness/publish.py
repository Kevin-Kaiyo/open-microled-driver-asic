"""Package successful normative checks and unhidden exploratory boundaries."""
from pathlib import Path
import csv
import hashlib
import json

import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def product_energy(t,a,b,left,right):
    """Exact integral of separately piecewise-linear saved terminal vectors."""
    mask=(t>left)&(t<right);x=np.r_[left,t[mask],right]
    av=np.r_[np.interp(left,t,a),a[mask],np.interp(right,t,a)]
    bv=np.r_[np.interp(left,t,b),b[mask],np.interp(right,t,b)]
    return float(np.sum(np.diff(x)*(2*av[:-1]*bv[:-1]+av[:-1]*bv[1:]+av[1:]*bv[:-1]+2*av[1:]*bv[1:])/6))


def power_account(batch,row):
    raw=ROOT/batch['run_directory']/row['name']/'waveform.dat'
    actual_hash=sha(raw)
    if actual_hash!=batch['raw_artifacts_sha256'][row['name']+'/waveform.dat']:
        raise RuntimeError('Power partition raw differs from frozen simulation: '+str(raw))
    a=np.loadtxt(raw,skiprows=1);index={v:n for n,v in enumerate(batch['vector_columns'])}
    t=a[:,0];left,right=row['measurement_window_s'];e=row['energies_j']
    led_sink=product_energy(t,a[:,index['i(VLEDLOAD)']],a[:,index['v(led_k)']],left,right)
    bias=e['reference_rail_absorbed_j']-e['reference_B_source_absorbed_j']
    joint=e['logic_joint_load_absorbed_j']+bias+led_sink+e['input_stimulus_generated_j']+e['neighbor_stimulus_generated_j']
    values=dict(external_LED_branch_rail_load=e['LED_load_absorbed_j'],
                LED_device_terminal_load=e['LED_load_absorbed_j']-led_sink,
                selected_joint_LED_K_terminal_input=led_sink,reference_supply_rail_load=e['reference_rail_absorbed_j'],
                behavioral_reference_element_load=e['reference_B_source_absorbed_j'],
                selected_joint_BIAS_terminal_input=bias,selected_joint_VDD_terminal_input=e['logic_joint_load_absorbed_j'],
                selected_joint_all_terminal_net_input=joint,
                declared_external_source_net_supply=e['LED_source_generated_j']+e['logic_source_generated_j']+e['input_stimulus_generated_j']+e['neighbor_stimulus_generated_j'])
    return dict(name=row['name'],group=batch['group'],window_s=[left,right],energies_j=values,
                duration_average_uW={k:v/(right-left)*1e6 for k,v in values.items()},raw_waveform_sha256=actual_hash,
                interpretation='selected joint terminal net input includes losses and internal stored-energy change; not pure heat or full PG power; reference rail and B-element are nested accounts, not additive independent loads')


def figure_slice(batch,name,outpath,left,right,columns,stride=1):
    raw=ROOT/batch['run_directory']/name/'waveform.dat';a=np.loadtxt(raw,skiprows=1)
    actual_hash=sha(raw)
    if actual_hash!=batch['raw_artifacts_sha256'][name+'/waveform.dat']:
        raise RuntimeError('Teaching slice raw differs from frozen simulation: '+str(raw))
    indices={v:n for n,v in enumerate(batch['vector_columns'])};mask=(a[:,0]>=left)&(a[:,0]<=right)
    rows=a[mask][::stride];cols=[0]+[indices[c] for c in columns]
    with outpath.open('w') as f:
        writer=csv.writer(f);writer.writerow(['time_s']+columns);writer.writerows(rows[:,cols])
    return dict(path=str(outpath.relative_to(ROOT)),sha256=sha(outpath),source_waveform=str(raw.relative_to(ROOT)),
                source_waveform_sha256=actual_hash,time_window_s=[left,right],sample_stride=stride,
                purpose='teaching plot only; primary current/power integrals use every saved raw point')


def main():
    folder=ROOT/'evidence/robustness'
    batches={name:json.loads((folder/(name+'-summary.json')).read_text()) for name in ['probe','main','boundary']}
    source=batches['main']['source_hashes']
    for name,batch in batches.items():
        if batch['source_hashes']!=source:raise RuntimeError('Groups did not use identical frozen input/code/contract identities: '+name)
        for p,h in source.items():
            if sha(ROOT/p)!=h:raise RuntimeError('Current source differs from frozen successful run: '+p)
    paired=[]
    main=batches['main']
    for e in ['tt','ss','ff']:
        for duty in [0,1,64,255,256]:
            pre=next(r for r in main['results'] if r['name']==f'{e}_pre_d{duty}')
            post=next(r for r in main['results'] if r['name']==f'{e}_post_d{duty}')
            paired.append(dict(envelope=e,duty=duty,pre_current_uA=pre['current_uA'],post_current_uA=post['current_uA'],
                               delta_current_uA=post['current_uA']-pre['current_uA'],
                               relative_current_delta=(post['current_uA']/pre['current_uA']-1) if abs(pre['current_uA'])>=.001 else None,
                               pre_area_error_pct=pre['area_error_pct'],post_area_error_pct=post['area_error_pct'],
                               pre_rise_30_70_ns=pre['rise_30_70_ns'],post_rise_30_70_ns=post['rise_30_70_ns'],
                               pre_fall_70_30_ns=pre['fall_70_30_ns'],post_fall_70_30_ns=post['fall_70_30_ns']))
    boundary=batches['boundary']
    measured=[dict(name=r['name'],series_LED_R_ohm=r['rled_ohm'],current_uA=r['current_uA'],
                   current_error_pct=(r['current_uA']/100-1)*100,
                   full_on_5pct_target_met=95<=r['current_uA']<=105,LED_anode_v=r['LED_anode_v'])
              for r in boundary['dc_results']]
    startup=[dict(name=r['name'],bias_above_live_rail_max_v=r['bias_above_reference_rail_max_v'],
                  reference_B_active_delivery_energy_j=r['reference_B_source_active_delivery_energy_j'],
                  minimum_reference_B_absorbed_power_uW=r['minimum_reference_B_source_power_absorbed_uW'],
                  command_low_peak_LED_branch_current_uA=r['command_low_peak_LED_branch_current_uA'],
                  interpretation='LED branch includes displacement; active B-reference energy identifies ideal-source boundary; no optical startup qualification')
             for r in boundary['results'] if 'logic_start_s' in r]
    powers=[power_account(main,r) for r in main['results'] if r['name'] in ['tt_post_d0','tt_post_d1','tt_post_d256']]
    powers += [power_account(boundary,r) for r in boundary['results'] if 'logic_start_s' in r or r['name'].startswith('impedance_')]
    slices=[figure_slice(main,'tt_post_d1',folder/'nominal-lowest-pulse.csv',514.45e-6,515.6e-6,
                         ['v(input)','v(pwm)','v(gate)','v(led_k)','i(VLEDLOAD)']),
            figure_slice(boundary,'LED_first_ideal_early',folder/'startup-ideal-LED-first.csv',0,20e-6,
                         ['v(logic_rail)','v(led_a)','v(bias)','v(pwm)','i(VLEDLOAD)','i(VLREF)'],5),
            figure_slice(boundary,'LED_first_compliant_early',folder/'startup-compliant-LED-first.csv',0,20e-6,
                         ['v(logic_rail)','v(led_a)','v(bias)','v(pwm)','i(VLEDLOAD)','i(VLREF)'],5),
            figure_slice(boundary,'RTL_enable',folder/'registered-enable.csv',0,600e-6,
                         ['v(raw_pwm)','v(pwm)','i(VLEDLOAD)'],20)]
    result=dict(schema_version=1,status='actual joint output/analog extracted cutout electrical regression plus explicit power/control boundary study',
                passed=batches['probe']['passed'] and main['passed'] and boundary['completed_numerically'],
                normative_engineering_guards_passed=main['passed'],boundary_studies_completed_numerically=boundary['completed_numerically'],
                boundary_studies_are_system_qualification=False,source_hashes=source,scope=main['scope'],
                model_contract=main['contract'],integration_method=main['integration_method'],
                boundary_finding=main['boundary_finding'],pre_post_pairs=paired,
                conditions=main['conditions'],normative_checks_count=len(main['checks']),
                development_failure_record_path='evidence/robustness/failure-record.json',
                development_failure_record_sha256=sha(folder/'failure-record.json'),
                main_post_matrix=[dict(name=r['name'],MOS_envelope=r['envelope'],RC_style=r.get('post_rc_style','nominal'),
                                      duty=r['duty'],current_uA=r['current_uA'],area_error_pct=r['area_error_pct'],
                                      rise_30_70_ns=r['rise_30_70_ns'],fall_70_30_ns=r['fall_70_30_ns'])
                                  for r in main['results'] if r['view']=='post'],
                selected_terminal_power_decomposition=powers,teaching_waveform_slices=slices,
                power_decomposition_method='exact saved-vector product integral at LED_K; linear account identities for LED_A split and VREF -> behavioral reference -> BIAS split; selected joint includes VDD + BIAS + LED_K + input/neighbor, with storage changes and exclusions declared',
                measured_static_supply_boundary=measured,observed_reference_startup_boundaries=startup,
                control_timing=dict(reset_assert_input_s=20e-6,reset_registered_PWM_low_s=20.5e-6,
                                    reset_release_input_s=30e-6,registered_PWM_high_s=30.5e-6,
                                    enable_low_input_s=20e-6,frame_committed_PWM_low_s=258.5e-6,
                                    enable_high_input_s=300e-6,frame_committed_PWM_high_s=514.5e-6,
                                    semantics='actual RTL functional timing; additional electrical output-stage delay recorded separately; no POR/voltage-aware FF'),
                counts=dict(transient_runs=sum(b['transient_runs'] for b in batches.values()),
                            dc_circuit_runs=sum(b['dc_runs'] for b in batches.values()),synthetic_LED_calibration_runs=len(batches)),
                batches={name:dict(summary_path=f'evidence/robustness/{name}-summary.json',summary_sha256=sha(folder/(name+'-summary.json')),
                                  run_directory=batch['run_directory'],passed=batch['passed'],transient_runs=batch['transient_runs'],dc_runs=batch['dc_runs'])
                         for name,batch in batches.items()},
                packager_sha256=sha(Path(__file__)))
    (folder/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    manifest={str(p.relative_to(ROOT)):sha(p) for p in sorted(folder.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    (folder/'manifest.json').write_text(json.dumps(dict(files_sha256=manifest),indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],counts=result['counts'],measured_static_supply_boundary=measured),indent=2))
    if not result['passed']:raise RuntimeError('Normative result or numerical completion failed')


if __name__=='__main__':main()
