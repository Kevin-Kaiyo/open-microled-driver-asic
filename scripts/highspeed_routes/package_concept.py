"""Blender concept illustration only: no GDS, physical dimensions or field solver."""
from pathlib import Path
import bpy, math, json, hashlib
from mathutils import Vector
R=Path(__file__).resolve().parents[2]
O=R/'docs/research/highspeed-driver-routes-20261019';O.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene;s.name='高速MicroLED异质集成概念'
def rgb(h):
 a=[int(h[i:i+2],16)/255 for i in (1,3,5)];return tuple(x/12.92 if x<.04045 else ((x+.055)/1.055)**2.4 for x in a)+(1,)
def mat(name,h,em=False):
 m=bpy.data.materials.new(name);m.diffuse_color=rgb(h);m.use_nodes=True
 if em:
  ns=m.node_tree.nodes;ns.clear();e=ns.new('ShaderNodeEmission');e.inputs[0].default_value=rgb(h);o=ns.new('ShaderNodeOutputMaterial');m.node_tree.links.new(e.outputs[0],o.inputs['Surface'])
 else:
  p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=rgb(h);p.inputs['Roughness'].default_value=.52
 return m
ink=mat('中文标注','#233f4a',True);muted=mat('次要标注','#647980',True);gold=mat('示意垂直互连','#cda85c');silicon=mat('硅芯片','#8c9ba2');beol=mat('互连功能示意','#d8e8e7');board=mat('封装支撑示意','#e5e9e6')
def box(name,loc,scale,m):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(m);return o
def pipe(name,a,b,r,m):
 a=Vector(a);b=Vector(b);d=b-a;bpy.ops.mesh.primitive_cylinder_add(vertices=20,radius=r,depth=d.length,location=(a+b)/2);o=bpy.context.object;o.name=name;o.rotation_euler=d.to_track_quat('Z','Y').to_euler();o.data.materials.append(m);return o
box('封装支撑面（无真实尺寸）',(0,0,-.42),(9,6,.28),board)
box('Si CMOS芯片',(0,0,.05),(7,4.6,.65),silicon)
box('BEOL/RDL示意，不代表金属层数',(0,0,.43),(7,4.6,.12),beol)
blocks=[('输入与重定时',(-2.35,-1.2,.54),(1.6,1.35,.12),'#abbfd3'),('前置驱动',(-.4,-1.2,.54),(1.5,1.35,.12),'#8fb8bc'),('输出级',(1.55,.05,.56),(1.7,1.35,.16),'#d5a574'),('参考与校准',(-2.3,1.05,.54),(1.6,1.2,.12),'#abbfa4'),('时钟分配',(-.4,1.05,.54),(1.5,1.2,.12),'#b2a4bf'),('限流与故障控制',(1.65,-1.4,.54),(1.8,.8,.12),'#c3c3b8')]
for n,l,d,c in blocks:box(n,l,d,mat(n,c))
for x in [-2.6,-1.8,-1,-.2,.6,1.4,2.2,3]:
 pipe('示意IO连接',(x,-2.15,-.28),(x,-2.15,-.1),.10,gold)
signal=mat('短数据连接','#7b668f');supply=mat('供电示意','#b47557');ret=mat('回流示意','#477b82')
for y in [-.95,-1.15]:
 pipe('数据短连线',(-1.55,y,.68),(-1.15,y,.68),.035,signal)
 pipe('前置驱动到输出',(.35,y,.69),(1.0,y,.69),.035,signal)
 pipe('输出局部连接',(1.0,y,.69),(1.0,-.5,.69),.035,signal)
