#!/usr/bin/env python3
"""Original schematic figures for the NRZ PVT experiment; not simulated geometry."""
from pathlib import Path
import importlib.util
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/research/highspeed-nrz-pvt-20261023/figures'
spec = importlib.util.spec_from_file_location('drawing', ROOT/'scripts/highspeed_routes/circuits.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.OUT = OUT

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = m.Drawing('快冷过冲：输入边沿通过寄生电容推高内部节点',
                  '原理解释图｜用 Cgd 表示器件耦合路径；布线耦合也在 RC 仿真中，尚未独立分解各电容贡献', 1040)
    d.text(500, 185, 'VDD = 3.6 V', 22, m.BLUE, True, 'middle')
    d.line([(500,200),(500,258)],m.BLUE)
    d.mos(500,310,'P1',['N1 / GB','DATA','VDD','VDD'],True,m.BLUE)
    d.mos(500,550,'N1',['N1 / GB','DATA','VSS','VSS'],False,m.TEAL)
    d.line([(500,362),(500,498)],m.TEAL); d.dot(500,430,m.TEAL)
    d.line([(500,602),(500,635)]); d.ground(500,635)
    d.line([(170,430),(330,430),(330,310),(438,310)],m.PURPLE)
    d.line([(330,430),(330,550),(438,550)],m.PURPLE); d.dot(330,430,m.PURPLE)
    d.text(65,405,'DATA',23,m.PURPLE,True)
    d.text(65,462,'0 → 3.6 V',19,m.PURPLE)
    d.text(65,492,'外部边沿 20 ps',18,m.MUTE)
    d.line([(500,430),(920,430),(920,550),(1018,550)],m.TEAL)
    d.dot(760,430,m.TEAL)
    d.mos(1080,550,'N2',['CTRL / GP','N1 / GB','VSS','VSS'],False,m.ORANGE)
    d.line([(1080,602),(1080,635)]);d.ground(1080,635)
    d.line([(1080,498),(1080,465)]);d.text(1115,470,'后级输出',18,m.MUTE)
    d.text(1108,623,'B = VSS',18,m.MUTE)
    d.text(550,280,'B = VDD',18,m.MUTE);d.text(550,606,'B = VSS',18,m.MUTE)
    d.text(760,473,'A：N1；B：GB',20,m.TEAL,True,'middle')
    d.line([(330,310),(330,225),(630,225)],m.PURPLE,2,'7 5')
    d.line([(630,205),(630,245)],m.PURPLE)
    d.line([(646,205),(646,245)],m.PURPLE)
    d.line([(646,225),(760,225),(760,430)],m.PURPLE,2,'7 5')
    d.text(650,180,'等效 Cgd',20,m.PURPLE,True)
    d.arrow(380,250,590,250,m.PURPLE)
    d.text(800,270,'位移电流：i ≈ Cgd · dVDATA/dt',21,m.PURPLE)
    d.text(800,315,'电荷先注入 N1 / GB；',21)
    d.text(800,350,'下拉导通后，节点才转向下降。',21)
    d.text(970,700,'检查 VGB = VG − VB',23,m.ORANGE,True)
    d.lines(64,737,[
        '① 切换前：DATA = 0，P1 导通，内部节点接近 VDD。',
        '② 输入快速上升：电容耦合产生向上的短暂电压尖峰；后一级栅极承受此尖峰。',
        '③ N1 导通后：内部节点放电，完成正常逻辑翻转。实际峰值还取决于驱动强度和节点负载。'
    ],21,38)
    d.footer(['示意省略后级 PMOS，其完整连接在电路网表中；端子 B 的连接已逐管标注。',
              'Cgd 已在 MOS 模型中，没有额外重复添加。3.63 V 为项目筛查线，不是晶圆厂可靠性批准。'])
    d.save('feedthrough-principle')
    path=OUT/'feedthrough-principle.svg'
    path.write_text(re.sub(r'<desc>.*?</desc>', '<desc>前级 CMOS 反相器栅漏寄生电容引起内部节点过冲的原理示意。非物理版图。</desc>', path.read_text(), flags=re.S))
    revision()
    substrate()

def revision():
    d=m.Drawing('修改点：输入端工艺电阻与独立偏置供电',
                '电路修改示意｜高速路径中的其余 MOS 连接和尺寸保持旧版；完整连接由网表与 LVS 核对',1350)
    d.text(55,180,'两条路线共同修改：DATA → RIN → DI → 原前置驱动器',25,m.TEAL,True)
    d.text(70,370,'DATA',22,m.PURPLE,True)
    d.line([(70,400),(225,400)],m.PURPLE)
    d.p.append(f'<rect x="225" y="385" width="100" height="30" fill="white" stroke="{m.TEAL}" stroke-width="2.7"/>')
    d.line([(325,400),(490,400),(490,300),(578,300)],m.PURPLE)
    d.line([(490,400),(490,540),(578,540)],m.PURPLE)
    d.dot(490,400,m.PURPLE)
    d.text(272,350,'RIN',23,m.TEAL,True,'middle')
    d.lines(70,478,['ppolyf_u_1k_6p0','W = 1 µm；A: L = 48 µm','B: L = 58 µm；SUB = VSS'],19,31,m.TEAL)
    d.text(440,370,'DI',22,m.PURPLE,True)
    d.mos(640,300,'P1',['N1 / GB','DI','VDD','VDD'],True,m.BLUE)
    d.mos(640,540,'N1',['N1 / GB','DI','VSS','VSS'],False,m.ORANGE)
    d.line([(640,248),(640,222)],m.BLUE);d.text(640,210,'VDD',21,m.BLUE,True,'middle')
    d.line([(640,352),(640,488)]);d.dot(640,420)
    d.line([(640,592),(640,620)]);d.ground(640,620)
    d.lines(680,330,['W/L = 2/0.28 µm','B = VDD'],17,26,m.MUTE)
    d.lines(680,570,['W/L = 1/0.28 µm','B = VSS'],17,26,m.MUTE)
    d.line([(640,420),(950,420)],m.PURPLE)
    d.box(950,365,290,110,'原 INV2',[ '输出 CTRL / GP' ],m.PURPLE)
    d.text(770,399,'N1 / GB',21,m.PURPLE,True)
    d.text(55,650,'RIN 的实际模型还含分段电阻、温度系数和对衬底电容；这些均计入仿真。',21)
    d.box(1020,190,520,130,'阻尼的收益与代价',['降低 DI 的变化率，减小电容耦合尖峰；','增加延迟和边沿时间，必须重测速率余量。'],m.TEAL,size=18)
    d.text(1290,418,'→ 输出级',20,m.ORANGE,True)
    d.line([(1240,420),(1280,420)],m.ORANGE)
    d.line([(48,695),(1552,695)],m.LIGHT,1.5)
    d.text(55,750,'仅路线 B：RREF 从逻辑 VDD 改接已有 VDUMMY = 3.3 V',25,m.TEAL,True)
    d.text(320,813,'VDUMMY = 3.3 V',22,m.TEAL,True,'middle')
    d.line([(320,828),(320,850)],m.TEAL)
    d.resistor(320,894,'RREF = 88.386106 kΩ',m.TEAL)
    d.line([(320,938),(320,1028)],m.TEAL);d.dot(320,980,m.TEAL)
    d.mos(320,1080,'REF',['BIAS','BIAS','VSS','VSS'],False,m.TEAL)
    d.line([(258,1080),(235,1080),(235,980),(320,980)],m.PURPLE)
    d.line([(320,1132),(320,1155)]);d.ground(320,1155)
    d.line([(320,980),(750,980)],m.PURPLE)
    d.text(640,955,'BIAS',22,m.PURPLE,True)
    d.box(750,917,735,147,'连接不变的电流镜',['REF：D = G = BIAS，S = B = VSS，W/L = 2/1 µm。',
        'BASE 与 TAIL 的 G 接 BIAS，分别建立基线与转向电流。',
        'BASE W/L = 2/1 µm；TAIL W/L = 5.76/1 µm。'],m.TEAL,size=18)
    d.text(750,1110,'IREF ≈ (VDUMMY − VGS,REF) / RREF',23,m.TEAL,True)
    d.text(750,1150,'减小逻辑电源变化的影响，仍保留器件温度／工艺依赖。',20)
    d.footer(['VDUMMY 供电与输入激励的全部取能均参与能耗统计；本修改没有实现片内稳压器或温补基准。',
              '此图只展开改动处；其余 MOS 的完整原理图、器件表、新 GDS 和提取网表在报告中分别链接。'])
    d.save('revision-schematic')
    path=OUT/'revision-schematic.svg'
    path.write_text(re.sub(r'<desc>.*?</desc>', '<desc>实际候选电路修改处：两路线加入三端工艺电阻，B的参考电阻改接已有固定3.3V电源。其余电路未展开。</desc>', path.read_text(), flags=re.S))

def substrate():
    d=m.Drawing('为什么加一个输入电阻，还必须设计它的衬底接地？',
                '局部等效电路｜工艺电阻有第 3 端 SUB；这里只展开寄生电容的返回路径，不能把 SUB 当作永远为零的理想节点',1100)
    d.text(70,205,'DATA 快速下降',24,m.PURPLE,True)
    d.line([(85,250),(480,250)],m.PURPLE)
    d.p.append(f'<rect x="480" y="235" width="105" height="30" fill="white" stroke="{m.TEAL}" stroke-width="2.7"/>')
    d.line([(585,250),(1020,250)],m.PURPLE)
    d.text(535,205,'RIN 的电阻路径',21,m.TEAL,True,'middle')
    d.text(1040,257,'DI → 前置驱动器',22,m.PURPLE,True)
    d.dot(220,250,m.PURPLE);d.line([(220,250),(220,350)],m.PURPLE)
    d.line([(188,350),(252,350)],m.PURPLE);d.line([(188,368),(252,368)],m.PURPLE)
    d.line([(220,368),(220,490),(570,490)],m.PURPLE)
    d.text(280,352,'Csub：工艺模型的对衬底电容',21,m.PURPLE)
    d.text(280,390,'图示为合并说明，实际模型含多个 RC 分段。',18,m.MUTE)
    d.dot(570,490,m.ORANGE);d.text(590,475,'电阻局部 SUB',22,m.ORANGE,True)
    d.line([(570,490),(570,566)],m.ORANGE)
    d.resistor(570,610,'衬底／接触返回电阻',m.ORANGE)
    d.line([(570,654),(570,760)]);d.ground(570,760)
    d.text(600,755,'VSS 端口',20,m.MUTE)
    d.arrow(180,450,180,395,m.PURPLE)
    d.lines(65,560,['下降沿从衬底端抽取位移电流；',
        '返回路径有阻抗，就会产生', 'ΔVB ≈ iC × Zreturn。'],21,34,m.ORANGE)
    d.line([(570,490),(1060,490),(1060,566)],m.TEAL)
    d.resistor(1060,610,'新增衬底接触与接地金属',m.TEAL)
    d.line([(1060,654),(1060,760)],m.TEAL);d.ground(1060,760)
    d.text(1090,755,'低阻返回路径',20,m.TEAL,True)
    d.lines(840,830,['首次版图的具体失效：',
       'CTRL = 3.595125 V，MOS 体端 B = −0.111542 V；',
       '|VCTRL − VB| = 3.706667 V。'],22,36,m.ORANGE)
    d.lines(65,830,['检查端子之间的电压，而非只看对地波形。',
        'C-only 把衬底网络视为等电位；',
        '完整 RC 才暴露这条返回路径的影响。'],22,36)
    d.footer(['新增接触是版图中的实际 p+ 衬底接触与金属连接；不能用仿真里把体端短接理想地替代最终验证。',
              '数值来自当前公开 PDK 提取模型，不是实测硅片衬底阻抗；高频衬底模型的准确性仍待独立验证。'])
    d.save('substrate-return-principle')
    path=OUT/'substrate-return-principle.svg'
    path.write_text(re.sub(r'<desc>.*?</desc>', '<desc>工艺电阻衬底寄生电容和有限接地返回路径的等效电路，以及新增衬底接触的作用。</desc>',path.read_text(),flags=re.S))

if __name__ == '__main__': main()
