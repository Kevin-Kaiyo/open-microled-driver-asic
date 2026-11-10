#!/usr/bin/env python3
"""Plot native-derived receiver waveforms around the worst amplitude sample."""
from pathlib import Path
import csv,json,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/highspeed_workbench_20261110'))
from replay import module
EV=ROOT/'evidence/blue-emitter-speed-review-20261110'
DOC=ROOT/'docs/research/blue-emitter-speed-review-20261110'

def main():
    data=json.loads((EV/'speed-sweep-all.json').read_text())
    dyn=module(ROOT/'scripts/microled_dynamic_v1/analyze.py','sweep_wave_dynamics')
    stim=json.loads((ROOT/'build/microled-dynamic-v1/electrical/run-r1/stimulus.json').read_text())
    bits=np.array(stim['bits'])[576:4672]
    font='/System/Library/Fonts/Hiragino Sans GB.ttc';font_manager.fontManager.addfont(font)
    plt.rcParams.update({'font.family':[font_manager.FontProperties(fname=font).get_name(),'DejaVu Sans'],'font.size':12,'axes.unicode_minus':False})
    fig,axs=plt.subplots(2,2,figsize=(11.8,6.7),layout='constrained');export=[]
    for ax,(route,rate) in zip(axs.flat,[('A',.8),('A',1.6),('B',.4),('B',.8)]):
        row=next(r for r in data['rows'] if r['family']=='MicroLED' and r['route']==route and r['net_Gbps']==rate and r['steps_per_symbol']==40 and r['capacitance_fF']==200)
        t,current=np.loadtxt(ROOT/row['source_case']/'waveform.dat.gz',skiprows=1,usecols=(0,1)).T
        _,y=dyn.cascade_pwl(t,current,200e-12,1/(2*np.pi*1e9));y*=1e6
        ui=(32/37)/(rate*1e9);delay=row['full_receiver']['delay_bit_UI']
        ts=(np.arange(576,4672)+delay)*ui;samples=np.interp(ts,t,y)
        signed=np.where(bits==1,samples-62.5,62.5-samples)
        worst=int(signed.argmin());begin=max(0,worst-3);end=min(4096,begin+8);begin=max(0,end-8)
        ref=ts[begin];grid=ref+np.arange(-.5,7.5,1/128)*ui
        vals=np.interp(grid,t,y);x=(grid-ref)/ui
        ax.plot(x,vals,color='#236d73',lw=1.7,label='接收代理')
        ax.axhline(62.5,color='#90734d',ls='--',lw=1.2,label='固定阈值')
        ax.plot(np.arange(end-begin),samples[begin:end],'o',color='#233c4a',ms=4)
        for k,b in enumerate(bits[begin:end]):ax.text(k,112,str(b),ha='center',fontsize=10,color='#5b727d');ax.axvline(k,color='#d9e3e2',lw=.6,zorder=0)
        k=worst-begin;ax.plot(k,samples[worst],'o',mfc='white',mec='#ad5d38',ms=9,mew=1.8)
        rx=row['full_receiver'];status='通过筛查' if row['combined_research_screen_pass'] else '零错，但余量不足'
        ax.set(title=f'{route} · 净 {rate:g} Gb/s · 最差幅度 {signed[worst]:.2f} µAeq\n{status} · 单侧时间 {rx["one_sided_margin_bit_UI"]:.3f} bit UI',xlabel='相对采样位置 / bit UI',ylabel='接收代理 / µAeq',xlim=(-.5,7.5),ylim=(13,119))
        ax.spines[['top','right']].set_visible(False)
        for xx,v in zip(x,vals):export.append({'route':route,'net_Gbps':rate,'worst_payload_index':worst,'first_payload_index':begin,'sample_aligned_bit_UI':float(xx),'receiver_uAeq':float(v)})
    fig.savefig(DOC/'assets/rate-waveforms.png',dpi=180);plt.close(fig)
    with (EV/'waveform-excerpt.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(export[0]));w.writeheader();w.writerows(export)

if __name__=='__main__':main()
