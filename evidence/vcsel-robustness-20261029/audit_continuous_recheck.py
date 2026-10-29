#!/usr/bin/env python3
"""Recheck continuous startup->frame from the unsliced native parent waveform."""
from pathlib import Path
import argparse,json
import numpy as np
from audit_recheck import ROOT,EV,UI,END,sha,load_module,positive_pwl,uniform_rx,receiver


def run(parent,label):
    work=ROOT/'build/vcsel-robustness-20261029'/parent
    fw=work.with_name(parent+'-frame');aw=fw/('analysis-'+label)
    m=json.loads((work/'manifest.json').read_text());r=json.loads((work/'result.json').read_text())
    fm=json.loads((fw/'manifest.json').read_text());fr=json.loads((fw/'result.json').read_text())
    analysis=json.loads((aw/'result.json').read_text());plan=json.loads((aw/'plan.json').read_text())
    start=m['config']['frame_start_ns']*1e-9;end=m['end_s']
    assert m['config']['mode']=='startup_frame' and abs(end-start-END)<1e-18
    assert r['simulation_ok'] and r['manifest_sha256']==sha(work/'manifest.json')
    assert r['deck_sha256']==sha(work/'testbench.spice')
    assert r['waveform']['sha256']==sha(ROOT/r['waveform']['path'])==fm['parent_waveform_sha256']
    assert fr['continuous_run']['parent_result_sha256']==sha(work/'result.json')
    assert fr['waveform']['sha256']==sha(ROOT/fr['waveform']['path'])==plan['waveform_sha256']
    assert analysis['plan_sha256']==sha(aw/'plan.json')
    for name,digest in m['source_hashes'].items():assert sha(ROOT/name)==digest
    for name,digest in plan['sources'].items():assert sha(aw/'inputs'/name)==digest
    native=np.loadtxt(ROOT/r['waveform']['path'],skiprows=1);nt=native[:,0]
    assert np.all(np.diff(nt)>0) and nt[0]==0 and abs(nt[-1]-end)<1e-15
    ix={e:k+1 for k,e in enumerate(m['expressions'])}
    cut=np.r_[start,nt[(nt>start)&(nt<end)],end]
    assert np.diff(cut).max()<=UI/m['config']['frame_steps']*1.0001
    energy={};startup={}
    for port,node in m['ports'].items():
        p=-native[:,ix['v('+node+')']]*native[:,ix['i('+port+')']]
        values=positive_pwl(cut,np.interp(cut,nt,p));whole=positive_pwl(nt,p)
        for key,value in values.items():assert abs(value-fr['energy_by_port'][port][key])<1e-20
        energy[port]=values;startup[port]={key:whole[key]-values[key] for key in values}
    pJ=sum(v['positive_J'] for v in energy.values())/4096*1e12
    assert abs(pJ-fr['total_energy']['positive_pJ_per_offered_payload_bit'])<1e-9
    before=20e-9
    native_pre=np.r_[start-before,nt[(nt>start-before)&(nt<end)],start,end]
    native_pre=np.unique(native_pre)
    reconstructed=np.column_stack([native_pre-start]+[np.interp(native_pre,nt,native[:,k]) for k in range(1,native.shape[1])])
    stored=np.loadtxt(ROOT/fr['waveform']['path'],skiprows=1)
    assert reconstructed.shape==stored.shape and np.max(abs(reconstructed-stored))<1e-13
    del stored
    frame=np.column_stack([cut-start]+[np.interp(cut,nt,native[:,k]) for k in range(1,native.shape[1])])
    devices=[]
    for dev in m['devices']:
        v=[np.zeros(len(frame)) if n=='0' else frame[:,ix['v('+n+')']] for n in dev['nodes']]
        pairs={(i,j):float(np.max(abs(v[i]-v[j]))) for i in range(4) for j in range(i+1,4)}
        sign=1 if dev['model'].startswith('p') else -1
        body=max(float(np.max(sign*(v[0]-v[3]))),float(np.max(sign*(v[2]-v[3]))),0)
        pair=max(pairs,key=pairs.get)
        devices.append({'instance':dev['instance'],'max_terminal_V':pairs[pair],'pair':'DGSB'[pair[0]]+'DGSB'[pair[1]],'body_forward_V':body})
    maxv=max(d['max_terminal_V'] for d in devices);maxbody=max(d['body_forward_V'] for d in devices)
    assert abs(maxv-fr['max_terminal_V'])<1e-12 and abs(maxbody-fr['max_body_forward_V'])<1e-12
    optical=load_module(aw/'inputs/scripts/three_gbps_experiment/vcsel_model.py')
    # Match the preserved 20 ns prehistory, independently apply the RX recurrence.
    ft=np.linspace(reconstructed[0,0],fm['end_s'],int(np.ceil((fm['end_s']-reconstructed[0,0])/(plan['grid_ps']*1e-12)))+1)
    cur=np.interp(ft,reconstructed[:,0],reconstructed[:,ix['v(jmon)']])
    power=optical.optical_power(ft,cur,response='figure3mA_proxy')
    lo,hi=optical.static_power(np.array([.003,.007]));eq=25+(power-lo)*75/(hi-lo)
    filtered=uniform_rx(eq,ft[1]-ft[0]);stim=json.loads((work/'stimulus.json').read_text())
    assert sha(work/'stimulus.json')==m['stimulus_sha256']==sha(fw/'stimulus.json')
    rx=receiver(ft,filtered,np.array(stim['bits']));exp=analysis['receiver']
    assert rx['errors']==exp['validation']['bit_errors']
    assert abs(rx['margin_uAeq']-exp['validation']['decision_distance_min_uA'])<1e-7
    assert abs(rx['time_ps']-exp['horizontal_margin']['min_ps'])<1e-4
    assert abs(rx['delay_ps']-exp['sampling']['delay_s']*1e12)<1e-7
    domain=frame[:,ix['v(jmon)']].min()>=.002 and frame[:,ix['v(jmon)']].max()<=.0075 and power.min()>=0
    combined=domain and maxv<=3.63 and maxbody<=.3 and rx['errors']==0 and rx['margin_uAeq']>=7.5 and rx['time_ps']>=100
    assert combined==analysis['combined_screen_passed']
    rails={n: [float(frame[:,ix['v('+n+')']].min()),float(frame[:,ix['v('+n+')']].max())] for n in ['vl','xdrv.dr']}
    return dict(parent_case=parent,frame_case=fw.name,analysis_label=label,parent_waveform_sha256=r['waveform']['sha256'],analysis_sha256=sha(aw/'result.json'),
        start_us=start*1e6,frame_ns=(end-start)*1e9,prehistory_ns=before*1e9,max_frame_native_step_ps=float(np.diff(cut).max()*1e12),
        exact_slice_reconstructed=True,receiver_independent=rx,energy_by_port_J=energy,startup_energy_by_port_J=startup,
        positive_pJ_per_offered_payload_bit=pJ,maximum_frame_terminal_V=maxv,terminal_headroom_mV=(3.63-maxv)*1000,
        maximum_body_forward_V=maxbody,parent_startup_plus_frame_max_terminal_V=r['max_terminal_V'],
        frame_rail_ranges_V=rails,native_current_range_mA=[float(frame[:,1].min()*1e3),float(frame[:,1].max()*1e3)],
        combined_screen_passed=bool(combined),scope='Same continuous transistor trajectory without OP restart; 20 ns pre-frame samples retain filter state. Startup energy separated, never amortized invisibly into frame pJ. External precision-source internal power, optical noise and asynchronous enable sequencing remain outside scope.')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--case',action='append',required=True);ap.add_argument('--label',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    assert a.output.startswith('audit-') and '/' not in a.output and a.output.endswith('.json')
    rows=[]
    for case in a.case:
        row=run(case,a.label);rows.append(row)
        print(json.dumps({k:row[k] for k in ['parent_case','receiver_independent','positive_pJ_per_offered_payload_bit','terminal_headroom_mV','combined_screen_passed']},indent=2),flush=True)
    (EV/a.output).write_text(json.dumps({'script_sha256':sha(__file__),'helper_sha256':sha(Path(__file__).with_name('audit_recheck.py')),'rows':rows},indent=2)+'\n')
