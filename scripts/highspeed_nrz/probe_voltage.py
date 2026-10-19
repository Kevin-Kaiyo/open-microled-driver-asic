#!/usr/bin/env python3
"""Prototype route A with the pinned full PDK; this is not link qualification."""
from pathlib import Path
import hashlib, json, math, subprocess

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'build/highspeed-nrz/voltage-probe'
PDK = ROOT / 'build/layout/pdk/gf180mcuD/libs.tech/ngspice'
DUT = ROOT / 'analog/highspeed_nrz/voltage_driver.spice'
LED = ROOT / 'analog/models/measured-led/lin2026-yellow20-dc.spice'
FIELDS = ['data', 'out', 'led_k', 'n1', 'ctrl', 'iled', 'ivled', 'ivdd', 'ivh', 'ivl', 'idata']
VECTORS = 'v(data) v(out) v(led_k) v(xdrv.n1) v(xdrv.ctrl) i(vmon) i(vled) i(vdd) i(vh) i(vl) i(vdata)'

def run(name, vh, vl, data=0, rate=None):
    folder = WORK / name
    folder.mkdir(parents=True, exist_ok=True)
    for fn in ('design.ngspice', 'sm141064.ngspice'):
        p = folder / fn
        if not p.exists(): p.symlink_to(PDK / fn)
    if rate:
        ui = 1 / rate
        source = f'PULSE(0 3.3 {ui:.16g} 20p 20p {ui-20e-12:.16g} {2*ui:.16g})'
        command = f'tran {min(ui/100,4e-12):.16g} {10*ui:.16g} 0 {min(ui/200,4e-12):.16g}'
    else:
        source, command = str(data), 'op'
    deck = f'''Route A transistor prototype: {name}
.include design.ngspice
.param sw_stat_global=0 sw_stat_mismatch=0
.lib sm141064.ngspice typical
.include "{DUT}"
.include "{LED}"
.temp 27
VDD vdd 0 3.3
VH vh 0 {vh:.16g}
VL vl 0 {vl:.16g}
VLED led_a 0 5
VMON led_a led_dc 0
XLED led_dc led_k lin2026_yellow20_dc
CLED led_a led_k 200f
RPKG led_k pkg 1
LPKG pkg out 0.5n
VDATA data 0 {source}
XDRV data out vdd vh vl 0 hs_voltage_driver
.options reltol=1e-5 abstol=1e-14 vntol=1e-8 method=trap
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
{command}
wrdata values.dat {VECTORS}
quit
.endc
.end
'''
    (folder / 'testbench.spice').write_text(deck)
    result = subprocess.run(['/opt/homebrew/bin/ngspice', '-b', 'testbench.spice'], cwd=folder, text=True, capture_output=True)
    (folder / 'ngspice.log').write_text(result.stdout + result.stderr)
    if result.returncode or not (folder / 'values.dat').exists():
        raise RuntimeError(f'{name}: ngspice failed; see {folder}/ngspice.log')
    rows = []
    for line in (folder / 'values.dat').read_text().splitlines()[1:]:
        values = list(map(float, line.split()))
        if len(values) != len(FIELDS)+1 or not all(map(math.isfinite, values)):
            raise ValueError(f'{name}: malformed/nonfinite result')
        rows.append(dict(zip(['time' if rate else 'op_scale']+FIELDS, values)))
    return rows

def integral(rows, values):
    return sum((rows[i]['time']-rows[i-1]['time'])*(values[i]+values[i-1])/2 for i in range(1, len(rows)))

def stresses(rows, vh, vl):
    terminal_maps = {
        'XN1': ('n1','data',0,0), 'XP1': ('n1','data',3.3,3.3),
        'XN2': ('ctrl','n1',0,0), 'XP2': ('ctrl','n1',3.3,3.3),
        'XNOUT': ('out','ctrl',vl,0), 'XPOUT': ('out','ctrl',vh,vh),
    }
    pairs = ['gs','gd','gb','ds','db','sb']
    output = {}
    for name, source in terminal_maps.items():
        records = []
        for row in rows:
            nodes = dict(zip('dgsb', [row[x] if isinstance(x,str) else x for x in source]))
            records.append({p:nodes[p[0]]-nodes[p[1]] for p in pairs})
        output[name] = {p:{'min_V':min(r[p] for r in records),'max_V':max(r[p] for r in records),'max_abs_V':max(abs(r[p]) for r in records)} for p in pairs}
    return output

