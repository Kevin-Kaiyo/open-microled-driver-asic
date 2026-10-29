#!/usr/bin/env python3
"""Read licensed original XLSX data without rewriting any historical model.

Python stdlib parses XLSX; NumPy/Matplotlib are used only for derived checks/plots.
No transient phase, capacitance or carrier lifetime is invented from magnitude.
"""
from pathlib import Path
import csv, hashlib, io, json, math, re, urllib.request, zipfile
import xml.etree.ElementTree as ET
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/microled-dynamic-20261029'
EV=ROOT/'evidence/microled-dynamic-20261029'
ARCHIVE=ROOT/'build/led-fit/lin2026-source-data.zip'
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
SELECTED=[25e-6,50e-6,60e-6,80e-6,100e-6]

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def emit(p,obj):
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def workbook(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        sheet_names=[x.get('name') for x in ET.fromstring(z.read('xl/workbook.xml')).find('s:sheets',NS)]
        sheets={}
        for k,name in enumerate(sheet_names,1):
            rows=[]
            for row in ET.fromstring(z.read(f'xl/worksheets/sheet{k}.xml')).findall('s:sheetData/s:row',NS):
                cells={}
                for c in row:
                    v=c.find('s:v',NS);v=v.text if v is not None else None
                    if c.get('t')=='s' and v is not None:v=strings[int(v)]
                    elif c.get('t')=='inlineStr':v=''.join(c.find('s:is',NS).itertext())
                    cells[re.sub('[0-9]','',c.get('r'))]=v
                rows.append(cells)
            sheets[name]=rows
        return sheets

def crossing(f,db,level):
    i=np.flatnonzero((db[:-1]>level)&(db[1:]<=level))
    assert len(i)>0
    k=i[0]
    return float(f[k]+(level-db[k])/(db[k+1]-db[k])*(f[k+1]-f[k]))

def writecsv(name,headers,rows):
    with (EV/name).open('w',newline='') as out:
        w=csv.writer(out,lineterminator='\n');w.writerow(headers);w.writerows(rows)

def run():
    BUILD.mkdir(parents=True,exist_ok=True);EV.mkdir(parents=True,exist_ok=True)
    assert sha(ARCHIVE)=='4873cfd00f6ffa7e9c75e425e4e41d230a7100e43e9e74bb67225e37ea09c3ee'
    names=['yellow20_s21_bandwidths.xlsx','bandwidth.xlsx','frequency_response_low_current.xlsx','diamond-optical-power.xlsx']
    books={};sources=[]
    with zipfile.ZipFile(ARCHIVE) as z:
        for name in names:
            blob=z.read(name);p=BUILD/name;p.write_bytes(blob);books[name]=workbook(blob)
            sources.append({'archive_member':name,'sha256':sha(p),'bytes':len(blob),'sheets':list(books[name])})
    w=books[names[0]];bw_rows,mag_rows=list(w.values());hdr=mag_rows[0]
    columns={float(v[:-1]):k for k,v in hdr.items() if k!='A'}
    f=np.array([float(x['A'])*1e6 for x in mag_rows[1:]])
    assert len(f)==2001 and f[0]==30e6 and f[-1]==3e9 and np.all(np.diff(f)>0)
    mags={i:np.array([float(x[columns[i]]) for x in mag_rows[1:]]) for i in SELECTED}
    bw=[[float(r[c]) for c in ['A','B','C','D']] for r in bw_rows[1:]]
    writecsv('yellow20-bandwidth.csv',['current_A','current_density_A_cm2','source_BW_minus3dB_MHz','source_BW_minus6dB_MHz'],bw)
    writecsv('yellow20-s21-selected.csv',['frequency_Hz']+[f'S21_dB_at_{i*1e6:g}uA' for i in SELECTED],zip(f,*[mags[i] for i in SELECTED]))
    p_rows=list(books['diamond-optical-power.xlsx'].values())[0][2:]
    pi=[[float(r['A']),float(r['B'])] for r in p_rows if r.get('A') is not None and r.get('B') is not None]
    writecsv('yellow20-optical-power.csv',['current_A','source_optical_power_uW'],pi)
    freq_rows=list(books['frequency_response_low_current.xlsx'].values())[0]
    cmp=np.array([[float(r['A'])*1e6,float(r['B'])] for r in freq_rows[1:]])
    assert np.max(np.abs(cmp[:,0]-f))<1e-5
    assert np.max(np.abs(cmp[:,1]-mags[100e-6]))<1e-12
    results=[]
    for i in SELECTED:
        db=mags[i];ref=next(r for r in bw if abs(r[0]-i)<1e-14)
        b3=crossing(f,db,-3);b6=crossing(f,db,-6)
        results.append(dict(current_uA=i*1e6,current_density_A_cm2=i/(20e-4)**2,
            source_BW3_MHz=ref[2],source_BW6_MHz=ref[3],recomputed_BW3_MHz=b3/1e6,recomputed_BW6_MHz=b6/1e6,
            ratio_BW6_to_BW3=b6/b3,single_pole_ratio_for_exact_minus3_minus6_dB=math.sqrt((10**.6-1)/(10**.3-1)),
            single_pole_tau_from_minus3_ps=math.sqrt(10**.3-1)/(2*math.pi*b3)*1e12,
            source_S21_at_Nyquist1p85GHz_dB=float(np.interp(1.85e9,f,db)),
            max_S21_dB=float(db.max()),power_at_bias_uW=float(np.interp(i,np.array(pi)[:,0],np.array(pi)[:,1])),power_value_method='linear interpolation of static P-I table; not a dynamic optical calibration'))
    maxerr=max(abs(r[a]-r[b]) for r in results for a,b in [('source_BW3_MHz','recomputed_BW3_MHz'),('source_BW6_MHz','recomputed_BW6_MHz')])
    assert maxerr<1e-8
    # Algebraic counterexample only: |H exp(-s*delay)|=|H|, no fitted phase.
    example_tau=results[0]['single_pole_tau_from_minus3_ps']*1e-12
    h=1/(1+2j*np.pi*f*example_tau);delayed=h*np.exp(-2j*np.pi*f*100e-12)
    assert np.max(np.abs(abs(h)-abs(delayed)))<1e-15
    pi_a=np.array(pi)
    old=json.loads((ROOT/'analog/models/measured-led/model-card.json').read_text())
    summary=dict(source_workbooks=sources,selected_points=results,
        checks=dict(points_per_curve=2001,selected_curves=len(SELECTED),bandwidth_table_recompute_max_error_MHz=maxerr,
                    independent_workbook_100uA_response_matches=True,allpass_delay_magnitude_max_error=float(np.max(np.abs(abs(h)-abs(delayed)))),
                    source_current_density_area_check_max_A_cm2=max(abs(r[1]-r[0]/(20e-4)**2) for r in bw),
                    all_selected_curves_equal_zero_dB_at_30MHz=bool(all(db[0]==0 for db in mags.values()))),
        current_point_coverage={'NRZ_25_100uA':'both exact published bias columns','PAM4_25_50_75_100uA':'75uA not a published dynamic column; 60/80uA bracket it, interpolation is not measured'},
        static_model_source_sha256=sha(ROOT/'analog/models/measured-led/model-card.json'),
        original_archive_sha256=sha(ARCHIVE),
        measurement_plane='VNA RF source -> bias tee -> MicroLED -> fiber optics -> SPD-4 photodetector -> VNA. Published normalized S21 magnitude only.',
        dynamic_domain={'current_A':[min(columns),max(columns)],'frequency_Hz':[float(f[0]),float(f[-1])],'temperature_C':None,'same_serial_as_IV':None,'same_structure_size_colour':'20um yellow on diamond','physical_sample_count':None},
        absent=['complex S11','S21 phase or group delay','RF modulation amplitude at each bias','deembedded detector and fixture response','C(V,I,f,T)','same physical pixel serial across I-V/L-I/S21','cross-temperature S21'],
        decision='Do not promote the old assumed 200fF/200ps model to measured dynamics. Do not cascade the measured composite S21 after those same device/receiver poles. Do not infer a unique transient model or 3.2Gb/s BER from magnitude.',
        publication='Derived numerical data/plots under source dataset CC BY4.0, with attribution. Original paper figures are separate CC BY-NC-ND4.0 and not included in public artifacts.')
    emit(EV/'extraction-checks.json',summary)
    emit(EV/'source-cell-extract.json', {
        'source':'yellow20_s21_bandwidths.xlsx', 'method':'Faithful cell-value extraction; not an Excel screenshot',
        'Bandwidths': [{'row':1,'cells':bw_rows[0]}]+[{'row':n+1,'cells':r} for n,r in enumerate(bw_rows) if n and float(r['A']) in SELECTED],
        'Shifted_Curves': [{'row':n+1,'cells':{k:r[k] for k in ['A']+[columns[i] for i in SELECTED]}} for n,r in enumerate(mag_rows) if n in [0,1,2,2000,2001]],
        'unit_check':'2.5e-05 A = 0.025 mA = 25 uA; 0.0001 A = 0.1 mA = 100 uA',
        'normalization_observed':'Every selected curve is exactly 0 dB at first frequency 30 MHz; not evidence of independently measured DC normalization'})
    font=ROOT/'build/fair-driver-v1/report-font/NotoSansCJKsc-Regular.otf'
    if font.exists():plt.rcParams['font.family']=FontProperties(fname=font).get_name();matplotlib.font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,ax=plt.subplots(1,2,figsize=(12,4.8),constrained_layout=True)
    colours=['#0e7490','#287c64','#6c7793','#a47726','#924b6a']
    for i,c in zip([25e-6,50e-6,100e-6],[colours[0],colours[1],colours[-1]]):ax[0].plot(f/1e9,mags[i],label=f'{i*1e6:g} µA',color=c,lw=1.6)
    ax[0].axhline(-3,c='gray',ls='--',lw=.8);ax[0].axhline(-6,c='gray',ls=':',lw=.8)
    ax[0].set(xlabel='Frequency / GHz',ylabel='Published normalized S21 / dB',title='作者已归一化数据：20 µm 黄色 MicroLED',xlim=(0,3),ylim=(-8,1));ax[0].legend(ncol=3,fontsize=9);ax[0].grid(alpha=.17)
    b=np.array(bw);ax[1].semilogx(b[:,0]*1e6,b[:,2]/1000,'o-',ms=3,label='source −3 dB / E–E',color='#0e7490');ax[1].semilogx(b[:,0]*1e6,b[:,3]/1000,'s-',ms=3,label='source −6 dB / E–O',color='#a47726');ax[1].axvspan(25,100,color='#0e7490',alpha=.1,label='本项目 25–100 µA')
    ax[1].set(xlabel='DC bias / µA',ylabel='Source-defined cutoff / GHz',title='偏置依赖：两种截止定义不得互换');ax[1].legend(fontsize=9);ax[1].grid(alpha=.17)
    fig.suptitle('Lin et al. / Zenodo 20034288：独立重绘；不是本项目器件实测',fontsize=12)
    fig.savefig(EV/'source-response.png',dpi=160);fig.savefig(EV/'source-response.svg');plt.close(fig)
    fig,ax=plt.subplots(1,2,figsize=(12,4.6),constrained_layout=True)
    ax[0].plot(pi_a[:,0]*1e6,pi_a[:,1],color='#0e7490',marker='o',ms=3);ax[0].set(xlabel='DC current / µA',ylabel='Published optical power / µW',title='同系列 P–I 原始数据：低电流区',xlim=(0,120),ylim=(0,6));ax[0].grid(alpha=.17)
    a=200e-12;b=1/(2*np.pi*1e9);ff=np.geomspace(10e6,5e9,800)
    oldh=1/(1+2j*np.pi*ff*a)/(1+2j*np.pi*ff*b)
    ax[1].semilogx(ff/1e9,20*np.log10(abs(oldh)),label='原假设 optical 200ps + RX 1GHz',color='#924b6a');ax[1].set(xlabel='Frequency / GHz',ylabel='Calculated proxy amplitude / dB',title='旧后处理代理：不同参考面，不是实测 S21',ylim=(-35,1));ax[1].axvline(1.85,color='gray',ls=':');ax[1].legend(fontsize=9);ax[1].grid(alpha=.17)
    fig.suptitle('分开理解静态光功率与动态假设；不能直接叠乘整条已测 S21',fontsize=12)
    fig.savefig(EV/'power-and-old-proxy.png',dpi=160);fig.savefig(EV/'power-and-old-proxy.svg');plt.close(fig)
    print(json.dumps({'curves':len(SELECTED),'points':len(f),'max_bandwidth_error_MHz':maxerr,'selected':results},ensure_ascii=False,indent=2))

if __name__=='__main__':run()
