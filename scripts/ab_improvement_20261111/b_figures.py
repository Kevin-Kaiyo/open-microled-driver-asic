#!/usr/bin/env python3
"""Matched net0.8-Gb/s B edge-charge illustration from verified native excerpts."""
from pathlib import Path
import csv
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'evidence/ab-improvement-20261111'
OUT=ROOT/'docs/research/driver-improvement-20261111/assets'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with (EV/'b-transitions.csv').open() as f:rows=list(csv.DictReader(f))
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['PingFang SC','Heiti SC','DejaVu Sans'],
        'font.size':12.5,'axes.titlesize':13,'axes.labelsize':12.5,'legend.fontsize':11.5,
        'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False,
        'svg.fonttype':'path','axes.edgecolor':'#9aa7ad','text.color':'#21323c','axes.labelcolor':'#21323c'})
    styles=[('B_baseline','原版 B','#29495e','-'),('B_fast_wide','快门驱＋宽 R','#81898c','--'),
            ('B_wide_ff20','＋20 fF 前馈','#338c8c','-.'),('B_wide_ff31p275','＋31.275 fF 前馈','#b76c2d','-')]
    fig,ax=plt.subplots(2,2,figsize=(10.8,7.8),sharex=True)
    handles=[]
    for col,transition in enumerate(['0->1','1->0']):
        selected={name:[r for r in rows if r['candidate']==name and r['transition']==transition] for name,_,_,_ in styles}
        assert all(selected.values())
        for name,label,color,line in styles:
            rr=selected[name];t=np.array([float(r['relative_time_ps']) for r in rr])/1000
            current=np.array([float(r['current_uA']) for r in rr])
            h,=ax[0,col].plot(t,current,label=label,color=color,ls=line,lw=2.0)
            if col==0:handles.append(h)
            if name in ['B_wide_ff20','B_wide_ff31p275']:
                q=np.array([float(r['CFF_GB_plate_charge_fC']) for r in rr]);q-=np.interp(0,t,q)
                ax[1,col].plot(t,q,color=color,ls=line,lw=2,label=label.replace('＋','CFF = '))
        rr=selected['B_wide_ff31p275'];t=np.array([float(r['relative_time_ps']) for r in rr])/1000
        vf=np.array([float(r['led_terminal_V']) for r in rr])
        qled=-200*(vf-np.interp(0,t,vf))
        ax[1,col].plot(t,qled,color='#29495e',lw=1.7,ls=':',label='200 fF 结电容阴极电荷变化')
        for target in [25,100]:ax[0,col].axhline(target,color='#d2d8da',ls=':',lw=1,zorder=0)
        ax[0,col].set_title('数据 0 → 1：LED 电流上升' if col==0 else '数据 1 → 0：LED 电流下降',pad=12)
        ax[0,col].set_ylim(10,120);ax[0,col].set_yticks([25,50,75,100])
        ax[1,col].set_ylim((-110,15) if col==0 else (-15,110))
        ax[1,col].axhline(-81.4 if col==0 else 81.4,color='#c9b49c',ls='--',lw=1)
        ax[1,col].text(1.05,-73 if col==0 else 73,'约 81 fC：200 fF × 0.407 V',fontsize=10.5,color='#7c6653')
        ax[1,col].set_xlabel('相对数据跳变时间（ns）')
        ax[1,col].set_title('从阴极移走电荷' if col==0 else '向阴极补充电荷',pad=10)
        for a in ax[:,col]:
            a.axvline(0,color='#aab6bd',lw=.8,ls=':');a.grid(axis='y',color='#e6ebed',lw=.7)
            a.set_xlim(-.1,2.05);a.set_xticks([0,.5,1,1.5,2])
    ax[0,0].set_ylabel('LED 导通电流（µA）')
    ax[1,0].set_ylabel('相对边沿起点的电荷变化（fC）')
    fig.suptitle('B：门驱变快还不够，前馈电容补足瞬态充放电电流',fontsize=16,y=.985)
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.943),ncol=4,frameon=False,columnspacing=1.3,handlelength=2)
    ax[1,0].legend(loc='upper right',frameon=False,fontsize=10)
    fig.text(.07,.055,'固定负载：200 fF／0.5 nH，净速率 0.8 Gb/s。曲线为连续三位相同数据后的边沿示例。',fontsize=11)
    fig.text(.07,.025,'QFF = CFF × (VGB − VOUT)；与结电容电荷并不完全相等，其差还包括导通电流及其他节点电容。',fontsize=10.5,color='#50636d')
    fig.subplots_adjust(left=.10,right=.98,bottom=.15,top=.84,hspace=.34,wspace=.22)
    paths=[]
    for ext in ['png','svg']:
        p=OUT/f'b-edge-charge.{ext}';fig.savefig(p,dpi=180,facecolor='white');paths.append(p)
    plt.close(fig)
    receipt={'source_csv':str((EV/'b-transitions.csv').relative_to(ROOT)),
             'source_csv_sha256':hashlib.sha256((EV/'b-transitions.csv').read_bytes()).hexdigest(),
             'selected_cases':[s[0] for s in styles],'net_Gbps':.8,
             'plot_scope':'Illustration only; receiver uses the full native waveforms. QFF is net charge, not capacitor peak current.',
             'outputs':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    (EV/'b-figure-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print('Created',*[str(p.relative_to(ROOT)) for p in paths])

if __name__=='__main__':main()
