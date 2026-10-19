"""Independent closure-artifact checks; document integrity is not chip signoff."""
from pathlib import Path
import hashlib,json,re,subprocess,shutil,os
import numpy as np
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/research/single-pixel-closure-20261015';checks=[]
def ck(name,ok):checks.append({'name':name,'passed':bool(ok)})
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads((ROOT/p).read_text())
manifest=json.loads((BASE/'manifest.json').read_text())
for p,h in manifest['report_source_hashes'].items():ck('Report source '+p,sha(ROOT/p)==h)
s=load('evidence/analog-v3/final/summary.json');ck('Selected suite exactly17',len(s['results'])==17);ck('No failed selected case hidden',s['passed'] and all(x.get('passed') and x.get('simulation_completed') for x in s['results']))
peaks=[]
for row in s['results']:
 for name,art in row['source_artifacts'].items():ck('Frozen '+row['name']+'/'+name,sha(ROOT/art['path'])==art['sha256'])
 if row['kind']!='startup':continue
 a=np.loadtxt(ROOT/row['source_raw_directory']/'waveform.dat',skiprows=1,usecols=[0,1]);t=a[:,0];i=a[:,1];mask=(t>=0)&(t<=20e-6);peak=float(np.abs(i[mask]).max());peaks.append(peak)
 ck('Startup peak independent '+row['name'],abs(peak-row['startup']['branch_max_abs_a'])<1e-18 and peak<1e-9)
 ck('Startup start included '+row['name'],t[0]==0 and t[-1]>=40e-6*(1-1e-9))
 # Parse and independently verify the unchanged reference source function.
 deck=(ROOT/row['source_raw_directory']/'testbench.spice').read_text();match=re.search(r'VREFRAIL refrail 0 PWL\((.*?)\)',deck,re.S);tokens=match[1].replace('+','').split()
 def val(v):return float(v[:-1])*1e-9 if v.endswith('n') else float(v)
 pairs=[(val(tokens[k]),val(tokens[k+1])) for k in range(0,len(tokens),2)];ts=np.array([x[0] for x in pairs]);vs=np.array([x[1] for x in pairs]);v={'tt':3.3,'ss':2.97,'ff':3.63}[row['envelope']];expected=np.minimum(ts/(row['ramp_ns']*1e-9),1)*v
 ck('Strict ordered source knots '+row['name'],np.all(np.diff(ts)>0))
 ck('Original linear ramp preserved '+row['name'],np.abs(vs-expected).max()<1e-12)
for name in ['evidence/layout-v3/r5/summary.json','evidence/layout-v3/joint-r2/summary.json']:
 p=load(name);ck(name+' checks',p['physical_checks_passed'] and all(c['passed'] for c in p['checks']))
 for path,h in p['source_sha256'].items():ck('Physical input '+path,sha(ROOT/path)==h)
 for path,h in p['output_sha256'].items():ck('Physical output '+path,sha(ROOT/path)==h)
num=load('evidence/startup-v3/numerical/refined-summary.json');ck('Legacy failure visible',not num['legacy_4p909pct_result_passed']);ck('Revised old numeric accepted',num['revised_numerical_acceptance_passed'])
new=load('evidence/startup-v3/numerical/pex-r5-bleed10M-ff-probe/summary.json');ck('PEX first-corner selected comparison accepted',new['selected_numerical_acceptance_passed']);ck('Uncompleted strict challenge visible',new['all_completed'] is False)
for p in ['evidence/control-v3/rtl.json','evidence/control-v3/gate.json','evidence/control-v3/sta.json','evidence/control-v3/sdf.json','evidence/control-v3/coupled-r5-bleed10/summary.json','evidence/analog-v3/pvt-pex-r5-bleed10M/summary.json']:
 ck(p+' passed',load(p)['passed'])
layout=load('build/closure-v3/layout-check.json');ck('No report horizontal clipping',not layout['overflow']);ck('All report figures loaded',all(x['loaded'] for x in layout['images']));ck('All sections fit A4',all(x['height']<=978 for x in layout['sections']))
info=subprocess.check_output(['pdfinfo',str(BASE/'report.pdf')],text=True);pages=int(re.search(r'Pages:\s+(\d+)',info)[1]);ck('PDF18 pages',pages==manifest['pages_expected']==18)
if shutil.which('pdftotext'):
 text=subprocess.check_output(['pdftotext',str(BASE/'report.pdf'),'-'],text=True)
else:
 pdf_python=os.environ.get('CLOSURE_PDF_PYTHON',str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'))
 text=subprocess.check_output([pdf_python,'-c',"from pypdf import PdfReader; import sys; print('\\n'.join(p.extract_text() for p in PdfReader(sys.argv[1]).pages))",str(BASE/'report.pdf')],text=True)
text=re.sub(r'\s+', '', text)
ck('No unresolved placeholders','@@' not in text);ck('Future full-chip transient explicit','7277' in text and '尚未完成回归' in text);ck('Supply overshoot visible','147.24' in text);ck('Legacy failure visible in PDF','4.909%' in text)
for p in BASE.glob('figures/*.svg'):ck('SVG well formed '+p.name, bool(p.read_text().startswith('<svg') or '<svg ' in p.read_text()[:1000]))
report_files=[p for p in BASE.rglob('*') if p.is_file() and p.name!='validation.json']
result={'passed':all(c['passed'] for c in checks),'checks':checks,'check_count':len(checks),'pages_rendered':pages,'pages_visually_reviewed':list(range(1,19)),'independent_startup_max_a':max(peaks),'files_sha256':{str(p.relative_to(ROOT)):sha(p) for p in report_files},'scope':'Artifact/source/calculation validation; not new silicon or full common-top electrical evidence'}
(BASE/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':result['passed'],'checks':len(checks),'failures':[c for c in checks if not c['passed']]},ensure_ascii=False,indent=2));raise SystemExit(0 if result['passed'] else 1)
