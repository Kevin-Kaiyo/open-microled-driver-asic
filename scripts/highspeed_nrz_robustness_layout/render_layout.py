#!/usr/bin/env python3
"""Render final physical GDS at physical XY scale, plus a MOS-region inset."""
from pathlib import Path
import hashlib, json, argparse
import klayout.db as k
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle, Patch
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'evidence/highspeed-nrz-robustness-layout/visuals'
FIG=OUT/'figures'
F=ROOT/'build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf'
font_manager.fontManager.addfont(str(F));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(F)).get_name()
plt.rcParams['svg.fonttype']='none'
STYLES={55:('Dualgate 6 V','#ecd99e',.30),21:('N-well','#d9e5ea',.7),204:('P-well','#dbe9df',.7),22:('Active','#92b59d',.85),30:('Poly','#bf775a',.9),33:('Contact','#283b44',1),34:('Metal1','#7c97b8',.8),35:('Via1','#233e51',1),36:('Metal2','#31849e',.8),38:('Via2','#233e51',1),42:('Metal3','#9a74a6',.8),40:('Via3','#233e51',1),46:('Metal4','#c09239',.8)}

def main():
    global OUT,FIG
    ap=argparse.ArgumentParser();ap.add_argument('--work',default='build/highspeed-nrz-robustness-layout/hv-r2');ap.add_argument('--out',default='evidence/highspeed-nrz-robustness-layout/visuals');ap.add_argument('--routes',default='AB');ap.add_argument('--work-A');ap.add_argument('--work-B');args=ap.parse_args()
    OUT=ROOT/args.out;FIG=OUT/'figures'
    FIG.mkdir(parents=True,exist_ok=True);data={}
    for route in args.routes:
        folder=ROOT/(getattr(args,'work_'+route) or args.work)/route
        c=json.loads((folder/'physical-contract.json').read_text());gds=folder/'generate'/f"{c['top']}.gds"
        assert hashlib.sha256(gds.read_bytes()).hexdigest()==c['gds_sha256']
        lay=k.Layout();lay.read(str(gds));top=lay.cell(c['top']);polys=[]
        for li in lay.layer_indexes():
            inf=lay.get_info(li)
            if inf.datatype or inf.layer not in STYLES:continue
            it=top.begin_shapes_rec(li)
            while not it.at_end():
                s=it.shape()
                if s.is_box() or s.is_polygon() or s.is_path():
                    p=s.polygon.transformed(it.trans());assert p.holes()==0
                    polys.append({'layer':inf.layer,'points':[[round(q.x*lay.dbu,5),round(q.y*lay.dbu,5)] for q in p.each_point_hull()]})
                it.next()
        data[route]={'contract':c,'polygons':polys,'styles':STYLES,'gds':str(gds.relative_to(ROOT))}
        fig,axs=plt.subplots(1,2,figsize=(14,8),gridspec_kw={'width_ratios':[1,1.25]},facecolor='#fafbf8')
        for ax in axs:
            for p in sorted(polys,key=lambda p:list(STYLES).index(p['layer'])):
                _,co,alpha=STYLES[p['layer']];ax.add_patch(Polygon(p['points'],facecolor=co,edgecolor=co,lw=.15,alpha=alpha))
            ax.set_aspect('equal');ax.spines[['top','right']].set_visible(False);ax.set(xlabel='x (µm)',ylabel='y (µm)')
        b=c['bbox_um'];axs[0].set(xlim=(b[0]-3,b[2]+2),ylim=(b[1]-2,b[3]+3),title=f'{route} · 完整核心（真实 XY 比例）')
        r=c['resistors'][0];axs[0].annotate(f"RIN：{r['r_length_um']:g} × {r['r_width_um']:g} µm\n高阻 P-poly，6.0 V 型",xy=(r['cx'],r['cy']),xytext=(7,r['cy']-8),arrowprops={'arrowstyle':'->','color':'#188578'},fontsize=10,color='#188578')
        if r.get('substrate_screen_geometry'):
            g=r['substrate_screen_geometry'];axs[0].annotate('VSS 衬底接触带',xy=(g['center_x_um'],r['cy']+9),xytext=(6,27) if r['r_length_um']<20 else (9,r['cy']+14),arrowprops={'arrowstyle':'->','color':'#3d729e'},fontsize=10,color='#3d729e')
        for pin,xy in r['pins_um'].items():
            if pin=='B':continue
            axs[0].annotate('DATA' if pin=='1' else 'DI',xy=xy,xytext=(3,xy[1]),fontsize=9,color='#8164a8',arrowprops={'arrowstyle':'->','color':'#8164a8'})
        axs[0].add_patch(Rectangle((0,4),b[2]+1,30,fill=False,edgecolor='#188578',linestyle='--',lw=1))
        axs[1].set(xlim=(-1,b[2]+1),ylim=(3,35),title='MOS 与互连区域放大')
        for d in c['devices']:
            axs[1].text(d['cx'],30.8,d['name']+'\n'+f"{d['w_um']:g}/{d['l_um']:g}"+'\n'+('6 V' if d['model'].endswith('06v0') else '3.3 V'),ha='center',va='bottom',fontsize=7,color=('#8b651c' if d['model'].endswith('06v0') else '#285f6e'))
            axs[1].plot([d['cx'],d['cx']],[30.3,d['cy']+d['w_um']/2+.5],lw=.5,color='#80949c')
        fig.suptitle(f"{route} · {len(c['devices'])} MOS + 1 工艺电阻 / {c['width_um']:.2f} × {c['height_um']:.2f} µm",fontsize=16,x=.06,ha='left')
        fig.legend(handles=[Patch(facecolor=STYLES[i][1],label=STYLES[i][0])for i in [55,21,22,30,34,36,42,46]],loc='lower center',ncol=8,frameon=False)
        fig.text(.06,.10,'实际 GDS 回读；6 V 器件由 Dualgate 层与提取模型双重验证。此图是核心，不是最终芯片。',fontsize=10,color='#547078')
        fig.tight_layout(rect=(0,.17,1,.95))
        for ext in ['svg','png']:fig.savefig(FIG/f'layout-{route}.{ext}',dpi=160,bbox_inches='tight')
        plt.close(fig)
    (OUT/'geometry.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    print('Rendered actual GDS for',','.join(data))

if __name__=='__main__':main()
