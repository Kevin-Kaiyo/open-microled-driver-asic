"""Original system diagrams and explicit design calculations; no new EDA claims."""
from pathlib import Path
import json, math, html
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/product-framework-20261014/figures'
OUT.mkdir(parents=True,exist_ok=True)
def svg(name,body,h=430):
    (OUT/name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 {h}"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6" fill="#426873"/></marker></defs><style>text{{font-family:Avenir Next,PingFang SC,sans-serif;fill:#244b56;font-size:18px}}.small{{font-size:15px}}.title{{font-size:21px;font-weight:600}}.box{{fill:#edf5f4;stroke:#44818a;stroke-width:1.6}}.pending{{fill:#fff8ee;stroke:#ae8452;stroke-dasharray:6 4;stroke-width:1.5}}.wire{{fill:none;stroke:#426873;stroke-width:2;marker-end:url(#arrow)}}</style>'+body+'</svg>')
def box(x,y,w,h,lines,pending=False):
    parts=[f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" class="'+('pending' if pending else 'box')+'"/>']
    for i,t in enumerate(lines):parts.append(f'<text x="{x+w/2}" y="{y+27+i*25}" text-anchor="middle">{html.escape(t)}</text>')
    return ''.join(parts)
def wire(points):return f'<path d="{points}" class="wire"/>'
body='<text x="20" y="25" class="title">目标系统：电源、信号、电流与光四条链路</text>'
body+=box(20,65,150,85,['主控 / FPGA','命令与时钟'])+box(210,65,175,85,['输入与寄存器','帧边界提交'],True)+box(425,65,160,85,['PWM逻辑','0…256 时槽'])+box(625,65,155,85,['保护门','输出buffer'])+box(820,65,160,85,['像素开关','MOUT gate'])
for a,b in [(170,210),(385,425),(585,625),(780,820)]:body+=wire(f'M{a},107 H{b}')
body+=box(20,220,210,85,['外部VSET / RSET','精密基准边界'])+box(270,220,230,85,['参考源 + 隔离','IREF → VBIAS'])+box(540,220,160,85,['MREF / MOUT','设定导通电流'])+box(740,220,240,85,['外接 MicroLED','电流 → 光响应'])
for a,b in [(230,270),(500,540),(700,740)]:body+=wire(f'M{a},263 H{b}')
body+=wire('M900,150 V185 H620 V220')
body+='<text x="20" y="350">LED主电流：VLED → LED → MOUT → VSS；逻辑输出主要搬运栅极电荷。</text><text x="20" y="380" class="small">虚线：目标硬件未实现；实线：已有部分电路或实验，不表示全系统已物理集成。</text><text x="20" y="405" class="small">供电稳压、POR、pad/ESD、封装、PCB、温度检测与光学测量也属于产品边界，尚需建立。</text>'
svg('system-architecture.svg',body)
body='<text x="20" y="28" class="title">电路要完成两种工作：设定电流，再决定何时送入LED</text>'
body+=box(25,75,250,85,['设定量：VSET / RSET','ISENSE ≈ 100 µA'])+box(375,75,250,85,['参考输出镜像','IREF → MREF → VBIAS'])+box(725,75,250,85,['像素镜像','ILED ≈ k · IREF'])
body+=wire('M275,117 H375')+wire('M625,117 H725')
body+=box(25,240,250,85,['时间量：duty / clock','Tframe = 256 / fCLK'])+box(375,240,250,85,['保护 / buffer / 开关','Gate连到BIAS或VSS'])+box(725,240,250,85,['输出积分','Iavg = QLED / Tframe'])
body+=wire('M275,282 H375')+wire('M625,282 H725')+wire('M850,160 V240')
body+='<text x="25" y="385" class="small">镜像比、headroom、失配、动态寄生会造成误差；电气平均电流不是已测光输出。</text>'
svg('current-and-time.svg',body,420)
body='<text x="20" y="28" class="title">从设计到硅片：每一步有不同的输入、输出和验收</text>'
labels=[['需求 / 测试规范','电流、时序、LED、接口'],['RTL / 原理图','逻辑功能与MOS网络'],['综合 / 布局布线','几何、供电、时钟'],['提取 / 复验','RC、时序、电流、故障'],['流片冻结 / 制造接受','GDS、报告、manifest'],['封装 / 测试 / 关联','引脚、PCB、实测与模型']]
for i,l in enumerate(labels):
    x=20+(i%3)*330;y=70+(i//3)*165
    body+=box(x,y,290,90,l)
    if i%3<2:body+=wire(f'M{x+290},{y+45} H{x+330}')
body+=wire('M970,160 V204 H165 V235')
body+='<text x="20" y="375">测试计划在需求阶段定义；流片前要能说明每一项性能怎样测、怎样判定。</text><text x="20" y="405" class="small">当前：旧核心已有版图，新参考和保护主要为前仿真；最终制造包仍为空。</text>'
svg('development-flow.svg',body)
calcs={
 'scope':'独立教学计算，不是新GF180仿真、光学测量或工艺额定值',
 'pwm':{'clock_hz':1e6,'slots':256,'frame_s':256e-6,'frame_hz':1e6/256,'d1_high_s':1e-6,'nominal_current_a':100e-6,'d1_ideal_charge_c':100e-12,'d64_average_a':25e-6},
 'driver_scale':{'assumed_C_F':1e-12,'assumed_delta_v_V':1,'assumed_edge_s':100e-12,'charge_C':1e-12,'average_edge_current_A':.01},
 'link_scale':{'bitrate_bps':1e9,'UI_s':1e-9,'assumed_edge_UI':.2,'edge_s':.2e-9,'single_pole_bw_Hz':.35/.2e-9,'note':'single pole 10-90 approximation, not arbitrary complete link rate requirement'},
 'bondwire_scale':{'assumed_L_H':1e-9,'delta_I_A':.007,'edge_s':100e-12,'Ldi_dt_V':.07},
 'zero_error_binomial':{'target_BER':1e-12,'confidence':.95,'bits_approx':-math.log(.05)/1e-12,'time_s_at_1Gbps':-math.log(.05)/1e-12/1e9,'note':'independent Bernoulli stationary errors, zero errors; approximate one-sided confidence upper bound'},
 'sense':{'R_ohm':100,'vset_low_V':.01,'vset_high_V':.7,'min_A':.0001,'max_A':.007,'power_at_max_W':.0049,'offset_V':.0001,'offset_error_A':1e-6},
 'mim':{'assumed_C_fF':3000,'assumed_density_fF_um2':[1,1.5],'plate_area_um2':[3000,2000],'not_included':'edge,contacts,keepout,accepted-device selection'},
}
(OUT.parent/'calculations.json').write_text(json.dumps(calcs,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'figures':3,'calculation_groups':len(calcs)-1}))
