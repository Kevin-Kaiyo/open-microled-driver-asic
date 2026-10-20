#!/usr/bin/env python3
"""Render real GDS geometry and an annotated layer/net viewer; no invented 3D."""
from pathlib import Path
import json, hashlib, html
import klayout.db as k
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Patch
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/highspeed-nrz-pex-20261020'
FIG=OUT/'figures'; FIG.mkdir(parents=True,exist_ok=True)
FONT=ROOT/'build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf'
font_manager.fontManager.addfont(str(FONT));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(FONT)).get_name()
plt.rcParams['svg.fonttype']='none'
STYLES={21:('N-well','#d9e5ea',.7),204:('P-well','#dbe9df',.7),22:('Active','#92b59d',.85),30:('Poly','#bf775a',.9),33:('Contact','#283b44',1),34:('Metal1','#7c97b8',.8),35:('Via1','#233e51',1),36:('Metal2','#31849e',.8),38:('Via2','#233e51',1),42:('Metal3','#9a74a6',.8),40:('Via3','#233e51',1),46:('Metal4','#c09239',.8)}
G={}
for route in ['A','B']:
    folder=ROOT/'build/highspeed-nrz-layout/r4'/route
    c=json.loads((folder/'physical-contract.json').read_text())
    candidates=[p for p in folder.rglob('*.gds') if 'negative' not in str(p)]
    gds=next(p for p in candidates if hashlib.sha256(p.read_bytes()).hexdigest()==c['gds_sha256'])
    lay=k.Layout();lay.read(str(gds));top=lay.cell(c['top']);polys=[]
    for li in lay.layer_indexes():
        inf=lay.get_info(li)
        if inf.datatype or inf.layer not in STYLES:continue
        it=top.begin_shapes_rec(li)
        while not it.at_end():
            s=it.shape()
            if s.is_box() or s.is_polygon() or s.is_path():
                poly=s.polygon.transformed(it.trans())
                assert poly.holes()==0, 'Viewer must preserve polygon holes'
                pts=[[round(p.x*lay.dbu,5),round(p.y*lay.dbu,5)] for p in poly.each_point_hull()]
                polys.append({'layer':inf.layer,'points':pts})
            it.next()
    G[route]={'contract':c,'polygons':polys,'gds':str(gds.relative_to(ROOT)),'styles':STYLES}
    fig,ax=plt.subplots(figsize=(13,7),facecolor='#fafbf8');ax.set_facecolor('#fafbf8')
    for p in sorted(polys,key=lambda p:list(STYLES).index(p['layer'])):
        _,col,alpha=STYLES[p['layer']];ax.add_patch(Polygon(p['points'],facecolor=col,edgecolor=col,lw=.15,alpha=alpha))
    for d in c['devices']:
        ax.text(d['cx'],26.7,f"{d['name']}\n{d['w_um']:g}/{d['l_um']:g}",ha='center',va='bottom',fontsize=8)
        ax.plot([d['cx'],d['cx']],[25.7,d['cy']+d['w_um']/2+.4],color='#80949c',lw=.5)
    for name,y in c['buses_um'].items():
        x1,x2=c['bus_spans_um'][name];ax.text(x1-.55,y,name,ha='right',va='center',fontsize=7,color='#314d59',bbox={'facecolor':'white','alpha':.85,'edgecolor':'none','pad':.2})
    ax.set(xlim=(-2,c['bbox_um'][2]+2),ylim=(-1,31),xlabel='x (µm)',ylabel='y (µm)')
    ax.set_aspect('equal');ax.spines[['top','right']].set_visible(False)
    ax.set_title(f"{route} · {'受限摆幅电压驱动 / 6 MOS' if route=='A' else '电流转向 / 9 MOS'} · 实际 GDS",loc='left',fontsize=15,pad=15)
    ax.legend(handles=[Patch(facecolor=STYLES[i][1],label=STYLES[i][0])for i in [21,22,30,34,36,42,46,33]],loc='lower center',bbox_to_anchor=(.5,-.23),ncol=8,frameon=False,fontsize=8)
    fig.savefig(FIG/f'layout-{route}.png',dpi=180,bbox_inches='tight');fig.savefig(FIG/f'layout-{route}.svg',bbox_inches='tight');plt.close(fig)
