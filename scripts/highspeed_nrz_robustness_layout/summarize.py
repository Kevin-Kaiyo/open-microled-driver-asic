"""Read actual GDS/PEX metrics for old LV, retained HV48 and revised HV8 cores."""
from pathlib import Path
import importlib.util
import json
import klayout.db as k
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('pvt_metrics',ROOT/'scripts/highspeed_nrz_pvt_layout/summarize.py')
metrics=importlib.util.module_from_spec(spec);spec.loader.exec_module(metrics)

def main():
    definitions=[('LV-A48','build/highspeed-nrz-pvt-layout/final-r4','A'),('LV-B58','build/highspeed-nrz-pvt-layout/final-r4','B'),('HV-A48','build/highspeed-nrz-robustness-layout/hv-r2','A'),('HV-B58','build/highspeed-nrz-robustness-layout/hv-r2','B'),('HV-A8','build/highspeed-nrz-robustness-layout/hv-A8-r3','A'),('HV-A8-ties','build/highspeed-nrz-robustness-layout/hv-A8-ties-r5','A')]
    result={'schema_version':1,'method':'Read actual final GDS and audited PEX; substrate transfer uses extracted VSS resistor network only, not a field solver.','routes':{label:metrics.inspect(ROOT/base,route) for label,base,route in definitions}}
    for label,base,route in definitions:
        folder=ROOT/base/route
        c=json.loads((folder/'physical-contract.json').read_text())
        lay=k.Layout();lay.read(str(folder/'generate'/(c['top']+'.gds')));top=lay.cell(c['top'])
        cuts=k.Region(top.begin_shapes_rec(lay.layer(33,0)))
        active=k.Region(top.begin_shapes_rec(lay.layer(22,0)))
        pplus=k.Region(top.begin_shapes_rec(lay.layer(31,0)))
        count={}
        for d in c['devices']:
            if not d['model'].startswith('nfet'):continue
            x,y=d['cx'],d['cy'];w=d['w_um']
            region=k.Region(k.DBox(x-2.2,y-w/2-2.5,x+2.2,y+w/2+2.5).to_itype(lay.dbu))
            count[d['name']]=sum(1 for _ in (cuts & active & pplus & region).merged().each())
        result['routes'][label]['nmos_pplus_body_contact_cuts']=count
        result['routes'][label]['total_contact_cuts']=sum(1 for _ in cuts.merged().each())
    target=ROOT/'evidence/highspeed-nrz-robustness-layout/physical-comparison.json';target.write_text(json.dumps(result,indent=2)+'\n')
    for label,x in result['routes'].items():
        print(label,round(x['area_um2'],6),x['dimensions_um'],round(x['di_incident_sum_fF'],6),x['explicit_capacitance_total_fF'],x['counts'],round(x['compact_resistor_substrate_capacitance_total_fF'],6),round(x['transfer_resistance']['self_ohm'],4))
if __name__=='__main__':main()