def main():
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK/'ngspice-version.txt').write_text(subprocess.check_output(['/opt/homebrew/bin/ngspice','--version'], text=True))
    vh, vl = 1.63, 1.20
    trace=[]
    # Finite-difference Newton calibration of each dedicated rail at DC.
    for bit, target in [(0,25e-6),(1,100e-6)]:
        for k in range(6):
            row=run(f'calibrate-bit{bit}-{k}',vh,vl,data=3.3*bit)[0]
            trace.append({'bit':bit,'iteration':k,'vh_V':vh,'vl_V':vl,'iled_A':row['iled']})
            err=row['iled']-target
            if abs(err)<1e-11:break
            dh=1e-4
            row2=run(f'calibrate-bit{bit}-{k}-diff',vh+dh*(bit==0),vl+dh*(bit==1),data=3.3*bit)[0]
            slope=(row2['iled']-row['iled'])/dh
            correction=max(-.1,min(.1,err/slope))
            if bit: vl-=correction
            else: vh-=correction
        if abs(row['iled']-target)>1e-9:raise RuntimeError('Calibration failed')
    dc={str(bit):run(f'dc-final-{bit}',vh,vl,data=3.3*bit)[0] for bit in (0,1)}
    cases=[]
    for rate in (100e6,1e9):
        rows=run(f'tran-{rate:g}',vh,vl,rate=rate)
        stable=[r for r in rows if r['time']>=2/rate]
        dt=stable[-1]['time']-stable[0]['time']
        powers={}
        for name,voltage,key in [('VLED',5,'ivled'),('VDD',3.3,'ivdd'),('VH',vh,'ivh'),('VL',vl,'ivl')]:
            power=[-voltage*r[key] for r in stable]
            powers[name]={'signed_delivered_W':integral(stable,power)/dt,'positive_delivered_W':integral(stable,[max(0,p) for p in power])/dt,'absorbed_W':integral(stable,[max(0,-p) for p in power])/dt}
        total=sum(p['signed_delivered_W'] for p in powers.values())
        gross=sum(p['positive_delivered_W'] for p in powers.values())
        cases.append({'rate_bps':rate,'pattern':'1010, 10 UI, power window 2 UI through 10 UI','rows':len(rows),'rail_powers':powers,'signed_power_W':total,'positive_delivered_power_W':gross,'signed_energy_J_per_bit':total/rate,'positive_delivered_energy_J_per_bit':gross/rate,'led_current_min_A':min(r['iled'] for r in stable),'led_current_max_A':max(r['iled'] for r in stable),'out_min_V':min(r['out'] for r in stable),'out_max_V':max(r['out'] for r in stable),'terminal_stresses':stresses(rows,vh,vl)})
    files=[DUT,LED,Path(__file__),PDK/'design.ngspice',PDK/'sm141064.ngspice']
    payload={'status':'transistor prototype; no optical/BER validation','interface':'hs_voltage_driver data out vdd vh vl vss','logic':'DATA=1 => CTRL=1 => OUT low => LED current high','internal_nodes':['n1','ctrl'],'rails':{'VLED_V':5,'VDD_V':3.3,'VH_V':vh,'VL_V':vl},'device_sizing':{'L_um':.28,'XN1_W_um':1,'XP1_W_um':2,'XN2_W_um':4,'XP2_W_um':8,'XNOUT_W_um':4,'XPOUT_W_um':8,'diffusion_extension_um':.6},'assumptions':['TT 27 C only','Measured static LED I-V, assumed 200 fF capacitance; no carrier model in this prototype','Rpackage=1 ohm, Lpackage=0.5 nH are assumptions','Ideal VLED, VDD, VH and VL sources. VH/VL can absorb current; regulator loss and implementation excluded.','20 ps ideal DATA edge; input source driver energy excluded, input current waveform retained','Positive delivered rail power is summed per rail per time sample and gives no credit for rail absorption; it still excludes actual regulator loss','Transient alternation is an initial functional check, not PRBS eye or maximum data-rate evidence','Nonzero device diffusion capacitance uses isolated rectangles, not PEX'],'dc':dc,'calibration_trace':trace,'prototype_cases':cases,'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    out=ROOT/'evidence/highspeed-nrz/voltage-prototype.json'
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps({'rails':payload['rails'],'dc_current_A':{k:v['iled'] for k,v in dc.items()},'cases':[{k:c[k] for k in ('rate_bps','signed_power_W','positive_delivered_power_W','led_current_min_A','led_current_max_A')} for c in cases]},indent=2))

if __name__=='__main__':main()
