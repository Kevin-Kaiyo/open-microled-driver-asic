"""Compact case index, calibrated DC results and plots from actual ngspice outputs."""
from pathlib import Path
import argparse
import json
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
import run as a

OUT=a.ROOT/'docs/research/driver-ab-20261118/assets'
TEAL='#147c79';NAVY='#173952';RUST='#aa5235';GRAY='#70838b'
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['PingFang SC','Hiragino Sans GB','Arial Unicode MS','DejaVu Sans'],'font.size':10,'axes.unicode_minus':False})
def save(fig,name):
    OUT.mkdir(parents=True,exist_ok=True)
    fig.savefig(OUT/f'{name}.png',dpi=175,bbox_inches='tight',facecolor='white')
    plt.close(fig)

def orig(point,l):
    return a.read(a.PARENT/f'{point}-DC-L{l}'/'result.json')

def res(point,c,level):
    return a.read(a.BUILD/f'sense-{point}'/f'dc{level}-h{c[0]}-l{c[1]}'/'result.json')

def scope(row):
    return {k:row[k] for k in ['current_uA','DC_error_percent','DC_pass']}

def grid():
    tt=a.read(a.EV/'TT-ideal.json')['codes']
    data=[]
    for point in a.GRID:
        cal=a.read(a.EV/f'{point}-ideal.json')
        data.append(dict(point=point,pvt=a.GRID[point],codes=cal['codes'],
                         parent=[scope(orig(point,l)) for l in [0,1]],
                         midpoint=[scope(res(point,[128,128],l)) for l in [0,1]],
                         fixed_TT=[scope(res(point,tt,l)) for l in [0,1]],
                         adaptive=[scope(a.read(a.ROOT/v['case_path']/'result.json')) for v in cal['final']]))
    hold=[]
    for point,source in [('holdTT','TT'),('holdSS','SShotlow')]:
        original=a.read(a.EV/f'{source}-ideal.json')['codes']
        row=a.read(a.EV/f'{point}-ideal.json')
        hold.append(dict(point=point,source=source,pvt=a.HOLD[point],codes_before=original,codes_after=row['codes'],
                         held=[scope(res(point,original,l)) for l in [0,1]],
                         recalibrated=[scope(res(point,row['codes'],l)) for l in [0,1]]))
    aggregate={}
    for method in ['parent','midpoint','fixed_TT','adaptive']:
        cols=[[r[method][l]['DC_error_percent'] for r in data] for l in [0,1]]
        aggregate[method]=dict(pass_count=sum(x['DC_pass'] for row in data for x in row[method]),
                               max_abs_errors_percent=np.max(np.abs(cols),axis=1).tolist(),
                               currents_uA=[[min(r[method][l]['current_uA'] for r in data),max(r[method][l]['current_uA'] for r in data)] for l in [0,1]])
    out=dict(points=data,aggregate=aggregate,holdout=hold,errors=[a.read(a.EV/f'SShotlow-{tag}.json')['final'] for tag in ['down','up']])
    a.emit(a.EV/'dc-summary.json',out)
    fig,axes=plt.subplots(2,1,figsize=(10.8,5.8),sharex=True)
    x=np.arange(len(data))
    for l,ax in enumerate(axes):
        ax.axhspan(-1,1,color=TEAL,alpha=.095);ax.axhline(0,color=GRAY,lw=.6)
        for name,title,color,marker in [('parent','原电压跟踪',GRAY,'x'),('fixed_TT','加检测电阻，固定 TT 码',RUST,'s'),('adaptive','按实测支路压降重新校准',TEAL,'o')]:
            ax.plot(x,[r[name][l]['DC_error_percent'] for r in data],marker=marker,label=title,color=color,ms=5,lw=1.6)
        ax.set_ylabel(f'{[25,100][l]} µA 误差 / %')
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',alpha=.15);ax.set_ylim(-2.4,2.4)
    axes[0].legend(loc='upper center',bbox_to_anchor=(.5,1.29),ncol=3,frameon=False,fontsize=9)
    axes[-1].set_xticks(x,['TT','TT 冷','TT 热','TT 低压','TT 高压','SS 热低','FF 冷高','SF 热低','FS 冷高'])
    fig.tight_layout();save(fig,'a-current-error')

