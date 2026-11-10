#!/usr/bin/env python3
"""Compare real and ideal VCSEL stages at fixed, UI-normalized sampling rules."""
import argparse
from collections import Counter
import gzip
import hashlib
from pathlib import Path

import numpy as np

from replay import ROOT, module, read_json, sha
from vcsel_x10_run import BUILD, SAVED, emit, PAYLOAD

EV = ROOT / 'evidence/highspeed-workbench-20261110'
DOC = ROOT / 'docs/research/highspeed-workbench-20261110'
OPTO_PATH = ROOT / 'scripts/three_gbps_experiment/vcsel_model.py'
RX_PATH = ROOT / 'scripts/three_gbps_experiment/vcsel_driver_receiver_v3.py'
PARAMETERS = ROOT / 'analog/models/vcsel_research_20261027/parameters.json'
THRESHOLD = 62.5
AMPLITUDE_MARGIN = 7.5
TIME_MARGIN_UI = .37
DELAYS_UI = np.arange(513) / 64


def one_pole(time, signal, hz):
    """Exact response to piecewise-linear inputs on a uniform grid."""
    out = np.empty_like(signal)
    out[0] = signal[0]
    h = time[1]-time[0]
    tau = 1/(2*np.pi*hz)
    m = -np.expm1(-h/tau)
    e = 1-m
    slope_term = 1-m*tau/h
    for k in range(1,len(out)):
        out[k] = e*out[k-1] + m*signal[k-1] + slope_term*(signal[k]-signal[k-1])
    return out


def receive(rx, t, signal, bits, ui, end, delays_ui=DELAYS_UI):
    """Choose one delay from training only, then score independent validation."""
    training = np.arange(64, 512)
    validation = np.arange(576, 4672)
    assert (training[-1]+delays_ui[-1])*ui < 576*ui
    assert (validation[-1]+delays_ui[-1])*ui < end
    prefix = t < 576*ui
    tt, yy = t[prefix], signal[prefix]
    thresholds = np.array([THRESHOLD])
    events = rx._crossing_events(tt, yy, thresholds)
    expected_train = bits[training]
    train_sign = 2*expected_train-1
    delays = delays_ui*ui
    t_train = training[None,:]*ui + delays[:,None]
    y_train = np.interp(t_train, t, signal)
    signed = train_sign*(y_train-THRESHOLD)
    train_amplitude = signed.min(axis=1)
    scores = train_amplitude/AMPLITUDE_MARGIN
    for k in np.flatnonzero(train_amplitude > 0):
        time = rx._horizontal(tt, yy, t_train[k], y_train[k], expected_train, thresholds,
                              64*ui, float(tt[-1]), ui, ui, events_by_level=events)
        scores[k] = min(scores[k], time['min_symbol_UI']/TIME_MARGIN_UI)
    selected = int(np.argmax(scores))
    expected = bits[validation]
    sample_t = (validation+delays_ui[selected])*ui
    sample = np.interp(sample_t, t, signal)
    distance = (2*expected-1)*(sample-THRESHOLD)
    wrong = (sample>=THRESHOLD)!=expected
    margin = rx._horizontal(t, signal, sample_t, sample, expected, thresholds, 0, end, ui, ui)
    train_errors = int(np.count_nonzero((y_train[selected]>=THRESHOLD)!=expected_train))
    errors = int(np.count_nonzero(wrong))
    sample_levels = {str(k): {'p05':float(np.percentile(sample[expected==k],5)),
                              'median':float(np.median(sample[expected==k])),
                              'p95':float(np.percentile(sample[expected==k],95))}
                     for k in [0,1]}
    before = bits[validation-1]
    transitions = Counter(zip(before, expected))
    bad_transitions = Counter(zip(before[wrong], expected[wrong]))
    result = {
        'delay_UI': float(delays_ui[selected]), 'delay_ps': float(delays[selected]*1e12),
        'train_errors': train_errors, 'errors': errors, 'validation_bits': PAYLOAD,
        'min_training_errors_any_delay':int(np.count_nonzero((y_train>=THRESHOLD)!=expected_train,axis=1).min()),
        'worst_signed_margin_uAeq':float(distance.min()), 'one_sided_margin_UI':margin['min_symbol_UI'],
        'one_sided_margin_ps':margin['min_ps'], 'sample_level_quantiles_uAeq':sample_levels,
        'transition_errors': {f'{a}->{b}': {'errors':bad_transitions[a,b], 'occurrences':transitions[a,b]}
                              for a,b in sorted(transitions)},
        'screen_pass': bool(train_errors==errors==0 and distance.min()>=AMPLITUDE_MARGIN
                            and margin['min_symbol_UI']>=TIME_MARGIN_UI),
    }
    return result


