#!/usr/bin/env python3
"""Reproduce the r10 LDO AC diagnostic from its frozen DC testbenches.

Default: verify all six retained decks and recalculate their stored AC data.
--run-missing: run ngspice only for absent cases; existing evidence is not rewritten.
The legacy descending-crossing calculation is reproduced for provenance only.
Additional ascending crossings are affected by input loading; this ratio is not
a verified return ratio. See audit-ac-all-crossings.json, not the first PM field,
for the withdrawn stability interpretation.
"""
from pathlib import Path
import argparse, json, re, subprocess
import numpy as np
from run import ROOT, BUILD, CIR, EV, sha, emit


def prepare(label, branch):
    src=BUILD/f'regulated-{label}-1-r10'
    work=BUILD/f'ac-final-{label}-{branch}-r10'
    original=(src/'inputs/driver.spice').read_text()
    assert original==(CIR/'regulated-r10.spice').read_text()
    lines=[]
    for line in original.splitlines():
        w=line.split()
        if line.startswith('X') and len(w)>5 and w[2]==branch+'fb':
            w[2]+='_test';line=' '.join(w)
        lines.append(line)
    text='\n'.join(lines).replace('.ends vcsel_servo',f'VLOOP {branch}fb_test {branch}fb DC 0 AC 1\n.ends vcsel_servo')+'\n'
    deck=(src/'testbench.spice').read_text().replace(str(src/'inputs/driver.spice'),str(work/'driver.spice'))
    deck=re.sub(r'CLDO=\S+','CLDO=3e-11',deck)
    deck=deck[:deck.index('.control')]+f'''.control
set numdgt=12
set wr_singlescale
set wr_vecnames
save v(xdrv.{branch.lower()}fb) v(xdrv.{branch.lower()}fb_test)
ac dec 60 1 1e9
wrdata ac.dat v(xdrv.{branch.lower()}fb) v(xdrv.{branch.lower()}fb_test)
quit
.endc
.end
'''
    return src,work,text,deck


def inspect(label,branch,run_missing=False):
    src,work,text,deck=prepare(label,branch)
    retained=(work/'result.json').exists()
    if not retained:
        assert run_missing, f'Missing case: {work.name}; use --run-missing after restoring its DC inputs'
        assert not work.exists(),f'Incomplete case must be preserved and investigated: {work}'
        work.mkdir();(work/'driver.spice').write_text(text);(work/'testbench.spice').write_text(deck)
        with (work/'ngspice.log').open('w') as f:
            subprocess.run(['ngspice','-b','testbench.spice'],cwd=work,stdout=f,stderr=subprocess.STDOUT,check=True)
    assert (work/'driver.spice').read_text()==text,work.name
    assert (work/'testbench.spice').read_text()==deck,work.name
    a=np.loadtxt(work/'ac.dat',skiprows=1);freq=a[:,0]
    gain=-(a[:,1]+1j*a[:,2])/(a[:,3]+1j*a[:,4]);mag=20*np.log10(abs(gain));phase=np.unwrap(np.angle(gain))*180/np.pi
    xs=[]
    for k in np.flatnonzero((mag[:-1]>=0)&(mag[1:]<0)):
        alpha=mag[k]/(mag[k]-mag[k+1])
        xs.append(dict(unity_Hz=float(np.exp(np.log(freq[k])*(1-alpha)+np.log(freq[k+1])*alpha)),phase_margin_deg=float(180+phase[k]*(1-alpha)+phase[k+1]*alpha)))
    m=json.loads((src/'manifest.json').read_text())
    result=dict(case=work.name,branch=branch,corner=m['config']['corner'],rz_ohm=100000.,bleed_ohm=5000.,cldo_F=30e-12,
                low_frequency_gain_dB=float(mag[0]),unity_crossings=xs,exit_code=0,source_circuit_sha256=sha(src/'inputs/driver.spice'),
                modified_circuit_sha256=sha(work/'driver.spice'),deck_sha256=sha(work/'testbench.spice'),data_sha256=sha(work/'ac.dat'),
                method='Approximate -Vfb/Vfb_test series voltage injection at amplifier feedback gate, DC operating point retained; input capacitance nonzero, not a formal foundry stability signoff',
                revision='r10',source_case=src.name,dc_state=json.loads((src/'result.json').read_text())['nodes_final_V'],
                interpretation='SS dropout is not regulation; do not label missingunitycrossing as sufficientPM' if label=='SS' else 'RegulatedDC operatingpoint, one selectedfeedbackgate injection')
    if retained:
        prior=json.loads((work/'result.json').read_text())
        assert prior==result,work.name
    else:
        emit(work/'result.json',result);np.savez_compressed(work/'plot.npz',frequency_Hz=freq,loop_gain_dB=mag,phase_deg=phase)
    return dict(case=work.name,retained_bytes_unmodified=retained,source_sha256=result['source_circuit_sha256'],deck_sha256=result['deck_sha256'],data_sha256=result['data_sha256'],recomputed_values_match=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-missing',action='store_true');args=p.parse_args()
    rows=[inspect(c,b,args.run_missing) for c in ['TT','SS','FF'] for b in ['L','D']]
    receipt=dict(status='PASS',script_sha256=sha(Path(__file__)),rows=rows,scope='Reconstructed deck/text and stored legacy AC arithmetic only; no ngspice rerun when cases already exist. The first PM field is not established phase margin: ascending crossings and input loading invalidate a general return-ratio interpretation. No stability claim.',
                 stability_evidence=False,interpretation_audit='evidence/vcsel-robustness-20261029/audit-ac-all-crossings.json')
    emit(EV/'ac-r10-reproduction-check.json',receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))
