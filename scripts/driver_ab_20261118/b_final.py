"""Apply the W6/L3 mirror and later clamp to the already integrated W4/L2 circuit."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/'build/driver-ab-20261118'
PARENT=STAGE/'b/merged220c10'
spec=importlib.util.spec_from_file_location('b_pvt',ROOT/'scripts/driver_pvt_20261117/b/run.py')
prior=importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
SOURCE=Path(__file__).read_bytes()
NAME='unit6-r260'
FEEDFORWARD='unit6-r260-ff36'
BUFFERED='unit6-r260-n4ff36'
OPTIONS=(NAME,FEEDFORWARD,BUFFERED)


def prepare(variant, grid, mode, level=None, steps=40):
    assert variant in OPTIONS
    kind=f'DC-L{level}' if mode=='dc' else f'{mode}-s{steps}'
    name=grid+'-'+kind
    source=PARENT/name
    change_step=steps!=40 and not source.is_dir()
    if change_step:
        source=PARENT/(grid+'-'+mode+'-s40')
    work=STAGE/'b_final'/variant
    work.mkdir(parents=True,exist_ok=True)
    folder=work/name
    with (work/'.prepare.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if (folder/'manifest.json').exists():
            m=prior.read(folder/'manifest.json')
            assert prior.sha(folder/'testbench.spice')==m['deck_sha256']
            return folder,m
        if not (work/'inputs').exists():
            shutil.copytree(PARENT/'inputs',work/'inputs')
            route=work/'inputs/route_b.spice'
            old='nfet_03v3 w=4u l=2u ad=1.76p as=1.76p pd=8.88u ps=8.88u'
            new='nfet_03v3 w=6u l=3u ad=2.64p as=2.64p pd=12.88u ps=12.88u'
            s=route.read_text()
            rows=[line.split()[0] for line in s.splitlines() if old in line]
            assert set(rows)=={'XREF','XBASE','XTAIL','XTAIL1','XTAIL2'}
            s=s.replace(old,new)
            if variant in (FEEDFORWARD,BUFFERED):
                assert s.count('CFF GB OUT 31.275f')==1
                s=s.replace('CFF GB OUT 31.275f','CFF GB OUT 36f')
            if variant==BUFFERED:
                old_line=next(line for line in s.splitlines() if line.startswith('XINV2N '))
                new_line=prior.prior.mos('XINV2N','GP','GB','VSS','VSS','nfet_03v3',4,.28)
                s=s.replace(old_line,new_line)
            route.write_text(s)
        m=prior.read(source/'manifest.json')
        deck=(source/'testbench.spice').read_text()
        if change_step:
            import re
            step=(4096/4736)/1.6e9/steps
            deck,n=re.subn(r'(?m)^tran .+$',f'tran {step:.16g} {m["end_s"]:.16g} 0 {step:.16g}',deck)
            assert n==1
            m['case'].update(name=name,steps_per_symbol=steps)
        assert deck.count('RCLAMP iso_g clamp_g 200k')==1
        assert 'RGATE iso_g iso_p 220k' in deck and 'CIB1 ib1 0 10f' in deck
        deck=deck.replace('RCLAMP iso_g clamp_g 200k','RCLAMP iso_g clamp_g 260k')
        folder.mkdir()
        (folder/'testbench.spice').write_text(deck)
        (folder/'execution-source.py').write_bytes(SOURCE)
        shutil.copy2(source/'stimulus.json',folder/'stimulus.json')
        shutil.copytree(source/'execution-sources',folder/'execution-sources')
        m['case']['variant']=variant
        m['circuit_change'].update(unit_W_um=6,unit_L_um=3,RCLAMP_kohm=260)
        m['circuit_change']['CFF_fF']=36 if variant in (FEEDFORWARD,BUFFERED) else 31.275
        m['circuit_change']['XINV2N_W_um']=4 if variant==BUFFERED else 2.5
        m['source_case']=str(source.relative_to(ROOT))
        m.update(source_deck_sha256=prior.sha(source/'testbench.spice'), source_manifest_sha256=prior.sha(source/'manifest.json'),
                 execution_sha256=hashlib.sha256(SOURCE).hexdigest(),deck_sha256=prior.sha(folder/'testbench.spice'))
        m['inputs']['route_b.spice']=prior.sha(work/'inputs/route_b.spice')
        m['extra_caps']=[c for c in m.get('extra_caps',[]) if c[0]!='CIB1']+[['CIB1',10e-15,'ib1','0']]
        prior.emit(folder/'manifest.json',m)
        return folder,m


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['dc','assert','release','full','normal1'])
    p.add_argument('grids',help='all or comma-separated PVT keys')
    p.add_argument('--variant',choices=OPTIONS,default=NAME)
    p.add_argument('--steps',type=int,default=40)
    args=p.parse_args()
    prior.prepare=prepare
    for grid in prior.GRID if args.grids=='all' else args.grids.split(','):
        for level in [0,1] if args.mode=='dc' else [None]:
            prior.run(args.variant,grid,args.mode,level,args.steps)
