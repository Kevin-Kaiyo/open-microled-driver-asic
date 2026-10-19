"""Run with Blender --background --python this_file. Deterministic GDS extrusion."""
from pathlib import Path
import bpy, json, math, hashlib
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/blender-layout-20261018'; OUT.mkdir(parents=True,exist_ok=True)
SOURCE=ROOT/'build/blender-demo/geometry-3d.json'
DATA=json.loads(SOURCE.read_text())
Z=12.0
# Nominal Magic visualization/extraction height table, microns. This is NOT a process profile.
STACK={21:(0,.0145),204:(0,.0145),22:(.0145,.30),30:(.32,.2),34:(1.23,.55),35:(1.78,.60),36:(2.38,.55),38:(2.93,.60),42:(3.53,.55)}
COLORS={21:'#cadbde',204:'#d7e5d4',22:'#5b997e',30:'#c36d3d',33:'#be9f6d',34:'#3f708f',35:'#d3af63',36:'#388e91',38:'#d3af63',42:'#8b719f'}
bpy.ops.wm.read_factory_settings(use_empty=True)
FONT=bpy.data.fonts.load('/System/Library/Fonts/Supplemental/Arial.ttf')
def color(s):
 rgb=[int(s[i:i+2],16)/255 for i in (1,3,5)]
 return tuple((v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4) for v in rgb)+(1,)
def mat(name,hex,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=color(hex);m.use_nodes=True
 p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=color(hex);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=.42
 return m
MATS={k:mat(DATA['layers'][str(k)]['name'],c,.25 if k in [33,34,35,36,38,42] else 0) for k,c in COLORS.items()}
BASEMAT=mat('Display support - NOT wafer thickness','#e6e7e3')
def clip(poly,b):
 pts=[tuple(p) for p in poly]
 for axis,edge,keep in [(0,b[0],1),(0,b[2],-1),(1,b[1],1),(1,b[3],-1)]:
  old=pts;pts=[]
  if not old:break
  a=old[-1]
  for c in old:
   ai=keep*(a[axis]-edge)>=-1e-10;ci=keep*(c[axis]-edge)>=-1e-10
   if ai!=ci:
    f=(edge-a[axis])/(c[axis]-a[axis]);p=[a[0]+f*(c[0]-a[0]),a[1]+f*(c[1]-a[1])];p[axis]=edge;pts.append(tuple(p))
   if ci:pts.append(c)
   a=c
 # drop coincident vertices, including closing vertex
 clean=[]
 for p in pts:
  if not clean or (Vector(p)-Vector(clean[-1])).length>1e-9:clean.append(p)
 if len(clean)>1 and (Vector(clean[0])-Vector(clean[-1])).length<1e-9:clean.pop()
 return clean
# Contact type is read from independently checked GDS classification.
audit=json.loads((ROOT/'build/blender-demo/stack-audit.json').read_text())
assert audit['exact_selected_GDS_vertex_multisets_equal']
def prism(verts,faces,pts,low,high):
 # CCW ensures top normals face outwards; meshes keep original planar vertices.
 if sum(pts[i][0]*pts[(i+1)%len(pts)][1]-pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts)))<0:pts=list(reversed(pts))
 n=len(pts);o=len(verts);verts.extend((x,y,low) for x,y in pts);verts.extend((x,y,high) for x,y in pts)
 faces.extend([tuple(o+i for i in reversed(range(n))),tuple(o+n+i for i in range(n))]);faces.extend((o+i,o+(i+1)%n,o+n+(i+1)%n,o+n+i) for i in range(n))
def meshobj(name,vs,fs,material,collection):
 mesh=bpy.data.meshes.new(name);mesh.from_pydata(vs,[],fs);mesh.update();obj=bpy.data.objects.new(name,mesh);collection.objects.link(obj);obj.data.materials.append(material);return obj
def emission(hex):
 m=bpy.data.materials.new('Label '+hex);m.use_nodes=True;n=m.node_tree.nodes;n.clear();e=n.new('ShaderNodeEmission');e.inputs[0].default_value=color(hex);out=n.new('ShaderNodeOutputMaterial');m.node_tree.links.new(e.outputs[0],out.inputs['Surface']);return m
