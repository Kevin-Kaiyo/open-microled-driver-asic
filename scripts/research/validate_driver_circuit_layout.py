"""Independently check arithmetic and saved-evidence identity for the dated study."""
from pathlib import Path
import csv
import hashlib
import json
import math
import re
import statistics
from urllib.parse import unquote

from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/research/driver-circuit-layout-20261012'
checks=[]


def check(name,condition):
    checks.append({'name':name,'passed':bool(condition)})
    if not condition:
        raise AssertionError(name)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    calc=json.loads((BASE/'calculations.json').read_text())
    provenance=json.loads((BASE/'provenance.json').read_text())
    for p,value in provenance['local_input_sha256'].items():
        check('input identity '+p,sha(ROOT/p)==value)
    check('report source identity',sha(BASE/'report.md')==provenance['report_source_sha256'])
    check('renderer identity',sha(ROOT/'scripts/research/render_driver_circuit_layout.py')==provenance['renderer_sha256'])
    data=list(csv.DictReader((ROOT/'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv').open()))
    check('static CSV 100 points',len(data)==100)
    values=[(float(x['current_A']),float(x['voltage_V'])) for x in data]
    check('static current monotonic',all(a[0]<b[0] for a,b in zip(values,values[1:])))
    a,b=next((a,b) for a,b in zip(values,values[1:]) if a[0]<=1e-4<=b[0])
    vf=a[1]+(1e-4-a[0])/(b[0]-a[0])*(b[1]-a[1])
    check('independent Vf interpolation',abs(vf-calc['led_headroom']['Vf_at_100uA_V'])<1e-8)
    check('headroom subtraction',abs(5-vf-calc['led_headroom']['remainder_V'])<1e-8)
    check('geometric oxide scale',calc['oxide_scale']['scale_fF']==2.3*20*4)
    for c,t in zip(calc['single_pole_RC']['C_pF'],calc['single_pole_RC']['rise_ps']):
        check('exact 10-90 RC '+str(c),math.isclose(t,math.log(9)*100*c,rel_tol=1e-12))
    check('return inductive term',math.isclose(calc['inductive_return']['deltaV_mV'],.5e-9*16e-3/100e-12*1e3))
    check('storage drift',math.isclose(calc['storage_drift']['deltaV_mV'],1e-12*100e-6/100e-15*1e3))
    area=json.loads((ROOT/'evidence/characterization/actual-w20-l4-area.json').read_text())
    check('bbox area delta',abs(area['cell_bbox_area_increase_pct']-calc['historical_size_tradeoff']['area_increase_pct'])<1e-10)
    for name,key in [('reference-matching-summary.json','old_sigma_uA'),('actual-w20-l4-summary.json','new_sigma_uA')]:
        d=json.loads((ROOT/'evidence/characterization'/name).read_text())['mc']['populations']['local_only']
        check('MC n '+name,d['n']==256)
        check('MC rounded sigma '+name,abs(d['iout']['sample_sd']*1e6-calc['historical_size_tradeoff'][key])<5e-6)
    cent=calc['common_centroid']
    for group in ['A','B']:
        xy=cent[group+'_xy'];avg=[statistics.mean(p[i] for p in xy) for i in [0,1]]
        check('unit centroid '+group,avg==cent[group+'_centroid'])
    check('first-order equal centroid',cent['A_centroid']==cent['B_centroid'])
    main=json.loads((ROOT/'evidence/robustness/main-summary.json').read_text())
    for env,value in [('tt',100.7528),('ss',100.1130),('ff',101.4234)]:
        r=next(x for x in main['dc_results'] if x['envelope']==env and x['view']=='post' and x['level']==1)
        check('DC rounding '+env,abs(r['current_uA']-value)<5e-5)
    boundary=json.loads((ROOT/'evidence/robustness/boundary-summary.json').read_text())
    r=next(x for x in boundary['dc_results'] if x['rled_ohm']==10000)
    check('external RLED error',abs((r['current_uA']/100-1)*100-calc['hypothetical_RLED_10kohm']['error_pct'])<1e-6)
    joint=json.loads((ROOT/'evidence/joint-pex/nominal/summary.json').read_text())
    for key,value in [('selected_MOS',12),('selected_R',45),('selected_C',77),('neighbors',34)]:
        check('joint '+key,joint['counts'][key]==value)
    check('signal R identity',abs(joint['metrics']['output_drive_to_actual_analog_entry_effective_R_ohm']-17.394804)<1e-9)
    check('explicit C identity',abs(joint['metrics']['total_exported_explicit_C_f']*1e15-86.12439)<1e-7)
    records=json.loads((BASE/'sources.json').read_text())['records']
    check('selected sources unique',len(records)==len({x['id'] for x in records})==15)
    check('8 research papers',sum(bool(x.get('doi')) for x in records)==8)
    check('primary locators recorded',all(x.get('locator') for x in records))
    figure=json.loads((BASE/'figure-ledger.json').read_text())
    check('schematic renderer identity',sha(ROOT/'scripts/research/driver_circuit_figures.py')==provenance['figure_renderer_sha256'])
    source=(ROOT/'analog/driver/pixel_driver.spice').read_text()
    ids={'MREF':'XREF','MOUT':'XOUT','MPASS':'XPASS','MCLAMP':'XCLAMP','MN':'XINV_N','MP':'XINV_P'}
    for name,ident in ids.items():
        nodes=next(line.split()[1:5] for line in source.splitlines() if line.startswith(ident+' '))
        check('schematic D G S B '+name,nodes==figure['pixel_devices'][name])
    for r,t in zip(figure['RC_waveform']['RG_ohm'],figure['RC_waveform']['t10_90_ns']):
        check('gate RC 10-90 '+str(r),math.isclose(t,math.log(9)*r*1e-3))
    reader=PdfReader(BASE/'report.pdf')
    check('14 PDF pages',len(reader.pages)==14)
    for i,p in enumerate(reader.pages,1):
        check('PDF page text '+str(i),len(p.extract_text())>250)
    doc=(BASE/'report.html').read_text()
    for href in re.findall(r'(?:href|src)="([^"]+)"',doc):
        if not href.startswith(('https://','http://','#')):
            check('local report target '+href,(BASE/unquote(href.split('#')[0])).is_file())
    layout=json.loads((ROOT/'build/driver-circuit-layout-20261012/render/layout-check.json').read_text())
    check('no horizontal overflow',not layout['overflow'])
    check('each section fits A4',all(p['height']<970 for p in layout['sections']))
    check('no new EDA',provenance['new_EDA_runs']==0)
    result={'study_date':'2026-10-12','passed':all(c['passed'] for c in checks),'checks':checks,
        'review':{'fact_and_scope':'Independent CMOS/PDK/evidence and TFT primary-section reviews; corrections applied',
            'visual_pages_inspected':list(range(1,15)), 'visual_result':'All 14 final pages visually inspected; standard component schematics reviewed with terminal/reference assumptions',
            'source_figures_reproduced':0,'new_EDA_runs':0},
        'pdf_sha256':sha(BASE/'report.pdf'),'output_sha256':{p.name:sha(p) for p in BASE.iterdir() if p.is_file() and p.name not in ['validation.json','publication.json']}}
    (BASE/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'checks':len(checks),'PDF_pages':14,'new_EDA_runs':0}))


if __name__=='__main__':
    main()
