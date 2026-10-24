#!/usr/bin/env python3
"""Figures computed from declared, inspectable simulation rows; no invented points."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/driver-robustness-20261024/figures'
F=ROOT/'build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf'
font_manager.fontManager.addfont(str(F))
plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(F)).get_name(),'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'font.size':11})
COLORS={'A':'#377893','B':'#1c8479'}
ENERGY='rail_plus_DATA_positive_draw_fJ_per_gross_bit'

def save(fig,name):
    OUT.mkdir(parents=True,exist_ok=True)
    for ext in ['svg','png']:fig.savefig(OUT/f'{name}.{ext}',dpi=160,bbox_inches='tight')
    plt.close(fig)

def voltage_budget(rows):
    previous=ROOT/'evidence/highspeed-nrz-pvt/summary.json'
    old=json.loads(previous.read_text())['rows']
    reused=[r|{'kind':'FF','reused_from':'evidence/highspeed-nrz-pvt/summary.json'} for r in old if r.get('variant')=='AFTER' and r['kind']=='fast_cold' and r['rate_Gbps']==(1 if r['route']=='A' else .5)]
    rows=list(rows)+reused
    fig,ax=plt.subplots(figsize=(10.8,5.7))
    for route in 'AB':
        rr=sorted([r for r in rows if r['route']==route and r.get('analysis_ok') and r['corner']=='ff' and r['temp_C']==-40 and r.get('kind') in ['FF','FFplus50_tracking','FFvdd_-0.05','FFvdd_-0.025','FFvdd_0.025']],key=lambda r:r['vdd_V'])
        if not rr:continue
        ax.plot([r['vdd_V'] for r in rr],[(3.63-r['max_abs_terminal_V'])*1000 for r in rr],marker='o',color=COLORS[route],label=f"{route} / {rr[0]['rate_Gbps']:g} Gb/s")
        for r in rr:
            y=(3.63-r['max_abs_terminal_V'])*1000
            if r['vdd_V'] in [3.6,3.65]:ax.annotate(f'{y:+.2f}',(r['vdd_V'],y),xytext=(6,10 if route=='A' else -17),textcoords='offset points',fontsize=10,color=COLORS[route])
    ax.axhline(0,color='#ab563d',ls='--',label='3.63 V 项目筛查：余量 = 0')
    ax.set_xlabel('理想逻辑电源 / V（DATA高电平同步改变）');ax.set_ylabel('3.63 V − 最大 MOS 端差 / mV')
    ax.set_title('旧薄栅氧核心：仅增加供电就会耗尽 9–11 mV 余量',loc='left',pad=18)
    ax.grid(axis='y',alpha=.15);ax.legend(loc='lower left');fig.tight_layout()
    fig.text(.07,-.02,'FF / −40°C；原真实RC。3.600 V点引用10月23日原证据，其余为本轮。线不代表已验证连续区间。各路线用原目标速率。',fontsize=10,color='#566d77')
    save(fig,'nrz-voltage-budget')

def matrix_chart(rows,name,title):
    rr=[r for r in rows if r.get('analysis_ok') and 'dc_bit' not in r and r.get('kind') in ['TT','SS','FF','SSminus50','FFplus50','FFplus50_tracking','FFvdd_0.025']]
    if not rr:return
    fig,axs=plt.subplots(1,3,figsize=(14,5.5))
    labels=[f"{r['route']} {r['kind']}\n{r['rate_Gbps']:g}G" for r in rr]
    for ax,key,scale,label,line in [(axs[0],'threshold_margin_normalized',1,'接收垂直余量',.1),(axs[1],'minimum_device_specific_margin_V',1000,'按实际器件筛查的最小余量 / mV',0),(axs[2],ENERGY,1/1000,'正向取能 / pJ / gross bit',None)]:
        vals=[r.get(key,3.63-r['max_abs_terminal_V'])*scale for r in rr]
        ax.bar(range(len(rr)),vals,color=[COLORS[r['route']] for r in rr]);ax.set_xticks(range(len(rr)),labels,rotation=70,ha='right',fontsize=8);ax.set_ylabel(label)
        if line is not None:ax.axhline(line,color='#ab563d',ls='--',lw=1)
        ax.grid(axis='y',alpha=.15)
    fig.suptitle(title,x=.06,ha='left');fig.tight_layout();save(fig,name)


def package_waveform():
    import numpy as np
    p=ROOT/'evidence/highspeed-nrz-robustness/baseline-A-supply-return-window.csv'
    meta=json.loads(p.with_suffix('.json').read_text());data=np.genfromtxt(p,delimiter=',',names=True)
    x=(data['time_s']-meta['center_time_s'])*1e9
    fig,axs=plt.subplots(3,1,figsize=(11.4,9.0),sharex=True)
    axs[0].plot(x,data['source_VDD_V'],color='#555',ls='--',label='板端理想VDD')
    axs[0].plot(x,data['die_VDD_V'],color=COLORS['A'],label='芯片端VDD')
    axs[0].set_ylabel('供电电位 / V');axs[0].legend(ncol=2,loc='upper right')
    axs[1].plot(x,data['die_VSS_V']*1000,color='#a65a40',label='芯片VSS相对板级地')
    axs[1].axhline(0,color='#999',lw=.7);axs[1].set_ylabel('回地扰动 / mV');axs[1].legend(loc='upper right')
    axs[2].plot(x,np.abs(data['worst_VDS_V']),color='#a65a40',label='第二级PMOS局部 |VDS|')
    axs[2].plot(x,data['worst_max_abs_gate_pair_V'],color=COLORS['B'],label='同一PMOS最大栅极端差')
    axs[2].axhline(3.63,color='#444',ls='--',lw=1,label='3.63 V旧筛查线');axs[2].set_ylabel('局部端差 / V')
    axs[2].set_xlabel('相对最大|VDS|时刻 / ns');axs[2].legend(loc='lower right');axs[2].set_ylim(3.2,3.8)
    for ax in axs:ax.set_xlim(-.10,.12);ax.grid(alpha=.15);ax.axvline(0,color='#bbb',lw=.8)
    axs[0].set_title('外部仍为3.600 V，封装供电与回地阻抗也会耗尽余量',loc='left',pad=17)
    fig.text(.09,.015,'旧A / FF / −40°C / 1 Gb/s；VDD与VSS各1 Ω、2 nH（假设）。局部VSS没有强制等同板级地。\n截取最大|VDS|附近0.22 ns；全局最大栅极端差发生在其他器件/时刻。原CSV保留±2 ns及数据来源。',fontsize=10,color='#566d77')
    fig.tight_layout(rect=(0,.07,1,1));save(fig,'nrz-package-return')

def common_energy(rows):
    import numpy as np
    keys={'A':['TT_rate04','SSminus50_rate04','FFplus50_rate04'],'B':['TT_common04','SSminus50_common04','FFplus50_common04']}
    labels=['TT / 27°C / 3.3 V','SS / 125°C / 2.95 V','FF / -40°C / 3.65 V']
    fig,axs=plt.subplots(1,2,figsize=(12.8,5.8))
    for i,route in enumerate('AB'):
        rr=[next(r for r in rows if r['route']==route and r['kind']==k and r['rate_Gbps']==.4) for k in keys[route]]
        assert all(r['combined_screen_passed'] for r in rr)
        x=np.arange(3)+(i-.5)*.33
        for ax,key,scale in [(axs[0],ENERGY,.001),(axs[1],'timing_min_margin_ui',1)]:
            bars=ax.bar(x,[r[key]*scale for r in rr],width=.30,color=COLORS[route],label=route)
            ax.bar_label(bars,fmt='%.3f',padding=4,fontsize=10)
    axs[0].set_ylabel('全部电源＋DATA正向取能 / pJ / gross bit');axs[0].set_ylim(0,2.12)
    axs[1].set_ylabel('最小水平余量 / UI');axs[1].set_ylim(0,.35);axs[1].axhline(.1,color='#a65a40',ls='--',label='0.1 UI门槛')
    for ax in axs:
        ax.set_xticks(range(3),labels,rotation=10,fontsize=10);ax.grid(axis='y',alpha=.15);ax.legend(loc='upper left',ncol=3,fontsize=10)
    fig.suptitle('相同0.4 Gb/s、负载和接收器：取能较低与时序余量较大，是不同目标',x=.07,ha='left',fontsize=15)
    fig.text(.07,.015,'仅对应固定辅助电源的六个通过点；A在其他辅助供电扰动点仍失败。电流并非完全相同，未测光功率；未计实际电源生成和接收器损耗。',fontsize=10,color='#566d77')
    fig.tight_layout(rect=(0,.06,1,.95));save(fig,'nrz-common-energy')

def matched_package_window():
    import numpy as np
    fig,axs=plt.subplots(3,1,figsize=(11.4,8.8),sharex=True)
    for stem,label,color in [('baseline-A-supply-return-window-global','旧A：03v3','#a65a40'),('final-A-supply-return-window-matched','新A：06v0 + RIN8',COLORS['A'])]:
        path=ROOT/'evidence/highspeed-nrz-robustness'/stem
        meta=json.loads(path.with_suffix('.json').read_text());a=np.genfromtxt(path.with_suffix('.csv'),delimiter=',',names=True)
        x=(a['time_s']-meta['center_time_s'])*1e9
        for ax,key,scale in [(axs[0],'die_VDD_minus_VSS_V',1),(axs[1],'die_VSS_V',1000),(axs[2],'all_MOS_max_abs_gate_pair_V',1)]:
            ax.plot(x,a[key]*scale,label=label,color=color)
    axs[0].set_ylabel('芯片VDD - VSS / V');axs[1].set_ylabel('芯片地相对板地 / mV');axs[2].set_ylabel('全MOS最大栅极端差 / V')
    axs[2].axhline(3.63,color='#555',ls='--',lw=1,label='旧03v3筛查线3.63 V')
    axs[2].set_ylim(3.2,3.8);axs[2].set_xlabel('相对旧版最大|VDS|时刻 / ns（两图同绝对时间）')
    for ax in axs:ax.set_xlim(-.1,.12);ax.grid(alpha=.15);ax.legend(loc='upper right',fontsize=9,ncol=2)
    axs[0].set_title('同3.600 V / FF / -40°C / 1 Gb/s：电路与版图修订后的供电波形',loc='left',pad=18)
    fig.text(.09,.015,'VDD与VSS各1 ohm / 2 nH；同一LED、码型与RX。该窗口对应旧版149.040736 ns事件，不保证包含新版全局最坏峰。\n新A全部MOS采用6.0 V项目筛查，3.63 V线仅作旧器件比较。全时域峰值、余量与失败条件见正文。',fontsize=10,color='#566d77')
    fig.tight_layout(rect=(0,.07,1,1));save(fig,'nrz-package-before-after')

if __name__=='__main__':
    p=ROOT/'evidence/highspeed-nrz-robustness/baseline-r1-summary.json'
    voltage_budget(json.loads(p.read_text())['rows'])
    package_waveform()

    cfg=json.loads((OUT.parent/'report-config.json').read_text())
    summary=json.loads((ROOT/cfg['final_summary']).read_text());common_energy(summary.get('selected',summary)['rows'])

    matched_package_window()
