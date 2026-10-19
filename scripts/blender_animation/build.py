"""Blender keyframed teaching animation; no simulation data are invented.
All moving indicators are explanatory conventional-current arrows.
"""
from pathlib import Path
import bpy,json,math,hashlib,sys
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'docs/research/blender-pwm-animation-20261018';RAW=ROOT/'build/blender-pwm-animation';OUT.mkdir(parents=True,exist_ok=True)
D=json.loads((ROOT/'build/blender-demo/geometry-3d.json').read_text());MAP=json.loads((RAW/'mapping.json').read_text())
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene;sc.name='逐层展开与PWM原理';FPS=24;END=1536;Z=12
sc.frame_start=1;sc.frame_end=END;sc.render.fps=FPS
FONT=bpy.data.fonts.load(str(RAW/'fonts/NotoSansCJKsc-Regular.otf'));FONT.pack()
C={21:'#cadbde',204:'#d7e5d4',22:'#5b997e',30:'#c36d3d',33:'#be9f6d',34:'#3f708f',35:'#d3af63',36:'#388e91',38:'#d3af63',42:'#8b719f'}
NAMES={21:'N阱',204:'P阱',22:'有源区',30:'多晶硅栅极',33:'接触孔 Contact',34:'第一层金属 M1',35:'第一层通孔 Via1',36:'第二层金属 M2',38:'第二层通孔 Via2',42:'第三层金属 M3'}
def color(h):
 a=[int(h[i:i+2],16)/255 for i in (1,3,5)];return tuple(x/12.92 if x<.04045 else ((x+.055)/1.055)**2.4 for x in a)+(1,)
def material(name,h,emit=False):
 m=bpy.data.materials.new(name);m.diffuse_color=color(h);m.use_nodes=True
 if emit:
  n=m.node_tree.nodes;n.clear();e=n.new('ShaderNodeEmission');e.inputs[0].default_value=color(h);o=n.new('ShaderNodeOutputMaterial');m.node_tree.links.new(e.outputs[0],o.inputs['Surface'])
 else:
  n=m.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=color(h);n.inputs['Roughness'].default_value=.46
 return m
MATS={k:material(NAMES[k],c) for k,c in C.items()};INK=material('文字','#243e47',True);GRAY=material('说明','#65767c',True);WHITE=material('面板','#ffffff',True);LED=material('LED常规电流','#d77a1d',True);REF=material('参考电流','#188b7d',True);GATE=material('边沿栅极充放电','#8a5ab3',True)
def vis(obj,ranges):
 for prop in ['hide_render','hide_viewport']:
  setattr(obj,prop,True);obj.keyframe_insert(prop,frame=1)
  for a,b in ranges:
   setattr(obj,prop,False);obj.keyframe_insert(prop,frame=a)
   setattr(obj,prop,True);obj.keyframe_insert(prop,frame=b+1)
 if obj.animation_data and obj.animation_data.action:
  for f in obj.animation_data.action.fcurves:
   if f.data_path.startswith('hide_'):
    for p in f.keyframe_points:p.interpolation='CONSTANT'
def clip(poly,b):
 pts=[tuple(p) for p in poly]
 for axis,edge,sgn in [(0,b[0],1),(0,b[2],-1),(1,b[1],1),(1,b[3],-1)]:
  old=pts;pts=[]
  if not old:break
  a=old[-1]
  for c in old:
   ai=sgn*(a[axis]-edge)>=-1e-10;ci=sgn*(c[axis]-edge)>=-1e-10
   if ai!=ci:
    f=(edge-a[axis])/(c[axis]-a[axis]);p=[a[0]+f*(c[0]-a[0]),a[1]+f*(c[1]-a[1])];p[axis]=edge;pts.append(tuple(p))
   if ci:pts.append(c)
   a=c
 q=[]
 for p in pts:
  if not q or (Vector(p)-Vector(q[-1])).length>1e-9:q.append(p)
 if len(q)>1 and (Vector(q[0])-Vector(q[-1])).length<1e-9:q.pop()
 return q

def prism(v,f,p,z,t):
 if sum(p[i][0]*p[(i+1)%len(p)][1]-p[(i+1)%len(p)][0]*p[i][1] for i in range(len(p)))<0:p=list(reversed(p))
 n=len(p);o=len(v);v.extend((x,y,z) for x,y in p);v.extend((x,y,z+t) for x,y in p);f.extend([tuple(o+i for i in reversed(range(n))),tuple(o+n+i for i in range(n))]);f.extend((o+i,o+(i+1)%n,o+n+(i+1)%n,o+n+i) for i in range(n))
