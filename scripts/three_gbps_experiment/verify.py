#!/usr/bin/env python3
"""Check delivery integrity without upgrading circuit/model qualification."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote,urlsplit
import hashlib,json,math,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'evidence/three-gbps-experiment-20261027'
REPORT=ROOT/'docs/research/three-gbps-experiment-20261027/index.html'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.images=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        for k in ['href','src']:
            if k in d:self.links.append(d[k])
        if tag=='img':self.images.append(d)
def main():
    records=[]
    for name in ['report-manifest.json','vcsel-model/manifest.json']:
        m=read(EV/name)
        for x in m['files']:
            assert sha(ROOT/x['path'])==x['sha256'],x['path'];records.append(x['path'])
    micro=read(EV/'microled-summary.json');assert len(micro['records'])==12 and len(micro['dc'])==16 and not micro['missing'] and not micro['failures']
    assert sum(x['group']=='baseline' for x in micro['records'])==9
    for x in micro['records']:
        p=ROOT/x['source_result'];assert sha(p)==x['source_result_sha256'];r=read(p)
        assert r['simulation_ok'] and r['exit_code']==0
        assert sha(p.with_name('testbench.spice'))==x['deck_sha256']
        assert sha(p.with_name('waveform.dat.gz'))==x['gzip_sha256']
        assert set(x['energy_ports_pJ_netbit'])=={'VIN','VDD','VREF','VLED','VD0','VD1','VDISABLE'}
        assert math.isclose(sum(x['energy_ports_pJ_netbit'].values()),x['energy_pJ_netbit'],abs_tol=1e-10)
        assert all(x['stages'][s]['bit_count']==4096 for s in x['stages'])
        assert not x['stages']['full']['passed']
    assert all(x['capacitance_DC_delta_uA']==0 for x in micro['dc_capacitance_checks'])
    n=read(EV/'microled-validation.json');assert len(n['transistor_refinement'])==3 and all(x['all_gates_passed'] for x in n['transistor_refinement'])
    v=read(EV/'vcsel-driver-summary.json');assert len(v['cases'])==21 and len(v['dc'])==14
    checked=set()
    for x in v['cases']+v['dc']:
        p=ROOT/x['result'];assert sha(p)==x['result_sha256'];assert sha(p.with_name('manifest.json'))==x['manifest_sha256']
        r=read(p);assert r['simulation_ok'] and r['exit_code']==0
        if p not in checked:
            assert sha(ROOT/r['waveform']['path'])==r['waveform']['sha256'];checked.add(p)
        if 'analysis' not in x:continue
        assert sha(ROOT/x['analysis'])==x['analysis_sha256'];assert sha(ROOT/x['plot_data'])==x['plot_data_sha256']
        assert x['validation_bits']==4096
        e=x['energy'];ports=x['energy_by_port'];assert set(ports)=={'VLASER','VDD','VREF','VD','VDB'}
        for k in ['positive_J','returned_J','net_J']:assert math.isclose(sum(a[k] for a in ports.values()),e[k],abs_tol=1e-18)
        assert math.isclose(e['positive_J']-e['returned_J'],e['net_J'],abs_tol=1e-18)
        assert math.isclose(e['positive_pJ_per_offered_payload_bit'],e['positive_J']/4096*1e12,abs_tol=1e-10)
        assert not (x['args']['pvt'] in ['SS','FF'] and x['combined_screen_passed'])
    holdout=[x for x in v['cases'] if x.get('stimulus_seed')==0x57AE]
    assert len(holdout)==2
    h=next(x for x in holdout if x['analysis_label']=='v3-diagnostic');assert h['combined_screen_passed'] and h['errors']==0 and h['time_margin_ps']>=100
    assert not next(x for x in holdout if x['analysis_label']=='baseline')['combined_screen_passed']
    figures=read(EV/'circuit-figures.json');assert sha(ROOT/figures['source'])==figures['source_sha256'];names=[]
    for f in figures['figures']:
        p=ROOT/f['path'];assert sha(p)==f['sha256']
        symbols={s.attrib['data-device']:s.attrib for s in ET.parse(p).getroot().iter() if 'data-device' in s.attrib}
        for name,d in f['devices'].items():assert symbols[name]['data-nets'].split()==d['nets'] and symbols[name]['data-terminal-order']=='D G S B';names.append(name)
    assert len(names)==len(set(names))==13
    parser=Links();parser.feed(REPORT.read_text());local=[]
    for raw in parser.links:
        u=urlsplit(raw)
        if u.scheme or u.netloc or not u.path:continue
        p=(REPORT.parent/unquote(u.path)).resolve();assert p.is_file(),raw;local.append(str(p.relative_to(ROOT)))
    assert len(parser.images)>=8 and all(x.get('alt') for x in parser.images)
    result=dict(delivery_integrity_passed=True,script_sha256=sha(Path(__file__)),report_sha256=sha(REPORT),
        microled_baseline_frames=9,microled_cap_controls=3,microled_DC=16,microled_numerical_refinements=3,
        vcsel_frames=len({x['case'] for x in v['cases']}),vcsel_analyses=len(v['cases']),vcsel_DC=len(v['dc']),
        figures_MOS_checked=13,hash_bound_manifest_files=len(records),local_links_checked=len(local),images=len(parser.images),
        holdout_seed=0x57AE,holdout_errors=h['errors'],holdout_time_margin_ps=h['time_margin_ps'],
        scope='Delivery consistency and limited simulation controls; not all-corner circuit success, optical BER, physical implementation or silicon qualification.')
    (EV/'delivery-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
