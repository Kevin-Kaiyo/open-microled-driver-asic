#!/usr/bin/env python3
"""Read archived GF180 GDS and build faithful 2-D views / illustrative z projection.

The viewer is geometry only: no field, thermal, carrier or post-layout solver.
Run with build/layout/venv/bin/python. Never modifies the source GDS.
"""
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import klayout.db as kdb

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/research/product-framework-20261014/layout'
PDK = ROOT / 'build/layout/pdk/gf180mcuD/libs.tech/klayout/tech'
SOURCES = {
    'integrated': ('evidence/integration/pixel_integrated.gds', '旧版联合顶层', '305 × 180 µm · 宏与互连占用跨度'),
    'pixel': ('evidence/layout/pixel_driver_layout.gds', '旧版单像素模拟宏', '95 × 37.66 µm · 六只 MOS 的实际布局'),
}
# The z index is arbitrary illustration order, not micrometres or process data.
STYLES = {
    21: ('N-well', '#cad4e3', -.3, 'well'),
    204: ('P-well', '#d9e0d1', -.2, 'well'),
    22: ('Active / COMP', '#6b9e78', 0, 'device'),
    30: ('Poly gate', '#bd7049', .4, 'device'),
    33: ('Contact', '#38434b', .8, 'via'),
    34: ('Metal1', '#557ab2', 1.2, 'metal'),
    35: ('Via1', '#364d67', 1.7, 'via'),
    36: ('Metal2', '#31a3ad', 2.2, 'metal'),
    38: ('Via2', '#236671', 2.7, 'via'),
    42: ('Metal3', '#9d76b7', 3.2, 'metal'),
    40: ('Via3', '#624e76', 3.7, 'via'),
    46: ('Metal4', '#d6a244', 4.2, 'metal'),
    41: ('Via4', '#8b6627', 4.7, 'via'),
    81: ('Metal5', '#c1637f', 5.2, 'metal'),
}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def roundn(x):
    return round(x, 6)

def mapping():
    names = {}
    for el in ET.parse(PDK / 'gf180mcu.lyp').getroot().iter('properties'):
        src = el.findtext('source', '').strip()
        m = re.match(r'(?:(.*?)\s+)?(\d+)/(\d+)@', src)
        if m:
            names[(int(m[2]), int(m[3]))] = el.findtext('name', '').strip() or (m[1] or '')
    assert names[(34,0)] == 'Metal1' and names[(81,0)] == 'Metal5'
    assert names[(22,0)] == 'COMP' and names[(30,0)] == 'Poly2'
    return names

def extract(key, spec, names):
    path, title, caption = spec
    layout = kdb.Layout()
    layout.read(str(ROOT/path))
    top = layout.top_cell()
    dbu = layout.dbu
    bbox = top.bbox()
    layers, statistics = [], []
    physical_region_bbox = None
    for li in layout.layer_indexes():
        info = layout.get_info(li)
        it = top.begin_shapes_rec(li)
        reg = kdb.Region()
        raw, texts, other = 0, 0, 0
        while not it.at_end():
            s = it.shape()
            if s.is_box() or s.is_polygon() or s.is_path():
                reg.insert(s.polygon.transformed(it.trans()))
                raw += 1
            elif s.is_text():
                texts += 1
            else:
                other += 1
            it.next()
        reg.merge()
        selected = info.datatype == 0 and info.layer in STYLES
        row = dict(layer=info.layer, datatype=info.datatype,
                   pdk_name=names.get((info.layer, info.datatype), 'unmapped'),
                   raw_geometric_shapes=raw, text_shapes=texts, other_shapes=other,
                   merged_polygons=reg.size(), union_area_um2=roundn(reg.area()*dbu*dbu),
                   displayed=selected, counted_as_conductor=selected and STYLES[info.layer][3] in ('metal','via'))
        statistics.append(row)
        if not selected:
            continue
        if not reg.is_empty():
            physical_region_bbox = reg.bbox() if physical_region_bbox is None else physical_region_bbox + reg.bbox()
        name, color, z, kind = STYLES[info.layer]
        polygons = []
        for p in reg.each():
            contours = [[[roundn(pt.x*dbu),roundn(pt.y*dbu)] for pt in p.each_point_hull()]]
            for h in range(p.holes()):
                contours.append([[roundn(pt.x*dbu),roundn(pt.y*dbu)] for pt in p.each_point_hole(h)])
            polygons.append(contours)
        layers.append(dict(id=info.layer, name=name, pdk_name=row['pdk_name'], color=color,
                           z=z, kind=kind, polygons=polygons, area_um2=row['union_area_um2']))
    b = [roundn(v*dbu) for v in [bbox.left,bbox.bottom,bbox.right,bbox.top]]
    g = physical_region_bbox
    metadata = dict(id=key, title=title, path=path, sha256=sha(ROOT/path), top_cell=top.name,
                    dbu_um=dbu, cell_bbox_um=b, span_area_um2=roundn(bbox.area()*dbu*dbu),
                    displayed_geometry_bbox_um=[roundn(v*dbu) for v in [g.left,g.bottom,g.right,g.top]],
                    layer_statistics=statistics)
    data = dict(id=key, title=title, caption=caption, bbox=b, layers=sorted(layers,key=lambda l:l['z']),
                sha256=metadata['sha256'], dbu_um=dbu, path=path)
    return data, metadata