def mesh(name,v,f,m,coll=None,parent=None):
 data=bpy.data.meshes.new(name);data.from_pydata(v,[],f);data.update();o=bpy.data.objects.new(name,data);(coll or sc.collection).objects.link(o);o.data.materials.append(m);o.parent=parent;return o
full={};pixel={}
for group,bounds,ranges,dest in [('完整模拟宏',D['bbox_um'],[(1,600)],full),('像素局部',[503,-4,632,164],[(601,END)],pixel)]:
 coll=bpy.data.collections.new(group);sc.collection.children.link(coll);bags={k:([],[]) for k in C};counts={k:0 for k in C}
 for p in D['polygons']:
  k=p['layer'];q=clip(p['points'],bounds)
  if len(q)<3:continue
  if abs(sum(q[i][0]*q[(i+1)%len(q)][1]-q[(i+1)%len(q)][0]*q[i][1] for i in range(len(q))))<1e-9:continue
  prism(*bags[k],q,p['z_nominal_um']*Z,p['thickness_nominal_um']*Z);counts[k]+=1
 for k,(v,f) in bags.items():
  if not v:continue
  o=mesh(group+' / '+NAMES[k],v,f,MATS[k],coll);o['gds_layer']=k;o['polygon_count']=counts[k];o['scope']='真实GDS平面，名义Z×12；展开位移仅为教学';vis(o,ranges);dest[k]=o
 v=[];f=[];prism(v,f,[(bounds[0],bounds[1]),(bounds[2],bounds[1]),(bounds[2],bounds[3]),(bounds[0],bounds[3])],-2,1.8);base=mesh(group+' / 展示底板',v,f,material(group+'底板','#e8ece9'),coll);vis(base,ranges)
# Explode top-to-bottom. Vias move as independent cut shapes; gaps are expressly illustrative.
steps=[(42,73,144,150),(38,145,192,125),(36,193,240,100),(35,241,288,75),(34,289,336,50),(33,337,384,25),(30,385,432,10)]
for k,a,b,offset in steps:
 o=full[k]
 for fr,z in [(1,0),(a,0),(b,offset),(528,offset),(600,0)]:o.location.z=z;o.keyframe_insert('location',frame=fr)
camdata=bpy.data.cameras.new('教学相机');cam=bpy.data.objects.new('教学相机',camdata);sc.collection.objects.link(cam);sc.camera=cam;camdata.type='ORTHO';camdata.clip_end=5000
fulltarget=Vector((328,96,95));direction=Vector((.28,-1.20,1.10)).normalized();rot=(-direction).to_track_quat('-Z','Y');pixrot=(-Vector((.10,-1.2,1.22)).normalized()).to_track_quat('-Z','Y')
pixscale=370.;pixtarget=Vector((568,78,22));right=pixrot@Vector((1,0,0));pixpos=pixtarget+Vector((.10,-1.2,1.22)).normalized()*1200-right*(.23*pixscale)
for fr,pos,q,scale in [(1,fulltarget+direction*1600,rot,920),(600,fulltarget+direction*1600,rot,920),(601,pixpos,pixrot,pixscale),(END,pixpos,pixrot,pixscale)]:
 cam.location=pos;cam.rotation_euler=q.to_euler();cam.keyframe_insert('location',frame=fr);cam.keyframe_insert('rotation_euler',frame=fr);camdata.ortho_scale=scale;camdata.keyframe_insert('ortho_scale',frame=fr)
for obj in [cam,camdata]:
 for f in obj.animation_data.action.fcurves:
  for p in f.keyframe_points:p.interpolation='CONSTANT'
hud=bpy.data.objects.new('中文标注与教学箭头（相机投影）',None);sc.collection.objects.link(hud);hud.parent=cam;hud.location=(0,0,-3)
for fr,s in [(1,.920),(600,.920),(601,.370),(END,.370)]:hud.scale=(s,s,s);hud.keyframe_insert('scale',frame=fr)
for f in hud.animation_data.action.fcurves:
 for p in f.keyframe_points:p.interpolation='CONSTANT'
def txt(body,x,y,size=14,mat=INK,ranges=[(1,END)],align='LEFT'):
 c=bpy.data.curves.new(body,'FONT');c.body=body;c.font=FONT;c.size=size*3.07;c.align_x=align;c.space_character=1.03;o=bpy.data.objects.new(body,c);sc.collection.objects.link(o);o.parent=hud;o.location=(x,y,.8);o.data.materials.append(mat);vis(o,ranges);return o
