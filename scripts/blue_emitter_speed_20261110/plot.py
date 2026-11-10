#!/usr/bin/env python3
"""Plot only native-simulation points; connectors are not inferred maxima."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'evidence/blue-emitter-speed-review-20261110'
DOC=ROOT/'docs/research/blue-emitter-speed-review-20261110/assets'
COLORS={'A':'#215b83','B':'#25796f','C':'#a16c33','r10-NRZ':'#695484'}
def records(data,family,route):
    return sorted([r for r in data['rows'] if r['family']==family and r['route']==route and r['steps_per_symbol']==40 and abs(r['capacitance_fF']-(200 if family=='MicroLED' else 150))<1e-6], key=lambda r:r['net_Gbps'])
def finish(ax,rates):
    ax.set_xscale('log',base=2);ax.set_xticks(rates,labels=[f'{v:g}' for v in rates]);ax.set_xlabel('Offered net rate (Gb/s)');ax.grid(alpha=.16)
def main():
    data=json.loads((EV/'speed-sweep-all.json').read_text());DOC.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axs=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for route in 'ABC':
        rows=records(data,'MicroLED',route);rate=[r['net_Gbps'] for r in rows]
        for ax,key in zip(axs,['worst_signed_margin_uAeq','one_sided_margin_bit_UI']):
            ax.plot(rate,[r['full_receiver'][key] for r in rows],'o-',label=route,color=COLORS[route])
    axs[0].axhline(7.5,ls='--',c='.45',lw=1,label='Research screen: 7.5 µAeq');axs[0].set_ylabel('Worst signed amplitude margin (µAeq)');axs[0].set_title('MicroLED | fixed 200 fF / 200 ps / 1 GHz RX')
    axs[1].axhline(.37,ls='--',c='.45',lw=1,label='Research screen: 0.37 bit UI');axs[1].set_ylabel('Worst one-sided margin / line-bit UI');axs[1].set_title('Same absolute timing allowance for A/B/C')
    for ax in axs:finish(ax,[.2,.4,.8,1.6,3.2]);ax.legend(fontsize=8)
    fig.savefig(DOC/'microled-rate.png',dpi=180);plt.close(fig)
    rows=records(data,'VCSEL','r10-NRZ');fig,ax=plt.subplots(figsize=(9,4.3),layout='constrained')
    for key,label,color,style in [('pin','Predriver input polarity','#4485a5','o-'),('gate','Steering-gate polarity','#a16c33','s-'),('electrical','VCSEL conduction current','#25796f','^-'),('full','Original optical model + 5 GHz RX','#695484','D-')]:
        ys=[]
        for r in rows:
            y=(r['stages']['predriver_input_polarity']['errors'] if key=='pin' else r['stages']['steering_gate_polarity']['errors'] if key=='gate' else r['electrical_only']['errors'] if key=='electrical' else r['full_receiver']['errors']);ys.append(y)
        ax.plot([r['net_Gbps'] for r in rows],ys,style,color=color,label=label,markersize=5)
    ax.set_ylabel('Errors / 4096 validation bits');ax.set_title('850 nm r10 | where errors first appear in the path');finish(ax,[r['net_Gbps'] for r in rows]);ax.legend(fontsize=9)
    fig.savefig(DOC/'vcsel-rate.png',dpi=180);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(11,4.2),layout='constrained')
    for ax,family in zip(axs,['MicroLED','VCSEL']):
        for route in ('ABC' if family=='MicroLED' else ['r10-NRZ']):
            rows=records(data,family,route);rate=[r['net_Gbps'] for r in rows];energy=[r['energy_pJ_per_attempted_payload_bit']['positive'] for r in rows]
            ax.plot(rate,energy,'-',color=COLORS[route],label=route)
            for r,y in zip(rows,energy):ax.scatter(r['net_Gbps'],y,marker='o' if r['combined_research_screen_pass'] else 'x',color=COLORS[route],s=45,zorder=3)
        ax.set_yscale('log');ax.set_ylabel('pJ / attempted payload bit (positive source energy)');ax.set_title(f'{family} | circle: screened pass, ×: failed')
        finish(ax,[.2,.4,.8,1.6,3.2] if family=='MicroLED' else [r['net_Gbps'] for r in records(data,'VCSEL','r10-NRZ')]);ax.legend(fontsize=8)
    fig.savefig(DOC/'energy-rate.png',dpi=180);plt.close(fig)
    rows=sorted([r for r in data['rows'] if r['family']=='MicroLED' and r['route']=='B' and r['net_Gbps']==3.2 and r['steps_per_symbol']==40],key=lambda r:r['capacitance_fF'])
    fig,axs=plt.subplots(1,2,figsize=(11,3.9),layout='constrained');ax=axs[0]
    ax.plot([r['capacitance_fF'] for r in rows],[r['full_receiver']['errors'] for r in rows],'o-',color=COLORS['B']);ax.set_xscale('symlog',linthresh=10);ax.set_xticks([0,10,50,200,800],labels=['0','10','50','200','800']);ax.set_xlabel('Hypothetical parallel junction capacitance (fF)');ax.set_ylabel('Errors / 4096 validation bits');ax.set_title('B at 3.2 Gb/s net | original optics and RX');ax.grid(alpha=.16)
    low=sorted([r for r in data['rows'] if r['family']=='MicroLED' and r['route']=='B' and r['net_Gbps']==.4 and r['steps_per_symbol']==40],key=lambda r:r['capacitance_fF']);ax=axs[1]
    for r in low:
        ax.scatter(r['capacitance_fF'],r['full_receiver']['one_sided_margin_bit_UI'],s=65,marker='o' if r['combined_research_screen_pass'] else 'x',color=COLORS['B'])
        ax.annotate(f'{r["full_receiver"]["errors"]} errors',(r['capacitance_fF'],r['full_receiver']['one_sided_margin_bit_UI']),xytext=(8,8),textcoords='offset points',fontsize=9)
    ax.axhline(.37,ls='--',c='.45',lw=1);ax.set_xlim(0,1100);ax.set_ylim(-.02,.55);ax.set_xlabel('Hypothetical parallel junction capacitance (fF)');ax.set_ylabel('One-sided margin / line-bit UI');ax.set_title('B at 0.4 Gb/s net | two-point load control');ax.grid(alpha=.16)
    fig.savefig(DOC/'load-envelope.png',dpi=180);plt.close(fig)
if __name__=='__main__':main()
