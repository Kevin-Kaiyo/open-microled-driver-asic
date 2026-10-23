"""Report exact input capacitance, geometry, substrate cuts, and model resistance."""
from pathlib import Path
import importlib.util
import json
import re
import subprocess
import klayout.db as k

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('transfer',Path(__file__).with_name('substrate_transfer.py'))
transfer=importlib.util.module_from_spec(spec);spec.loader.exec_module(transfer)


def inspect(base,route):
    folder=base/route
    c=json.loads((folder/'physical-contract.json').read_text())
    a=json.loads((folder/'capacitance-correction.json').read_text())
    pex=json.loads((folder/'pex-audit.json').read_text())
    di=[v for v in a['capacitance_matrix'] if 'DI' in v['nodes']]
    value=dict(directory=str(folder.relative_to(ROOT)),bbox_um=c['bbox_um'],
        dimensions_um=[c['width_um'],c['height_um']],area_um2=c['area_um2'],
        counts=pex['counts'],di_ground_fF=a['ground_allocation']['DI']['authoritative_ground_farad']*1e15,
        di_incident_pairs=[dict(nodes=v['nodes'],fF=v['target_farad']*1e15) for v in di],
        di_incident_sum_fF=sum(v['target_farad'] for v in di)*1e15,
        explicit_capacitance_total_fF=a['authoritative_total_sum_fF'],
        transfer_resistance=transfer.solve(folder))
    r=c['resistors'][0]
    value['compact_resistor']=r
    effective_l_um=r['r_length_um']-2*3.85e-5
    effective_w_um=r['r_width_um']-2*.0148
    value['compact_resistor_substrate_capacitance_total_fF']=effective_l_um*effective_w_um*.0885
    screen=r.get('substrate_screen_geometry')
    if screen:
        layout=k.Layout();layout.read(str(folder/'generate'/(c['top']+'.gds')))
        cell=layout.cell(c['top'])
        contacts=k.Region(cell.begin_shapes_rec(layout.layer(33,0)))
        x=screen['center_x_um']
        box=k.Region(k.DBox(x-.13,screen['bottom_um'],x+.13,screen['top_um']).to_itype(layout.dbu))
        selected=(contacts & box).merged()
        value['substrate_screen_contact_cuts']=sum(1 for _ in selected.each())
        value['substrate_screen_contact_area_um2']=selected.area()*layout.dbu**2
    return value


def characterize(base,route,length):
    out=base/'resistor-dc'/route;out.mkdir(parents=True,exist_ok=True)
    model=ROOT/'build/layout/pdk/gf180mcuD/libs.tech/ngspice'
    results=[]
    for corner,temp in [('typical',27),('ss',125),('ff',-40)]:
        p=out/f'{corner}-{temp}.cir'
        p.write_text(f'''Actual selected high-R poly DC model characterization
.include "{model/'design.ngspice'}"
.lib "{model/'sm141064.ngspice'}" res_{corner}
.temp {temp}
VTEST a 0 3.6
XR a 0 0 ppolyf_u_1k_6p0 r_width=1u r_length={length}u
.control
set numdgt=15
op
print i(VTEST)
quit
.endc
.end
''')
        run=subprocess.run(['ngspice','-b',str(p)],cwd=out,capture_output=True,text=True)
        log=run.stdout+run.stderr;p.with_suffix('.log').write_text(log)
        match=re.search(r'i\(vtest\)\s*=\s*([-+\d.eE]+)',log)
        assert run.returncode==0 and match,log
        current=-float(match[1])
        results.append(dict(corner=corner,temp_C=temp,test_voltage_V=3.6,
                            test_current_A=current,resistance_ohm=3.6/current))
    return results


if __name__=='__main__':
    base=ROOT/'build/highspeed-nrz-pvt-layout'
    result=dict(definitions={'di_incident_sum_fF':'Ground C plus each extracted coupling incident on DI once; excludes intrinsic MOS and compact resistor C. It is not a fixed small-signal effective capacitance under arbitrary neighbor transitions.',
        'rc_estimate_ps':'Rpoly(SS,125C) multiplied by this added interconnect capacitance sum. Order of magnitude only; nonlinear inverter Miller effects and coupled-node movement prevent interpreting it as an exact time constant.'},routes={})
    for route in 'AB':
        before=inspect(base/'poly58-r1',route)
        after=inspect(base/'final-r4',route)
        after['resistor_dc']=characterize(base,route,after['compact_resistor']['r_length_um'])
        rss=next(x['resistance_ohm'] for x in after['resistor_dc'] if x['corner']=='ss')
        after['rc_estimate_ps']=rss*after['di_incident_sum_fF']*1e-3
        before['rc_estimate_ps']=66899.84919325369*before['di_incident_sum_fF']*1e-3
        result['routes'][route]=dict(failed_poly58_r1=before,final=after)
    path=base/'final-metrics.json';path.write_text(json.dumps(result,indent=2)+'\n')
    print(path)