def path_d(contours, tx):
    chunks=[]
    for contour in contours:
        points=[tx(*p) for p in contour]
        chunks.append('M'+' L'.join(f'{x:.3f},{y:.3f}' for x,y in points)+' Z')
    return ' '.join(chunks)

def make_svg(data):
    key=data['id']; W,H = (1280,850) if key=='integrated' else (1280,740)
    b=data['bbox']; plot=(95,160,1110,520) if key=='integrated' else (95,190,1110,390)
    scale=min(plot[2]/(b[2]-b[0]),plot[3]/(b[3]-b[1]))
    ox=plot[0]+(plot[2]-(b[2]-b[0])*scale)/2; oy=plot[1]+(plot[3]+(b[3]-b[1])*scale)/2
    def tx(x,y):return ox+(x-b[0])*scale,oy-(y-b[1])*scale
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         '<style>text{font-family:"Avenir Next","PingFang SC",sans-serif;fill:#233c46} .muted{fill:#5c6c72} .axis{fill:#62737b;font-size:15px}</style>',
         f'<rect width="{W}" height="{H}" fill="#fbfcfa"/>',
         f'<text x="52" y="52" font-size="29" font-weight="600">{data["title"]}：从 GDS 读取的真实二维几何</text>',
         f'<text x="52" y="86" font-size="19" class="muted">{data["caption"]} · X/Y 尺寸按原文件 · DBU = 1 nm</text>',
         '<text x="52" y="117" font-size="17" fill="#905932">未包含新增参考源、启动隔离、独立保护、pad / ESD 与封装；不是最终可流片芯片。</text>']
    for layer in data['layers']:
        opacity=.48 if layer['kind']=='well' else (.77 if layer['kind']=='metal' else .86)
        svg.append(f'<g fill="{layer["color"]}" fill-opacity="{opacity}" stroke="none" data-layer="{layer["id"]}/0">')
        for p in layer['polygons']:
            svg.append(f'<path d="{path_d(p,tx)}" fill-rule="evenodd"/>')
        svg.append('</g>')
    x1,y1=tx(b[0],b[3]);x2,y2=tx(b[2],b[1])
    svg.append(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" fill="none" stroke="#667e87" stroke-dasharray="6 5" stroke-width="1"/>')
    if key=='integrated':
        for x,y,w,h,label in [(25,105.22,95,37.66,'旧单像素 analog macro'),(150,25,180,180,'旧 PWM digital macro')]:
            xx,yy=tx(x,y+h);svg.append(f'<rect x="{xx}" y="{yy}" width="{w*scale}" height="{h*scale}" fill="none" stroke="#284e60" stroke-width="1.5" stroke-dasharray="6 4"/>')
            svg.append(f'<text x="{xx+w*scale/2}" y="{yy-13}" text-anchor="middle" font-size="18">{label}</text>')
        for text,x,y,lx,ly in [('PWM · M3',130,111.52,92,71),('VDD · M4',140,88,91,48),('VSS · M5',135,98,69,90)]:
            xx,yy=tx(x,y);ax,ay=tx(lx,ly)
            svg.append(f'<path d="M{ax+36},{ay-5} L{xx},{yy}" stroke="#48616c" fill="none"/><text x="{ax}" y="{ay}" text-anchor="middle" font-size="17">{text}</text>')
    else:
        for name,x,w,l in [('MREF',10,20,4),('MOUT',25,20,4),('MPASS',40,2,1),('MCLAMP',55,2,1),('MINV_N',70,2,1),('MINV_P',85,4,1)]:
            xx,_=tx(x,0); svg.append(f'<text x="{xx}" y="153" text-anchor="middle" font-size="17">{name}</text><text x="{xx}" y="176" text-anchor="middle" font-size="14" class="muted">W/L {w}/{l} µm</text>')
        for name,y in [('VSS',0),('BIAS',2),('GATE',4),('PWM',6),('PWM_B',8),('LED_K',10),('VLOGIC',12)]:
            xx,yy=tx(0,y);svg.append(f'<text x="{xx-9}" y="{yy+4}" text-anchor="end" font-size="13">{name}</text>')
    length=50 if key=='integrated' else 10
    yy=H-104;xx=68
    svg.append(f'<path d="M{xx},{yy-5}v10 M{xx},{yy}h{length*scale} M{xx+length*scale},{yy-5}v10" stroke="#243e49" stroke-width="2"/><text x="{xx}" y="{yy+25}" font-size="15">{length} µm</text>')
    legend=[22,30,33,34,36,42,46,81] if key=='integrated' else [22,30,33,34,35,36,38,42]
    for i,lid in enumerate(legend):
        name,col,_,_=STYLES[lid]; x=330+(i%4)*210;y=H-105+(i//4)*28
        svg.append(f'<rect x="{x}" y="{y-11}" width="16" height="12" fill="{col}"/><text x="{x+23}" y="{y}" font-size="15">{name} · {lid}/0</text>')
    svg.append(f'<text x="52" y="{H-20}" font-size="13" class="muted">来源：{data["path"]} · SHA-256 {data["sha256"][:16]}… · 标签层未作为导体绘制</text></svg>')
    (OUT/f'{key}-2d.svg').write_text('\n'.join(svg))

HTML = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MicroLED ASIC：实际 GDS 版图查看</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f3f6f4;color:#203e48;font:16px/1.6 "Avenir Next","PingFang SC",sans-serif}header{padding:24px 30px 15px;border-bottom:1px solid #ccd8d7;background:#fff}h1{font-size:26px;margin:0 0 6px}p{margin:6px 0}.muted{color:#64777d}.warning{color:#895b2e;font-size:14px}.layout{display:grid;grid-template-columns:290px minmax(0,1fr);gap:16px;padding:18px}aside,main{background:white;border:1px solid #d4dfdc;border-radius:9px;padding:17px}button,select{font:inherit;padding:7px 12px;border:1px solid #a5bbba;border-radius:5px;background:white;color:#234750;cursor:pointer}button.active{background:#176d72;color:white;border-color:#176d72}.controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center}label.layer{display:flex;gap:8px;align-items:center;font-size:14px;padding:3px 0;cursor:pointer}.swatch{width:13px;height:13px;border-radius:2px}label.layer small{color:#78898d;margin-left:auto;font-size:12px}.list{margin-top:14px;border-top:1px solid #e3eae7;padding-top:10px}input[type=range]{width:100%}.range{font-size:14px;display:block;margin-top:12px}canvas{display:block;width:100%;height:650px;background:#fcfdfc;border:1px solid #e3ebe6;margin-top:14px;touch-action:none;cursor:grab}.stat{font-size:13px;color:#5f747b;overflow-wrap:anywhere;margin-top:12px}.caption{font-size:14px;padding:12px 0 0;min-height:80px}details{font-size:14px;margin-top:10px}code{font-size:12px;overflow-wrap:anywhere}.badge{background:#eaf3f1;padding:3px 7px;border-radius:4px;font-size:13px}.foot{padding:0 30px 25px;font-size:14px}.source-links a{color:#126d72}@media(max-width:900px){.layout{grid-template-columns:1fr}aside .list{columns:2}canvas{height:520px}header{padding:18px}h1{font-size:23px}.layout{padding:12px}.range{max-width:360px}}
</style><header><h1>MicroLED Driver：实际 GDS 的二维与三维分层投影</h1><p>逐层看晶体管几何、金属互连与通孔；这些图来自仓库已有版图。</p><p class="warning">旧版版图：新增参考电流源、启动隔离、独立保护、pad / ESD 尚未放入。三维图只表达层次，不是最终芯片、工艺截面或物理仿真。</p></header>
<div class="layout"><aside><b>选择已有设计</b><p><select id="design"><option value="integrated">旧联合顶层</option><option value="pixel">旧单像素模拟宏</option></select></p><div class="controls"><button id="two" class="active">二维平面</button><button id="three">三维分层</button></div><label class="range">缩放 <span id="zoomLabel"></span><input id="zoom" type="range" min=".5" max="10" value="1" step=".05"></label><div id="threeControls" hidden><label class="range">分层距离（示意）<input id="spread" type="range" min=".2" max="3" value="1.1" step=".05"></label><label class="range">视角倾斜<input id="tilt" type="range" min="10" max="80" value="50" step="1"></label></div><div class="controls"><button id="fit">适合窗口</button><button id="metals">仅互连</button><button id="all">全部所绘层</button></div><div class="list" id="layers"></div><div id="stats" class="stat"></div><details><summary>坐标与显示边界</summary><p>X / Y 多边形与尺寸来自原始 GDS。层内重叠多边形合并，保留孔洞；文本及标签图形不计作金属。</p><p>Z 仅是相对层序，分层距离为显示参数；未输入真实厚度、介电常数、掺杂或材料热参数。显示色彩不代表实际材料颜色。</p></details></aside>
<main><div class="controls"><b id="title"></b><span class="badge" id="modeBadge">二维几何</span></div><canvas id="canvas" aria-label="真实 GDS 几何视图"></canvas><div class="caption" id="caption"></div><p class="muted" style="font-size:13px">二维：拖动平移；三维：拖动旋转。滚轮缩放；每个复选框开关一个实际 GDS 层。网页离线可用，不调用外部资源。</p><details><summary>这幅图可以证明什么？</summary><p>可以观察现有 GDS 中器件、布线和层间连接的几何关系。其可见形状不自动证明电气连通、DRC、LVS、PEX、可靠性或制造接受。</p><p>这里没有重新布局，也没有执行新的签核。旧 top 的指定 DRC / LVS 结果请查 evidence/integration/summary.json；旧检查未开启 density / antenna，也没有当前新电路的全芯片验证。</p></details></main></div>
<div class="foot source-links"><a href="integrated-2d.svg">联合顶层二维 SVG</a> · <a href="pixel-2d.svg">像素局部二维 SVG</a> · <a href="../layout-chapter.md">阅读说明</a> · <a href="manifest.json">来源与逐层统计</a><p>下一版需要重新实现新模拟宏与完整安全逻辑、pad / ESD / POR、供电及测试接口，并在匹配的完整 PDK 上完成对应验证。</p></div>
<script id="geometry" type="application/json">__DATA__</script><script>
const DATA=JSON.parse(document.querySelector('#geometry').textContent);let key='integrated',mode='2d',visible=new Set(),zoom=1,spread=1.1,tilt=50,yaw=-.55,pan=[0,0],drag=null,scheduled=false;
const $=s=>document.querySelector(s),canvas=$('#canvas'),ctx=canvas.getContext('2d');let cw=1,ch=1;
function changeDesign(){key=$('#design').value;visible=new Set(DATA[key].layers.filter(l=>key==='pixel'||l.kind==='metal'||l.kind==='well'||l.id===22||l.id===30).map(l=>l.id));pan=[0,0];zoom=1;$('#zoom').value=1;layerUI();draw()}
function layerUI(){const d=DATA[key];$('#title').textContent=d.title;$('#layers').innerHTML=d.layers.map(l=>`<label class="layer"><input type="checkbox" data-layer="${l.id}" ${visible.has(l.id)?'checked':''}><span class="swatch" style="background:${l.color}"></span>${l.name}<small>${l.id}/0</small></label>`).join('');$('#stats').textContent=`DBU ${d.dbu_um} µm · bbox [${d.bbox.join(', ')}] µm · SHA-256 ${d.sha256}`;$('#layers').querySelectorAll('input').forEach(x=>x.onchange=()=>{x.checked?visible.add(+x.dataset.layer):visible.delete(+x.dataset.layer);draw()})}
function render(){scheduled=false;const rect=canvas.getBoundingClientRect(),dpi=window.devicePixelRatio||1;cw=rect.width;ch=rect.height;if(canvas.width!==Math.round(cw*dpi)||canvas.height!==Math.round(ch*dpi)){canvas.width=Math.round(cw*dpi);canvas.height=Math.round(ch*dpi)}ctx.setTransform(dpi,0,0,dpi,0,0);ctx.clearRect(0,0,cw,ch);const d=DATA[key],b=d.bbox,w=b[2]-b[0],h=b[3]-b[1],mx=(b[0]+b[2])/2,my=(b[1]+b[3])/2;let sc=Math.min((cw-80)/w,(ch-80)/h)*zoom*(mode==='3d'?.72:1),tr=tilt*Math.PI/180;
function point(x,y,z=0){x-=mx;y-=my;if(mode==='2d')return[cw/2+x*sc+pan[0],ch/2-y*sc+pan[1]];const rx=x*Math.cos(yaw)-y*Math.sin(yaw),ry=x*Math.sin(yaw)+y*Math.cos(yaw);return[cw/2+rx*sc,ch*.57+(ry*Math.sin(tr)-z*(w/28)*spread*Math.cos(tr))*sc]}
function path(contours,z){ctx.beginPath();for(const c of contours){c.forEach((p,i)=>{const q=point(p[0],p[1],z);i?ctx.lineTo(...q):ctx.moveTo(...q)});ctx.closePath()}}
const border=[[[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]]]];ctx.fillStyle='#f1f5f1';path(border,-.5);ctx.fill('evenodd');ctx.strokeStyle='#c8d6d1';ctx.stroke();let n=0;
for(const l of d.layers){if(!visible.has(l.id))continue;ctx.fillStyle=l.color;ctx.globalAlpha=l.kind==='well'?.52:(l.kind==='metal'?.85:.93);for(const p of l.polygons){path(p,l.z);ctx.fill('evenodd');n++}if(mode==='3d'){ctx.globalAlpha=.3;ctx.strokeStyle=l.color;path(border,l.z);ctx.stroke()}}
ctx.globalAlpha=1;ctx.font='13px "Avenir Next","PingFang SC",sans-serif';ctx.fillStyle='#425f69';if(mode==='2d'){const unit=w>150?50:10,len=unit*sc;ctx.beginPath();ctx.moveTo(24,ch-35);ctx.lineTo(24+len,ch-35);ctx.strokeStyle='#385563';ctx.lineWidth=2;ctx.stroke();ctx.fillText(`${unit} µm`,24,ch-15)}else{ctx.fillText('X/Y：实际几何   Z：相对层序（无物理单位）',18,26);ctx.fillText('拖动旋转；并非电场 / 热 / 载流子仿真',18,47)}
$('#zoomLabel').textContent=zoom.toFixed(2)+'×';$('#caption').textContent=d.caption+'。当前显示 '+visible.size+' 个层、'+n.toLocaleString()+' 个合并多边形。'+(mode==='3d'?'各层按声明的相对 Z 顺序投影；不表示真实厚度和层间距。':'关闭上层金属可查看下面的栅极与有源区。');window.FRAMEWORK_VIEWER_STATE={design:key,mode,visible_layers:[...visible],rendered_polygons:n,zoom};}
function draw(){if(!scheduled){scheduled=true;requestAnimationFrame(render)}}function setMode(m){mode=m;pan=[0,0];$('#two').classList.toggle('active',m==='2d');$('#three').classList.toggle('active',m==='3d');$('#threeControls').hidden=m!=='3d';$('#modeBadge').textContent=m==='2d'?'二维几何':'三维分层示意';draw()}
$('#design').onchange=changeDesign;$('#two').onclick=()=>setMode('2d');$('#three').onclick=()=>setMode('3d');$('#zoom').oninput=e=>{zoom=+e.target.value;draw()};$('#spread').oninput=e=>{spread=+e.target.value;draw()};$('#tilt').oninput=e=>{tilt=+e.target.value;draw()};$('#fit').onclick=()=>{zoom=1;pan=[0,0];yaw=-.55;$('#zoom').value=1;draw()};$('#metals').onclick=()=>{visible=new Set(DATA[key].layers.filter(l=>l.kind==='metal'||l.kind==='via').map(l=>l.id));layerUI();draw()};$('#all').onclick=()=>{visible=new Set(DATA[key].layers.map(l=>l.id));layerUI();draw()};canvas.onpointerdown=e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId)};canvas.onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag[0],dy=e.clientY-drag[1];drag=[e.clientX,e.clientY];if(mode==='2d'){pan[0]+=dx;pan[1]+=dy}else{yaw+=dx*.006;tilt=Math.max(10,Math.min(80,tilt+dy*.15));$('#tilt').value=tilt}draw()};canvas.onpointerup=()=>drag=null;canvas.onpointercancel=()=>drag=null;canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.5,Math.min(10,zoom*Math.exp(-e.deltaY*.001)));$('#zoom').value=zoom;draw()},{passive:false});new ResizeObserver(draw).observe(canvas);changeDesign();
</script></html>'''

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    names=mapping(); data={}; records=[]
    for key,spec in SOURCES.items():
        d,m=extract(key,spec,names);data[key]=d;records.append(m);make_svg(d)
    (OUT/'viewer.html').write_text(HTML.replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':'))))
    manifest=dict(schema_version=1, generated_on='2026-10-14',
        method='Recursive transformed KLayout polygons, union-merged per layer; holes retained. Text and datatype 10 labels excluded from displayed/conductor geometry.',
        klayout_version=kdb.__version__, gds_modified=False, new_layout_generated=False,
        geometry_3d='Actual XY polygons projected at arbitrary relative layer indices. No physical z units, thickness, dielectric, doping, field, temperature or carrier solution.',
        no_signoff_performed=True, known_missing=['new reference','startup TG isolation','independent protection','pads/ESD/POR','package','real LED'],
        pdk_mapping={str((PDK/f).relative_to(ROOT)):sha(PDK/f) for f in ['gf180mcu.lyp','gf180mcu.map','drc/rule_decks/layers_def.drc']},
        geometry_sources=records,
        primary_sources_checked_on='2026-10-14',
        primary_sources=[
            {'url':'https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_06.html','supports':'Hierarchical GDSII, all design layers, DRC before submission'},
            {'url':'https://github.com/wafer-space/gf180mcu-precheck','supports':'Manufacturing precheck scope including DBU/slot/layers/density/antenna/DRC; not performance signoff'},
            {'url':'https://docs.openems.de/en/latest/','supports':'EM material/mesh/port/field/S-parameter workflow; no project simulation performed'},
            {'url':'https://devsim.org/introduction.html','supports':'Semiconductor TCAD and 1D/2D/3D capability; not foundry calibrated project model'}],
        z_illustration={str(lid):dict(name=v[0],relative_order=v[2],unit='arbitrary; not um') for lid,v in STYLES.items()},
        script=dict(path=str(Path(__file__).relative_to(ROOT)),sha256=sha(__file__)),
        output_sha256={p.name:sha(p) for p in [OUT/'integrated-2d.svg',OUT/'pixel-2d.svg',OUT/'viewer.html']})
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    # Re-read serialized polygons and compare their area with KLayout's integer
    # geometry. This catches contour holes, scaling and serialization errors.
    saved = json.loads((OUT/'viewer.html').read_text().split('<script id="geometry" type="application/json">',1)[1].split('</script>',1)[0])
    baseline = json.loads((ROOT/'docs/research/startup-tapeout-20261014/area-baseline.json').read_text())
    expected = {x['path']:x for x in baseline['layouts']}
    checks=[]
    def check(name, passed, details=None):
        checks.append(dict(name=name,passed=bool(passed),details=details))
    for rec in records:
        exp=expected[rec['path']]
        check(rec['id']+'_source_hash_unchanged',rec['sha256']==exp['sha256'])
        check(rec['id']+'_bbox_unchanged',rec['cell_bbox_um']==exp['bbox_um'])
        check(rec['id']+'_dbu',rec['dbu_um']==exp['dbu_um'])
        check(rec['id']+'_labels_not_conductors',all(not x['counted_as_conductor'] for x in rec['layer_statistics'] if x['datatype']!=0))
        check(rec['id']+'_pdk_names_resolved',all(x['pdk_name'] not in ('','unmapped') for x in rec['layer_statistics'] if x['displayed']))
        for layer in saved[rec['id']]['layers']:
            area=0
            for polygon in layer['polygons']:
                for i,contour in enumerate(polygon):
                    signed=sum(p[0]*q[1]-q[0]*p[1] for p,q in zip(contour,contour[1:]+contour[:1]))/2
                    area+=abs(signed)*(1 if i==0 else -1)
            error=abs(area-layer['area_um2'])
            check(f'{rec["id"]}_{layer["id"]}_polygon_area',error<1e-6,{'area_error_um2':error})
    check('viewer_reading_link_exists',(OUT/'../layout-chapter.md').is_file())
    result=dict(passed=all(x['passed'] for x in checks),checks=checks,
                checked_viewer_sha256=sha(OUT/'viewer.html'),checked_script_sha256=sha(__file__),
                claim='Geometry serialization and source identity only; no new DRC/LVS/PEX or functional simulation.')
    (OUT/'geometry-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    assert result['passed'], 'Geometry validation failed; inspect geometry-validation.json'
    print(json.dumps({'output':str(OUT.relative_to(ROOT)), 'sources':len(records),'viewer_bytes':(OUT/'viewer.html').stat().st_size,'new_layout':False}))

if __name__=='__main__':main()
