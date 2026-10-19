from pathlib import Path
import re,json
from run import ROOT,B,E,run,sha
F=B/'physical/final';out=B/'sdf';out.mkdir(exist_ok=True)
wrapper=B/'verification/cells.v'
text=run(['iverilog','-g2012','-gspecify','-ginterconnect','-s','tb_control_sdf','-o',str(out/'sim.vvp'),str(wrapper),str(F/'nl/pixel_control_v3.nl.v'),str(ROOT/'scripts/control_v3/tb_sdf.v')],out/'compile.log')
results=[]
for sdf in sorted((F/'sdf').glob('*/*.sdf')):
 c=sdf.parent.name;p=out/c;p.mkdir(exist_ok=True)
 text=run(['vvp',str(out/'sim.vvp'),f'+SDF={sdf}',f'+OUT={p}/events.csv'],p/'run.log')
 assert 'CONTROL_SDF_PASS' in text
 unmatched=re.findall(r'Unable to match ModPath.* in tb_control_sdf.dut.(\S+)',text)
 cells=dict((instance,cell) for cell,instance in re.findall(r'(gf180mcu_fd_sc_mcu7t5v0__\w+)\s+(\w+)\s*\(',(F/'nl/pixel_control_v3.nl.v').read_text()))
 assert all(re.search(r'__(?:xor2|xnor2)_',cells.get(i,'')) for i in unmatched),unmatched
 errors=[x for x in text.splitlines() if 'SDF ERROR:' in x and 'Unable to match ModPath' not in x];assert not errors,errors
 match=re.search(r'checks=(\d+) fault_delay_ns=([\d.]+)',text)
 results.append({'corner':c,'checks':int(match[1]),'fault_to_monitor_off_ns':float(match[2]),'unsupported_xor_modpath_instances':sorted(set(unmatched)),'sdf_sha256':sha(sdf),'events_sha256':sha(p/'events.csv'),'passed':True})
(E/'sdf.json').write_text(json.dumps({'passed':len(results)==9,'corners':results,'limitations':['Icarus does not support all conditional XOR paths or timing checks.','Register-clock/output and asynchronous fault arcs exercised; static recovery/removal reports retained separately.','Analog macro and arbitrary clock-edge metastability not modeled here.']},indent=2)+'\n')
