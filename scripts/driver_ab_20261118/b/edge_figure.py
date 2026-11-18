"""Draw the receiver-margin experiment's actual switched nodes and device connections."""
from pathlib import Path
from xml.sax.saxutils import escape
import json, hashlib
ROOT=Path(__file__).resolve().parents[3]
ASSET=ROOT/'docs/research/driver-ab-20261118/assets'
source=ROOT/'build/driver-ab-20261118/b/merged220c10r260n4ff36/inputs/route_b.spice'
netlist=source.read_text()
for token in ['CFF GB OUT 36f','XINV2N GP GB VSS VSS nfet_03v3 w=4u', 'XINV2P GP GB VDD VDD pfet_03v3','XLED OUT GP VX VSS','XDUMMY DUMMY GB VX VSS','RDUMMY VIN DUMMY 27.6k','XBASE OUT BIAS VSS VSS']:
    assert token in netlist, token
INK='#1b3443'
TEAL='#076f70'
LIGHT='#d3e3e0'
parts=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 570" role="img" aria-labelledby="title desc"><title id="title">B 电流转向与下降沿补偿</title><desc id="desc">GB 上升时 NMOS 拉低 GP，LED 支路关闭，尾电流转入假负载。CFF 把 GB 边沿耦合到 OUT。</desc><rect width="1120" height="570" fill="#fbfcfa"/><g font-family="PingFang SC,Microsoft YaHei,Arial,sans-serif">']
def text(x,y,s,size=16,color=INK,bold=False,center=False):
    parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{650 if bold else 400}" text-anchor="{"middle" if center else "start"}">{escape(s)}</text>')
def wire(points,color=INK,width=2.5):
    parts.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in points)+f'" stroke="{color}" stroke-width="{width}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
def dot(x,y,color=INK):
    parts.append(f'<circle cx="{x}" cy="{y}" r="3.6" fill="{color}"/>')
def gate(x,y,p=False):
    # d/s contact locations (x+13, y±28); gate contact (x-23,y)
    wire([(x+13,y-28),(x+13,y-17),(x,y-17),(x,y+17),(x+13,y+17),(x+13,y+28)])
    wire([(x-6,y-15),(x-6,y+15)])
    if p:
        parts.append(f'<circle cx="{x-11}" cy="{y}" r="4.2" fill="#fbfcfa" stroke="{INK}" stroke-width="2"/>')
        wire([(x-23,y),(x-15,y)])
    else:
        wire([(x-23,y),(x-6,y)])
def gnd(x,y):
    wire([(x,y),(x,y+8)]);wire([(x-11,y+8),(x+11,y+8)]);wire([(x-7,y+13),(x+7,y+13)]);wire([(x-3,y+18),(x+3,y+18)])
text(28,42,'B 电流转向级如何缩短接收端下降沿',28,bold=True)
text(28,72,'以 DATA 由 1 变 0 为例。图中同名节点直接相连，器件尺寸与支路名称可在 SPICE 网表中查阅。')
wire([(28,87),(1092,87)],LIGHT,1.2)
text(34,120,'栅极预驱动',22,TEAL,True)
text(34,154,'第一级反相器输出 GB，以互补控制转向支路。',15)
text(175,198,'VDD',16,center=True);wire([(175,204),(175,220)])
gate(162,248,True);wire([(175,276),(175,301),(175,326)])
gate(162,354);gnd(175,382)
wire([(83,248),(139,248)]);wire([(83,248),(83,354),(139,354)]);wire([(43,301),(83,301)]);dot(83,301)
text(35,290,'GB ↑',17,TEAL,True);wire([(175,301),(268,301)],TEAL);dot(175,301);text(276,308,'GP ↓',18,TEAL,True)
text(209,248,'XINV2P',16);text(208,355,'XINV2N',16);text(208,378,'W  2.5 → 4 µm（试验）',14)
text(33,439,'GB 上升后，XINV2N 将 GP 的栅电荷放到 VSS。',15)
text(33,465,'GP 下降使 XLED 关断。该管加宽只改变预驱动。',15)
wire([(448,108),(448,480)],LIGHT,1.2)
text(474,120,'LED 与假负载之间的电流转向',22,TEAL,True)
text(474,154,'OUT 接封装串联支路，通往 LED 阴极。',15)
text(976,170,'VIN',15,center=True);wire([(976,177),(976,186)])
wire([(976,186),(969,192),(983,198),(969,204),(983,210),(976,216),(976,233)])
text(994,204,'27.6 kΩ',14);text(981,248,'DUMMY',13)
text(731,188,'OUT（LED 阴极侧）',16,TEAL,True)
wire([(735,200),(760,200),(760,267)]);wire([(976,233),(976,267)]);dot(760,211)
gate(747,295);gate(963,295)
wire([(700,295),(724,295)]);text(666,300,'GP',16,TEAL,True)
wire([(916,295),(940,295)]);text(882,300,'GB',16,TEAL,True)
text(779,301,'XLED',15);text(994,300,'XDUMMY',15)
wire([(760,323),(760,345),(976,345),(976,323)]);wire([(868,345),(868,370)]);dot(868,345);text(880,368,'VX',14)
gate(855,398);wire([(800,398),(832,398)]);text(754,403,'BIAS',15,TEAL,True);gnd(868,426);text(888,403,'XTAIL ×3',15)
wire([(570,211),(602,211)]);wire([(602,199),(602,223)],TEAL);wire([(610,199),(610,223)],TEAL);wire([(610,211),(760,211)],TEAL);text(531,216,'GB',16,TEAL,True);text(547,249,'CFF  31.275 → 36 fF',15,TEAL)
text(474,466,'XBASE 接 OUT / BIAS / VSS / VSS，提供约 25 µA 基流。',15)
wire([(28,487),(1092,487)],LIGHT,1.2)
text(30,519,'GB 上升还通过 CFF 向 OUT 注入瞬态电荷，降低 LED 正向电压，加快 LED 导通电流下降。',17,TEAL,True)
text(30,549,'NMOS 体接 VSS，PMOS 体接 VDD。CFF 由预驱动供能，数字输入、供电与参考端口均计入每比特能耗。',15)
parts.append('</g></svg>')
ASSET.mkdir(parents=True,exist_ok=True)
(ASSET/'b-edge-assist.svg').write_text(''.join(parts)+'\n')
ev=ROOT/'evidence/driver-ab-20261118/b'
(ev/'edge-assist-source.json').write_text(json.dumps({'path':str(source.relative_to(ROOT)),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'generator':str(Path(__file__).resolve().relative_to(ROOT))},indent=2)+'\n')