def waveform(folder, manifest, result, frozen=False):
    expressions = manifest['expressions']
    nodes = ['v(jmon)','v(xdrv.di)','v(xdrv.dbi)','v(xdrv.gp)','v(xdrv.gn)','v(xdrv.dr)',
             'v(xdrv.vx)','v(xdrv.dummy)','v(vl)','i(v.xdrv.vibase)','i(v.xdrv.vitail)']
    nodes += manifest.get('gate_nodes',[])
    p = folder/'waveform.dat.gz'
    if frozen and not p.exists():
        p = ROOT / result['waveform']['path']
    assert sha(p)==result['waveform']['sha256']
    with gzip.open(p,'rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==result['waveform']['raw_sha256']
    with gzip.open(p,'rt') as f:
        raw = np.loadtxt(f, skiprows=1, usecols=[0]+[expressions.index(n)+1 for n in nodes])
    return raw[:,0], dict(zip(nodes, raw[:,1:].T))


def ideal_current(time, bits, ui, edge_ps):
    position = time/ui
    k = np.minimum(np.floor(position).astype(int),len(bits)-1)
    last = bits[np.maximum(0,k-1)]
    fraction = np.clip((time-k*ui)/(edge_ps*1e-12),0,1)
    return .003 + .004*(last+fraction*(bits[k]-last))


def analyze(folder, rx, opto, frozen=False, oversample=128):
    manifest, solved = (read_json(folder/name) for name in ('manifest.json','result.json'))
    assert solved['simulation_ok']
    ns = manifest.get('net_Gbps',3.2)
    edge = manifest.get('source_edge_ps_0_to_100',20.)
    stim = read_json(folder/'stimulus.json')
    bits = np.asarray(stim['bits'])
    assert sha(folder/'stimulus.json')==manifest['stimulus_sha256']
    end = manifest['end_s']
    ui = end/len(bits)
    native_t, raw = waveform(folder, manifest, solved, frozen)
    t = np.linspace(0,end,len(bits)*oversample+1)
    signal = {name: np.interp(t,native_t,values) for name,values in raw.items()}
    current = signal['v(jmon)']
    current_ideal = ideal_current(t, bits, ui, edge)
    p0,p1 = opto.static_power([.003,.007])
    normalize = lambda p:25+75*(p-p0)/(p1-p0)
    eq_current = lambda i:25+75*(i-.003)/.004
    photo = normalize(opto.optical_power(t,current))
    photo_ideal = normalize(opto.optical_power(t,current_ideal))
    static_photo = normalize(opto.static_power(current))
    static_ideal = normalize(opto.static_power(current_ideal))
    pathways = {
        'actual_electrical': eq_current(current),
        'actual_graph_5GHzRX': one_pole(t, photo,5e9),
        'actual_graph_25GHzRX': one_pole(t,photo,25e9),
        'actual_static_25GHzRX': one_pole(t,static_photo,25e9),
        'actual_25GHzOpt_25GHzRX': one_pole(t,one_pole(t,static_photo,25e9),25e9),
        'ideal_graph_5GHzRX': one_pole(t,photo_ideal,5e9),
        'ideal_graph_25GHzRX': one_pole(t,photo_ideal,25e9),
        'ideal_25GHzOpt_25GHzRX': one_pole(t,one_pole(t,static_ideal,25e9),25e9),
        'ideal_static_25GHzRX':one_pole(t,static_ideal,25e9),
    }
    out = {name:receive(rx,t,x,bits,ui,end) for name,x in pathways.items()}
    d_diff = signal['v(xdrv.di)']-signal['v(xdrv.dbi)']
    dr = signal['v(xdrv.dr)']
    gate_pos, gate_neg = manifest.get('gate_nodes',['v(xdrv.gp)','v(xdrv.gn)'])
    gp,gn = signal[gate_pos],signal[gate_neg]
    gate_rail = manifest.get('gate_source_rail_V',dr)
    gates = THRESHOLD + 37.5*(gp-gn)/gate_rail
    inputs = THRESHOLD + 37.5*d_diff/3.3
    stages = {'predriver_input_polarity':receive(rx,t,inputs,bits,ui,end),
              'steering_gate_polarity':receive(rx,t,gates,bits,ui,end)}
    dummy = (signal['v(vl)']-signal['v(xdrv.dummy)'])/500
    observed = {'predriver_input_differential_peak_V':float(np.max(abs(d_diff))),
                'steering_gate_differential_peak_V':float(np.max(abs(gp-gn))),
                'laser_rail_range_V':[float(np.min(signal['v(vl)'])),float(np.max(signal['v(vl)']))],
                'predriver_rail_range_V':[float(dr.min()),float(dr.max())],
                'electrical_current_range_mA':[float(np.min(raw['v(jmon)'])*1e3),float(np.max(raw['v(jmon)'])*1e3)],
                'base_current_range_mA':[float(np.min(raw['i(v.xdrv.vibase)'])*1e3),float(np.max(raw['i(v.xdrv.vibase)'])*1e3)],
                'tail_current_range_mA':[float(np.min(raw['i(v.xdrv.vitail)'])*1e3),float(np.max(raw['i(v.xdrv.vitail)'])*1e3)],
                'dummy_resistor_current_range_mA':[float(dummy.min()*1e3),float(dummy.max()*1e3)],
                'optical_graph_negative_fraction':float(np.mean(photo<normalize(0.))),
                'within_calibrated_electrical_and_optical_current_range': bool(np.min(raw['v(jmon)'])>=.002 and np.max(raw['v(jmon)'])<=.0075),
                'terminal_screen_pass':solved.get('terminal_screen_pass',solved.get('device_screen_passed')),
                'terminal_peak':solved.get('terminal_peak',{'value_V':solved.get('max_terminal_V')}),
                'max_body_forward_V':solved['max_body_forward_V']}
    energy = {p:{k.replace('_J',''):v*1e12/PAYLOAD for k,v in row.items()} for p,row in solved['energy_by_port'].items()}
    totals = {k:sum(row[k] for row in energy.values()) for k in ['positive','returned','net']}
    metrics = {
        'run':str(folder.relative_to(ROOT)), 'frozen_baseline':frozen, 'net_Gbps':ns, 'line_GBd':1e-9/ui,
        'UI_ps':ui*1e12,'input_edge_ps_0_to_100':edge,'plot_grid_step_ps':ui/oversample*1e12,
        'ideal_gate_injection':manifest.get('gate_source_edge_ps') is not None,
        'forced_gate_edge_ps':manifest.get('gate_source_edge_ps'),
        'forced_gate_rail_V':manifest.get('gate_source_rail_V'),
        'forced_gate_driver_sha256':manifest.get('gate_control_driver_sha256'),
        'steps_per_UI':manifest.get('steps_per_UI',40), 'native_rows':len(native_t),
        'deck_sha256':sha(folder/'testbench.spice'),'stimulus_sha256':sha(folder/'stimulus.json'),
        'waveform':solved['waveform'],'ngspice_exit_code':solved['exit_code'],
        'ngspice_log_sha256':sha(folder/'ngspice.log'),'native_source_hashes':manifest.get('source_sha256',manifest.get('source_hashes')),
        'stages':stages,'observed':observed,'pathways':out,'source_energy_pJ_per_attempted_net_bit':totals,
        'energy_by_source_pJ_per_attempted_net_bit':energy,
    }
    if ns==32 and edge==20 and manifest.get('steps_per_UI')==40 and not metrics['ideal_gate_injection']:
        wide = np.arange(2049)/64
        metrics['wide_delay_control_0_to_32_UI'] = {
            'gate_polarity':receive(rx,t,gates,bits,ui,end,wide),
            'actual_electrical':receive(rx,t,pathways['actual_electrical'],bits,ui,end,wide),
            'actual_graph_5GHzRX':receive(rx,t,pathways['actual_graph_5GHzRX'],bits,ui,end,wide),
        }
    window = slice(576*oversample,592*oversample+1)
    traces = {'time_UI': t[window]/ui-576,'i_mA':current[window]*1e3,
              'ideal_mA':current_ideal[window]*1e3,'bits':bits[576:592],
              'pin_V':d_diff[window],'gate_V':(gp-gn)[window],
              **{name:values[window] for name,values in pathways.items()}}
    return metrics,traces


def render(cases):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    chosen = [pair for pair in cases if pair[0]['frozen_baseline'] or
              (pair[0]['net_Gbps']==32 and pair[0]['steps_per_UI']==40 and not pair[0]['ideal_gate_injection'])]
    fig, axs = plt.subplots(3,len(chosen),figsize=(5*len(chosen),7),sharex=True,layout='constrained')
    for col,(m,trace) in enumerate(chosen):
        u=trace['time_UI']
        ax=axs[0,col]
        ax.set_title(f'{m["net_Gbps"]:g} Gb/s net | {m["line_GBd"]:g} GBd | {m["input_edge_ps_0_to_100"]:g} ps edge')
        ax.plot(u,trace['pin_V'],label='DI − DBI',color='#265c91')
        ax.plot(u,trace['gate_V'],label='GP − GN',color='#9a6035')
        ax.axhline(0,color='.7',lw=.7)
        ax.set_ylabel('Differential (V)')
        ax.legend(loc='lower left',fontsize=8)
        ax=axs[1,col]
        ax.plot(u,trace['i_mA'],label='r10 conduction current',color='#186c62')
        ax.plot(u,trace['ideal_mA'],label='Ideal 3/7 mA current',color='#737f83',alpha=.65)
        ax.set_ylabel('Current (mA)')
        ax.legend(loc='lower left',fontsize=8)
        ax=axs[2,col]
        for name,label,color in [('actual_graph_5GHzRX','Actual + original RX','#9a6035'),
                                 ('actual_graph_25GHzRX','Actual + 25 GHz RX','#265c91'),
                                 ('ideal_25GHzOpt_25GHzRX','Ideal current + two 25 GHz poles','#186c62')]:
            ax.plot(u,trace[name],label=label,color=color)
        ax.axhline(THRESHOLD,ls='--',lw=.7,color='.6')
        ax.set_ylabel('Receiver proxy (µAeq)')
        ax.set_xlabel('UI from validation start')
        ax.legend(loc='lower left',fontsize=7.5)
        for ax in axs[:,col]:
            ax.set_xlim(0,16)
            ax.set_xticks(np.arange(0,17,2))
            ax.grid(alpha=.16)
    fig.savefig(DOC/'vcsel-x10-waveforms.png',dpi=155)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cases',nargs='+',help='Case directory names; "baseline" uses frozen 3.2G raw')
    parser.add_argument('--oversample',type=int,default=128)
    args = parser.parse_args()
    rx = module(RX_PATH,'vcsel_x10_offline_rx')
    opto = module(OPTO_PATH,'vcsel_x10_optical')
    cases = []
    for name in args.cases:
        frozen = name=='baseline'
        m,traces = analyze(SAVED if frozen else BUILD/name, rx, opto, frozen,args.oversample)
        cases.append((m,traces))
        print(f'{name}: ' + ', '.join(f'{key}={data["errors"]}' for key,data in m['pathways'].items()),flush=True)
    summary = {
        'comparison':'VCSEL r10 transistor re-evaluation at fixed frame efficiency 4096/4736',
        'scope':'Electrical transistor model with fixed hypothetical package and VCSEL graph response; all receiver variants are deterministic offline controls with separately trained delays. No device, PCB PHY or optical test.',
        'screen':{'training_scored_bits':[64,512], 'validation_bits':[576,4672],
                  'delay_UI':[0,8],'delay_step_UI':1/64,'minimum_one_sided_UI':TIME_MARGIN_UI,
                  'minimum_signed_uAeq':AMPLITUDE_MARGIN,
                  'threshold_uAeq':THRESHOLD,'training_and_validation_errors':0,
                  'selection':'Maximize min(worst training signed margin / 7.5 µAeq, min training one-sided time margin / 0.37 UI); earliest tie.',
                  'note':'Historical 100 ps at 3.7 GBd equals 0.37 UI; scaled requirement is a new deterministic diagnostic, not a timing specification or BER certification.'},
        'normalized_3mA_7mA_uAeq':[25,100],
        'controls':{
            'actual_electrical':'Conduction current transformed linearly, bypasses optical and RX.',
            'actual_graph_5GHzRX':'Original published-figure shape proxy at 3 mA and original 5 GHz RX pole.',
            'actual_graph_25GHzRX':'Original optical proxy plus hypothetical 25 GHz RX pole.',
            'actual_static_25GHzRX':'Bypass optical dynamics but keep P-I nonlinearity and 25 GHz RX pole.',
            'actual_25GHzOpt_25GHzRX':'Simulated conduction current with assumed 25 GHz optical pole and 25 GHz RX pole. Retains static P-I.',
            'ideal_graph_5GHzRX':'Replace circuit/LED electrical response with ideal 3/7 mA current, same per-case ramp; original optical/RX.',
            'ideal_graph_25GHzRX':'Ideal current control, original optical proxy, hypothetical 25 GHz RX pole.',
            'ideal_25GHzOpt_25GHzRX':'Ideal current control, static P-I plus assumed 25 GHz optical pole and 25 GHz RX pole. Illustrative target, not matched to any actual 25 GHz part.',
            'ideal_static_25GHzRX':'Ideal current control, no optical dynamics, 25 GHz RX pole.',
        },
        'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),RX_PATH,OPTO_PATH,PARAMETERS]},
        'cases':[m for m,_ in cases],
    }
    emit(EV/'vcsel-x10-summary.json',summary)
    render(cases)


if __name__=='__main__':
    main()
