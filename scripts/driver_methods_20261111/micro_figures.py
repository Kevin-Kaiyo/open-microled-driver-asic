#!/usr/bin/env python3
"""Source-backed same-rate waveforms and positive port-energy comparison."""
from pathlib import Path
import csv
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'evidence/driver-methods-20261111'
OUT=ROOT/'docs/research/driver-methods-20261111/assets'
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['PingFang SC','Heiti SC','DejaVu Sans'],'axes.unicode_minus':False,'svg.fonttype':'path','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
COLORS={'A_before':'#8a919b','A_RCFF':'#167b83','B_before':'#8a919b','B_VIN_only':'#bc743a','B_VIN_Rdummy':'#167b83'}
LABELS={'A_before':'A：原版','A_RCFF':'A：阻尼前馈','B_before':'B：VIN 5 V / 50 kΩ','B_VIN_only':'B：VIN 3.3 V / 50 kΩ','B_VIN_Rdummy':'B：VIN 3.3 V / 27.6 kΩ'}

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=list(csv.DictReader((DATA/'micro-edge-extract.csv').open()))
    def curve(label,transition):return [x for x in rows if x['label']==label and x['transition']==transition]
    def draw(ax,label,transition,field,text=None,style='-'):
        rs=curve(label,transition);ax.plot([float(x['time_ps']) for x in rs],[float(x[field]) for x in rs],style,color=COLORS[label],lw=1.7,label=text or LABELS[label])
    for route,labels,node in [('A',['A_before','A_RCFF'],'out_V'),('B',['B_before','B_VIN_only','B_VIN_Rdummy'],'vx_V')]:
        fig,ax=plt.subplots(2,2,figsize=(12,7.2),sharex=True)
        for j,(transition,title) in enumerate([('0->1','0→1：亮电平上升'),('1->0','1→0：亮电平下降')]):
            for label in labels:
                draw(ax[0,j],label,transition,'current_uA');draw(ax[1,j],label,transition,node)
            ax[0,j].set_title(title,loc='left');ax[0,j].axhline(25,color='#ced3d8',lw=.7,ls=':');ax[0,j].axhline(100,color='#ced3d8',lw=.7,ls=':')
            ax[0,j].set_ylabel('LED 导通电流 / µA');ax[1,j].set_ylabel(('OUT 阴极电压' if route=='A' else 'VX 尾电流节点')+' / V');ax[1,j].set_xlabel('相对数据边沿 / ps')
            for a in ax[:,j]:a.axvline(0,color='#c9ced5',lw=.8);a.grid(alpha=.12);a.set_xlim(-150,1700)
        fig.legend(*ax[0,0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.55,.855),ncol=len(labels),fontsize=9,frameon=False)
        fig.suptitle(('A：提前提供结电容电荷，同时降低过冲' if route=='A' else 'B：降压节能需要同时维持虚支路顺应电压')+'\n净 1.6 Gb/s；同一 200 fF / 200 ps MicroLED 与 1 GHz RX',fontsize=14,x=.06,ha='left')
        fig.text(.06,.025,'图示为连续四个相同比特后的代表边沿；接收判据使用完整原生波形。新原理图仿真，未进行新布局/PEX。',fontsize=9,color='#56606e')
        fig.tight_layout(rect=[.03,.06,1,.91]);
        for ext in ['png','svg']:fig.savefig(OUT/f'micro-{route.lower()}-waveforms.{ext}',dpi=170)
        plt.close(fig)
    # A internal nodes clarify that FF is driven from the earlier complementary node.
    fig,ax=plt.subplots(1,2,figsize=(12,4.0),sharex=True,sharey=True)
    palette={'n1_V':'#8a919b','ff_V':'#167b83','ctrl_V':'#bc743a','out_V':'#24466b'}
    for j,tr in enumerate(['0->1','1->0']):
        rs=curve('A_RCFF',tr);t=[float(x['time_ps']) for x in rs]
        for f,label in [('n1_V','N1：反相信号'),('ff_V','FF：串联电阻后'),('ctrl_V','CTRL：主输出控制'),('out_V','OUT：LED 阴极')]:ax[j].plot(t,[float(x[f]) for x in rs],color=palette[f],label=label,lw=1.6)
        ax[j].set_xlim(-100,700);ax[j].set_title(tr.replace('->','→'),loc='left');ax[j].set_xlabel('相对数据边沿 / ps');ax[j].grid(alpha=.12)
    ax[0].set_ylabel('节点电压 / V');fig.legend(*ax[1].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.54,.88),ncol=4,fontsize=8.5,frameon=False)
    fig.suptitle('A 前馈电荷的来源：N1 → 约 1 kΩ PDK 电阻 → FF → 31.275 fF → OUT',fontsize=13)
    fig.tight_layout(rect=[0,0,1,.90])
    for ext in ['png','svg']:fig.savefig(OUT/f'micro-a-ff-nodes.{ext}',dpi=170)
    plt.close(fig)
    summary=json.loads((DATA/'micro-summary.json').read_text())['records']
    names=['a-rin1wide-core03-matched','A_rcff31p275','B_wide_ff31p275','B_vin3p3_dummy50k_control','B_vin3p3_dummy27p6k']
    data=[next(x for x in summary if x['candidate']==name and x['kind']=='transient' and x['case']['net_rate_Gbps']==1.6 and x['case']['steps_per_symbol']==40) for name in names]
    fig,ax=plt.subplots(figsize=(11.3,4.5));x=np.arange(5);bottom=np.zeros(5)
    for port,color in [('VIN','#355c7d'),('VDD','#167b83'),('VREF','#8cadad'),('VLED','#bd854e'),('VD0','#a6aeb8')]:
        values=np.array([r['port_energy_pJ'][port]['positive'] for r in data]);ax.bar(x,values,bottom=bottom,color=color,label=port,width=.64);bottom+=values
    for i,total in enumerate(bottom):ax.text(i,total+.018,f'{total:.3f}',ha='center',fontsize=10)
    ax.set_xticks(x,['A 原版','A 阻尼前馈','B VIN5V/50k','B VIN3.3V/50k','B VIN3.3V/27.6k']);ax.set_ylabel('E+（pJ / 尝试净载荷 bit）');ax.set_ylim(0,1.4);ax.legend(ncol=5,frameon=False,loc='upper right');ax.grid(axis='y',alpha=.15)
    ax.set_title('同净 1.6 Gb/s 的供能源头：B 的主要节能来自 VIN',loc='left',fontsize=14)
    fig.text(.07,.03,'分母为4096个尝试净载荷bit；七个源端计量、回流单列。未含上游转换器、RX及主机/时钟；VLED=5V、VDD=3.3V不变。',fontsize=9,color='#56606e')
    fig.tight_layout(rect=[0,.07,1,1])
    for ext in ['png','svg']:fig.savefig(OUT/f'micro-energy-by-source.{ext}',dpi=170)
    plt.close(fig)
    receipt=dict(script_sha256=sha(Path(__file__)),inputs={p.name:sha(p) for p in [DATA/'micro-summary.json',DATA/'micro-edge-extract.csv',DATA/'micro-causal.json']},outputs={p.name:sha(p) for p in OUT.glob('micro-*')})
    (DATA/'micro-figures-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
