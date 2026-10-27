#!/usr/bin/env python3
"""Rebuild the public-figure research proxy; not a device parameter extraction."""
import csv, hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
MODEL=ROOT/'analog/models/vcsel_research_20261027'
EVID=ROOT/'evidence/three-gbps-experiment-20261027/vcsel-model'
FIG=ROOT/'docs/research/three-gbps-vcsel-20261027/figures/frontiers-2021-figure8.webp'

def response_db(f,f0,zeta,fp):
    u=np.asarray(f)/f0
    return -10*np.log10((1-u*u)**2+(2*zeta*u)**2)-10*np.log10(1+(np.asarray(f)/fp)**2)

def main():
    MODEL.mkdir(parents=True,exist_ok=True);EVID.mkdir(parents=True,exist_ok=True)
    # Coordinates refer to the unchanged 2008 x 2328 original, origin at top left.
    # Human-selected approximate measured blue dots, NOT the dark-blue author's fit.
    spectral_pixels=[(461,1322),(624,1280),(786,1244),(867,1174),(908,1153),(948,1173),(1029,1252),(1110,1350),(1191,1464),(1272,1575),(1353,1674),(1435,1755),(1516,1816),(1597,1864),(1678,1924),(1759,1982),(1840,2049)]
    s21=[{'pixel_x':x,'pixel_y':y,'frequency_Hz':(x-218)/1622*20e9,'s21_dB':(1338-y)/44.6,'uncertainty_dB':0.6} for x,y in spectral_pixels]
    with (MODEL/'figure8b-3mA-manual-points.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=s21[0]);w.writeheader();w.writerows(s21)
    im=np.asarray(Image.open(FIG).convert('RGB')).astype(int)
    pi=[]
    for current in [0.5,1,2,3,4,5,6,7,7.5]:
        x=round(182+796*current/8); col=im[40:824,x-3:x+4]
        # Blue measured and modeled traces overlap: do NOT label these measured-only.
        mask=(col[:,:,2]>col[:,:,0]+40)&(col[:,:,2]>col[:,:,1]+10)&(col[:,:,0]<100)
        y=float(np.median(np.where(mask)[0]+40))
        pi.append({'current_mA':current,'power_mW':(821-y)*4/777,'pixel_x':x,'pixel_y':y,'uncertainty_mW':0.08,'trace':'25C blue measured/model overlap'})
    with (MODEL/'figure8a-pi-blue-trace.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=pi[0]);w.writeheader();w.writerows(pi)
    iv=[(0.4,1.5),(1,1.60),(2,1.734),(3,1.834),(4,1.923),(5,2.004),(6,2.074),(7,2.136),(8,2.195)]
    # Retain pixel support near manually chosen measured-dot columns. A light-blue
    # mask distinguishes most marker pixels from the darker author's model line.
    # It does not reconstruct laboratory raw data; model knots remain rounded.
    iv_pixels=[]
    for x in [1224,1280,1385,1483,1587,1684,1786,1888,1983]:
        ymax=808 if x<1400 else 610
        col=im[26:ymax,x-3:x+4]
        mask=(col[:,:,0]>80)&(col[:,:,2]>col[:,:,0]+20)&(col[:,:,2]>col[:,:,1]+12)&(col[:,:,0]<190)
        iv_pixels.append((x,float(np.median(np.where(mask)[0]+26))))
    with (MODEL/'figure8a-iv-manual-points.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['model_current_mA','model_voltage_V','sampled_pixel_column','blue_pixel_median_y','pixel_inferred_current_mA','pixel_inferred_voltage_V','uncertainty_V','uncertainty_current_mA','classification'])
        for (i,v),(x,y) in zip(iv,iv_pixels):w.writerow([i,v,x,y,(x-1184)*8/800,1.5+(806-y)*.7/780,.020,.05,'manual rounded measured-dot knot; nearby color-mask pixel support'])
    # Fit a minimal, stable, causal shape. This does not identify intrinsic physics.
    freq=np.array([v['frequency_Hz']/1e9 for v in s21]);mag=np.array([v['s21_dB'] for v in s21])
    bounds=[(8,11),(.18,.50),(7,30)];best=None
    for _ in range(4):
        f0,zeta,fp=np.meshgrid(*[np.linspace(lo,hi,31) for lo,hi in bounds],indexing='ij')
        vals=response_db(freq[None,:],f0.ravel()[:,None],zeta.ravel()[:,None],fp.ravel()[:,None])
        loss=((vals-mag)**2).mean(axis=1);k=int(loss.argmin());best=[float(v.ravel()[k]) for v in [f0,zeta,fp]]
        bounds=[(max(1e-5,b-(hi-lo)/15),b+(hi-lo)/15) for b,(lo,hi) in zip(best,bounds)]
    pred=response_db(freq,*best);res=pred-mag
    params={
      'schema_version':1,'status':'independent public-figure-constrained research proxy; NOT validated VCSEL model',
      'source':{'authors':'Giannakopoulos et al.','title':'A 112 Gb/s Radiation-Hardened Mid-Board Optical Transceiver in 130-nm SiGe BiCMOS for Intra-Satellite Links','date':'2021-05-17','doi':'10.3389/fphy.2021.672941','url':'https://www.frontiersin.org/journals/physics/articles/10.3389/fphy.2021.672941/full','figure_path':str(FIG.relative_to(ROOT)),'figure_sha256':hashlib.sha256(FIG.read_bytes()).hexdigest(),'reuse':'CC BY 4.0; original figure already retained with adjacent notice'},
      'temperature_C':{'value':25,'provenance':'Fig.8A blue legend; only static curves. Fig.8B temperature is not specified.'},
      'iv':{'current_A':[i*.001 for i,v in iv],'voltage_V':[v for i,v in iv],'provenance':'approximate manual Fig.8A measured light-blue dots, 25 C','voltage_reading_uncertainty_V':.020,'current_reading_uncertainty_A':.00005,'trusted_simulation_current_A':[.002,.008],'outside_scope':'0-0.4mA artificial linear numerical continuation; >8mA extends final slope; no reverse-breakdown or thermal validity'},
      'pi':{'current_A':[0]+[p['current_mA']*.001 for p in pi],'power_W':[0]+[p['power_mW']*.001 for p in pi],'provenance':'Fig.8A blue pixel trace, measured/model curves overlap; extraction details and pixels in CSV; zero-current zero-power is numerical assumption','power_reading_uncertainty_W':.00008,'trusted_current_A':[.001,.0075],'outside_scope':'linear continuation above last point is unsupported; no thermal rollover, spontaneous emission or absolute calibration verification'},
      'electrical_assumptions':{'CJ_F':{'default':150e-15,'sweep':[50e-15,150e-15,500e-15],'provenance':'engineering sensitivity choices; NOT disclosed by source and NOT fitted from S11'},'series_resistance_ohm':{'value':0,'provenance':'no added resistor; measured terminal I-V already contains static series loss; not a claim that physical series resistance is zero'}},
      'dynamic':{'name':'figure3mA_proxy','f0_Hz':best[0]*1e9,'zeta':best[1],'fp_Hz':best[2]*1e9,'formula':'H(s) = w0^2/(s^2 + 2*zeta*w0*s + w0^2) * wp/(s+wp)','parameter_provenance':'all three parameters jointly derived by deterministic coarse-to-fine least-squares magnitude-only shape approximation to manually digitized Fig.8B 3mA points; none disclosed by authors','fit_rms_dB':float(np.sqrt(np.mean(res**2))),'fit_max_abs_dB':float(abs(res).max()),'figure_reading_uncertainty_dB':.6,'fit_validation':'in-sample graphical shape agreement only; no held-out device measurements or phase validation','bias_A':.003,'temperature_C':None,'dc_gain':1.0,'application':'fixed normalized shape applied to static P(I); no bias interpolation; only constant 3mA reference shape across whole swing','double_counting':'published electrical-to-optical S21 is not de-embedded; applying this shape to conductive current after separate assumed CJ can double-count electrical roll-off. No unique correction is possible without same-device S11/complex S21.'},
      'alternative_responses':{'lowpass8GHz_assumed':{'pole_Hz':8e9,'provenance':'engineering sensitivity assumption, not extracted intrinsic pole'},'lowpass4GHz_assumed':{'pole_Hz':4e9,'provenance':'deliberate slower response sensitivity assumption'},'static':{'provenance':'instantaneous P(I) control; no optical dynamics'}},
      'excluded':['authors original Spectre model','same-device capacitance/impedance calibration','bias/temperature-dependent optical dynamics','carrier-photon rate equations','noise, RIN, chirp, modal competition','package/PDN and receiver physics','BER or optical-link validation']}
    (MODEL/'parameters.json').write_text(json.dumps(params,indent=2)+'\n')
    (EVID/'shape-fit-summary.json').write_text(json.dumps({'status':'shape approximation only, not device validation','best_parameters':params['dynamic'],'frequency_Hz':(freq*1e9).tolist(),'figure_read_dB':mag.tolist(),'proxy_dB':pred.tolist(),'residual_dB':res.tolist()},indent=2)+'\n')
    print(json.dumps({'f0_GHz':best[0],'zeta':best[1],'fp_GHz':best[2],'rms_dB':params['dynamic']['fit_rms_dB'],'max_abs_dB':params['dynamic']['fit_max_abs_dB']},indent=2))
if __name__=='__main__':main()