def schematic():
    fig,ax=plt.subplots(figsize=(11.9,5.6))
    ax.set_xlim(0,19);ax.set_ylim(0,9);ax.axis('off')
    def label(x,y,s,**kw):ax.text(x,y,s,va='center',color=NAVY,**kw)
    def line(*pt,**kw):ax.plot(*zip(*pt),color=kw.get('c',NAVY),lw=1.5)
    def node(x,y):ax.add_patch(Circle((x,y),.055,color=NAVY))
    def box(x,y,w,h,s):
        ax.add_patch(Rectangle((x,y),w,h,ec=TEAL,fc='#f2f8f7',lw=1.1))
        label(x+w/2,y+h/2,s,ha='center',fontsize=10)
    def resistor(x1,y,x2):
        p=np.array((x1,y));d=x2-x1
        line(tuple(p),(x1+d*.23,y),*[(x1+d*(.26+i*.06),y+(.12 if i%2==0 else -.12)) for i in range(9)],(x1+d*.77,y),(x2,y))
    def arrow(p,q):ax.annotate('',xy=q,xytext=p,arrowprops=dict(arrowstyle='->',lw=1.4,color=TEAL))
    label(.15,8.65,'校准时测串联电阻压降，传输时保持 H / L 两个抽头码',fontsize=16)
    label(.15,8.0,'数据通路',fontsize=12,fontweight='bold')
    box(.3,6.1,2.0,.92,'VLED / PISO');line((2.3,6.56),(3.0,6.56))
    box(3.0,6.1,3.0,.92,'MicroLED ∥ 200 fF');line((6.0,6.56),(6.45,6.56))
    box(6.45,6.1,3.0,.92,'封装 1 Ω ＋ 0.5 nH')
    line((9.45,6.56),(10,6.56));resistor(10,6.56,12.25);line((12.25,6.56),(13.0,6.56))
    box(13.,6.1,4.8,.92,'OUT · 原有 PMOS / NMOS 输出级')
    label(10.96,7.04,'RMON 100 Ω',ha='center',fontsize=10)
    for x,s,y in [(10.,'MON (+)',5.7),(12.25,'OUT (−)',5.7)]:
        node(x,6.56);line((x,6.56),(x,5.25));label(x+(.17 if x<11 else .18),y,s,fontsize=8)
    box(9.3,4.45,3.85,.8,'差分采样  ·  5 µV/LSB')
    label(13.55,4.85,'输入等效 10 MΩ ∥ 50 fF 跨接 RMON',fontsize=9)
    label(.15,5.15,'校准通路',fontsize=12,fontweight='bold')
    box(.3,3.3,4.4,.9,'控制器  ·  搜索抽头并锁存')
    arrow((9.3,4.86),(4.72,3.83));label(5.0,4.68,'V(MON) − V(OUT)',fontsize=9)
    arrow((2.48,3.28),(2.48,2.46))
    box(.3,1.55,4.4,.9,'H/L 两套 256 kΩ 电阻串')
    line((4.7,2.0),(5.4,2.0));resistor(5.4,2.,8.);line((8.,2.),(8.45,2.))
    label(6.57,2.4,'各 47 MΩ',fontsize=10,ha='center')
    box(8.45,1.55,4.0,.9,'HSENSE / LSENSE 求和点')
    arrow((12.46,2.0),(13.12,2.0));box(13.15,1.55,4.65,.9,'OTA ＋ 分流管 → VH / VL')
    arrow((15.48,2.49),(15.48,3.92));label(15.48,4.22,'设置输出级两路阴极电压',fontsize=9,ha='center')
    label(.3,.79,'D0 固定为 0 / 1 测得 25 / 100 µA。切换瞬间 RMON 含结电容位移电流及钳位电流，只在 DC 工作点进行校准。',fontsize=10)
    label(.3,.27,'外部控制器与 ADC 转换按功能建模。仿真计入无源电阻串和 ADC 差分输入负载，供电及失调预算另列。',fontsize=9)
    fig.tight_layout();save(fig,'a-sense-schematic')

def compact_wave(p):
    r=a.read(p/'result.json'); m=a.read(p/'manifest.json')
    frames=[]
    for f in r['frames']:
        frames.append({k:f[k] for k in ['frame','full_receiver','first_frame_phase_receiver','energy_pJ_per_attempted_payload_bit','rail_endpoints_V']})
    return dict(folder=str(p.relative_to(a.ROOT)),sha256=a.sha(p/'result.json'),codes=m.get('codes'),
                frames=frames,body_V=r['body_forward_V'],terminal_pass=r['terminal_pass'],body_pass=r['body_pass'],
                shutdown={k:r['shutdown'][k] for k in ['max_abs_current_uA','last_above_threshold_ns','recovery_screen','off_current_screen_pass']} if 'shutdown' in r else None,
                worst_body=max(r['stress'],key=lambda d:d['body_forward_V']),steady_screen=r['steady_screen'])

def waves():
    points={'TT parent':a.PARENT/'TT-continuous-f1-s40'}
    for path in sorted(a.BUILD.glob('*/*/preview.npz')):
        folder=path.parent
        if folder.parent.name!='edge-SS' and (folder/'result.json').exists():
            points[folder.parent.name+'-'+folder.name]=folder
    allwaves={k:compact_wave(v) for k,v in points.items()}
    a.emit(a.EV/'dynamic-summary.json',allwaves)
    candidates=[(k,v) for k,v in points.items() if 'SShotlow' in k and 'fault' in k and 'sensecap150' not in k]
    if len(candidates)<2:return
    fig,axes=plt.subplots(3,2,figsize=(11,7.4),sharex='col')
    ts=[.64,1.28]
    for name,p in candidates:
        z=np.load(p/'preview.npz')
        s='原 A' if 'baseline' in name else '电流校准 A'
        color=GRAY if 'baseline' in name else TEAL
        for j,origin in enumerate(ts):
            t=(z['time_s']-origin*1e-6)*1e9
            m=(t>=-4)&(t<=26)
            for ix,key in enumerate(['iled_cond','received_uAeq','iso_g']):
                axes[ix,j].plot(t[m],z[key][m]*(1e6 if key=='iled_cond' else 1),color=color,alpha=.88,lw=1.15,label=s)
    axes[0,0].set_title('DISABLE 断言  ·  0.64 µs',loc='left')
    axes[0,1].set_title('DISABLE 释放  ·  1.28 µs',loc='left')
    for i,row in enumerate(axes):
        row[0].set_ylabel(['LED 导通电流 / µA','接收代理 / µAeq','隔离级 ISO_G / V'][i])
        for ax in row:
            ax.axvline(0,color=RUST,ls=':',lw=1);ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.13)
            if i==1:ax.axhline(62.5,lw=.7,ls='--',color=RUST)
            if i==2:ax.set_xlabel('相对于 DISABLE 边沿 / ns')
    axes[0,1].legend(frameon=False,fontsize=9,loc='upper right')
    fig.tight_layout();save(fig,'a-fault-waves')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('what',choices=['static','wave']);args=p.parse_args()
    if args.what=='static':grid();schematic()
    else:waves()
