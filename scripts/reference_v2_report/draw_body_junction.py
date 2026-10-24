#!/usr/bin/env python3
"""Explain a measured simulated diffusion/well voltage, not an invented current."""
from pathlib import Path
import importlib.util,json,hashlib
ROOT=Path(__file__).resolve().parents[2];sp=importlib.util.spec_from_file_location('draw',ROOT/'scripts/highspeed_routes/circuits.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
OUT=ROOT/'docs/research/nrz-b-reference-power-20261024/figures';m.OUT=OUT
d=m.Drawing('掉电时的寄生 PN 结：为什么端压幅值通过仍不够','只展开 IPD2 的扩散区—n阱结及 IN2 外部补偿；并非新增器件，也不代替完整 PMOS 原理图',1030)
for off,label,forward in [(0,'正常供电：结反偏',False),(800,'RAW 掉电后：观察到正向结压',True)]:
 color=m.ORANGE if forward else m.BLUE;x=off+230;y=410
 d.text(off+60,190,label,24,color,True)
 d.text(x-90,280,'IN2.t1 / p+ 扩散区',20,m.PURPLE,True);d.text(off+530,280,'VIN.t6 / n阱',20,m.BLUE,True)
 d.text(x-40,325,'0.749006 V' if forward else 'IN2 低于 VIN',21,m.PURPLE,True);d.text(off+555,325,'0.002357 V' if forward else '约 5 V',21,m.BLUE,True)
 d.line([(x,y),(off+420,y)]);d.dot(x,y);d.p.append(f'<path d="M{off+420},380 L{off+420},440 L{off+470},410 Z" fill="white" stroke="{color}" stroke-width="3"/>');d.line([(off+475,376),(off+475,444)],color,3);d.line([(off+475,y),(off+690,y)],color);d.dot(off+640,y,color)
 d.text(off+405,475,'寄生 PN 结',19,color,True);d.text(off+385,510,'A：p+       K：n阱',18)
 d.line([(x,y),(x,570)]);d.line([(x-24,570),(x+24,570)]);d.line([(x-24,586),(x+24,586)]);d.line([(x,586),(x,700)]);d.ground(x,700);d.text(x+35,600,'150 pF',21,m.TEAL,True);d.text(x-65,752,'PCB GND',18,m.BLUE)
 if forward:
  d.arrow(off+340,545,off+585,545,m.ORANGE);d.text(off+350,585,'可能的储能释放路径',18,m.ORANGE)
  d.lines(off+360,660,['结压 = 0.746649 V','t = 21.173660 us','并未保存该结电流'],20,32)
 else:
  d.lines(off+360,620,['PMOS 的 n阱连接 VIN。','扩散区低于 n阱时，','该寄生结不正向导通。'],20,32)
d.line([(800,190),(800,795)],m.LIGHT,1.4)
d.box(48,815,1504,105,'从已验证事实到待验证机制',['已核对：扩散区、阱、RAW 与 DISABLE 的原始波形；>0.7 V 约1.400 us，仅描述时长，不是允许值。','尚待验证：结电流与电荷、井电阻/注入影响，以及掉电时主动释放补偿电荷的复位电路。'],size=18)
d.footer(['原始条件：VLED与2.5V基准保留；RAW在20–21us从5V降至0V，DISABLE保持高；绝对端压筛查不覆盖这一正向结风险。','IPD2 原D对应提取S=IN2.t1，B=VIN.t6；D/S互换有记录。图中箭头为机制推断，不是已测量的结电流。'])
r=d.save('body-junction-powerdown');p=OUT/'body-junction-powerdown.svg';p.write_text(p.read_text().replace('原创教学示意。候选架构，未经高速晶体管或版图仿真。器件端子和电流方向有明确标注。','从实际保存波形解释掉电风险的局部等效图；无新增电路或可靠性验收。'))
sources=[ROOT/'evidence/nrz-reference-v2/restart-body-review.json',ROOT/'analog/nrz_reference_v2/vi_reference_switched_keeper.spice']
(OUT/'body-junction-powerdown-manifest.json').write_text(json.dumps({'svg_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'sources':{str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sources},'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+'\n')