def line(name,pts,mat,width=.7,ranges=[(1,END)],z=.10):
 c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=width;c.bevel_resolution=1;s=c.splines.new('POLY');s.points.add(len(pts)-1)
 for p,xy in zip(s.points,pts):p.co=(xy[0],xy[1],z,1)
 o=bpy.data.objects.new(name,c);sc.collection.objects.link(o);o.parent=hud;o.data.materials.append(mat);vis(o,ranges);return o
def rect(name,x,y,w,h,mat,ranges,z=-.4):
 o=mesh(name,[(x-w/2,y-h/2,z),(x+w/2,y-h/2,z),(x+w/2,y+h/2,z),(x-w/2,y+h/2,z)],[(0,1,2,3)],mat,parent=hud);vis(o,ranges);return o
def disk(name,x,y,r,mat,ranges,z=.3):
 v=[(x+r*math.cos(i*math.tau/32),y+r*math.sin(i*math.tau/32),z) for i in range(32)];o=mesh(name,v,[tuple(range(32))],mat,parent=hud);vis(o,ranges);return o
# Persistent conditions. Teaching time is not the electrical simulation clock.
txt('单像素驱动：从图层到电流路径',-470,244,23)
txt('正常工作前提：参考已稳定，FAULT=0，PERMIT=1；PWM指缓冲后的 PWM_DRIVE。',-470,217,12,GRAY,[(601,END)])
txt('真实GDS平面 · PDK名义层高×12 · 分层位移为教学展开，介质未画出',-470,217,12,GRAY,[(1,600)])
txt('箭头表示常规电流方向；运动速度与电荷量不按比例。此动画不新增电路、TCAD或电热仿真。',-470,-266,10,GRAY)
chapters=[(1,72,'01 先看整体','当前是39 MOS模拟宏。接下来展开图层，再定位其中六只像素MOS。'),(73,144,'02 第三层金属 M3','先抬起M3：这里分配电源与信号总线。颜色代表图层，不代表金属本色。'),(145,192,'03 第二层通孔 Via2','Via2位于M2与M3之间；只有放置通孔的位置，才有局部垂直连接。'),(193,240,'04 第二层金属 M2','M2从器件端点接向总线；平面交叉并不自动形成电气连接。'),(241,288,'05 第一层通孔 Via1','Via1连接M1和M2。展开后的空隙是观察手段，不是真实空气层。'),(289,336,'06 第一层金属 M1','M1连接器件接触孔，再经Via1接到更高金属层。'),(337,384,'07 接触孔 Contact','Contact分别连接扩散区或多晶硅栅极；它们的起始高度不同。'),(385,432,'08 器件层','Poly栅极跨过有源区；井/有源层只作图层示意，不代表掺杂深度。'),(433,528,'09 看清上下层关系','器件 → Contact → M1 → Via1 → M2 → Via2 → M3。'),(529,600,'10 合拢后看像素','恢复层叠关系；下一幕左边是原理图，右边是相同器件的真实版图局部。'),(601,696,'11 对照相同编号','1参考管、2输出管、3传递管、4下拉管、5/6反相器：两图编号一一对应。'),(697,936,'12 PWM高电平：LED导通','3传递BIAS栅压，4关闭；2吸取LED电流。1的参考支路继续工作。'),(937,960,'13 下降沿：栅极放电','3关闭，4短暂释放GATE电荷。紫色运动只表示边沿充放电。'),(961,1176,'14 PWM低电平：LED关断','4把GATE保持在低电位，2关断。参考支路仍有电流；栅极稳态不持续吸流。'),(1177,1200,'15 上升沿：重新建立栅压','3重新导通，给GATE充电；4关闭。这里是慢放示意，不是实际纳秒波形。'),(1201,1392,'16 再次导通','栅压稳定后，紫色充电箭头停止；橙色LED电流继续，青绿色参考电流继续。'),(1393,1536,'17 把原理与版图连起来','PWM控制导通时间；电流镜设定导通电流。参考支路、栅极控制和LED输出是三条不同路径。')]
for a,b,title,caption in chapters:
 txt(title,-470,188,15,INK,[(a,b)]);txt(caption,-470,-239,12,INK,[(a,b)])
 sc.timeline_markers.new(title,frame=a)
