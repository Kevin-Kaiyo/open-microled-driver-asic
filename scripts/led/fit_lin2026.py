"""Extract and validate one explicitly licensed, measured MicroLED I-V curve.

Default: fit the committed normalized CSV offline. --extract-source verifies
and reads the cached original archive; --download additionally fetches it from
Zenodo. This is a static curve replay, not a temperature/optical/dynamic model.
"""
from pathlib import Path
import argparse, csv, hashlib, json, math, subprocess, urllib.request, zipfile
from xml.etree import ElementTree as ET
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
MODELS=ROOT/'analog/models/measured-led'
RAW=ROOT/'build/led-fit'
EVIDENCE=ROOT/'evidence/led-fit'
CSV=MODELS/'lin2026-yellow20-diamond-iv.csv'
LOCK=MODELS/'source-lock.json'
CARD=MODELS/'model-card.json'
ARCHIVE=RAW/'lin2026-source-data.zip'
ZIP_URL='https://zenodo.org/api/records/20034288/files/source_data.zip/content'
ZIP_SHA256='4873cfd00f6ffa7e9c75e425e4e41d230a7100e43e9e74bb67225e37ea09c3ee'
ZIP_MD5='755accbc45603195c376ffc70a776bc5'
XLSX_SHA256='9d60a001a0aaffb5a24787fa4036d8a66782f1b74c7b162b0e24df7b8ed936f2'
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def extract():
    if sha(ARCHIVE)!=ZIP_SHA256 or hashlib.md5(ARCHIVE.read_bytes()).hexdigest()!=ZIP_MD5:
        raise RuntimeError('Original archive hash does not match pinned source')
    with zipfile.ZipFile(ARCHIVE) as archive:
        payload=archive.read('I-V.xlsx')
    if hashlib.sha256(payload).hexdigest()!=XLSX_SHA256:
        raise RuntimeError('I-V.xlsx source hash mismatch')
    xlsx=RAW/'I-V.xlsx'; xlsx.write_bytes(payload)
    with zipfile.ZipFile(xlsx) as book:
        strings=[''.join(e.itertext()) for e in ET.fromstring(book.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        rows=ET.fromstring(book.read('xl/worksheets/sheet1.xml')).findall('.//s:row',NS)
        parsed=[]
        for row in rows:
            cells={}
            for cell in row:
                value=cell.find('s:v',NS)
                if value is not None:
                    cells[cell.get('r')]=(strings[int(value.text)] if cell.get('t')=='s' else value.text)
            parsed.append(cells)
    if parsed[0]['A1']!='20μm yellow' or parsed[1]['A2']!='Current(mA)' or parsed[1]['B2']!='Voltage(V)':
        raise RuntimeError('Source sheet identification changed')
    with CSV.open('w',newline='') as output:
        writer=csv.writer(output)
        writer.writerow(['source_excel_row','source_current_mA','current_A','voltage_V'])
        for row in range(3,103):
            r=parsed[row-1];ma=float(r[f'A{row}']);v=float(r[f'B{row}'])
            writer.writerow([row,format(ma,'.17g'),format(ma*1e-3,'.17g'),format(v,'.17g')])

def metrics(errors_v):
    return {'count':len(errors_v),'rmse_mV':float(np.sqrt(np.mean(errors_v**2))*1e3),
            'max_abs_mV':float(np.max(np.abs(errors_v))*1e3)}

def law_fit(currents,voltages,train,reference=100e-6):
    # V=b+a*ln(I/Iref)+r*(I-Iref), with nonnegative a and r.
    X=np.c_[np.ones(len(currents)),np.log(currents/reference),currents-reference]
    coeff=np.linalg.lstsq(X[train],voltages[train],rcond=None)[0]
    unconstrained=coeff.copy()
    if coeff[2]<0:
        two=np.linalg.lstsq(X[train,:2],voltages[train],rcond=None)[0]
        coeff=np.r_[two,0.0]
    if coeff[1]<=0 or coeff[2]<0:raise RuntimeError('Nonmonotonic local model')
    return coeff,unconstrained,X@coeff

def validate_spice(path,points):
    values=[];maximum=0.0
    folder=RAW/'spice-static';folder.mkdir(exist_ok=True)
    for index,(current,expected) in enumerate(points):
        deck=f'''Static measured-curve replay verification
.include "{path}"
Itest 0 a {current:.17g}
XLED a 0 lin2026_yellow20_dc
.options reltol=1e-9 abstol=1e-17 vntol=1e-11
.control
set numdgt=15
set wr_singlescale
op
wrdata result.dat v(a)
quit
.endc
.end
'''
        (folder/'test.spice').write_text(deck);(folder/'result.dat').unlink(missing_ok=True)
        run=subprocess.run(['ngspice','-b','test.spice'],cwd=folder,capture_output=True,text=True)
        (folder/f'case-{index:03d}.log').write_text(run.stdout+run.stderr)
        (folder/f'case-{index:03d}.spice').write_text(deck)
        if run.returncode or not (folder/'result.dat').exists():raise RuntimeError('Static SPICE replay failed')
        voltage=float((folder/'result.dat').read_text().split()[-1]);delta=voltage-expected
        if not math.isfinite(voltage):raise RuntimeError('Nonfinite SPICE result')
        maximum=max(maximum,abs(delta));values.append({'current_A':current,'expected_V':expected,'ngspice_V':voltage,'delta_V':delta})
    return {'runs':len(values),'maximum_abs_voltage_difference_V':maximum,'passed':maximum<1e-5,'points':values}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract-source',action='store_true')
    parser.add_argument('--download',action='store_true')
    args=parser.parse_args()
    for p in (MODELS,RAW,EVIDENCE):p.mkdir(parents=True,exist_ok=True)
    if args.download:
        temporary=ARCHIVE.with_suffix('.download')
        with urllib.request.urlopen(ZIP_URL,timeout=60) as response, temporary.open('wb') as target:
            while chunk:=response.read(1024*1024):target.write(chunk)
        if sha(temporary)!=ZIP_SHA256:raise RuntimeError('Downloaded archive differs from pinned source')
        temporary.replace(ARCHIVE)
    if args.extract_source or args.download:extract()
    lock=json.loads(LOCK.read_text())
    if (lock['archive_sha256']!=ZIP_SHA256 or lock['archive_md5']!=ZIP_MD5
            or lock['workbook_sha256']!=XLSX_SHA256 or lock['download_url']!=ZIP_URL):
        raise RuntimeError('Source lock and extractor pins differ')
    if sha(CSV)!=lock['normalized_csv_sha256']:
        raise RuntimeError('Normalized source CSV differs from its pinned extraction')
    # Freeze the verified inputs and script before running numerical work.
    frozen_inputs={str(p.relative_to(ROOT)):sha(p) for p in [CSV,LOCK,CARD,Path(__file__)]}
    with CSV.open() as f:rows=list(csv.DictReader(f))
    I=np.array([float(x['current_A']) for x in rows]);V=np.array([float(x['voltage_V']) for x in rows])
    if len(I)!=100 or not np.isfinite(I).all() or not np.isfinite(V).all() or np.any(I<=0) or np.any(np.diff(I)<=0) or np.any(np.diff(V)<=0):
        raise RuntimeError('Invalid measured curve')
    if not np.allclose(I,[float(x['source_current_mA'])*1e-3 for x in rows],rtol=1e-15,atol=0):raise RuntimeError('Unit conversion differs')
    # Every fourth point is withheld; both domain endpoints remain in training.
    held=np.arange(len(I))%4==1
    predicted=np.interp(I[held],I[~held],V[~held])
    hold_error=predicted-V[held]
    local=(I>=10e-6)&(I<=1e-3);il,vl=I[local],V[local]
    local_held=np.arange(len(il))%4==1
    coeff,unconstrained,local_pred=law_fit(il,vl,~local_held)
    global_coeff,_,global_pred=law_fit(I,V,~held)
    # Full-data replay retains the original knot values after held-out validation.
    # Its out-of-domain mathematical extension is not a measured off/reverse law.
    lines=['* Static measured I-V curve only; source dataset CC BY 4.0.',
           '* Lin et al. 2026; Zenodo 10.5281/zenodo.20034288; I-V.xlsx Sheet1 A3:B102.',
           '* 20 um square-mesa yellow InGaN on diamond; source temperature unspecified.',
           '* Validated input domain: 0.1 uA .. 32 mA / 2.41622 V .. 6.40451 V.',
           '* No capacitance, optical output, self-heating, leakage or temperature scaling.',
           '* Below first point a line to (0 V,0 A) is a startup extension, not measured data.',
           '* Above last point linear extrapolation is numerical only; reverse response unvalidated.',
           '.subckt lin2026_yellow20_dc anode cathode',
           'BLED anode cathode I = pwl(v(anode,cathode),0,0,']
    pairs=[f'{v:.17g},{i:.17g}' for i,v in zip(I,V)]
    for n in range(0,len(pairs),3):lines.append('+ '+','.join(pairs[n:n+3])+(',' if n+3<len(pairs) else ''))
    lines+=['+ )','.ends lin2026_yellow20_dc']
    netlist=MODELS/'lin2026-yellow20-dc.spice';netlist.write_text('\n'.join(lines)+'\n')
    frozen_inputs[str(netlist.relative_to(ROOT))]=sha(netlist)
    v100=float(np.interp(100e-6,I,V))
    spice=validate_spice(netlist,list(zip(I.tolist(),V.tolist()))+[(100e-6,v100)])
    report={'evidence_level':'single published measured I-V curve; static piecewise-linear interpolation and held-out same-curve validation only',
            'physical_sample_count':None,'curve_count':1,'measurement_temperature_C':None,
            'measurement_temperature_reason':'not specified in the article measurement method or source workbook',
            'thermal_model_validated':False,'dynamic_model_validated':False,'optical_model_validated':False,
            'source_dataset_doi':'10.5281/zenodo.20034288','source_license':'CC-BY-4.0',
            'source_archive_sha256':ZIP_SHA256,'source_archive_md5':ZIP_MD5,'source_xlsx_sha256':XLSX_SHA256,
            'selected_source':'I-V.xlsx / Sheet1 / A3:B102 / 20μm yellow / Fig.2a',
            'measured_points':len(I),'current_domain_A':[float(I.min()),float(I.max())],
            'voltage_domain_V':[float(V.min()),float(V.max())],
            'interpolation_at_100uA_V':v100,'current_density_at_100uA_A_cm2':25.0,
            'held_out_interpolation':{'method':'linear V versus I; inversely equivalent to linear I versus V;  every fourth knot index modulo 4 equals 1 withheld; endpoints retained',
                'training_count':int((~held).sum()),'holdout_count':int(held.sum()),**metrics(hold_error),
                'local_10uA_to_1mA':metrics(hold_error[(I[held]>=10e-6)&(I[held]<=1e-3)]),
                'interpretation':'same-curve interpolation error;  not cross-device or cross-temperature generalization'},
            'local_analytic_fit':{'form':'V=b+a*ln(I/100uA)+r*(I-100uA); a>=0, r>=0',
                'nominal_requested_domain_A':[10e-6,1e-3],'actual_points_domain_A':[float(il.min()),float(il.max())],
                'training_count':int((~local_held).sum()),'holdout_count':int(local_held.sum()),
                'b_V':float(coeff[0]),'a_V':float(coeff[1]),'r_ohm':float(coeff[2]),
                'unconstrained_r_ohm':float(unconstrained[2]),'held_out_error':metrics(local_pred[local_held]-vl[local_held]),
                'training_error':metrics(local_pred[~local_held]-vl[~local_held]),
                'interpretation':'empirical local shape; a is not reported as physical N because measurement T is unspecified; r=0 boundary is not device series resistance'},
            'global_analytic_fit':{'b_V':float(global_coeff[0]),'a_V':float(global_coeff[1]),'r_ohm':float(global_coeff[2]),
                'held_out_error':metrics(global_pred[held]-V[held]),'selected_as_circuit_model':False},
            'spice_replay':spice,'ngspice_version':subprocess.check_output(['ngspice','--version'],text=True),
            'source_hashes':frozen_inputs,
            'python_numerical_versions':{'numpy':np.__version__,'matplotlib':matplotlib.__version__}}
    if any(sha(ROOT/name)!=digest for name,digest in frozen_inputs.items()):
        raise RuntimeError('An input changed while validation was running')
    if not spice['passed']:raise RuntimeError('Static replay validation exceeds 10 uV')
    (EVIDENCE/'lin2026-yellow20-fit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    with (EVIDENCE/'lin2026-yellow20-holdout.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['source_excel_row','current_A','measured_voltage_V','predicted_voltage_V','error_mV'])
        for j,vp in zip(np.flatnonzero(held),predicted):w.writerow([rows[j]['source_excel_row'],I[j],V[j],vp,(vp-V[j])*1e3])
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    fig,ax=plt.subplots(1,2,figsize=(10.4,3.8),layout='constrained')
    ax[0].semilogx(I*1e6,V,'.',color='#176e7b',label='Published points (one curve)')
    ax[0].semilogx(I[held]*1e6,predicted,'x',color='#ad5c3c',label='Held-out predictions')
    ax[0].axvline(100,color='#82939b',ls='--',lw=.8);ax[0].set(xlabel='Current (uA)',ylabel='LED voltage (V)',title='20 um yellow InGaN / diamond')
    ax[0].legend(fontsize=8);ax[0].grid(alpha=.15)
    ax[1].semilogx(I[held]*1e6,hold_error*1e3,'o-',color='#176e7b',ms=4)
    ax[1].axhline(0,color='#82939b',lw=.8);ax[1].set(xlabel='Held-out current (uA)',ylabel='Voltage residual (mV)',title='Same-curve holdout; temperature unspecified');ax[1].grid(alpha=.15)
    fig.savefig(RAW/'lin2026-yellow20-fit.png',dpi=180);plt.close(fig)
    print(json.dumps({k:report[k] for k in ['measured_points','interpolation_at_100uA_V','held_out_interpolation','local_analytic_fit','global_analytic_fit']},indent=2))
    print('SPICE static replay:',spice['runs'],'runs; max error',spice['maximum_abs_voltage_difference_V'],'V')
if __name__=='__main__':main()
