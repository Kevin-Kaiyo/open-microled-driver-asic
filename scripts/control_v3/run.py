"""Freeze the PWM + recovery wrapper and implement with the locked public PDK."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
B=ROOT/'build/control-v3'; E=ROOT/'evidence/control-v3'
IMAGE='ghcr.io/librelane/librelane@sha256:f91b21d75f79871f9ccf37451020b5d2f7b3236881a997ff709c561e8280a30f'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,log,env=None):
    with log.open('w') as f:
        p=subprocess.run(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
    log.with_suffix(log.suffix+'.command.json').write_text(json.dumps({'argv':cmd,'exit_code':p.returncode},indent=2)+'\n')
    if p.returncode: raise RuntimeError(str(log))
    return log.read_text()
def main():
    B.mkdir(parents=True,exist_ok=True); E.mkdir(parents=True,exist_ok=True)
    sources=['rtl/pixel_pwm.v','rtl/safety/pixel_safety.v','rtl/safety/pixel_control_v3.v','scripts/control_v3/tb_control.v']
    if sys.argv[1]=='rtl':
        run(['iverilog','-g2012','-s','tb_safety','-o',str(B/'sim.vvp')]+sources,B/'compile.log')
        cases=[]
        for duty,fault,stop in [(0,-1,-1),(1,-1,-1),(64,-1,-1),(256,-1,-1),(511,-1,-1),(256,520125,-1),(256,520125,519900),(64,520125,-1),(1,520125,-1),(0,520125,-1)]:
            name=f'd{duty}-f{fault}-s{stop}'
            output=run(['vvp',str(B/'sim.vvp'),f'+DUTY={duty}',f'+FAULT_NS={fault}',f'+STOP_NS={stop}',f'+OUT={B/(name+".csv")}'],B/(name+'.log'))
            cases.append({'case':name,'passed':'SAFETY_CASE_PASS' in output,'log':str((B/(name+'.log')).relative_to(ROOT))})
        (E/'rtl.json').write_text(json.dumps({'passed':all(x['passed'] for x in cases),'cases':cases,'sources':{p:sha(ROOT/p) for p in sources}},indent=2)+'\n')
    elif sys.argv[1]=='physical':
        for p,h in json.loads((ROOT/'scripts/physical/pdk-lock.json').read_text())['files'].items():
            assert sha(ROOT/'build/layout/pdk/gf180mcuD'/p)==h,p
        freeze=B/'inputs'; freeze.mkdir(exist_ok=True)
        for name in sources[:3]:
            dst=freeze/Path(name).name
            if dst.exists(): assert sha(dst)==sha(ROOT/name),'Changed frozen input'
            else: shutil.copyfile(ROOT/name,dst)
        config=json.loads((ROOT/'layout/digital/config.json').read_text())
        config.update(DESIGN_NAME='pixel_control_v3',VERILOG_FILES=[str(freeze/Path(n).name) for n in sources[:3]],DIE_AREA=[0,0,200,200],PNR_EXCLUDED_CELL_FILE=str(ROOT/'scripts/physical/no-pnr.cells'))
        cp=freeze/'config.json'; content=json.dumps(config,indent=2)+'\n'
        if cp.exists(): assert cp.read_text()==content,'Changed frozen config'
        else: cp.write_text(content)
        (E/'inputs.json').write_text(json.dumps({'sources':{p:sha(ROOT/p) for p in sources},'config_sha256':sha(cp),'image':IMAGE},indent=2)+'\n')
        (B/'physical').mkdir(exist_ok=True)
        env=dict(os.environ,LIMA_HOME=str(ROOT/'build/physical-flow/lima'))
        cmd=['limactl','shell','asic','nerdctl','run','--rm','-v',f'{ROOT}:{ROOT}','-w',str(ROOT),'-e','QT_QPA_PLATFORM=offscreen','-e',f'PYTHONPATH={ROOT}/build/physical-flow/linux-python',IMAGE,'librelane','--manual-pdk','--pdk-root',str(ROOT/'build/layout/pdk'),'--pdk','gf180mcuD','--scl','gf180mcu_fd_sc_mcu7t5v0','--force-run-dir',str(B/'physical'),'-j','4','--hide-progress-bar',str(cp)]
        run(cmd,B/'physical.log',env)
    else: raise ValueError(sys.argv)
if __name__=='__main__':main()
