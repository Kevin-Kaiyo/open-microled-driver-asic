"""Independent known-answer control for injection polarity/loading arithmetic."""
from pathlib import Path
import json,subprocess,tempfile,shutil
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
def main():
 w=Path(tempfile.mkdtemp(prefix='loop-control-',dir=ROOT/'build/analog-v3'));arr={}
 for method in ['voltage','current']:
  p=w/method;p.mkdir();inj='VINJ fb sense 0 AC 1' if method=='voltage' else 'VR inj sense 0\nVF inj fb 0\nIINJ 0 inj 0 AC 1';out='v(sense) v(fb)' if method=='voltage' else 'i(VR) i(VF)'
  s=f'''One pole amplifier with nonnegligible output/input impedances
EBUFFER buffered 0 fb 0 1
RPOLE buffered filtered 1k
CPOLE filtered 0 1n
EAMP drive 0 filtered 0 -1000
ROUT drive sense 10k
RIN fb 0 100k
CIN fb 0 100p
{inj}
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
ac dec 100 1 1G
wrdata ac.dat {out}
quit
.endc
.end
''';(p/'control.spice').write_text(s);r=subprocess.run(['ngspice','-b','control.spice'],cwd=p,text=True,capture_output=True);(p/'ngspice.log').write_text(r.stdout+r.stderr);assert r.returncode==0;arr[method]=np.loadtxt(p/'ac.dat',skiprows=1)
 av,ai=arr['voltage'],arr['current'];f=av[:,0];tv=-(av[:,1]+1j*av[:,2])/(av[:,3]+1j*av[:,4]);ti=(ai[:,1]+1j*ai[:,2])/(ai[:,3]+1j*ai[:,4]);T=(tv*ti-1)/(tv+ti+2);z=1j*2*np.pi*f;known=1000/(1+z*1e-6)/(1+1e4*(1/1e5+z*100e-12));err=float(np.max(np.abs(T-known)/np.maximum(np.abs(known),1e-9)));passed=err<1e-5
 result=dict(schema_version=1,raw_directory=str(w.relative_to(ROOT)),formula='Tanalytic = [1000/(1+s*1us)]/[1+10k*(1/100k+s*100pF)]',double_injection_max_relative_error=err,passed=passed,limitation='Known-answer independent linear network verifies signs/load correction and complex arithmetic. It does not prove the MOS reference is one loop or validate missing physics.')
 (w/'summary.json').write_text(json.dumps(result,indent=2)+'\n');shutil.copyfile(w/'summary.json',ROOT/'evidence/analog-v3/loop-control.json');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
