"""Actual GDS projections: historical19MOS versus selected joint test macro."""
from pathlib import Path
import argparse
import hashlib
import json
import klayout.db as k
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Rectangle
from render import STYLES
from visual_style import configure,text_bounds,file_record

ROOT=Path(__file__).resolve().parents[2]

def draw(ax,folder):
    c=json.loads((folder/'physical-contract.json').read_text())
    gds=folder/'generate'/(c['top']+'.gds')
    digest=hashlib.sha256(gds.read_bytes()).hexdigest();assert digest==c['gds_sha256']
    lay=k.Layout();lay.read(str(gds));top=lay.cell(c['top'])
    count=0
    for layer,(name,color,opacity) in STYLES.items():
        for p in k.Region(top.begin_shapes_rec(lay.layer(layer,0))).each():
            points=[(q.x*lay.dbu,q.y*lay.dbu) for q in p.each_point_hull()]
            assert not p.holes()
            ax.add_patch(Polygon(points,facecolor=color,edgecolor=color,lw=.1,alpha=opacity));count+=1
    b=c['bbox_um'];ax.set_aspect('equal');ax.set_xlim(b[0]-20,b[2]+20);ax.set_ylim(b[1]-20,b[3]+35)
    ax.set_xlabel('x (µm)');ax.set_ylabel('y (µm)');ax.spines[['top','right']].set_visible(False)
    ax.tick_params(labelsize=8)
    return c,dict(gds=str(gds.relative_to(ROOT)),sha256=digest,drawn_polygon_count=count,bbox_um=b)

def label(ax,text,point,xytext,color='#273f52'):
    ax.annotate(text,xy=point,xytext=xytext,fontsize=9,color=color,
                arrowprops=dict(arrowstyle='-',color=color,lw=.7),
                bbox=dict(boxstyle='round,pad=.2',facecolor='#fafbf8',edgecolor='none',alpha=.94))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--module',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    font=configure()
    fig,axes=plt.subplots(1,2,figsize=(16,8),gridspec_kw={'width_ratios':[1,1.2]},facecolor='#fafbf8')
    old,oldmeta=draw(axes[0],ROOT/'build/reference-v2-layout/nrz-r1/N')
    c,meta=draw(axes[1],ROOT/a.module)
    axes[0].set_title('历史参考源 + LDO | 19 MOS\n电路不同；此 LDO 候选未通过电气验证',fontsize=12,pad=12)
    axes[0].text(.02,.02,f"{old['width_um']:.2f} × {old['height_um']:.2f} µm\n{old['area_um2']/1e6:.6f} mm² 模块外框面积",transform=axes[0].transAxes,fontsize=9,bbox=dict(facecolor='#fafbf8',edgecolor='none'))
    axes[1].set_title(f"实际联通 VI + B 核心 | {len(c['devices'])} MOS + RIN\nVIN 与逻辑 VDD 保持独立",fontsize=12,pad=12)
    anchors=c['port_anchor_um'];ax=axes[1]
    label(ax,'VIN 5 V',anchors['VIN'],(75,118),'#1d7390')
    label(ax,'VSS',anchors['VSS'],(91,91),'#52655a')
    label(ax,'VSET 基准输入',anchors['VSET'],(145,49),'#6c4d83')
    label(ax,'IOUT → BIAS',anchors['BIAS'],(240,86),'#9f405f')
    label(ax,'逻辑 VDD',anchors['VDD'],(-3,-15),'#1d7390')
    label(ax,'DISABLE',anchors['DISABLE'],(270,142),'#6c4d83')
    if 'KRET' in anchors:
        label(ax,'KRET',anchors['KRET'],(320,133),'#6c4d83')
    rm=next(m for m in c['modules'] if m['tag']=='R')
    rc=json.loads((ROOT/rm['input_folder']/'physical-contract.json').read_text())
    for i,t in enumerate(rc.get('power_routing',{}).get('trunks',[])):
        point=[rm['offset_um'][0]+sum(t['span_um'])/2,rm['offset_um'][1]+t['y_um']]
        label(ax,t['net']+' 加宽 M5 · 6 µm',point,(95+i*70,317+i%2*14),'#9f405f')
    core=next(m for m in c['modules'] if m['tag']=='C')
    cc=json.loads((ROOT/core['input_folder']/'physical-contract.json').read_text());b=cc['bbox_um'];x,y=core['offset_um']
    ax.add_patch(Rectangle((b[0]+x-2,b[1]+y-2),b[2]-b[0]+4,b[3]-b[1]+4,fill=False,lw=.8,ls='--',edgecolor='#6a7e87'))
    label(ax,'原 B 核心\n全部制造多边形保留',(28,20),(70,-17))
    ax.text(.98,.02,f"{c['width_um']:.2f} × {c['height_um']:.2f} µm\n{c['area_um2']/1e6:.6f} mm² 实验宏外框面积",transform=ax.transAxes,ha='right',fontsize=9,bbox=dict(facecolor='#fafbf8',edgecolor='none'))
    fig.suptitle('实际 GDS 投影：历史模块与最终联通实验宏',fontsize=19,color='#263d4b',y=.98)
    fig.text(.06,.065,'各图横纵坐标等比例；两图器件数、摆放及电路不同，面积变化不能作为单纯布线优化的收益。',fontsize=10,color='#4d626d')
    fig.text(.06,.035,'面积不含片外精密电压基准、补偿、泄放电阻、dummy 负载、封装、pad 与 ESD；电气性能另行验证。',fontsize=9,color='#4d626d')
    fig.tight_layout(rect=(0,.09,1,.95))
    bounds=text_bounds(fig)
    out=ROOT/a.out;out.parent.mkdir(parents=True,exist_ok=True)
    for ext in ('png','svg'):fig.savefig(out.with_suffix('.'+ext),dpi=170)
    metadata=dict(source_projection=True,language='zh-CN',historical=oldmeta,joint=meta,generator=file_record(Path(__file__)),style=file_record(ROOT/'scripts/reference_v2_layout/visual_style.py'),font=font,text_bounds=bounds,images=[file_record(out.with_suffix('.'+ext)) for ext in ['png','svg']])
    out.with_suffix('.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
