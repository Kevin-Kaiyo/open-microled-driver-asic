"""Independent Blender scene checks; not electrical or manufacturing signoff.
Run: Blender --background --python scripts/blender_animation/validate.py
"""
from collections import Counter
from pathlib import Path
import bpy
import hashlib
import json
import math
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/research/blender-pwm-animation-20261018'
EVIDENCE = ROOT / 'evidence/blender-pwm-animation'
EVIDENCE.mkdir(parents=True, exist_ok=True)
GEOMETRY = ROOT / 'build/blender-demo/geometry-3d.json'
MAPPING = ROOT / 'build/blender-pwm-animation/mapping.json'
BLEND = OUT / 'pwm-layer-animation.blend'
D = json.loads(GEOMETRY.read_text())
M = json.loads(MAPPING.read_text())
T = json.loads((OUT / 'timeline.json').read_text())
checks = []
def check(name, ok, **detail):
    checks.append(dict(name=name, passed=bool(ok), **detail))
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def canon(xy):
    return tuple(sorted((round(float(x) * 1000), round(float(y) * 1000)) for x, y in xy))
def in_ranges(f, ranges):
    return any(a <= f <= b for a, b in ranges)

bpy.ops.wm.open_mainfile(filepath=str(BLEND))
sc = bpy.context.scene
check('GDS hash scene/mapping/geometry', sc.get('source_gds_sha256') == M['gds_sha256'] == D['gds_sha256'])
check('Animation duration / frame rate', sc.frame_start == 1 and sc.frame_end == 1536 and sc.render.fps == 24)
check('Explicit geometry and teaching scope', sc.get('nominal_z_scale') == 12 and '非' in sc.get('scope', ''))

# Recover each original XY polygon from a prism's downward-facing base. Keep a
# multiset so duplicate source polygons cannot disappear behind a set comparison.
full = {int(o['gds_layer']): o for o in bpy.data.objects if o.name.startswith('完整模拟宏 / ') and 'gds_layer' in o}
pixel = {int(o['gds_layer']): o for o in bpy.data.objects if o.name.startswith('像素局部 / ') and 'gds_layer' in o}
source = Counter((p['layer'], canon(p['points'])) for p in D['polygons'])
actual = Counter()
for layer, obj in full.items():
    for face in obj.data.polygons:
        zs = [obj.data.vertices[i].co.z for i in face.vertices]
        if face.normal.z < -0.999 and max(zs) - min(zs) < 1e-5:
            actual[(layer, canon([(obj.data.vertices[i].co.x, obj.data.vertices[i].co.y) for i in face.vertices]))] += 1
check('Full macro exact selected GDS XY polygon multiset at 1 nm quantization', actual == source,
      source_polygons=sum(source.values()), scene_prisms=sum(actual.values()),
      missing_polygons=sum((source - actual).values()), extra_polygons=sum((actual - source).values()),
      quantization_um=0.001)
check('All ten selected layer groups included', set(full) == set(pixel) == {21, 204, 22, 30, 33, 34, 35, 36, 38, 42})

# Independently specified teaching story, not derived from the saved curves.
steps = [(42, 73, 144, 150), (38, 145, 192, 125), (36, 193, 240, 100),
         (35, 241, 288, 75), (34, 289, 336, 50), (33, 337, 384, 25), (30, 385, 432, 10)]
for layer, start, finish, displacement in steps:
    obj = full[layer]
    for frame, expected in [(1, 0), (start, 0), (finish, displacement), (528, displacement), (600, 0)]:
        sc.frame_set(frame)
        check(f'Layer {layer} frame {frame} teaching offset', abs(obj.location.z - expected) < 1e-5,
              z_offset_um=float(obj.location.z), expected_display_offset_um=expected)
    vals = []
    for frame in range(start, finish + 1):
        sc.frame_set(frame); vals.append(obj.location.z)
    check(f'Layer {layer} unfolds monotonically', all(a <= b + 1e-5 for a, b in zip(vals, vals[1:])))
for layer in [21, 204, 22]:
    for frame in [1, 432, 528, 600]:
        sc.frame_set(frame)
        check(f'Layer {layer} stays at device baseline frame {frame}', full[layer].location.length < 1e-5)
