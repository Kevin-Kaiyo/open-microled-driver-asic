"""Build an editable layer-by-layer Blender model from audited GDS XY polygons."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'build/highspeed-workbench-20261110/physical'
DOC = ROOT / 'docs/research/highspeed-workbench-20261110/physical'
EVID = ROOT / 'evidence/highspeed-workbench-20261110'
BLEND = DOC / 'highspeed-cores.blend'
TIERS = {21:0, 204:0, 22:1, 30:2, 33:3, 34:4, 35:5, 36:6, 38:7, 42:8, 40:9, 46:10}


def material(layer, meta):
    rgba = [int(meta['color'][i:i+2], 16) / 255 for i in [1,3,5]] + [1]
    m = bpy.data.materials.new(f"{meta['name']}  |  GDS {layer}/0")
    m.diffuse_color = rgba
    m.use_nodes = True
    m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = rgba
    return m


def make_layer(layer, polygons, dbu, stack, scene, materials):
    layer_name = stack['layers'][str(layer)]['name']
    collection = bpy.data.collections.new(f'{scene.name}  |  {layer_name}')
    scene.collection.children.link(collection)
    verts, faces, bottom_faces = [], [], []
    z_scale = stack['z_multiplier']
    for poly in polygons:
        coords = poly['points']
        z_low = poly['height']['z'] * z_scale
        z_high = z_low + poly['height']['thickness'] * z_scale
        i = len(verts)
        n = len(coords)
        for z in (z_low, z_high):
            verts.extend((x * dbu, y * dbu, z) for x, y in coords)
        bottom_faces.append(len(faces))
        faces.append(tuple(range(i+n-1, i-1, -1)))
        faces.append(tuple(range(i+n, i+2*n)))
        for a in range(n):
            b = (a+1) % n
            faces.append((i+a, i+b, i+n+b, i+n+a))
    mesh = bpy.data.meshes.new(f'{layer_name} GDS polygon extrusion')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(f'{layer_name}  ({layer}/0)', mesh)
    collection.objects.link(obj)
    obj.data.materials.append(materials[layer])
    obj['gds_layer'] = layer
    obj['gds_datatype'] = 0
    obj['bottom_faces'] = bottom_faces
    obj['source_polygon_count'] = len(polygons)
    for frame, expansion in [(1, 0), (60, stack['exploded_gap_per_tier_um'])]:
        obj.location.z = TIERS[layer] * expansion
        obj.keyframe_insert(data_path='location', index=2, frame=frame)
    return obj


def camera_and_style(scene, bbox):
    x0, y0, x1, y1 = bbox
    target = Vector(((x0+x1)/2, (y0+y1)/2, 21))
    camera = bpy.data.objects.new('Isometric camera', bpy.data.cameras.new('Isometric camera'))
    scene.collection.objects.link(camera)
    camera.location = target + Vector((90, -116, 123))
    camera.rotation_euler = (target-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 110
    camera.data.clip_end = 400
    scene.camera = camera
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    scene.display.render_aa = '16'
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.background_type = 'WORLD'
    sh.show_shadows = True
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.show_object_outline = False
    scene.world = bpy.data.worlds.new('Neutral render background')
    scene.world.color = (0.88, 0.91, 0.94)
    scene.view_settings.view_transform = 'Standard'
    for name, frame in [('Connected view, Z ×6', 1), ('Exploded view, Z ×6 plus layer gaps', 60)]:
        scene.timeline_markers.new(name, frame=frame)


def verify(model):
    checks = []
    stack = model['stack']
    z_scale = stack['z_multiplier']
    for core in model['cores']:
        summary = core['summary']
        scene = bpy.data.scenes[summary['route'] + '  |  ' + summary['title']]
        bpy.context.window.scene = scene
        scene.frame_set(60)
        graph = bpy.context.evaluated_depsgraph_get()
        dbu = summary['dbu_um']
        from_gds, from_mesh = Counter(), Counter()
        for p in core['polygons']:
            from_gds[(p['layer'], tuple(sorted(map(tuple,p['points']))),
                      round(p['height']['z'] * z_scale, 4),
                      round((p['height']['z']+p['height']['thickness']) * z_scale, 4))] += 1
        for obj in scene.objects:
            if 'gds_layer' not in obj:
                continue
            layer = obj['gds_layer']
            assert abs(obj.evaluated_get(graph).location.z - TIERS[layer] * stack['exploded_gap_per_tier_um']) < 1e-6
            for face_index in obj['bottom_faces']:
                bottom = obj.data.polygons[face_index]
                top = obj.data.polygons[face_index+1]
                floor = [obj.data.vertices[i].co for i in bottom.vertices]
                roof = [obj.data.vertices[i].co for i in top.vertices]
                xy = tuple(sorted((round(v.x/dbu), round(v.y/dbu)) for v in floor))
                assert xy == tuple(sorted((round(v.x/dbu), round(v.y/dbu)) for v in roof))
                from_mesh[(layer, xy, round(floor[0].z, 4), round(roof[0].z, 4))] += 1
        assert from_gds == from_mesh, summary['route']
        scene.frame_set(1)
        graph = bpy.context.evaluated_depsgraph_get()
        assert all(abs(o.evaluated_get(graph).location.z) < 1e-6
                   for o in scene.objects if 'gds_layer' in o)
        checks.append(dict(route=summary['route'], polygons=sum(from_mesh.values()),
                           exact_xy_vertices_in_original_dbu=True, nominal_z_metadata=True,
                           frame_1_connected=True, frame_60_exploded=True))
    return checks


def main():
    model = json.loads((RUN / 'gds-model.json').read_text())
    stack = model['stack']
    default = bpy.context.scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    materials = {int(n):material(n,meta) for n,meta in stack['layers'].items()}
    first = None
    for core in model['cores']:
        summary = core['summary']
        route = summary['route']
        scene = bpy.data.scenes.new(route + '  |  ' + summary['title'])
        scene.frame_end = 60
        scene.unit_settings.system = 'NONE'
        scene['scope'] = 'Historical routed research core only. This is GDS geometry visualization.'
        scene['top'] = summary['top']
        scene['revision'] = summary['revision']
        scene['xy_unit'] = 'One Blender unit equals one micrometre in XY'
        scene['z_display'] = 'Nominal extraction height ×6. Frame 60 adds 2 display units per tier.'
        scene['gds_sha256'] = next(v for p,v in summary['source_sha256'].items() if p.endswith('.gds'))
        by_layer = defaultdict(list)
        for poly in core['polygons']:
            by_layer[poly['layer']].append(poly)
        for layer, polygons in by_layer.items():
            make_layer(layer, polygons, summary['dbu_um'], stack, scene, materials)
        camera_and_style(scene, summary['bbox_um'])
        scene.frame_set(60)
        scene.render.filepath = f'//core-{route.lower()}-3d.png'
        if first is None:
            first = scene
    bpy.context.window.scene = first
    bpy.data.scenes.remove(default)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                space.region_3d.view_perspective = 'CAMERA'
                space.shading.color_type = 'MATERIAL'
                space.overlay.show_floor = False
                space.overlay.show_axis_x = False
                space.overlay.show_axis_y = False
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND), compress=True)
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    checks = verify(model)
    for core in model['cores']:
        summary = core['summary']
        scene = bpy.data.scenes[summary['route'] + '  |  ' + summary['title']]
        scene.frame_set(60)
        bpy.context.window.scene = scene
        bpy.ops.render.render(write_still=True, scene=scene.name)
    (EVID / 'physical-blender-checks.json').write_text(json.dumps(dict(blender=bpy.app.version_string,
         reopened_saved_blend=True, checks=checks), ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
