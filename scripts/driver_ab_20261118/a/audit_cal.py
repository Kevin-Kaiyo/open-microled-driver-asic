"""Check that SAR sees only the quantized shunt voltage; read actual rails from each held-out netlist."""
from pathlib import Path
import re
import numpy as np
import run as a


def check(path):
    row=a.read(path)
    codes=[128,128]
    for level in [0,1]:
        lo,hi=1,255
        cand=[]
        prior_end=False
        for h in [h for h in row['history'] if h['level']==level]:
            assert not prior_end and lo<=hi
            code=(lo+hi)//2
            assert code==h['code']
            codes[level]=code
            case=a.ROOT/h['path']
            r=a.read(case/'result.json');m=a.read(case/'manifest.json')
            assert r['codes']==codes
            vals=np.loadtxt(case/'waveform.dat.gz',skiprows=1,ndmin=2)[-1]
            v=vals[m['vectors']['mon']]-vals[m['vectors']['out']]
            q=round((v*row['gain']+row['offset_uV']*1e-6)/5e-6)
            assert q==h['observed_adc']
            qtarget=[500,2000][level]
            cand.append((abs(q-qtarget),code))
            if q<qtarget:lo=code+1
            elif q>qtarget:hi=code-1
            else:prior_end=True
        assert prior_end or lo>hi
        codes[level]=min(cand)[1]
    assert codes==row['codes']
    for level,f in enumerate(row['final']):
        folder=a.ROOT/f['case_path'];r=a.read(folder/'result.json')
        assert r['codes']==codes and abs(r['current_uA']-f['current_uA'])<1e-12
        assert r['case']['level']==level
    return dict(calibration=str(path.relative_to(a.ROOT)),sha256=a.sha(path),reads=len(row['history']),codes=codes)

def main():
    checks=[check(p) for p in sorted(a.EV.glob('*-*.json')) if 'history' in a.read(p)]
    rails=[]
    for f in sorted(a.BUILD.glob('sense-hold*/*/manifest.json')):
        m=a.read(f)
        _,section,temp,scale=m['pvt']
        deck=(f.parent/'testbench.spice').read_text()
        values={k:float(re.search(r'(?m)^'+k+r' \w+ 0 (\S+)$',deck)[1]) for k in ['VIN','VLED','VDD','VREF']}
        assert np.allclose([values[k] for k in ['VIN','VLED','VDD','VREF']],[scale*5,scale*5,scale*3.3,2.5],rtol=1e-13)
        assert f'.temp {temp}\n' in deck and f'sm141064.ngspice" {section}\n' in deck
        rails.append(dict(case=str(f.parent.relative_to(a.ROOT)),temp_C=temp,process=section,actual_deck_rails_V=values))
    a.emit(a.EV/'calibration-audit.json',dict(sar=checks,holdout_decks=rails,
        interpretation='Two held-out operating points, not holdout PRBS. Frozen manifests retain parent template rails_V; actual rail values were read from source lines above. case.holdout describes bit-pattern provenance; indicates no PRBS holdout.'))
    print('Verified',len(checks),'calibration histories,',len(rails),'held-out operating-point decks.')
if __name__=='__main__':main()
