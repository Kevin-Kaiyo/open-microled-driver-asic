#!/usr/bin/env python3
"""Source-backed VCSEL node waveforms and matched-rate tradeoff plots."""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/highspeed_workbench_20261110'))
import vcsel_x10_analyze as analysis
from replay import module
BASE=ROOT/'build/blue-emitter-speed-review-20261110/vcsel/net6.4-edge20-s40'
NEW=ROOT/'build/ab-improvement-20261111/VCSEL/vc-atten50-steer20/net6.4-edge20-s40'
EV=ROOT/'evidence/ab-improvement-20261111'
ASSET=ROOT/'docs/research/driver-improvement-20261111/assets'
TEAL='#246e76';GRAY='#77858d';ORANGE='#bc6836'


def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def extract(folder):
    m=read(folder/'manifest.json');r=read(folder/'result.json')
    t,raw=analysis.waveform(folder,m,r,False)
    end=m['end_s'];bits=np.asarray(read(folder/'stimulus.json')['bits']);ui=end/len(bits)
    grid=np.linspace(0,end,len(bits)*128+1)
    current=np.interp(grid,t,raw['v(jmon)'])
    model=module(analysis.OPTO_PATH,'vcsel_plot_optical')
    p0,p1=model.static_power([.003,.007])
    signal=25+75*(model.optical_power(grid,current)-p0)/(p1-p0)
    received=analysis.one_pole(grid,signal,5e9)
    window=slice(576*128,584*128+1)
    return dict(ui=ui,bits=bits[576:584],x=grid[window]/ui-576,
        input=(np.interp(grid[window],t,raw['v(xdrv.di)'])-np.interp(grid[window],t,raw['v(xdrv.dbi)'])),
        gate=(np.interp(grid[window],t,raw['v(xdrv.gp)'])-np.interp(grid[window],t,raw['v(xdrv.gn)'])),
        current=current[window]*1e3,received=received[window])


def main():
    font=Path('/System/Library/Fonts/Hiragino Sans GB.ttc')
    if font.exists():font_manager.fontManager.addfont(font)
    plt.rcParams.update({'font.family':['Hiragino Sans GB','Arial'],'font.sans-serif':['Hiragino Sans GB','Arial','DejaVu Sans'],
        'font.size':10,'axes.titlesize':12,'axes.labelsize':10,'axes.unicode_minus':False,
        'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','savefig.facecolor':'white'})
    ASSET.mkdir(parents=True,exist_ok=True)
    a,b=extract(BASE),extract(NEW)
    assert np.array_equal(a['bits'],b['bits']) and np.allclose(a['x'],b['x'])
    fig,axs=plt.subplots(4,1,figsize=(10.2,7.0),sharex=True,layout='constrained')
    labels=[('input','输入 DI−DBI\n(V)'),('gate','换流门极 GP−GN\n(V)'),('current','VCSEL 导电电流\n(mA)'),('received','完整接收代理\n(µAeq)')]
    for ax,(key,label) in zip(axs,labels):
        ax.plot(a['x'],a[key],label='原版 r10',color=GRAY,lw=1.4,ls='--')
        ax.plot(b['x'],b[key],label='ATTEN 50Ω + 换流 MOS W20µm',color=TEAL,lw=1.4)
        ax.set_ylabel(label);ax.grid(alpha=.15);ax.set_xlim(0,8);ax.set_xticks(np.arange(9))
    for k,bit in enumerate(a['bits']):axs[0].text(k+.5,3.65,str(bit),ha='center',va='center',fontsize=10,color='#213e49')
    axs[0].set_ylim(-3.5,4.15);axs[0].legend(loc='lower center',bbox_to_anchor=(.5,1.05),ncol=2,fontsize=10,frameon=False)
    axs[0].set_title('净 6.4 Gb/s｜同一时间轴，逐级观察电路改善',loc='left',pad=37)
    axs[2].axhline(3,color='black',ls=':',lw=.7,alpha=.4);axs[2].axhline(7,color='black',ls=':',lw=.7,alpha=.4)
    axs[3].axhline(62.5,color=ORANGE,ls=':',lw=1);axs[3].text(7.96,64,'判决阈值',ha='right',va='bottom',color=ORANGE,fontsize=9)
    axs[3].set_xlabel('从验证窗口起点计时（线速率 bit UI；1 UI ≈ 135.14 ps）')
    fig.savefig(ASSET/'vcsel-waveforms.png',dpi=140,pil_kwargs={'optimize':True});plt.close(fig)

    causal=read(EV/'vcsel-causal-comparison.json');rows=causal['rows']
    names=['原版','仅 ATTEN 50Ω','仅换流 W20µm','组合修改'];colors=[GRAY,'#79a3a7','#a9c1c3',TEAL]
    fig,axs=plt.subplots(1,2,figsize=(10.2,3.5),layout='constrained')
    for ax,field,ylab in [(axs[0],'positive_pJ_per_attempted_bit','E+（pJ / 尝试载荷位）'),(axs[1],'full_margin_ps','单侧接收时间余量（ps）')]:
        bars=ax.bar(np.arange(4),[r[field] for r in rows],color=colors,width=.65)
        ax.set_xticks(np.arange(4),names,fontsize=9);ax.set_ylabel(ylab);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
        for rect,r in zip(bars,rows):ax.text(rect.get_x()+rect.get_width()/2,rect.get_height()+(.09 if field.startswith('positive') else .6),f'{r[field]:.3f}' if field.startswith('positive') else f'{r[field]:.2f}',ha='center',fontsize=10)
    axs[0].set_ylim(0,6.8);axs[0].set_title('同速率能量：组合约降低 1.21%',loc='left')
    axs[1].set_ylim(0,58);axs[1].axhline(50,color=ORANGE,ls='--',lw=1);axs[1].text(-.38,51.2,'50 ps 门槛',color=ORANGE,fontsize=9);axs[1].set_title('原版未过；组合只剩约 1.49 ps',loc='left')
    fig.savefig(ASSET/'vcsel-causal-bars.png',dpi=140,pil_kwargs={'optimize':True});plt.close(fig)
    sources=[Path(__file__).resolve(),Path(analysis.__file__).resolve(),analysis.OPTO_PATH,EV/'vcsel-causal-comparison.json']
    for folder in [BASE,NEW]:sources += [folder/'manifest.json',folder/'result.json']
    out=dict(scope='Figures use native transistor waveforms on the same absolute UI coordinate, then the unchanged optical proxy and5GHz receive filter. Plot interpolation only; no waveform time rescaling, phase alignment, new simulation or receiver scoring.',
        windows=dict(net_Gbps=6.4,validation_line_bit_range=[576,584],samples_per_UI=128),
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sources},
        figures={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in [ASSET/'vcsel-waveforms.png',ASSET/'vcsel-causal-bars.png']})
    (EV/'vcsel-plots.json').write_text(json.dumps(out,indent=2)+'\n')
    print(out['figures'])

if __name__=='__main__':main()
