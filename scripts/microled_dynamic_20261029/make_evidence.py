#!/usr/bin/env python3
"""Build original explanatory figures and contracts; never calibrate old models."""
from pathlib import Path
import csv, hashlib, json, math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch
import xml.etree.ElementTree as ET
from extract import ROOT, EV, BUILD, emit, sha

def text(x,y,s,size=18,colour='#243746',anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{colour}" text-anchor="{anchor}">{s}</text>'

def line(x1,y1,x2,y2,extra=''):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#243746" stroke-width="2.5" {extra}/>'

def render_own_svg(path,font):
    """Render this script's simple SVG primitives with explicit Noto glyph coverage."""
    tree=ET.fromstring(path.read_text());fig=plt.figure(figsize=(12.4,7.9),dpi=150)
    ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(0,1240),ylim=(790,0));ax.axis('off')
    for order,e in enumerate(tree):
        tag=e.tag.split('}')[-1];a=e.attrib
        if tag in ['defs','style']:continue
        def num(k,d=0):return float(a.get(k,d))
        if tag=='rect':ax.add_patch(Rectangle((num('x'),num('y')),num('width'),num('height'),facecolor=a.get('fill','none'),edgecolor=a.get('stroke','none'),linewidth=num('stroke-width')*.72,zorder=order))
        elif tag=='circle':ax.add_patch(Circle((num('cx'),num('cy')),num('r'),facecolor=a.get('fill','none'),edgecolor=a.get('stroke','none'),linewidth=num('stroke-width')*.72,zorder=order))
        elif tag=='line':
            x=[num('x1'),num('x2')];y=[num('y1'),num('y2')]
            if 'marker-end' in a:ax.add_patch(FancyArrowPatch((x[0],y[0]),(x[1],y[1]),arrowstyle='-|>',mutation_scale=15,linewidth=num('stroke-width')*.72,color='#0e7490',zorder=order))
            else:ax.plot(x,y,color=a.get('stroke','#243746'),linewidth=num('stroke-width')*.72,solid_capstyle='butt',zorder=order)
        elif tag=='text':ax.text(num('x'),num('y'),e.text or '',fontproperties=FontProperties(fname=str(font)),fontsize=num('font-size')*.72,color=a.get('fill','#243746'),ha={'middle':'center','end':'right'}.get(a.get('text-anchor'),'left'),va='baseline',zorder=order)
    fig.savefig(path.with_suffix('.png'),dpi=150);plt.close(fig)