INK=emission('#233e48');GRAY=emission('#5b6b70')
def label(sc,cam,txt,x,y,size,material=INK):
 curve=bpy.data.curves.new(txt,'FONT');curve.body=txt;curve.font=FONT;curve.size=size;curve.align_x='LEFT';curve.space_character=1.05
 ob=bpy.data.objects.new(txt,curve);sc.collection.objects.link(ob);ob.parent=cam;ob.location=(x,y,-3);ob.data.materials.append(material);return ob
meta=[]
def build(name,bounds,title,subtitle,filename):
 sc=bpy.data.scenes.new(name);bpy.context.window.scene=sc
 coll=bpy.data.collections.new('GDS layers - independent visibility');sc.collection.children.link(coll)
 buckets={k:([],[]) for k in COLORS};counts={k:0 for k in COLORS}
 for index,p in enumerate(DATA['polygons']):
  k=p['layer'];pts=clip(p['points'],bounds)
  if len(pts)<3:continue
  area=abs(sum(pts[i][0]*pts[(i+1)%len(pts)][1]-pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts))))/2
  if area<1e-10:continue
  low=p['z_nominal_um'];thick=p['thickness_nominal_um']
  prism(*buckets[k],pts,low*Z,(low+thick)*Z);counts[k]+=1
 for k,(vs,fs) in buckets.items():
  if not vs:continue
  ob=meshobj(f'{k:03d} | '+DATA['layers'][str(k)]['name'],vs,fs,MATS[k],coll);ob['gds_layer']=k;ob['polygon_count']=counts[k];ob['z_exaggeration']=Z;ob['source']='r5 GDS / geometry.json';ob['scope']='planar mask extrusion; no TCAD profile'
 # Display base is intentionally separate from the semiconductor layers.
 b=bounds;vs=[];fs=[];prism(vs,fs,[(b[0],b[1]),(b[2],b[1]),(b[2],b[3]),(b[0],b[3])],-max(1,(b[2]-b[0])*.008),-.03)
 base=meshobj('Display base - illustrative, NOT silicon thickness',vs,fs,BASEMAT,sc.collection)
 target=Vector(((b[0]+b[2])/2,(b[1]+b[3])/2,20))
 cam_data=bpy.data.cameras.new(name+' camera');cam=bpy.data.objects.new('Camera',cam_data);sc.collection.objects.link(cam);cam.location=target+Vector((.35,-.9,1.08)).normalized()*1200;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam_data.type='ORTHO';cam_data.clip_end=5000;sc.camera=cam
 inv=cam.rotation_euler.to_quaternion().inverted();pr=[inv@(Vector((x,y,z))-target) for x in (b[0],b[2]) for y in (b[1],b[3]) for z in (-3,4.08*Z)]
 aspect=2000/1300;spanx=max(p.x for p in pr)-min(p.x for p in pr);spany=max(p.y for p in pr)-min(p.y for p in pr)
 scale=max(spanx/.88,spany*aspect/.65);cam_data.ortho_scale=scale
 W=scale;H=scale/aspect;pad=W*.045
 label(sc,cam,title,-W/2+pad,H*.415,H*.038)
 label(sc,cam,subtitle,-W/2+pad,H*.365,H*.019,GRAY)
 label(sc,cam,'REAL GDS XY  |  Z x12  |  nominal Magic heights  |  colors identify layers',-W/2+pad,-H*.385,H*.019,GRAY)
 label(sc,cam,'Mask extrusion only. No dielectric, doping profile, electrical field or thermal simulation.',-W/2+pad,-H*.425,H*.018,GRAY)
 legend=[(22,'Active'),(30,'Poly'),(33,'Contact'),(34,'M1'),(35,'Via1'),(36,'M2'),(38,'Via2'),(42,'M3')]
 for i,(k,s) in enumerate(legend):label(sc,cam,s,-W/2+pad+i*W*.112,-H*.475,H*.023,emission(COLORS[k]))
 world=bpy.data.worlds.new(name+' World');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(1,1,1,1);world.node_tree.nodes['Background'].inputs[1].default_value=1;sc.world=world
 for name2,position,power,size in [('Key',(-180,-210,600),2200,500),('Fill',(400,160,350),1400,400)]:
  light=bpy.data.lights.new(name2,'AREA');light.energy=power*(scale/200)**2;light.shape='DISK';light.size=size;obj=bpy.data.objects.new(name2,light);sc.collection.objects.link(obj);obj.location=target+Vector(position);obj.rotation_euler=(target-obj.location).to_track_quat('-Z','Y').to_euler()
 # A broad sun provides consistent illumination across both whole-macro and detail views.
 light=bpy.data.lights.new('Sun','SUN');light.energy=2;light.angle=.35;obj=bpy.data.objects.new('Sun',light);sc.collection.objects.link(obj);obj.rotation_euler=(.35,-.4,-.3)
 sc.unit_settings.system='METRIC';sc.unit_settings.scale_length=1e-6
 sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=2000;sc.render.resolution_y=1300;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.render.filepath=str(OUT/filename);sc.render.film_transparent=False
 sc.view_settings.view_transform='Standard';sc.view_settings.look='None';sc.view_settings.exposure=0;sc.view_settings.gamma=1
 sc['source_gds_sha256']=DATA['gds_sha256'];sc['xy_unit']='micrometre';sc['z_display_scale']=Z;sc['notice']='Nominal Magic heights; not foundry process, EM or TCAD simulation'
 for screen in bpy.data.screens:
  for area in screen.areas:
   if area.type=='VIEW_3D':
    area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='MATERIAL'
 if filename=='03-vias.png':
  def leader(text,loc,y):
   x=-W*.455
   label(sc,cam,text,x,y,H*.022)
   q=inv@(Vector(loc)-cam.location)
   curve=bpy.data.curves.new('Connection callout','CURVE');curve.dimensions='3D';curve.bevel_depth=W*.00055;curve.bevel_resolution=1
   line=curve.splines.new('POLY');line.points.add(2)
   for p,c in zip(line.points,[(x+W*.22,y-H*.006,-2.8),(x+W*.27,y-H*.006,-2.8),(q.x,q.y,-2.8)]):p.co=(*c,1)
   ob=bpy.data.objects.new('Callout: '+text,curve);sc.collection.objects.link(ob);ob.parent=cam;ob.data.materials.append(GRAY)
  leader('Via2 = electrical connection',(194.74,50,3.23*Z),H*.19)
  leader('Crossing without a Via2',(205.26,50,3.23*Z),-H*.04)
 meta.append({'scene':sc.name,'crop_um':bounds,'polygon_counts':counts,'render':filename,'z_exaggeration':Z})
 return sc
