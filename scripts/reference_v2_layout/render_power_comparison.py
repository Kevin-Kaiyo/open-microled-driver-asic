"""Two actual 10MOS GDS layouts, same XY scale, annotated extracted PG evidence."""
from pathlib import Path
import argparse
import json
import hashlib
import klayout.db as k
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Patch
from render import STYLES
from visual_style import configure,text_bounds,file_record

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser();p.add_argument("--comparison",required=True);p.add_argument("--out",required=True)
    args=p.parse_args();data=json.loads((ROOT/args.comparison).read_text());out=ROOT/args.out;out.mkdir(parents=True,exist_ok=True)
    font=configure()
    fig,axs=plt.subplots(1,2,figsize=(15,10),facecolor="#fafbf8")
    for i,(ax,run) in enumerate(zip(axs,data["runs"])):
        folder=ROOT/run["module"];c=json.loads((folder/"physical-contract.json").read_text())
        gds=folder/"generate"/(c["top"]+".gds")
        assert hashlib.sha256(gds.read_bytes()).hexdigest()==run["gds_sha256"]
        layout=k.Layout();layout.read(str(gds));cell=layout.cell(c["top"])
        for layer,(_,color,opacity) in STYLES.items():
            for polygon in k.Region(cell.begin_shapes_rec(layout.layer(layer,0))).each():
                assert polygon.holes()==0
                points=[(q.x*layout.dbu,q.y*layout.dbu) for q in polygon.each_point_hull()]
                ax.add_patch(Polygon(points,facecolor=color,edgecolor=color,lw=.1,alpha=opacity))
        for d in c["devices"]:
            ax.text(d["cx"],d["cy"]+d["w_um"]/2+4,d["name"],ha="center",va="bottom",fontsize=6,color="#2b4250")
        for net,position in {"VIN":(5,43),"VSS":(105,42),"VSET":(43,30),"IOUT":(174,29)}.items():
            ax.annotate(net if net!="IOUT" else "IOUT → BIAS",xy=c["port_anchor_um"][net],xytext=position,
                fontsize=9,color="#183e52",arrowprops=dict(arrowstyle="->",lw=.8,color="#183e52"),
                bbox=dict(facecolor="#fafbf8",edgecolor="none",alpha=.95,pad=1.5))
        if c.get("power_routing"):
            for trunk in c["power_routing"]["trunks"]:
                x=sum(trunk["span_um"])/2;y=trunk["y_um"]
                if trunk["net"]=="IOUT":
                    ax.annotate("IOUT 加宽连线",xy=(x,y),xytext=(136,89),fontsize=8,
                        arrowprops=dict(arrowstyle="->",lw=.7),bbox=dict(facecolor="#fafbf8",edgecolor="none",alpha=.9))
                else:ax.text(x,y,trunk["net"]+" · M5 6 µm",fontsize=8,ha="center",va="center",
                        bbox=dict(facecolor="#fafbf8",edgecolor="none",alpha=.9,pad=1))
        ax.set_aspect("equal");ax.set(xlim=(-4,213),ylim=(-7,218),xlabel="x (µm)",ylabel="y (µm)")
        ax.spines[["top","right"]].set_visible(False)
        ax.set_title(("10 MOS · 原始细线布线" if i==0 else "10 MOS · 新增加宽供电干线"),fontsize=12)
        vals=data["terminal_path_comparison"]
        key="thin" if i==0 else "pg"
        rows=[f"VIN / VSS 至漏源端的最大路径 R：{vals['VIN'][key]['max_DS_ohm']:.2f} / {vals['VSS'][key]['max_DS_ohm']:.2f} Ω",
              f"VIN / VSS 至体端的最大路径 R：{vals['VIN'][key]['max_body_ohm']:.2f} / {vals['VSS'][key]['max_body_ohm']:.2f} Ω",
              f"宏外框面积：{run['area_um2']:.1f} µm²　|　提取 C：{run['capacitance_fF']/1000:.4f} pF"]
        ax.text(.01,-.14,"\n".join(rows),transform=ax.transAxes,fontsize=10,color="#294652",linespacing=1.6,va="top")
    fig.suptitle("实际 GDS：相同电路的供电布线对照",x=.06,ha="left",fontsize=18,color="#173b4c")
    fig.text(.06,.105,"两图使用相同 XY 比例；10 MOS 的尺寸、位置与连接相同，保留全部原始制造多边形。",fontsize=11,color="#304e5c")
    fig.text(.06,.078,"仅新增金属与通孔：宏外框面积 +2.61%，互连 C +3.83%。体端 R 保留在 full RC 中；未完成衬底场验证。",fontsize=10,color="#59717b")
    names={55:"6 V 器件标识",21:"N 阱",22:"有源区",30:"多晶硅",34:"M1",36:"M2",42:"M3",46:"M4",81:"M5"}
    fig.legend(handles=[Patch(facecolor=STYLES[i][1],label=names[i]) for i in [55,21,22,30,34,36,42,46,81]],
        loc="lower center",ncol=9,frameon=False,fontsize=8)
    fig.tight_layout(rect=(.02,.23,.99,.94))
    bounds=text_bounds(fig)
    for ext in ["png","svg"]:fig.savefig(out/("vi-power-comparison."+ext),dpi=170)
    meta=dict(source_projection=True,language='zh-CN',generator=file_record(Path(__file__)),style=file_record(ROOT/'scripts/reference_v2_layout/visual_style.py'),font=font,text_bounds=bounds,comparison=file_record(ROOT/args.comparison),unchanged_source_gds=[dict(module=r['module'],sha256=r['gds_sha256']) for r in data['runs']],images=[file_record(out/('vi-power-comparison.'+ext)) for ext in ['png','svg']])
    (out/'vi-power-comparison.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    plt.close(fig)


if __name__=="__main__":main()