# Layer names in the overview are screen-aligned and linked to visible groups.
for j,k in enumerate([42,38,36,35,34,33,30,22]):
 rr=[(73,600)];yy=151-j*29
 txt(NAMES[k],346,yy,13,material('图层标注'+str(k),C[k],True),rr)
# Pixel schematic textures are packed; six MOS labels are shared with physical markers.
for state,rr in [('high',[(601,936),(1177,END)]),('low',[(937,1176)])]:
 img=bpy.data.images.load(str(OUT/f'figures/pwm-{state}.png'));img.pack();m=bpy.data.materials.new('原理图-'+state);m.use_nodes=True;n=m.node_tree.nodes;n.clear();tex=n.new('ShaderNodeTexImage');tex.image=img;e=n.new('ShaderNodeEmission');o=n.new('ShaderNodeOutputMaterial');m.node_tree.links.new(tex.outputs['Color'],e.inputs[0]);m.node_tree.links.new(e.outputs[0],o.inputs['Surface'])
 plane=rect('原理图'+state,-300,-17,338,400,m,rr,z=.02)
 uv=plane.data.uv_layers.new(name='UVMap')
 for loop,co in zip(uv.data,[(0,0),(1,0),(1,1),(0,1)]):loop.uv=co
# Project real 3D paths onto a dedicated annotation plane, retaining raw paths in JSON.
def project(p):
 v=Vector((p['x_um'],p['y_um'],p['z_nominal_um']*Z));q=pixrot.inverted()@(v-pixpos);return Vector((q.x/pixscale*1000,q.y/pixscale*1000))
def route(key):
 p=MAP['paths'][key]['points'];res=[]
 for a in p:
  a=dict(a);a['x_um']=max(503,min(632,a['x_um']));q=project(a)
  if not res or (q-res[-1]).length>1e-4:res.append(q)
 return res
HIGH=[(697,936),(1201,END)];LOW=[(961,1176)];REFR=[(697,END)];FALL=[(937,960)];RISE=[(1177,1200)]
def flowing(key,mat,ranges,n=4,period=90):
 p=route(key);line('电流路径 '+key,p,mat,1.0,ranges);lens=[0]
 for a,b in zip(p,p[1:]):lens.append(lens[-1]+(b-a).length)
 def position(s):
  d=s*lens[-1]
  for i in range(1,len(lens)):
   if d<=lens[i]:
    v=p[i]-p[i-1];return p[i-1]+v*((d-lens[i-1])/(lens[i]-lens[i-1])),math.atan2(v.y,v.x)
  return p[-1],0
 for i in range(n):
  ob=mesh('方向箭头 '+key+str(i),[(5,0,.4),(-3.5,2.8,.4),(-3.5,-2.8,.4)],[(0,1,2)],mat,parent=hud);vis(ob,ranges)
  for a,b in ranges:
   for fr in range(a,b+1):
    phase=((fr-a)/period+i/n)%1;q,angle=position(phase);ob.location=(q.x,q.y,0);ob.rotation_euler.z=angle;ob.keyframe_insert('location',frame=fr);ob.keyframe_insert('rotation_euler',frame=fr)
  for f in ob.animation_data.action.fcurves:
   if not f.data_path.startswith('hide'):
    for pt in f.keyframe_points:pt.interpolation='LINEAR'
flowing('led_high',LED,HIGH,4,120);flowing('reference',REF,REFR,4,140);flowing('gate_discharge_low_edge',GATE,FALL,2,28);flowing('pass_gate_charge_high_edge',GATE,RISE,2,28)
# Dashed connection continues from the GATE bus to the actual output-MOS gate.
# This is a voltage-control net, never a steady-state flow animation.
gate_points=route('gate_voltage_control')
for j,(a,b) in enumerate(zip(gate_points,gate_points[1:])):
 length=(b-a).length
 for n in range(math.ceil(length/5)):
  start=n*5
  if length<1e-6:continue
  line('GATE控制电压虚线 '+str(j)+'-'+str(n),[a+(b-a)*(start/length),a+(b-a)*(min(start+2.5,length)/length)],GATE,.55,[(697,END)])
# Number badges bind symbols to true device centres. Names remain in schematic and table.
ids=['P_REF','P_OUT','P_PASS','P_CLAMP','P_INV_N','P_INV_P']
for i,k in enumerate(ids,1):
 d=MAP['devices'][k];x,y=d['center_um'];q=project({'x_um':x,'y_um':y,'z_nominal_um':.9});yy=q.y+17
 disk('器件编号底'+str(i),q.x,yy,8.2,WHITE,[(601,END)],.5);txt(str(i),q.x,yy-5.7,14,INK,[(601,END)],'CENTER')
 txt(['参考管','输出管','传递管','下拉管','反相NMOS','反相PMOS'][i-1],q.x,yy+14,9,INK,[(601,END)],'CENTER')
