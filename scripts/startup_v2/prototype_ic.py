from pathlib import Path
import importlib.util, subprocess, re, json
import numpy as np
R=Path(__file__).resolve().parents[2]
S=R/'build/safety/fault-gate-00f_2k2g'
D=R/'build/startup-v2/prototype-ic';D.mkdir(parents=True,exist_ok=True)
sp=importlib.util.spec_from_file_location('safety',R/'scripts/safety/run.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
for name in ['servo_startup_default_fault','servo_startup_default_fault_fine']:
 t=D/name;t.mkdir(exist_ok=True)
 for fn in ['design.ngspice','sm141064.ngspice']:
  p=t/fn
  if not p.exists():p.symlink_to((S/name/fn).resolve())
 deck=(S/name/'testbench.spice').read_text()
 deck=deck.replace('option reltol=1e-6 abstol=1e-12 vntol=1e-7 method=trap','option reltol=1e-9 abstol=1e-18 vntol=1e-13 method=gear maxord=2')
 deck=deck.replace('VREFLOAD refout bias 0',f'VREFLOAD refout isolator_in 0\n.include "{R}/analog/startup_v2/reference_isolator.spice"\nXISO isolator_in bias fault_pin safety_vdd 0 reference_isolator')
 deck=deck.replace('wrdata waveform.dat ','wrdata waveform.dat v(isolator_in) v(xiso.fault_b) v(xref.ctrl) v(sense) ')
 init=(R/'build/startup-v2/prototype/servo_startup_default_fault/initial-state.dat').read_text().splitlines()
 header=init[0].split();vals=init[1].split();ics='\n'.join(f'.ic v({key})={value}' for key,value in zip(header[1:],vals[1:]) if not key.startswith('@') and '#' not in key)
 deck=deck.replace('.control',ics+'\n.control').replace('tran 10n 40000n 0 10n','tran 10n 40000n 0 10n uic').replace('tran 10n 40000n 0 2n','tran 10n 40000n 0 2n uic')
 (t/'testbench.spice').write_text(deck)
 p=subprocess.run(['ngspice','-b','testbench.spice'],cwd=t,text=True,capture_output=True)
 (t/'ngspice.log').write_text(p.stdout+p.stderr)
 if p.returncode or re.search(r'(?im)^Error:|timestep too small',p.stdout+p.stderr):raise RuntimeError(str(t))
 a=np.loadtxt(t/'waveform.dat',skiprows=1);i=a[:,m.IDX['i(VLEDLOAD)']+4];ts=a[:,0];mask=ts<=20e-6
 print(name,len(ts),'peak A',max(abs(i[mask])),'charge',m.split_charge(ts,i,0,20e-6),'last',i[-1])
