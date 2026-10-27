#!/usr/bin/env python3
"""Check implementation against its encoded data/equations, not silicon validity."""
import csv,hashlib,json,platform,subprocess,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import PIL
from vcsel_model import PARAMETERS,static_voltage,static_power,optical_power,filter_power,transfer_function

ROOT=Path(__file__).resolve().parents[2]
MODEL=ROOT/'analog/models/vcsel_research_20261027'
BUILD=ROOT/'build/three-gbps-experiment-20261027/vcsel-model'
EVID=ROOT/'evidence/three-gbps-experiment-20261027/vcsel-model'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    BUILD.mkdir(parents=True,exist_ok=True);EVID.mkdir(parents=True,exist_ok=True)
    spice=MODEL/'vcsel_research.spice';records=[];dc=None
    for cap in PARAMETERS['electrical_assumptions']['CJ_F']['sweep']:
        tag=f'{cap*1e15:.0f}f';deck=BUILD/f'load-{tag}.cir';out=BUILD/f'ac-{tag}.tsv';dcfile=BUILD/f'dc-{tag}.tsv'
        deck.write_text(f'''* Independent proxy implementation checks
.include {spice}
Vdrive a 0 DC 2.039 AC 1
Xload a 0 jmon vcsel_research CJ={cap}
.control
set wr_singlescale
set wr_vecnames
dc Vdrive 0 2.25 .001
wrdata {dcfile} v(a) v(jmon)
ac dec 30 1meg 100g
let yr = real(-i(vdrive))
let yi = imag(-i(vdrive))
wrdata {out} yr yi
quit
.endc
.end
''')
        run=subprocess.run(['ngspice','-b',str(deck)],capture_output=True,text=True)
        log=BUILD/f'load-{tag}.log';log.write_text(run.stdout+'\n'+run.stderr)
        if run.returncode or not out.exists():raise RuntimeError(f'ngspice failed: {log}')
        ac=np.loadtxt(out,skiprows=1);freq=ac[:,0];measured=ac[:,1]+1j*ac[:,2]
        expected=1/.070*.001+2j*np.pi*freq*cap
        err=float(np.max(np.abs(measured-expected)/np.abs(expected)))
        dc=np.loadtxt(dcfile,skiprows=1)
        currents=np.arange(2,8.001,.5)*.001
        actual=np.interp(currents,dc[:,2],dc[:,1]);target=static_voltage(currents)
        dcerr=float(abs(actual-target).max())
        records.append({'CJ_F':cap,'ngspice_exit_code':run.returncode,'dc_max_voltage_implementation_error_V':dcerr,'dc_acceptance_V':.0011,'ac_max_relative_admittance_error':err,'ac_acceptance':1e-5,'dc_status':'pass' if dcerr<.0011 else 'fail','ac_status':'pass' if err<1e-5 else 'fail','ac_bias_V':2.039,'ac_bias_A':.0055,'reference':'analytic G+jwC with local PWL G=1/70ohm, not measured S11','deck_sha256':sha(deck),'log_sha256':sha(log)})
    # Continuous transfer function versus actual ZOH implementation at representative frequencies.
    dt=.25e-12; t=np.arange(80001)*dt;optchecks=[]
    for response in ['figure3mA_proxy','lowpass8GHz_assumed','lowpass4GHz_assumed']:
        for f in [1e9,3.7e9,8e9,15e9]:
            # This sinusoid is injected at optical filter input to isolate implementation.
            x=.002+.0001*np.cos(2*np.pi*f*t);y=filter_power(t,x,response)
            take=t>=10e-9;A=np.column_stack([np.ones(take.sum()),np.cos(2*np.pi*f*t[take]),np.sin(2*np.pi*f*t[take])]);coef=np.linalg.lstsq(A,y[take],rcond=None)[0]
            gain=float(np.hypot(coef[1],coef[2])/.0001);ideal=float(abs(transfer_function(f,response)))
            err=abs(gain/ideal-1)
            optchecks.append({'response':response,'frequency_Hz':f,'measured_numeric_gain':gain,'continuous_formula_gain':ideal,'relative_error':err,'acceptance':.001,'status':'pass' if err<.001 else 'fail'})
    # DC equilibrium; actual 3->7mA step shows any overshoot instead of clipping it away.
    tstep=np.arange(8001)*.5e-12;i=np.where(tstep<1e-9,.003,.007);ystep=optical_power(tstep,i)
    staterr=float(np.max(abs(optical_power(tstep,np.full(tstep.shape,.003))-static_power(.003))))
    fit=json.loads((EVID/'shape-fit-summary.json').read_text())
    summary={'evidence_level':'behavioral electrical/optical research proxy implementation checks; not physical calibration or optical measurement','ngspice_version':subprocess.run(['ngspice','--version'],capture_output=True,text=True).stdout.splitlines()[1:4],'electrical':records,'optical_numeric':optchecks,'optical_static_error_W':staterr,'step':{'current_low_A':.003,'current_high_A':.007,'power_min_W':float(ystep.min()),'power_max_W':float(ystep.max()),'steady_final_W':float(ystep[-1]),'expected_final_W':float(static_power(.007))},'figure_shape_agreement':{'RMS_dB':PARAMETERS['dynamic']['fit_rms_dB'],'max_abs_dB':PARAMETERS['dynamic']['fit_max_abs_dB'],'digitization_uncertainty_dB':.6,'status':'rough shape match only; maximum error exceeds digitization uncertainty','no_phase_validation':True},'pass':all(r['dc_status']==r['ac_status']=='pass' for r in records) and all(r['status']=='pass' for r in optchecks) and staterr<1e-12,'scope_warning':'PASS checks implementation against its own equations; no same-device S11, dynamic phase, large-signal or physical model validation.'}
    summary['runtime_versions']={'python':platform.python_version(),'numpy':np.__version__,'pillow':PIL.__version__,'matplotlib':matplotlib.__version__}
    (EVID/'validation.json').write_text(json.dumps(summary,indent=2)+'\n')
    fig,ax=plt.subplots(2,2,figsize=(12,8),layout='constrained');fig.suptitle('VCSEL research proxy: public-figure constraints and implementation checks')
    p=PARAMETERS['iv'];ax[0,0].errorbar(np.array(p['current_A'])*1e3,p['voltage_V'],yerr=.020,fmt='o',label='Fig.8A approximate measured dots')
    ax[0,0].plot(dc[:,2]*1e3,dc[:,1],label='SPICE PWL');ax[0,0].set(xlim=(0,8.5),ylim=(1.45,2.25),xlabel='Current (mA)',ylabel='Terminal voltage (V)',title='25 C static I-V; +/−20 mV figure read')
    p=PARAMETERS['pi'];ax[0,1].errorbar(np.array(p['current_A'][1:])*1e3,np.array(p['power_W'][1:])*1e3,yerr=.08,fmt='o-',label='Fig.8A blue overlapping trace');ax[0,1].set(xlabel='Current (mA)',ylabel='Optical-power proxy (mW)',title='Not measured output of this project')
    freq=np.linspace(0,20e9,1001)
    ax[1,0].errorbar(np.array(fit['frequency_Hz'])/1e9,fit['figure_read_dB'],yerr=.6,fmt='.',label='Fig.8B 3mA manual measured-point estimates')
    for response in ['figure3mA_proxy','lowpass8GHz_assumed','lowpass4GHz_assumed']:ax[1,0].plot(freq/1e9,20*np.log10(abs(transfer_function(freq,response))),label=response)
    ax[1,0].set(xlabel='Frequency (GHz)',ylabel='Normalized magnitude (dB)',title='No phase / electrical de-embedding validation',ylim=(-20,6))
    ax[1,1].plot((tstep-1e-9)*1e12,ystep*1e3,label='3 -> 7mA, fixed 3mA shape');ax[1,1].axhline(float(static_power(.007))*1e3,color='gray',ls='--');ax[1,1].set(xlim=(-100,700),xlabel='Time from transition (ps)',ylabel='Optical-power proxy (mW)',title='Large-signal use is an unvalidated approximation')
    for a in ax.flat:a.grid(alpha=.2);a.legend(fontsize=7)
    fig.savefig(EVID/'model-checks.png',dpi=150);plt.close(fig)
    manifest=[]
    for p in sorted(list(MODEL.glob('*'))+list(EVID.glob('*'))+list((ROOT/'scripts/three_gbps_experiment').glob('vcsel_model*.py'))):
        if p.is_file() and p.name!='manifest.json':manifest.append({'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)})
    (EVID/'manifest.json').write_text(json.dumps({'files':manifest,'raw_logs_and_netlists':str(BUILD.relative_to(ROOT))},indent=2)+'\n')
    print(json.dumps({'implementation_checks_pass':summary['pass'],'electrical_records':len(records),'optical_numeric_records':len(optchecks),'optical_static_error_W':staterr,'step':summary['step']},indent=2))
    return 0 if summary['pass'] else 1
if __name__=='__main__':sys.exit(main())