def run():
    data=list(csv.DictReader((ROOT/'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv').open()))
    i=np.array([float(v['current_A']) for v in data]);v=np.array([float(v['voltage_V']) for v in data])
    rows=[]
    for bias in [25e-6,100e-6]:
        k=int(np.searchsorted(i,bias)-1);rd=float((v[k+1]-v[k])/(i[k+1]-i[k]));rs=50.;c=200e-15
        rp=1/(1/rs+1/rd)
        rows.append({'bias_uA':bias*1e6,'IV_bracket_A':i[k:k+2].tolist(),'IV_bracket_V':v[k:k+2].tolist(),
            'IV_source_excel_rows':[int(data[k]['source_excel_row']),int(data[k+1]['source_excel_row'])],
            'rd_Ohm':rd,'assumed_C_F':c,'illustrative_Rsource_Ohm':rs,
            'current_drive_tau_ps':rd*c*1e12,'voltage_drive_tau_ps':rp*c*1e12,
            'current_drive_f3dB_MHz':1/(2*math.pi*rd*c)/1e6,'voltage_drive_f3dB_GHz':1/(2*math.pi*rp*c)/1e9})
    emit(EV/'reference-plane-calculation.json',{'method':'Local slope of unchanged piecewise-linear static I-V; parallel RC illustrative small-signal circuit only',
        'static_iv_sha256':sha(ROOT/'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv'),
        'not_measured':['200 fF','50 ohm driver impedance','electrical pole frequencies','intrinsic recombination lifetime'],
        'not_claimed':'50 ohm is neither measured A-route output impedance nor a calibration of the Lin VNA fixture.', 'points':rows})
    font=ROOT/'build/fair-driver-v1/report-font/NotoSansCJKsc-Regular.otf'
    matplotlib.font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=FontProperties(fname=font).get_name()
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    f=np.geomspace(1e6,1e11,1200)
    fig,ax=plt.subplots(1,2,figsize=(12,4.7),constrained_layout=True)
    for r,col in zip(rows,['#0e7490','#924b6a']):
        for j,key in enumerate(['current_drive_tau_ps','voltage_drive_tau_ps']):
            h=1/(1+2j*np.pi*f*r[key]*1e-12)
            ax[j].semilogx(f/1e9,20*np.log10(abs(h)),label=f"{r['bias_uA']:g} µA: rd={r['rd_Ohm']/1000:.3f} kΩ",color=col)
    for a,title in zip(ax,['理想电流输入：τ = rd C','电压源 + 50 Ω 示例：τ = (Rs ∥ rd) C']):
        a.axhline(-3,color='gray',ls='--',lw=.8);a.axvline(1.85,color='gray',ls=':',lw=.8)
        a.set(title=title,xlabel='Frequency / GHz',ylabel='Normalized conductive-current response / dB',ylim=(-45,1));a.grid(alpha=.17);a.legend(fontsize=9)
    fig.suptitle('同一静态 I–V、同一假设 200 fF，不同激励参考面：原创 RC 计算（非测量）',fontsize=12)
    fig.savefig(EV/'reference-plane-response.png',dpi=160);fig.savefig(EV/'reference-plane-response.svg');plt.close(fig)
    # Faithful source-cell extract. Values are verbatim; rendering is new, not a screen capture.
    cells=json.loads((EV/'source-cell-extract.json').read_text())
    selected=[x for x in cells['Bandwidths'][1:] if float(x['cells']['A']) in [25e-6,50e-6,100e-6]]
    table=[['Excel row']+list(cells['Bandwidths'][0]['cells'].values())]+[[str(x['row'])]+list(x['cells'].values()) for x in selected]
    fig,ax=plt.subplots(figsize=(13,3.3),constrained_layout=True);ax.axis('off')
    t=ax.table(cellText=table[1:],colLabels=table[0],loc='center',cellLoc='left',colWidths=[.08,.13,.26,.26,.27]);t.auto_set_font_size(False);t.set_fontsize(9.5);t.scale(1,2)
    for (rr,cc),cell in t.get_celld().items():
        cell.set_edgecolor('#cbd5df')
        if rr==0:cell.set_facecolor('#e9f2f3')
    ax.set_title('源表忠实摘录（非 Excel 截屏）｜yellow20_s21_bandwidths.xlsx / Bandwidths',fontsize=12)
    fig.text(.03,.09,'Shifted_Curves: B1 = 2.5e-05A；E1 = 5e-05A；H1 = 0.0001A；A1 = frequency_MHz',fontsize=10)
    fig.text(.03,.02,'单位核对：2.5e-05 A = 0.025 mA = 25 µA；0.0001 A = 0.1 mA = 100 µA。作者数据，独立排版。',fontsize=10)
    fig.savefig(EV/'source-cell-extract.png',dpi=160);plt.close(fig)
    s=['<svg xmlns="http://www.w3.org/2000/svg" width="1240" height="790" viewBox="0 0 1240 790">',
       '<rect width="1240" height="790" fill="#fcfcfa"/>',
       '<style>text{font-family:"Noto Sans CJK SC","PingFang SC",sans-serif}</style>',
       '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#0e7490"/></marker></defs>',
       text(35,42,'为什么同一个 LED，电流驱动与电压驱动的 RC 时间常数不同？',26),
       text(35,73,'小信号等效原理图；rd 取自现有静态 I–V。C = 200 fF 与 Rs = 50 Ω 都只是说明用假设。',17,'#62717d')]
    for off,title in [(25,'① 理想电流输入'),(645,'② 电压源经过输出电阻')]:
        s += [f'<rect x="{off}" y="100" width="570" height="350" rx="12" fill="#f1f6f7"/>',text(off+20,133,title,21)]
        # top and bottom branch nodes, resistor and capacitor conventional symbols
        x0=off+80;xr=off+290;xc=off+430;yt=185;yb=350
        s += [line(x0,yt,xc,yt),line(x0,yb,xc,yb),line(xr,yt,xr,225),
              f'<rect x="{xr-12}" y="225" width="24" height="70" fill="none" stroke="#243746" stroke-width="2.5"/>',
              line(xr,295,xr,yb),text(xr+25,265,'rd',20),line(xc,yt,xc,250),line(xc-24,250,xc+24,250),line(xc-24,270,xc+24,270),line(xc,270,xc,yb),text(xc+30,265,'C',20),
              line(xr,yb,xr,365),line(xr-20,365,xr+20,365),line(xr-13,373,xr+13,373),line(xr-6,381,xr+6,381),
              f'<circle cx="{x0}" cy="270" r="30" fill="#fcfcfa" stroke="#243746" stroke-width="2.5"/>',line(x0,yt,x0,240),line(x0,300,x0,yb),
              text(xr+13,173,'vLED',17),f'<circle cx="{xr}" cy="{yt}" r="4" fill="#243746"/>',f'<circle cx="{xr}" cy="{yb}" r="4" fill="#243746"/>']
        if off==25:
            s += [line(x0,285,x0,255,'marker-end="url(#arrow)"'),text(x0-48,315,'iIN',17),text(off+20,416,'i导电 / iIN = 1 / (1 + s rd C)',19)]
        else:
            # replace the top source-to-node wire with a gap and resistor.
            s += [f'<rect x="{x0+35}" y="178" width="120" height="14" fill="#f1f6f7"/>',line(x0+35,185,x0+55,185),
                f'<rect x="{x0+55}" y="173" width="65" height="24" fill="#f1f6f7" stroke="#243746" stroke-width="2.5"/>',line(x0+120,185,x0+155,185),text(x0+85,160,'Rs',17,anchor='middle'),
                text(x0,262,'+',20,anchor='middle'),text(x0,290,'−',20,anchor='middle'),text(x0-48,315,'vIN',17),text(off+20,416,'H归一化 = 1 / [1 + s (Rs ∥ rd) C]',19)]
    s += [text(40,492,'同一条件下的计算结果（电容充放电极点；不含载流子复合、光学或接收器）',20)]
    for n,r in enumerate(rows):
        y=530+n*40
        s += [text(40,y,f"{r['bias_uA']:g} µA：rd = {r['rd_Ohm']/1000:.3f} kΩ",18),
            text(385,y,f"τI = {r['current_drive_tau_ps']:.1f} ps",18,'#0e7490'),
            text(650,y,f"τV = {r['voltage_drive_tau_ps']:.2f} ps",18,'#924b6a'),
            text(930,y,f"50 Ω ≪ rd",18)]
    s += [line(35,597,1205,597),text(40,630,'文献 S21 的实际测量跨度',21),
       text(40,668,'VNA → bias tee → LED 电学端口 → 电光转换 → 光纤 → SPD-4 检测器 → VNA',19,'#0e7490'),
       text(40,705,'要改成晶体管仿真模型，必须知道参考面及测量链响应；整条 S21 不能再叠加已有 LED RC / RX 极点。',17),
       text(40,746,'50 Ω 并非 A 路线的实测输出阻抗，也不意味着该示例已复现文献测试夹具。',17,'#62717d'),'</svg>']
    (EV/'reference-planes.svg').write_text('\n'.join(s))
    render_own_svg(EV/'reference-planes.svg',font)
    contract={
      'status':'evidence-frozen; no new transient model activated',
      'baseline_policy':'Keep old 200fF/200ps/RX1GHz baseline and A/B/C results unchanged; any candidate gets a new model ID and coupled regression.',
      'observed_response':{'file':'yellow20-s21-selected.csv','quantity':'author-normalized measured-chain S21 magnitude in dB','frequency_Hz':[30e6,3e9],'bias_uA':[25,50,60,80,100],'phase':None,'normalization':'observed 0dB at30MHz; independently measured DC normalization unavailable','same_individual_pixel_as_IV':'not established'},
      'admissible_now':['reproduce source magnitude/cutoff plots','test magnitude-only sensitivity in a separately labelled frequency-domain chain','check whether a proposed model reproduces source conditions; never infer unmeasured phase'],
      'not_admissible':['replace device lifetime by 1/(2pi*source cutoff)','apply full S21 after already simulated electrical RC and receiver','claim source GHz implies 3.2Gb/s net BER or energy','port blue/violet/different-size capacitance into yellow20 model'],
      'measurement_contract':[
        {'layer':'identity/static','required':'unique pixel/sample ID, geometry, epi/contact/package revision, I-V and P-I with uncertainty, J and junction/ambient temperature, repeatability'},
        {'layer':'electrical','required':'complex S11 or impedance vs bias/frequency/T at a calibrated device plane; OPEN/SHORT/LOAD/deembedding or equivalent calibration; RF voltage and current; small-signal amplitude'},
        {'layer':'electro-optic','required':'complex S21 (magnitude+phase) and noise floor/dark/background; absolute gain if optical energy is needed; calibrated PD/TIA and fiber response; confirm linearity at 25uA'},
        {'layer':'joint fit','required':'fit electrical and optical response together; hold out bias/T points; preserve passivity/causality and confidence/correlation; choose either full measured chain or separately deembedded blocks'},
        {'layer':'large signal/link','required':'large-signal P-I/dynamics and pattern-dependent response; optical loss, RX noise/bandwidth, jitter and temperature; fixed payload/frame overhead; BER qualification separately'}],
      'candidate_implementation':'Bias-indexed Z_LED(s,I,T) fitted to complex electrical data plus residual H_EO(s,I,T) fitted after removing calibrated electrical/receiver blocks; static nonlinear I-V/P-I and charge/lifetime state must be mutually consistent. Validate small-signal first, then 25–100uA transitions. No coefficients assigned until evidence exists.',
      'non_identifiability_counterexample':'H(s) and H(s)*exp(-s*100ps) have identical magnitude but different sampling delay; code verifies this algebraically.',
      'boundary':'temperature and physical-sample covariance remain unknown; not silicon/optical validation of this project'}
    emit(EV/'response-contract.json',contract)
    print(json.dumps({'reference_plane_points':rows,'original_figures_written':4},ensure_ascii=False,indent=2))

if __name__=='__main__':run()