scenes=[build('01 Full macro',DATA['bbox_um'],'SINGLE-PIXEL DRIVER / 3D LAYOUT','637.03 x 200.36 um footprint  |  39-MOS analog test macro  |  GF180MCU r5','01-overview.png'),build('02 Reference device',[191,92,209,106],'REFERENCE DEVICE / CONTACTS','Gate-contact end of the device  |  Contact / Metal1 / Via1 / Metal2','02-device.png'),build('03 Routing and vias',[185,36,220,59],'ROUTING / VIA CONNECTIONS','Cropped actual GDS  |  Metal2 vertical routes meet Metal3 horizontal buses through Via2','03-vias.png')]
if 'Scene' in bpy.data.scenes and len(bpy.data.scenes['Scene'].objects)==0:bpy.data.scenes.remove(bpy.data.scenes['Scene'])
bpy.context.window.scene=scenes[0]
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'single-pixel-r5.blend'))
for sc in scenes:
 bpy.context.window.scene=sc;bpy.ops.render.render(write_still=True,scene=sc.name)
bpy.context.window.scene=scenes[0]
result={'blender_version':bpy.app.version_string,'source_geometry_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'gds_sha256':DATA['gds_sha256'],'z_exaggeration':Z,'scenes':meta,'mesh_objects':len([o for o in bpy.data.objects if o.type=='MESH']),'total_mesh_vertices':sum(len(m.vertices) for m in bpy.data.meshes),'status':'3D educational visualization only; no new circuit or physical verification'}
(OUT/'scene-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('BLENDER_DEMO_COMPLETE',json.dumps(result))
