#!/usr/bin/env python3
"""Draw actual B-v6 protection candidate; preserve earlier candidate generators."""
from pathlib import Path
import hashlib
import json
import sys
sys.dont_write_bytecode = True
import protection_candidates as c

d = c.d
ROOT, OUT = d.ROOT, d.OUT
CASE = ROOT / 'build/driver-interface-20261115/MicroLED/B-protected_v6/fault-f2-net1.6-s40'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    manifest = json.loads((CASE / 'manifest.json').read_text())
    deck = (CASE / 'testbench.spice').read_text()
    defs = {line.split()[0]: line.split() for line in deck.splitlines()
            if line and line[0] not in ['+', '*']}
    expected = {
        'XFASTOFF': ['iso_p', 'iso_gb', 'led_feed', 'led_feed'],
        'XCLAMP': ['led_a', 'disable', 'led_k', '0'],
        'XREADYRESET': ['ready_rc', 'disable', '0', '0'],
        'XNAND_PDATA': ['nand_o', 'data_gate', 'vdd', 'vdd'],
        'XNAND_PREADY': ['nand_o', 'ready_rc', 'vdd', 'vdd'],
        'XNAND_NDATA': ['nand_o', 'data_gate', 'nand_s', '0'],
        'XNAND_NREADY': ['nand_s', 'ready_rc', '0', '0'],
        'XSAFE_N': ['data_safe', 'nand_o', '0', '0'],
        'XSAFE_P': ['data_safe', 'nand_o', 'vdd', 'vdd'],
    }
    for name, nodes in expected.items():
        assert defs[name][1:5] == nodes, (name, defs[name])
    for k in range(3):
        assert defs[f'XISO{k}'][1:5] == ['led_a', 'iso_p', 'led_feed', 'led_feed']
        assert defs[f'XISO{k}'][6:8] == ['w=100u', 'l=0.7u']
    assert len(manifest['devices']) == 39
    assert defs['XFASTOFF'][6:8] == ['w=4u', 'l=0.7u']
    assert defs['RGATE'][1:] == ['iso_g', 'iso_p', '100k']
    assert defs['RREADY'][1:] == ['en', 'ready_rc', '100k']
    assert defs['CREADY'][1:] == ['ready_rc', '0', '1p']
    assert defs['XDATAIN'][1:] == ['d0', 'data_gate', '0', 'ppolyf_u_1k_6p0', 'r_width=4u', 'r_length=8u']
    assert defs['RD0'][1:] == ['data0_src', 'd0', '100']
    assert defs['XDRV'][1] == 'data_safe' and defs['XDRV'][8] == '0'
    assert 'RDISABLE' not in defs
    assert 'XRIN D0 DI VSS ppolyf_u_1k_6p0' in (CASE.parent / 'inputs/route_b.spice').read_text()

    c.begin(1840, 'B · protected_v6：输入阻尼与受控关断的实际电路',
            '39 MOS 候选；本图展开 READY、数据门控与功率栅控制。W/L 单位 µm；验证状态以数据报告为准。')
    c.box(110,370,'1｜READY：慢充允许、主动复位；开环 RC 不等于电源良好检测')
    d.text(65,205,'en = NOT(disable)',19); d.line(65,225,230,225)
    d.resistor(230,225,405,'RREADY 100 kΩ'); d.line(405,225,1150,225)
    d.dot(450,225); d.dot(706,225); d.text(1000,207,'ready_rc',21)
    d.cap(450,225,415,''); d.text(425,350,'CREADY 1 pF',18,'end'); d.ground(450,415)
    d.mos(670,330,False,'XREADYRESET','disable'); d.line(706,273,706,225)
    d.ground(706,387); c.label_size(defs,'XREADYRESET',723,356)
    d.text(900,320,'RC 量级 = 100 ns',19)
    d.text(900,351,'实际阈值由 MOS 决定',17)
    d.text(900,382,'首次数据允许时间须验证',17,c=d.GRAY)
    d.text(45,457,'disable 高时主动放电；disable 低时由 en 充电。参考源保持工作，保护由另加的高边隔离及钳位实现。',17,c=d.GRAY)

    c.box(500,170,'2｜新加两方块 PDK poly 电阻：限制 NAND 数据栅的边沿注入')
    d.text(55,594,'VD0 / data0_src',17); d.line(55,610,250,610)
    d.resistor(250,610,430,'既有 100 Ω'); d.line(430,610,560,610)
    d.text(480,591,'d0',19); d.resistor(560,610,810,'XDATAIN'); d.line(810,610,1180,610)
    d.text(850,591,'data_gate → NAND 两只 DATA 管栅',18)
    d.text(565,649,'ppolyf_u_1k_6p0；W = 4 µm，L = 8 µm；衬底接 VSS',17)

    c.box(690,620,'3｜静态 CMOS NAND + 反相器：READY 未建立时，data_safe 保持低')
    # Parallel PMOS / series NMOS NAND; named input nets connect above.
    d.line(236,770,1076,770); d.text(685,753,'vdd ≈ 3.3 V；PMOS 体接 vdd，NMOS 体接 VSS',18,'middle')
    d.mos(200,850,True,'XNAND_PDATA','data_gate'); d.line(236,793,236,770); d.line(236,907,236,960)
    c.label_size(defs,'XNAND_PDATA',253,877)
    d.mos(550,850,True,'XNAND_PREADY','ready_rc'); d.line(586,793,586,770); d.line(586,907,586,960)
    c.label_size(defs,'XNAND_PREADY',603,877)
    d.line(236,960,900,960); d.dot(386,960); d.dot(586,960); d.text(690,940,'nand_o',21)
    d.mos(350,1025,False,'XNAND_NDATA','data_gate'); d.line(386,968,386,960)
    c.label_size(defs,'XNAND_NDATA',403,1052)
    d.mos(350,1210,False,'XNAND_NREADY','ready_rc'); d.line(386,1082,386,1153)
    d.text(401,1121,'nand_s',18); d.ground(386,1267); c.label_size(defs,'XNAND_NREADY',403,1237)
    d.mos(1040,895,True,'XSAFE_P',''); d.mos(1040,1025,False,'XSAFE_N','')
    d.line(1076,952,1076,968); d.dot(1076,960); d.line(1076,838,1076,770); d.ground(1076,1082)
    d.line(986,895,965,895); d.line(965,895,965,1025); d.line(965,1025,986,1025)
    d.line(900,960,965,960); d.dot(965,960)
    c.label_size(defs,'XSAFE_P',1093,922); c.label_size(defs,'XSAFE_N',1093,1052)
    d.line(1076,960,1270,960); d.text(1165,940,'data_safe',21,'middle')
    d.text(790,1165,'data_safe → XDRV.D0 → 既有 XRIN → DI / GB / GP',17)
    d.text(790,1197,'原 XRIN 保留；XDATAIN 是额外阻尼，并未搬移 XRIN。',17)
    d.text(790,1229,'外部 PRBS 保持翻转；没有理想 AND 或免费延迟元件。',17)
    d.text(790,1261,'慢输入也会改变延迟及交越电流，不能预设一定省电。',17,c=d.GRAY)

    c.box(1330,380,'4｜XFASTOFF 由 W20 改为 W4：减小隔离管栅充电冲击，同时核对关断时间')
    d.line(716,1410,1146,1410); d.text(930,1392,'led_feed ≈ 5 V（两组 PMOS 的 S/B）',18,'middle')
    d.mos(680,1490,True,'XFASTOFF','iso_gb'); d.line(716,1433,716,1410); d.line(716,1547,716,1590)
    c.label_size(defs,'XFASTOFF',733,1517)
    d.text(55,1572,'电平转换器输出 iso_g',18); d.line(55,1590,250,1590)
    d.resistor(250,1590,490,'RGATE 100 kΩ'); d.line(490,1590,1000,1590); d.dot(716,1590)
    d.text(755,1620,'iso_p：实际功率管栅',18)
    d.mos(1110,1490,True,'XISO0..2',''); d.line(1146,1433,1146,1410); d.line(1146,1547,1146,1655)
    d.line(1000,1590,1000,1490); d.line(1000,1490,1056,1490)
    d.text(1163,1517,'每只 100 / 0.7',16); d.text(1163,1543,'3 只并联',16)
    d.text(1146,1680,'LED_A',20,'middle')
    d.text(45,1675,'iso_gb 低：快关上拉导通；iso_gb 高：上拉截止，iso_p 经 RGATE 慢放电。实际响应由波形判定。',17,c=d.GRAY)
    d.text(35,1750,'本图省略原参考源、输出核心与 6 MOS 电平转换；高边其余端接与 v3r 图相同，B 保护命令接口未添加 100 Ω。',17)
    d.text(35,1780,'LED_A / LED_K 保留 CLED = 200 fF；XCLAMP D/G/S/B = LED_A / disable / LED_K / VSS，W/L = 10/0.7。',17)
    d.text(35,1810,'新增电阻及 MOS 的耗能包含于原 7 个源的端口积分；本图仅证明连接对应实际候选网表，不代表 PVT、PEX 或流片资格。',17,c=d.GRAY)
    d.S.append('</svg>')
    svg = OUT / 'micro-protection-v6.svg'
    svg.write_text('\n'.join(d.S)+'\n')
    import cairosvg
    cairosvg.svg2png(url=str(svg),write_to=str(svg.with_suffix('.png')),scale=1.3)
    paths = [Path(__file__), Path(c.__file__), Path(d.__file__)]
    receipt = {
        'status': 'actual_candidate_schematic_not_qualification',
        'source_case': str(CASE.relative_to(ROOT)),
        'manifest_sha256': sha(CASE/'manifest.json'),
        'deck_sha256': sha(CASE/'testbench.spice'),
        'generator_sha256': sha(Path(__file__)),
        'generator_dependencies': {str(p.relative_to(ROOT)): sha(p) for p in paths},
        'MOS_count': len(manifest['devices']),
        'connections_checked': expected,
        'input_damping': defs['XDATAIN'],
        'fast_off': defs['XFASTOFF'],
        'source_ports': manifest['sources'],
        'scope': 'Actual B protected_v6: W4 fast-off, extra two-square PDK poly before NAND DATA, original XRIN retained; no new SPICE and no passing claim. Same named nets connect. Earlier W20 figures and scripts preserved.'
    }
    (OUT/'micro-protection-v6.source.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(svg)


if __name__ == '__main__':
    main()
