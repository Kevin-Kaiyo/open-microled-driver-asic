"""Double-injection AC on exact extracted macro at X6 sense-input gate.
Flattening only removes the subckt wrapper; R/C/MOS connectivity is unchanged.
Both independent test sources have zero DC, retaining bias and terminal loads.
"""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[2];PDK=ROOT/'build/layout/pdk/gf180mcuD/libs.tech/ngspice'
ENV={'tt':('typical',27,3.3,5),'ss':('ss',85,2.97,4.5),'ff':('ff',0,3.63,5.5)}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--netlist',type=Path,required=True);ap.add_argument('--tag',required=True);ap.add_argument('--bleed-ohm',type=float);a=ap.parse_args();a.netlist=a.netlist.resolve();w=Path(tempfile.mkdtemp(prefix='ac-'+a.tag+'-',dir=ROOT/'build/analog-v3'))
 shutil.copyfile(a.netlist,w/'dut.spice');text=(w/'dut.spice').read_text();lines=[];inheader=False
 for line in text.splitlines():
  if line.lower().startswith('.subckt'):inheader=True;continue
  if inheader and line.startswith('+'):continue
  inheader=False
  if line.lower().startswith('.ends'):continue
  lines.append(line)
 body='\n'.join(lines);x6=next(l for l in lines if l.startswith('X6 '));ports=x6.split();gate=ports[2];assert gate.upper().startswith('SENSE') and 'pfet_06v0' in x6
 openbody=body.replace(x6,' '.join(ports[:2]+['FB_IN']+ports[3:]))
 rows=[]
 for env,(co,t,v,l) in ENV.items():
  for cc,cs in [(3,0),(3,30),(30,0),(30,30)]:
   outputs={};ops=[]
   for method in ['voltage','current','closed']:
    p=w/f'{env}_cc{cc}_cs{cs}_{method}';p.mkdir()
    if method=='voltage':extra=f'VINJECT FB_IN {gate} DC 0 AC 1';out=f'v({gate}) v(FB_IN)';dut=openbody
    elif method=='current':extra=f'VRETURN INJECT {gate} 0\nVFORWARD INJECT FB_IN 0\nIINJECT 0 INJECT DC 0 AC 1';out='i(VRETURN) i(VFORWARD)';dut=openbody
    else:extra='';out='v(sense)';dut=body
    ctl='ac dec 100 1 1G\nwrdata ac.dat '+out if method!='closed' else ''
    d=f'''Full exact macro double injection {a.tag}
.include "{PDK}/design.ngspice"
.param sw_stat_global=0 sw_stat_mismatch=0 LED_IS=2.2725351141552272e-20
.lib "{PDK}/sm141064.ngspice" {co}
.temp {t}
VGROUND VSS 0 0
VREF VREF 0 {v}
VSAFE VSAFE 0 {v}
VBUF VBUF 0 {v}
VLED LED_A 0 {l}
VRAW RAW_PWM 0 {v}
VFAULT FAULT 0 0
VPERMIT PERMIT 0 {v}
VSET VSET 0 .5
RSET SENSE 0 5k
RBIAS PB 0 100k
RRELEASE LED_A FAULT_HB 100k
CCOMP N2 CTRL {cc}p
CSENSE SENSE 0 {cs}p
{'RBLEED REFOUT 0 '+str(a.bleed_ohm) if a.bleed_ohm else '* No REFOUT bleed'}
.include "{ROOT}/analog/models/microled.spice"
XLED LED_A LED_K microled
{dut}
{extra}
.options reltol=1e-7 abstol=1e-14 vntol=1e-9
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
save all
op
wrdata op.dat v(sense) v(refout) v(bias) v(led_k) v(n2) v(ctrl)
{ctl}
quit
.endc
.end
'''
    (p/'testbench.spice').write_text(d);r=subprocess.run(['ngspice','-b','testbench.spice'],cwd=p,text=True,capture_output=True);(p/'ngspice.log').write_text(r.stdout+r.stderr)
    if r.returncode or re.search(r'(?im)^Error:|timestep too small|simulation interrupted',r.stdout+r.stderr):raise RuntimeError(str(p))
    ops.append(np.loadtxt(p/'op.dat',skiprows=1))
    if method!='closed':outputs[method]=np.loadtxt(p/'ac.dat',skiprows=1)
   av=outputs['voltage'];ai=outputs['current'];f=av[:,0];tv=-(av[:,1]+1j*av[:,2])/(av[:,3]+1j*av[:,4]);ti=(ai[:,1]+1j*ai[:,2])/(ai[:,3]+1j*ai[:,4]);T=(tv*ti-1)/(tv+ti+2);g=20*np.log10(abs(T));ph=np.unwrap(np.angle(T))*180/np.pi;j=np.flatnonzero((g[:-1]>=0)&(g[1:]<0));cross=[dict(frequency_hz=float(10**np.interp(0,[g[k+1],g[k]],[np.log10(f[k+1]),np.log10(f[k])])),phase_margin_deg=float(180+np.interp(0,[g[k+1],g[k]],[ph[k+1],ph[k]]))) for k in j];delta=max(float(np.max(np.abs(op-ops[-1]))) for op in ops[:-1]);row=dict(envelope=env,cc_pf=cc,csense_pf=cs,crossings=cross,dc_closed_vs_injected_max_delta=delta,dc_loop_gain_db=float(g[0]),phase_margin_60deg_pass=bool(cross) and all(x['phase_margin_deg']>=60 for x in cross));rows.append(row);np.savetxt(w/f'{env}_cc{cc}_cs{cs}.csv',np.c_[f,g,ph],delimiter=',',header='frequency_hz,loop_gain_db,loop_phase_deg',comments='')
 result=dict(schema_version=1,tag=a.tag,bleed_ohm=a.bleed_ohm,raw_directory=str(w.relative_to(ROOT)),dut_source=str(a.netlist.relative_to(ROOT)),dut_sha256=sha(w/'dut.spice'),script_sha256=sha(Path(__file__)),reference_input_gate=gate,results=rows,method='Double injection Tv=-V(return)/V(forward); Ti=I(outgoing_return)/I(outgoing_forward), T=(Tv*Ti-1)/(Tv+Ti+2). AC voltage source0VDC/current0ADC retain operating point. Compared every injected operating point against original shorted feedback circuit.',limitations=['Middlebrook local small-signal estimate; not full silicon stability qualification. Bidirectional transfer and interacting loops can require Tian/return-ratio or pole analysis.','Only external CCOMP/SENSE pin capacitance budget; package R/L, capacitor ESR/ESL, board/pad/ESD parasitics absent.'])
 (w/'summary.json').write_text(json.dumps(result,indent=2)+'\n');e=ROOT/'evidence/analog-v3'/('ac-'+a.tag);e.mkdir(parents=True,exist_ok=True)
 for p in list(w.glob('*.csv'))+[w/'summary.json']:shutil.copyfile(p,e/p.name)
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
