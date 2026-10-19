"""Reopen .blend and independently compare its whole-macro XY vertices to GDS JSON."""
from pathlib import Path
from collections import Counter
import bpy,json,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'docs/research/blender-layout-20261018'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'single-pixel-r5.blend'))
source=json.loads((ROOT/'evidence/layout-v3/r5/geometry.json').read_text())
scene=bpy.data.scenes['01 Full macro'];expected={};counts=Counter()
for p in source['polygons']:
 k=p['layer'];counts[k]+=1
 expected.setdefault(k,Counter()).update((round(x*1000),round(y*1000)) for x,y in p['points'] for _ in (0,1))
checks=[]
for ob in scene.objects:
 if 'gds_layer' not in ob:continue
 k=ob['gds_layer'];got=Counter((round(v.co.x*1000),round(v.co.y*1000)) for v in ob.data.vertices)
 checks.append({'name':f'Layer {k} XY vertices exactly match at 1nm GDS database precision','passed':got==expected[k]})
 checks.append({'name':f'Layer {k} source polygon count','passed':ob['polygon_count']==counts[k]})
checks.append({'name':'All ten source layers in full scene','passed':len([o for o in scene.objects if 'gds_layer' in o])==10})
checks.append({'name':'Three saved scenes','passed':len(bpy.data.scenes)==3})
checks.append({'name':'Original GDS hash retained in every scene','passed':all(s['source_gds_sha256']==source['gds_sha256'] for s in bpy.data.scenes)})
checks.append({'name':'Z enlargement labelled and recorded','passed':all(s['z_display_scale']==12 for s in bpy.data.scenes)})
result={'passed':all(c['passed'] for c in checks),'checks':checks,'scope':'Geometry preservation and saved Blender scene, not circuit/field simulation','source_gds_sha256':source['gds_sha256'],'output_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.suffix in ['.png','.blend','.json'] and p.name!='validation.json'}}
(OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False));assert result['passed']