for x in [1.18,1.93]:pipe('LED双端垂直互连方案',(x,.05,.65),(x,.05,1.65),.10,gold)
box('III-V MicroLED，双端引出方案示意',(1.55,.05,1.83),(1.45,1.05,.32),mat('III-V发光器件','#3c9fbc'))
box('光输出面示意',(1.55,.05,2.001),(1.12,.75,.025),mat('发光面','#c3e8ee'))
pipe('局部电源',(2.5,.5,.68),(2.5,1.8,.68),.045,supply)
pipe('局部回流',(2.8,.5,.68),(2.8,1.8,.68),.045,ret)
box('本地去耦功能位置',(2.65,1.55,.78),(.8,.55,.24),mat('去耦示意','#a8b2a4'))
cd=bpy.data.cameras.new('概念图相机');cam=bpy.data.objects.new('概念图相机',cd);s.collection.objects.link(cam);s.camera=cam
target=Vector((.1,0,.7));direction=Vector((8,-11,11)).normalized();cam.location=target+direction*25;cam.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler();cd.type='ORTHO';cd.ortho_scale=15.5
# All dimensions are presentation units. Fixed-camera leader labels are explanatory.
font=bpy.data.fonts.load(str(R/'build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf'));font.pack()
hud=bpy.data.objects.new('概念标注',None);s.collection.objects.link(hud);hud.parent=cam;hud.location=(0,0,-3);hud.scale=(15.5/1600,)*3
def text(body,x,y,size=20,m=ink):
 c=bpy.data.curves.new(body,'FONT');c.body=body;c.font=font;c.size=size*3.07;o=bpy.data.objects.new(body,c);s.collection.objects.link(o);o.parent=hud;o.location=(x,y,.2);c.materials.append(m)
def project(p):
 q=cam.rotation_euler.to_quaternion().inverted()@(Vector(p)-cam.location);return (q.x/15.5*1600,q.y/15.5*1600)
def leader(p,x,y,label,sub):
 px,py=project(p);c=bpy.data.curves.new(label+'引线','CURVE');c.dimensions='3D';c.bevel_depth=.6;c.bevel_resolution=1;sp=c.splines.new('POLY');sp.points.add(2)
 for v,co in zip(sp.points,[(px,py,.05),(x-25,y-3,.05),(x-6,y-3,.05)]):v.co=(*co,1)
 ob=bpy.data.objects.new(label+'引线',c);s.collection.objects.link(ob);ob.parent=hud;c.materials.append(muted);text(label,x,y,19);text(sub,x,y-28,14,muted)
text('高速发送器：让输出级靠近 MicroLED',-735,440,32)
text('Blender 原创概念示意｜非 GDS，尺寸、金属层数与键合工艺尚未确定',-735,393,18,muted)
leader((1.55,.05,1.99),330,285,'III-V 发光器件','示例：InGaN/GaN；不是驱动 MOS 的材料')
leader((1.18,.05,1.23),365,182,'短垂直互连','两端各自引出仅为一种候选封装方案')
leader((2.65,1.55,.90),345,62,'本地供电与回流','缩短高频回路；降低共享阻抗')
leader((1.55,-.35,.68),385,-260,'输出级紧邻发光器件','减少输出节点的互连电容与电感')
leader((-.4,-1.3,.7),-725,-275,'数据 → 前置驱动 → 输出级','功能区表示逻辑位置，不代表实际面积')
leader((-2,1,.63),-725,248,'参考、时钟与校准','慢速偏置不应被高速数据反复建立')
text('下层是 Si CMOS：数字逻辑、MOS 驱动及偏置。上层是独立的 III-V MicroLED。',-735,-380,20)
text('连接线与色块只解释系统关系；未进行寄生提取、电磁、热学或制造验证。',-735,-423,17,muted)
world=bpy.data.worlds.new('白色');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(1,1,1,1);world.node_tree.nodes['Background'].inputs[1].default_value=.8;s.world=world
ld=bpy.data.lights.new('柔光','AREA');lo=bpy.data.objects.new('柔光',ld);s.collection.objects.link(lo);lo.location=(0,-4,9);ld.energy=900;ld.shape='DISK';ld.size=8;lo.rotation_euler=(Vector((0,0,0))-lo.location).to_track_quat('-Z','Y').to_euler()
s.render.engine='BLENDER_EEVEE_NEXT';s.eevee.taa_render_samples=32;s.render.resolution_x=1920;s.render.resolution_y=1200;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.view_settings.view_transform='Standard'
s['evidence_class']='independent concept illustration; no GDS or physical dimensions';s['topology_scope']='Si CMOS driver plus separately fabricated III-V emitter; assembly option schematic, not a production stack'
s.render.filepath=str(O/'figures/package-concept.png')
bpy.ops.wm.save_as_mainfile(filepath=str(O/'package-concept.blend'));bpy.ops.render.render(write_still=True)
(O/'package-concept.json').write_text(json.dumps({'evidence_class':'original concept','source_gds':None,'dimensions':'arbitrary illustration units; not micrometres','metal_count':'undetermined','process':'not selected','font':'Noto Sans CJK SC, SIL OFL 1.1','blender_version':bpy.app.version_string,'scene_sha256':hashlib.sha256((O/'package-concept.blend').read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2)+'\n')