(OUT/'geometry.json').write_text(json.dumps(G,separators=(',',':'))+'\n')
# SVG viewBox stays in real micrometres. Labels are mirrored back to screen space.
viewer='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>NRZ 驱动器 · 实际 GDS 分层查看</title><link rel="stylesheet" href="report.css"><main><p class="eyebrow">2026-10-20 / GDS 几何 r3 · 电容组装 r4</p><h1>器件、金属与信号路径</h1><p>选择路线和网络，逐层隐藏金属。彩色多边形来自实际 GDS；红色网络框来自生成时的连接表，用来定位已由 LVS 核对的连线。显示比例为实际 XY 坐标；没有材料厚度、封装或电磁场模拟。</p><div class="viewer-controls"><label>路线 <select id="route"><option value="A">A · 电压驱动</option><option value="B">B · 电流转向</option></select></label><label>高亮网络 <select id="net"></select></label><label><input type="checkbox" id="labels" checked> 器件标注</label></div><div class="layers" id="layers"></div><svg class="viewer" id="layout" role="img" aria-label="实际GDS的二维分层视图"></svg><p id="info" class="small"></p><h2>怎么从原理图找到晶体管？</h2><p>器件编号对应原网表实例名（省略 X）；旧教学图的编号映射见研究报告。点击选择器查看 D/G/S/B 对应的网络和版图坐标；GDS 提取允许对称 MOS 的 D、S 交换，仿真使用提取网表的真实端子顺序。</p><label>器件 <select id="device"></select></label><div class="scroll"><table id="pins"></table></div><p id="device-info"></p><p><a href="index.html#layout">返回研究报告</a></p></main><script>const G=__DATA__;
const $=id=>document.getElementById(id), esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
function setup(){let a=G[$('route').value], c=a.contract; $('net').innerHTML='<option value="">全部网络</option>'+Object.keys(c.buses_um).map(n=>`<option>${n}</option>`).join('');$('device').innerHTML=c.devices.map(d=>`<option>${d.name}</option>`).join('');$('layers').innerHTML=Object.entries(a.styles).map(([n,s])=>`<label><input type="checkbox" value="${n}" checked> <span style="color:${s[1]}">■</span> ${s[0]}</label>`).join('');$('layers').querySelectorAll('input').forEach(i=>i.onchange=draw); draw(); pins();}
function draw(){let a=G[$('route').value],c=a.contract,b=c.bbox_um,net=$('net').value;let on=new Set([...$('layers').querySelectorAll('input:checked')].map(i=>+i.value));$('layout').setAttribute('viewBox',`${b[0]-3} ${-b[3]-6} ${b[2]-b[0]+6} ${b[3]-b[1]+10}`);let s=a.polygons.filter(p=>on.has(p.layer)).map(p=>`<polygon points="${p.points.map(q=>q[0]+','+(-q[1])).join(' ')}" fill="${a.styles[p.layer][1]}" opacity="${net?.24:a.styles[p.layer][2]}"/>`).join(''); if(net){s+=c.routes.filter(r=>r.net===net&&on.has({metal1:34,metal2:36,metal3:42,metal4:46}[r.layer])).map(r=>{let v=r.rect_um;return `<rect x="${v[0]}" y="${-v[3]}" width="${v[2]-v[0]}" height="${v[3]-v[1]}" fill="#b33f2d" opacity=".8"/>`}).join('');}if($('labels').checked){s+=c.devices.map(d=>`<text x="${d.cx}" y="${-b[3]-2.5}" text-anchor="middle" font-size="1" fill="#233d4b">${d.name}</text>`).join('');s+=Object.entries(c.buses_um).map(([n,y])=>`<text x="${c.bus_spans_um[n][0]-.4}" y="${-y+.2}" text-anchor="end" font-size=".65" fill="#233d4b">${n}</text>`).join('');}let d=c.devices.find(d=>d.name===$('device').value);if(d)s+=`<circle cx="${d.cx}" cy="${-d.cy}" r="1.5" fill="none" stroke="#b33f2d" stroke-width=".14"/>`; $('layout').innerHTML=s;$('info').textContent=`实际核心尺寸 ${c.width_um.toFixed(2)} × ${c.height_um.toFixed(2)} µm；包围盒面积 ${c.area_um2.toFixed(2)} µm²；4 层金属。GDS SHA256 ${c.gds_sha256}`;}
function pins(){let c=G[$('route').value].contract,d=c.devices.find(d=>d.name===$('device').value),m=c.extracted_device_mapping.find(m=>m.original_instance==='X'+d.name);$('pins').innerHTML='<tr><th>端子</th><th>原理图网络</th><th>版图坐标 x / y (µm)</th><th>对应 RC 局部节点</th></tr>'+['D','G','S','B'].map((p,i)=>`<tr><td>${p}</td><td>${d.nodes[i]}</td><td>${d.pins_um[p].map(x=>x.toFixed(3)).join(' / ')}</td><td>${m.rc_nodes[p]}</td></tr>`).join('');$('device-info').textContent=`${d.name}：${d.model}，W/L = ${d.w_um}/${d.l_um} µm；提取实例 ${m.extracted_instance}。D/S 交换：${m.drain_source_swapped?'是':'否'}。`;draw();}
$('route').onchange=setup;$('net').onchange=draw;$('labels').onchange=draw;$('device').onchange=pins;setup();</script></html>'''
(OUT/'layout-viewer.html').write_text(viewer.replace('__DATA__',json.dumps(G,separators=(',',':'))))
print(json.dumps({a:{'polygons':len(g['polygons']),'gds':g['gds']} for a,g in G.items()}))