for frame in [1, 500, 600, 601, 720, 1040, 1536]:
    sc.frame_set(frame)
    check(f'Full/crop swap frame {frame}',
          all(o.hide_render == (frame > 600) and o.hide_viewport == (frame > 600) for o in full.values()) and
          all(o.hide_render == (frame < 601) and o.hide_viewport == (frame < 601) for o in pixel.values()))
    check(f'Pixel crop stays assembled frame {frame}', all(o.location.length < 1e-5 for o in pixel.values()))

expected_ranges = {
    'led_high': [(697, 936), (1201, 1536)],
    'reference': [(697, 1536)],
    'gate_discharge_low_edge': [(937, 960)],
    'pass_gate_charge_high_edge': [(1177, 1200)],
}
periods = {'led_high': (4, 120), 'reference': (4, 140), 'gate_discharge_low_edge': (2, 28), 'pass_gate_charge_high_edge': (2, 28)}
vis_failures = []
objects_by_path = {}
for key in expected_ranges:
    group = [o for o in bpy.data.objects if o.name == '电流路径 ' + key or o.name.startswith('方向箭头 ' + key)]
    objects_by_path[key] = group
    check('Path and arrow objects exist: ' + key, len(group) == periods[key][0] + 1, count=len(group))
for frame in range(1, 1537):
    sc.frame_set(frame)
    for key, ranges in expected_ranges.items():
        hidden = not in_ranges(frame, ranges)
        for obj in objects_by_path[key]:
            if obj.hide_render != hidden or obj.hide_viewport != hidden:
                vis_failures.append(dict(frame=frame, path=key, object=obj.name))
check('Every frame: LED only high, reference continues during low, gate arrows only at edges', not vis_failures,
      frames_checked=1536, path_objects_checked=sum(map(len, objects_by_path.values())), failures=vis_failures[:20])
check('No steady gate-current arrow in high or low states',
      not any(in_ranges(f, expected_ranges['gate_discharge_low_edge'] + expected_ranges['pass_gate_charge_high_edge'])
              for f in list(range(697,937)) + list(range(961,1177)) + list(range(1201,1537))))

# Compare rendered centre-line order against audited physical paths after the
# documented clipping and camera projection. No current is inferred from color.
sc.frame_set(720)
cam = sc.camera
scale = cam.data.ortho_scale
inverse = cam.matrix_world.inverted()
route_points = {}
projection_errors = {}
for key in expected_ranges:
    projected = []
    for p in M['paths'][key]['points']:
        v = Vector((max(503, min(632, p['x_um'])), p['y_um'], p['z_nominal_um'] * 12))
        q = inverse @ v
        xy = Vector((q.x / scale * 1000, q.y / scale * 1000))
        if not projected or (xy - projected[-1]).length > 1e-4:
            projected.append(xy)
    obj = bpy.data.objects.get('电流路径 ' + key)
    points = [Vector((p.co.x, p.co.y)) for p in obj.data.splines[0].points]
    error = max((a - b).length for a, b in zip(projected, points)) if len(projected) == len(points) else None
    check('Audited path order and camera projection: ' + key,
          error is not None and error < 0.003, point_count=len(points), max_hud_distance=error)
    route_points[key] = points
    projection_errors[key] = error

