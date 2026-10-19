"""Reproduce the audited six-MOS/GDS mapping used by the Blender animation.

This is the original inline mapping generator, extracted into a CLI without
changing its output schema or electrical narrative. It does not overwrite the
final mapping unless a caller explicitly chooses that directory and --overwrite.

Run with the existing KLayout environment, for example:
  build/layout/venv/bin/python scripts/blender_animation/prepare_mapping.py \
      --output-dir build/blender-pwm-animation/mapping-reproduction \
      --compare-existing build/blender-pwm-animation/mapping.json
"""
import argparse
import hashlib
import json
from pathlib import Path

import klayout.db as k

ROOT = Path(__file__).resolve().parents[2]


def generate():
    R = ROOT
    c = json.loads((R/'layout/startup_v3/contract.json').read_text())
    g = json.loads((R/'build/blender-demo/geometry-3d.json').read_text())
    s = json.loads((R/'evidence/layout-v3/r5/summary.json').read_text())
    sha = lambda p: hashlib.sha256((R/p).read_bytes()).hexdigest()
    sources = [
        'layout/startup_v3/contract.json',
        'layout/startup_v3/startup_test_macro.spice',
        'scripts/layout_v3/generate.py',
        'scripts/layout/generate_pixel.tcl',
        'analog/driver/pixel_driver.spice',
        'analog/startup_v2/reference_isolator_tg.spice',
        'analog/safety/fault_gate.spice',
        'analog/safety/fault_led_clamp.spice',
        'layout/startup_v3/external-circuit-v3.json',
        'evidence/layout-v3/r5/startup_test_macro.gds',
        'evidence/layout-v3/r5/summary.json',
        'build/blender-demo/geometry-3d.json',
        'build/blender-demo/stack-audit.json',
        'build/layout/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.tech',
    ]
    for p in sources[:3]:
        assert sha(p) == s['source_sha256'][p], ('r5 frozen source changed', p)
    assert sha('evidence/layout-v3/r5/startup_test_macro.gds') == g['gds_sha256']
    ly = k.Layout()
    ly.read(str(R/'evidence/layout-v3/r5/startup_test_macro.gds'))
    top = ly.top_cell()
    db = ly.dbu
    regions = {n: k.Region(top.begin_shapes_rec(ly.layer(n, 0))).merged()
               for n in [22, 30, 33, 34, 35, 36, 38, 42]}

    def box(x, y, e=.005):
        return k.Box(round((x-e)/db), round((y-e)/db),
                     round((x+e)/db), round((y+e)/db))

    def contains(n, x, y):
        return (k.Region(box(x, y))-regions[n]).is_empty()

    def covered(n, xy1, xy2):
        b = k.Box(round((min(xy1[0], xy2[0])-.005)/db),
                  round((min(xy1[1], xy2[1])-.005)/db),
                  round((max(xy1[0], xy2[0])+.005)/db),
                  round((max(xy1[1], xy2[1])+.005)/db))
        return (k.Region(b)-regions[n]).is_empty()

    contacts = []
    for p in g['polygons']:
        if p['layer'] != 33:
            continue
        pts = p['points']
        contacts.append(dict(
            x_um=sum([min(a[0] for a in pts), max(a[0] for a in pts)])/2,
            y_um=sum([min(a[1] for a in pts), max(a[1] for a in pts)])/2,
            layer=33, landing_layer=p['landing_layer'],
            source_polygon_index=p['source_polygon_index'],
            z_nominal_um=p['z_nominal_um'],
            thickness_nominal_um=p['thickness_nominal_um']))

    roles = {
        'P_REF': ('MREF', '参考镜像管', 'NMOS', '二极管连接，D 与 G 同接 BIAS；把参考支路电流转换成栅源电压。'),
        'P_OUT': ('MOUT', 'LED 恒流下拉管', 'NMOS', 'D 接 LED_K；G 接 GATE；栅压与 MREF 相同时近似复制参考电流，需满足饱和区与电压余量。'),
        'P_PASS': ('MPASS', '栅压传递开关', 'NMOS', 'PWM_DRIVE 高电平时把 BIAS 接到 GATE；承载栅极充放电瞬态，不是 LED 主电流串联开关。'),
        'P_CLAMP': ('MCLAMP', '栅极放电管', 'NMOS', 'PWM_B 高电平时把 GATE 拉到 VSS，使 MOUT 关断。'),
        'P_INV_N': ('MINV_N', '反相器下拉管', 'NMOS', 'PWM_DRIVE 高时拉低 PWM_B，关闭 MCLAMP。'),
        'P_INV_P': ('MINV_P', '反相器上拉管', 'PMOS', 'PWM_DRIVE 低时拉高 PWM_B，打开 MCLAMP。'),
    }
    devices, checks = {}, []
    for d in c['devices']:
        if d['name'] not in roles:
            continue
        name, x, y = d['name'], d['cx'], d['cy']
        dx = d['l']/2+.26
        pinxy = {'D': [x-dx, y], 'G': [x, y-d['w']/2-.28],
                 'S': [x+dx, y], 'B': [x-max(3.5, d['l']/2+2.5), y]}
        pins = {}
        for pin, node in zip('DGSB', d['nodes']):
            xy = pinxy[pin]
            bx, by = xy[0], c['buses_um'][node]
            for layer in [34, 35, 36]:
                assert contains(layer, *xy), (name, pin, layer, xy)
            for layer in [36, 38, 42]:
                assert contains(layer, bx, by), (name, pin, layer, bx, by)
            assert covered(36, xy, [bx, by])
            assert covered(42, [bx, by], [c['port_anchor_um'][node], by])
            comp = regions[34].interacting(k.Region(box(*xy)))
            matches = [p for p in contacts if
                       (k.Region(box(p['x_um'], p['y_um']))-comp).is_empty()]
            matches.sort(key=lambda p: (
                round((p['x_um']-xy[0])**2+(p['y_um']-xy[1])**2, 8), -p['y_um']))
            ct = matches[0]
            assert ct['landing_layer'] == (30 if pin == 'G' else 22), (name, pin, ct)
            pins[pin] = dict(
                net=node, metal1_via1_xy_um=xy, metal2_via2_xy_um=[bx, by],
                metal3_port_xy_um=[c['port_anchor_um'][node], by],
                nearest_actual_contact=ct,
                route_from_device_to_bus=[
                    {'layer': 34, 'xy_um': xy}, {'layer': 35, 'xy_um': xy},
                    {'layer': 36, 'xy_um': xy}, {'layer': 36, 'xy_um': [bx, by]},
                    {'layer': 38, 'xy_um': [bx, by]}, {'layer': 42, 'xy_um': [bx, by]}],
                metal1_to_contact_caution='M1 金属面内连接到选定实际 Contact；动画采用中心线示意，不代表全部并联接触孔电流密度。')
            checks.append(dict(device=name, pin=pin, via1_landing=True,
                               via2_landing=True, metal2_centerline_covered=True,
                               metal3_to_port_covered=True,
                               contact_in_same_metal1_component=True))
        label, zh, typ, role = roles[name]
        devices[name] = dict(instance='X'+name, layout_name=name,
                             schematic_label=label, label_zh=zh, type=typ,
                             role_zh=role, model=d['model'], w_um=d['w'],
                             l_um=d['l'], center_um=[x, y], terminals=pins)

    z = {n: (g['layers'][str(n)]['z_nominal_um'] +
             .5*g['layers'][str(n)]['thickness_nominal_um'])
         for n in [22, 30, 34, 35, 36, 38, 42]}

    def pt(x, y, n, label=''):
        return dict(x_um=x, y_um=y, layer=n, z_nominal_um=z[n], label_zh=label)

    def down(name, pin, anchor=True):
        p = devices[name]['terminals'][pin]
        x, y = p['metal1_via1_xy_um']
        bx, by = p['metal2_via2_xy_um']
        ct = p['nearest_actual_contact']
        cx, cy = ct['x_um'], ct['y_um']
        arr = []
        if anchor:
            arr.append(pt(*p['metal3_port_xy_um'], 42, p['net']+' 端口'))
        arr += [pt(bx, by, 42), pt(bx, by, 38, 'Via2'), pt(bx, by, 36),
                pt(x, y, 36), pt(x, y, 35, 'Via1'), pt(x, y, 34),
                pt(cx, y, 34), pt(cx, cy, 34),
                dict(x_um=cx, y_um=cy, layer=33,
                     z_nominal_um=ct['z_nominal_um']+.5*ct['thickness_nominal_um'],
                     label_zh='接触孔 Contact'),
                pt(cx, cy, ct['landing_layer'], pin+' 端')]
        return arr

    def channelpath(name):
        d = devices[name]
        a, b = down(name, 'D'), down(name, 'S')
        x, y = d['center_um']
        cp = [pt(x, a[-1]['y_um'], 22, d['schematic_label']+' 沟道（示意）')]
        return a+cp+list(reversed(b))

    paths = {
        'led_high': dict(
            label_zh='PWM 高：LED 常规电流',
            active_when='FAULT=0, PERMIT=1, PWM_DRIVE=1; reference settled; adequate LED headroom',
            points=channelpath('P_OUT'), start_net='LED_K', end_net='VSS',
            conventional_direction='LED_A → 片外 MicroLED → LED_K → MOUT 漏极 → 导通沟道 → 源极 → VSS',
            scope='points 仅描述 LED_K 端口之后的实际片内路径；LED_A→片外LED→LED_K 必须单独画成片外示意引线，不属于 GDS。'),
        'reference': dict(
            label_zh='高、低电平均有参考支路电流',
            active_when='FAULT=0; reference settled; PWM_DRIVE may be 0 or 1',
            points=channelpath('P_REF'), start_net='BIAS', end_net='VSS',
            conventional_direction='VREF → 参考电流源 → REFOUT → 导通隔离传输门 → BIAS → MREF → VSS',
            scope='points 从 BIAS 总线到 MREF，未绘制上游参考源与隔离传输门完整路径。'),
        'gate_discharge_low_edge': dict(
            label_zh='下降沿：GATE 栅极电容放电',
            active_when='transition to PWM_DRIVE=0 only, not steady DC',
            points=channelpath('P_CLAMP'), start_net='GATE', end_net='VSS',
            scope='有界瞬态电荷移动，必须在低电平稳定阶段停止粒子；不表示 LED 稳态电流。'),
        'pass_gate_charge_high_edge': dict(
            label_zh='上升沿：BIAS 经 MPASS 给 GATE 充电',
            active_when='transition to PWM_DRIVE=1 only, not steady DC',
            points=channelpath('P_PASS'), start_net='BIAS', end_net='GATE',
            scope='P_PASS 的导通通道传递栅压，稳态MOS栅极近似无直流电流；不能持续画电流进入MOUT栅极。'),
    }
    paths['gate_voltage_control'] = dict(
        label_zh='GATE 电压控制 MOUT', points=down('P_OUT', 'G'),
        start_net='GATE', end_net='P_OUT.G',
        kind='voltage-only dashed line; no DC-flow particles')
    states = {
        'high': dict(
            condition='FAULT=0, PERMIT=1, reference settled, PWM_DRIVE=VBUF≈3.3V',
            PWM_B='≈0 V', GATE='≈BIAS', device_states={
                'P_REF': '导通（二极管连接）',
                'P_OUT': '导通，设计目标约100µA；有限电压余量决定实际值',
                'P_PASS': '导通/栅压连通；稳态近似无栅极直流',
                'P_CLAMP': '关断',
                'P_INV_N': '导通，PWM_B≈0V；稳定后不表示持续大电流',
                'P_INV_P': '关断'},
            active_dc_paths=['led_high', 'reference'],
            brief_transition_paths=['pass_gate_charge_high_edge']),
        'low': dict(
            condition='FAULT=0, PERMIT=1, reference settled, PWM_DRIVE≈0V',
            PWM_B='≈VBUF', GATE='≈0 V', device_states={
                'P_REF': '仍导通，参考偏置保持',
                'P_OUT': '关断，仅漏电/寄生瞬态',
                'P_PASS': '关断，隔离BIAS和GATE',
                'P_CLAMP': '导通，将GATE保持在VSS；放电结束后近似无直流',
                'P_INV_N': '关断',
                'P_INV_P': '导通，PWM_B≈VBUF；稳定后不表示持续大电流'},
            active_dc_paths=['reference'],
            brief_transition_paths=['gate_discharge_low_edge']),
        'fault_caveat': dict(
            condition='FAULT=1 或 PERMIT=0 与普通 PWM 低电平不同',
            description='实际上游保护使 SAFE_OUT=RAW_PWM AND PERMIT AND NOT FAULT，经 buf_2 得 PWM_DRIVE。FAULT=1 还关断参考隔离传输门、释放BIAS并打开LED端保护钳位；普通 PWM=0 不关闭参考支路。动画本轮正常高低电平必须显示 FAULT=0、PERMIT=1。'),
    }
    return dict(
        schema=1,
        scope='r5 模拟测试宏中的六只像素MOS；真实XY/层连接+概念电流方向，可视化不产生新电气验证',
        gds_sha256=g['gds_sha256'],
        units='XY and unscaled nominal Z: micrometres',
        terminal_order='D G S B as in SPICE source; layout D/S naming follows source and placement',
        source_sha256={p: sha(p) for p in sources},
        source_integrity={'contract_generator_schematic_match_r5_snapshot': True,
                          'gds_matches_geometry3d': True},
        six_mos_is_not_an_industry_standard_topology_name=True,
        devices=devices,
        ports={n: dict(x_um=c['port_anchor_um'][n], y_um=c['buses_um'][n],
                       layer=42, z_nominal_um=z[42])
               for n in ['LED_A', 'LED_K', 'VSS', 'BIAS', 'GATE', 'PWM_B', 'PWM_DRIVE', 'VBUF']},
        paths=paths, states=states, layer_stack=g['layers'], checks=checks,
        limitations=[
            'Blender 中层展开间距与垂直夸张只为教学，不能称为真实制造厚度。名义高度来自锁定 Magic technology height 注释，不是经晶圆厂认证的截面。',
            'GDS XY、实际 Contact 与 Via 布置有来源；电流动画采用导线中心线和单个代表接触孔，不是 PEX 电流密度、TCAD、EM、电热或电磁场仿真。',
            '栅极电压传递不等于栅极持续直流；PWM 高低的静态模型忽略传播延迟和过渡重叠，瞬态数值以已有SPICE报告为准。',
            'LED_A 片上端口还接故障保护钳位；正常 FAULT=0 时该钳位关断。LED 光输出、LED实物、封装与供电引线均不在此GDS中。',
            '六管指这次独立像素电路的6只MOS，r5模拟测试宏共39只MOS（另有参考、保护和6MOS缓冲器）。',
            'contract.json 的历史external_passives字段写CCOMP=3pF；最终电气合同以 external-circuit-v3.json 的30pF+10Mohm为准，均不在GDS。'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='Separate reproduction directory; final directory is not assumed.')
    parser.add_argument('--compare-existing', type=Path,
                        help='Optional reference JSON; comparison is full decoded JSON equality.')
    parser.add_argument('--overwrite', action='store_true',
                        help='Explicitly replace an existing output mapping, never the comparison input.')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    target = out/'mapping.json'
    if args.compare_existing and target == args.compare_existing.resolve():
        parser.error('Output and comparison input must be different files.')
    if target.exists() and not args.overwrite:
        parser.error(f'{target} already exists; choose another directory or explicit --overwrite.')
    data = generate()
    out.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    result = dict(schema=1, origin='Original inline Python generator extracted without a mapping-schema change.',
                  output=str(target), devices=len(data['devices']),
                  verified_terminal_routes=len(data['checks']),
                  output_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                  generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    if args.compare_existing:
        reference = args.compare_existing.resolve()
        reference_data = json.loads(reference.read_text())
        result.update(reference=str(reference),
                      reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
                      semantic_equal=(data == reference_data),
                      byte_equal=(target.read_bytes() == reference.read_bytes()))
    (out/'mapping-reproduction.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))
    if args.compare_existing and not result['semantic_equal']:
        raise SystemExit('Mapping changed: inspect mapping-reproduction.json; final input was not overwritten.')


if __name__ == '__main__':
    main()