txt('右图：真实像素版图局部',30,167,13,INK,[(601,END)])
txt('BIAS / VSS 总线向左延续；此处为裁切边界',28,-151,9,GRAY,[(601,END)])
txt('橙：LED电流    绿：参考电流',28,-174,11,GRAY,[(697,END)])
txt('紫色虚线：栅压连接；运动箭头：边沿充放电',28,-193,9,GRAY,[(697,END)])
txt('正常PWM低 ≠ 故障保护关断',28,-213,11,GRAY,[(601,END)])
# Off-chip LED is explicitly represented outside the cropped layout, not manufactured GDS.
port=project(MAP['paths']['led_high']['points'][0]);ledx=10;ledy=80
for rr,h in [(HIGH,LED),([(601,696),(937,1200)],GRAY)]:
 txt('片外 MicroLED',ledx-50,ledy+25,11,h,rr);line('片外LED引线',[(ledx,ledy-15),(ledx,port.y),(port.x,port.y)],h,.9,rr)
 meshob=mesh('片外LED符号',[(ledx-8,ledy+9,.3),(ledx+8,ledy+9,.3),(ledx,ledy-5,.3)],[(0,1,2)],h,parent=hud);vis(meshob,rr);line('LED阴极',[(ledx-9,ledy-6),(ledx+9,ledy-6)],h,.8,rr)
 txt('LED_K',port.x-14,port.y-14,9,GRAY,rr)
# A readable PWM timing strip; pulse heights are logical levels, not measured voltages.
for state,rr in [('高',[(601,936),(1177,END)]),('低',[(937,1176)])]:
 txt('PWM_DRIVE = '+state,205,185,13,LED if state=='高' else GRAY,rr)
# World and renderer.
world=bpy.data.worlds.new('白色背景');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(1,1,1,1);world.node_tree.nodes['Background'].inputs[1].default_value=1;sc.world=world
light=bpy.data.lights.new('柔和方向光','SUN');light.energy=2;light.angle=.35;o=bpy.data.objects.new('柔和方向光',light);sc.collection.objects.link(o);o.rotation_euler=(.35,-.4,-.3)
sc.render.engine='BLENDER_EEVEE_NEXT';sc.eevee.taa_render_samples=16;sc.render.resolution_x=1920;sc.render.resolution_y=1080;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.render.filepath=str(RAW/'frames/frame_');sc.view_settings.view_transform='Standard';sc.view_settings.look='None';sc.unit_settings.system='METRIC';sc.unit_settings.scale_length=1e-6
sc['source_gds_sha256']=D['gds_sha256'];sc['scope']='层叠展开和电流方向教学；非寄生/电流密度/光学模拟';sc['nominal_z_scale']=Z;sc['normal_conditions']='FAULT=0, PERMIT=1, reference settled';sc['annotation_projection']='Current arrows use fixed camera projection of audited 3D centre lines, not field simulation. Recompute if camera changes.'
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   a=area.spaces.active;a.region_3d.view_perspective='CAMERA';a.overlay.show_overlays=False;a.shading.type='MATERIAL';a.shading.use_scene_world=True
sc.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'pwm-layer-animation.blend'))
(OUT/'timeline.json').write_text(json.dumps({'fps':FPS,'frames':END,'duration_s':END/FPS,'chapters':[{'start_frame':a,'end_frame':b,'title':t,'caption':c} for a,b,t,c in chapters],'high_steady_ranges':HIGH,'low_steady_ranges':LOW,'reference_ranges':REFR,'gate_discharge_ranges':FALL,'gate_charge_ranges':RISE,'notes':'Teaching seconds do not represent SPICE time; all arrow speed and widths are illustrative.'},ensure_ascii=False,indent=2)+'\n')
if '--preview' in sys.argv:
 (RAW/'preview').mkdir(exist_ok=True)
 for frame in [1,144,384,500,650,720,948,1040,1188,1280,1490]:
  sc.frame_set(frame);sc.render.filepath=str(RAW/f'preview/{frame:04d}.png');bpy.ops.render.render(write_still=True)
print('ANIMATION_SCENE_READY')