# Verify arrow placement and orientation for both steady paths and both edges,
# excluding no interval or wraparound: expected phase uses the range's first frame.
arrow_failures = []
for key, ranges in expected_ranges.items():
    n, period = periods[key]
    pts = route_points[key]
    lengths = [0.0]
    for a, b in zip(pts, pts[1:]): lengths.append(lengths[-1] + (b-a).length)
    for a, b in ranges:
        for frame in sorted(set([a, min(a+5,b), (a+b)//2, b])):
            sc.frame_set(frame)
            for i in range(n):
                distance = (((frame-a)/period + i/n) % 1) * lengths[-1]
                j = next((j for j in range(1,len(lengths)) if distance <= lengths[j]), len(lengths)-1)
                v = pts[j] - pts[j-1]
                q = pts[j-1] + v * ((distance-lengths[j-1]) / (lengths[j]-lengths[j-1]))
                obj = bpy.data.objects.get('方向箭头 '+key+str(i))
                actualpos = Vector((obj.location.x,obj.location.y))
                actualdir = Vector((math.cos(obj.rotation_euler.z), math.sin(obj.rotation_euler.z)))
                if (q-actualpos).length > .003 or actualdir.dot(v.normalized()) < .99999:
                    arrow_failures.append(dict(path=key,frame=frame,arrow=i,position_error=float((q-actualpos).length)))
check('Moving arrows follow conventional-current path direction', not arrow_failures, failures=arrow_failures[:20])

# The added static dashed voltage net completes GATE bus -> output poly gate,
# without turning that control connection into a steady DC-current animation.
sc.frame_set(720)
gate_projected = []
for p in M['paths']['gate_voltage_control']['points']:
    q = inverse @ Vector((max(503, min(632, p['x_um'])), p['y_um'], p['z_nominal_um'] * 12))
    xy = Vector((q.x / scale * 1000, q.y / scale * 1000))
    if not gate_projected or (xy - gate_projected[-1]).length > 1e-4:
        gate_projected.append(xy)
dashes = [o for o in bpy.data.objects if o.name.startswith('GATE控制电压虚线 ')]
dash_ok = bool(dashes)
for obj in dashes:
    for point in obj.data.splines[0].points:
        xy = Vector((point.co.x,point.co.y))
        distances = []
        for a,b in zip(gate_projected,gate_projected[1:]):
            v=b-a;t=max(0,min(1,(xy-a).dot(v)/v.length_squared))
            distances.append((xy-(a+t*v)).length)
        dash_ok = dash_ok and min(distances)<.003
check('Static GATE voltage dashes follow the audited output gate connection',dash_ok,dash_segments=len(dashes))
for frame in [601,696,697,720,948,1040,1188,1280,1536]:
    sc.frame_set(frame)
    check(f'Static GATE voltage net visibility frame {frame}', all(o.hide_render==(frame<697) for o in dashes))
check('Voltage net has no moving current particles',not any(o.name.startswith('方向箭头 gate_voltage_control') for o in bpy.data.objects))
check('Cropped BIAS/VSS continuation labelled',any(o.type=='FONT' and 'BIAS / VSS 总线向左延续' in o.data.body and '裁切' in o.data.body for o in bpy.data.objects))

fonts = {o.data.font.name:o.data.font for o in bpy.data.objects if o.type == 'FONT'}
images = [im for im in bpy.data.images if im.source == 'FILE']
check('Chinese font packed in blend', bool(fonts) and all(f.packed_file for f in fonts.values()), fonts=list(fonts))
check('Both schematic images packed in blend', len(images) == 2 and all(im.packed_file for im in images), images=[im.name for im in images])
for state in ['high','low']:
    img = next((im for im in images if im.name == f'pwm-{state}.png'), None)
    check('Packed schematic source matches file: '+state, img is not None and
          hashlib.sha256(bytes(img.packed_file.data)).hexdigest() == sha(OUT/f'figures/pwm-{state}.png'))
check('Normal conditions state FAULT=0 and PERMIT=1', 'FAULT=0' in sc.get('normal_conditions','') and 'PERMIT=1' in sc.get('normal_conditions',''))
check('Projection explanation is stored', 'projection' in sc.get('annotation_projection','').lower())
sc.frame_set(1)

result = dict(schema=1, passed=all(c['passed'] for c in checks), blender_version=bpy.app.version_string,
              checks_count=len(checks), failed_count=sum(not c['passed'] for c in checks), checks=checks,
              source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [GEOMETRY,MAPPING,BLEND,OUT/'timeline.json',Path(__file__).resolve(),ROOT/'scripts/blender_animation/build.py']},
              interpretation='Blender scene fidelity, keyframes and asset portability only. These checks do not establish transistor, PEX, optical, field or manufacturing validation.',
              boundaries=[
                  'Full selected GDS XY shapes are exact at 1 nm quantization; Z is nominal technology height x12 and exploded offsets are pedagogical.',
                  'Current traces are camera-projected centre lines, not current density or carrier trajectories.',
                  'Reference and VSS lines continue left of the pixel crop; original ports are outside that crop.',
                  'Representative Contact/channel segments explain direction; they do not distribute current over all parallel contacts.',
                  'Gate charge/discharge indicators intentionally disappear in steady states; the reference path remains active during PWM low.'
                  ,'Edge-flow paths end on the GATE bus; a separately checked static dashed voltage connection continues to the actual output poly gate, with no DC-current particles.'
              ])
(EVIDENCE/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(passed=result['passed'],checks=result['checks_count'],failed=result['failed_count'],output=str(EVIDENCE/'validation.json')),ensure_ascii=False))
if not result['passed']:
    for item in checks:
        if not item['passed']:print('FAILED_CHECK',json.dumps(item,ensure_ascii=False))
    raise SystemExit(1)
