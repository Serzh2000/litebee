import bpy, math, os, bmesh
from mathutils import Vector
from math import pi
OUT=os.path.dirname(os.path.abspath(__file__))
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name != 'Collection' and c.users==0: bpy.data.collections.remove(c)
drone=bpy.data.collections.new('LiteBee FM aircraft'); bpy.context.scene.collection.children.link(drone)
def mat(n,c,metal=0,rough=.35,alpha=1):
 m=bpy.data.materials.new(n);m.diffuse_color=(*c,alpha);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,alpha);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough;p.inputs['Alpha'].default_value=alpha
 return m
white=mat('Ivory white ABS',(.82,.84,.81));gray=mat('Cool gray arm ABS',(.43,.47,.48));silver=mat('Brushed motor steel',(.65,.66,.62),.85,.24);black=mat('Black polymer',(.012,.015,.017));glass=mat('Optical lens',(.024,.035,.045),.3,.13);clear=mat('Frosted translucent propeller',(.8,.84,.83),0,.22,.56)
clear.node_tree.nodes.get('Principled BSDF').inputs['Transmission Weight'].default_value=.88
clear.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.14
clear.node_tree.nodes.get('Principled BSDF').inputs['IOR'].default_value=1.46
clear.node_tree.nodes.get('Principled BSDF').inputs['Alpha'].default_value=1
clear.diffuse_color=(.72,.79,.80,1)
led=mat('Opal LED diffuser',(.93,.94,.90),0,.28)
def put(o,n,m=None):
 o.name=n
 for c in list(o.users_collection):c.objects.unlink(o)
 drone.objects.link(o)
 if m:o.data.materials.append(m)
 return o
def bevel(o,r=.0008):
 b=o.modifiers.new('Molded edge radius','BEVEL');b.width=r;b.segments=3
 o.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL');return o
def box(n,loc,dim,m,r=.0006):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=put(bpy.context.object,n,m);o.dimensions=dim;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if r:bevel(o,r)
 return o
def rounded(n,loc,dim,m,r):
 w,l,h=dim;verts=[]
 for z in [-h/2,h/2]:
  for cx,cy,a in [(w/2-r,l/2-r,0),(-w/2+r,l/2-r,pi/2),(-w/2+r,-l/2+r,pi),(w/2-r,-l/2+r,3*pi/2)]:
   for i in range(9):
    t=a+i*pi/16;verts.append((cx+r*math.cos(t),cy+r*math.sin(t),z))
 N=len(verts)//2;faces=[tuple(range(N-1,-1,-1)),tuple(range(N,2*N))]
 for i in range(N):j=(i+1)%N;faces.append((i,j,j+N,i+N))
 me=bpy.data.meshes.new(n);me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new(n,me);drone.objects.link(o);o.location=loc;o.data.materials.append(m);bevel(o,.0004);return o
def cyl(n,loc,r,d,m,axis='Z',verts=48):
 bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=d,location=loc);o=put(bpy.context.object,n,m)
 if axis=='X':o.rotation_euler[1]=pi/2
 if axis=='Y':o.rotation_euler[0]=pi/2
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 return o
def hole(o,loc,r,d,axis='Z'):
 for modifier in list(o.modifiers):
  if modifier.type in {'BEVEL','WEIGHTED_NORMAL'}:o.modifiers.remove(modifier)
 c=cyl('Boolean tool',loc,r,d,None,axis,32);b=o.modifiers.new('Through bore','BOOLEAN');b.operation='DIFFERENCE';b.object=c;bpy.context.view_layer.objects.active=o
 bpy.ops.object.modifier_apply(modifier=b.name);bpy.data.objects.remove(c,do_unlink=True);normals(o)

def normals(o):
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free();o.data.update()
def tube(n,loc,ro,ri,d,m,axis='Z'):
 o=cyl(n,loc,ro,d,m,axis);hole(o,loc,ri,d*1.5,axis);bevel(o,.0003);return o

def difference(o,c):
 for modifier in list(o.modifiers):
  if modifier.type in {'BEVEL','WEIGHTED_NORMAL'}:o.modifiers.remove(modifier)
 b=o.modifiers.new('Molded recess','BOOLEAN');b.operation='DIFFERENCE';b.object=c;bpy.context.view_layer.objects.active=o
 bpy.ops.object.modifier_apply(modifier=b.name);bpy.data.objects.remove(c,do_unlink=True);normals(o)

def front_panel(n,loc,w,h,d,r,m):
 o=rounded(n,loc,(w,h,d),m,r);o.rotation_euler[0]=pi/2
 bpy.context.view_layer.update();return o

def landing_apron(mx,my,angle):
 # The landing foot is a thin curved continuation of the OUTER end of
 # the landing rail. It has no separate rectangular post or flat block sole.
 vs=[];segments=24
 levels=[(.0140,.0066,.0060,1.12),(.0115,.0067,.0051,1.05),(.0020,.0074,.0057,.68),(.0005,.0073,.0059,.53)]
 for z,ro,ri,half in levels:
  for r in [ro,ri]:
   for i in range(segments+1):
    a=angle-half+2*half*i/segments
    vs.append((mx+r*math.cos(a),my+r*math.sin(a),z))
 fs=[];stride=2*(segments+1)
 for j in range(len(levels)-1):
  for k in range(2):
   for i in range(segments):
    a=j*stride+k*(segments+1)+i;b=a+stride
    fs.append((a,a+1,b+1,b) if k==0 else (a,b,b+1,a+1))
 for j in [0,len(levels)-1]:
  for i in range(segments):
   a=j*stride+i;b=a+segments+1;fs.append((a,b,b+1,a+1))
 for j in range(len(levels)-1):
  for i in [0,segments]:
   a=j*stride+i;b=a+segments+1;fs.append((a,a+stride,b+stride,b))
 me=bpy.data.meshes.new('Tapered curved landing apron');me.from_pydata(vs,[],fs);me.update()
 o=bpy.data.objects.new('Integral curved landing fin',me);drone.objects.link(o);o.data.materials.append(gray);bevel(o,.00035)
 return o
def wire(n,pts,r=.0005,m=black,handles='AUTO'):
 cu=bpy.data.curves.new(n,'CURVE');cu.dimensions='3D';cu.resolution_u=16;cu.bevel_depth=r;cu.bevel_resolution=3;s=cu.splines.new('BEZIER');s.bezier_points.add(len(pts)-1)
 for b,p in zip(s.bezier_points,pts):b.co=p;b.handle_left_type=handles;b.handle_right_type=handles
 o=bpy.data.objects.new(n,cu);drone.objects.link(o);o.data.materials.append(m);return o
# The block construction is modeled as individual drilled molded parts.
base=box('Main lower white frame',(0,0,.019),(.038,.070,.009),white,.003)
for sx in [-1,1]:
 rail=box('Perforated longitudinal body rail',(sx*.020,0,.027),(.008,.064,.010),white,.001)
 for y in [-.024,-.016,-.008,0,.008,.016,.024]:hole(rail,(sx*.020,y,.027),.0024,.013,'X')
body=box('Removable gray 2S battery',(0,.005,.035),(.035,.051,.020),gray,.002)
box('White front electronics block',(0,-.0232,.035),(.035,.0054,.020),white,.0008)
# A single continuous battery shell avoids the intersecting rear-cap faces.
rounded('Battery top seam',(0,.005,.0436),(.0351,.0511,.00045),gray,.002)
for x in [-.012,-.004,.004,.012]:
 for y in [.019,.027]:tube('Rear gray hollow brick stud',(x,y,.0465),.00305,.00195,.003,gray)
 for y in [-.026,-.018]:tube('Front white hollow brick stud',(x,y,.0465),.00305,.00195,.003,white)
# Front camera enclosure and recessed lens, facing -Y.
cam=box('Front camera white housing',(0,-.033,.033),(.030,.014,.024),white,.003)
rim=front_panel('Rounded square camera bezel',(0,-.0404,.033),.025,.024,.0024,.0045,white)
for target in [cam,rim]:
 cutter=front_panel('Camera square recess tool',(0,-.041,.033),.0208,.0198,.008,.0038,white)
 difference(target,cutter)
front_panel('Camera recess ivory backing',(0,-.0373,.033),.021,.020,.0006,.0038,white)
cyl('Lens dark surround',(0,-.0384,.033),.0074,.0008,black,'Y')
cyl('Optical glass',(0,-.0390,.033),.0044,.00035,glass,'Y')
cyl('Lens reflection',(-.0013,-.03925,.0348),.00125,.0001,mat('Lens reflection',(.08,.12,.14),.2,.1),'Y')
box('Camera upper molded brow',(0,-.0408,.044),(.026,.005,.0025),white,.001)
gold=mat('Yellow LED support pegs',(.75,.49,.035),.15,.35)
for x in [-.012,.012]:
 for y in [-.018,.004]:cyl('Yellow LED stand off',(x,y,.049),.0027,.0045,gold)
rounded('FM square opal light diffuser',(0,-.007,.055),(.042,.042,.007),led,.006)
# 148 mm nominal diagonal motor wheelbase. Front/back rectangle from references.
for sx in [-1,1]:
 for sy in [-1,1]:
  mx,my=sx*.056,sy*.048
  root=Vector((sx*.025,sy*.035,.0125));end=Vector((mx,my,.0125));mid=(root+end)/2;length=(end-root).length
  angle=math.atan2(end.y-root.y,end.x-root.x)
  tray=rounded('Thin capsule landing rail',mid,(length+.013,.013,.0023),gray,.0064);tray.rotation_euler[2]=angle
  # Long main beam is supported by the thin landing rail, not a separate leg.
  arm=rounded('Gray perforated main arm',(mid.x,mid.y,.0184),(length+.009,.009,.0086),gray,.0044);arm.rotation_euler[2]=angle
  for t in [0,.25,.5,.75]:
   h=root.lerp(end,t);h.z=.0184;hole(arm,h,.0025,.014)
  # The curved outer apron grows from the round motor-end platform.
  landing_apron(mx,my,angle)
  # Upper two-hole beam at motor end, with genuine vertical bores.
  direction=(end-root).normalized()
  pos=end-direction*(length*.25);pos.z=.025
  beam=rounded('Gray two hole motor beam',pos,(length*.5+.009,.009,.008),gray,.0044);beam.rotation_euler[2]=angle
  for t in [.25,.50]:
   h=end-direction*(length*t);h.z=.025;hole(beam,h,.00265,.016)
   tube('Black recessed friction-pin sleeve',(h.x,h.y,.025),.00248,.00185,.0068,black)
  # White inner anchor tabs and visible dark pin sockets.
  tab=rounded('White body to arm mounting tab',(sx*.022,sy*.035,.020),(.016,.010,.009),white,.0045)
  hole(tab,(sx*.025,sy*.035,.020),.0025,.014)
  tube('Attachment black pin sleeve',(sx*.025,sy*.035,.021),.00235,.00165,.006,black)
  tube('Motor gray cylindrical socket',(mx,my,.019),.0064,.0048,.014,gray)
  clip=box('Motor cup molded retaining clip',(mx+sy*.0059,my-sx*.003,.021),(.003,.002,.0035),gray,.0006);clip.rotation_euler[2]=angle
  cyl('1020 brushed silver motor',(mx,my,.0265),.0049,.014,silver)
  top=cyl('Motor vented metal end cap',(mx,my,.0337),.00495,.0013,silver)
  for a in range(6):
   th=a*pi/3;hole(top,(mx+.0035*math.cos(th),my+.0035*math.sin(th),.0337),.00065,.003)
  cyl('Motor shaft',(mx,my,.0375),.0008,.007,silver)
  # Low friction pins near arm root.
  pivot=root.lerp(end,.25)
  cyl('Arm pivot pin',(pivot.x,pivot.y,.0227),.0024,.006,gray)
  tube('Arm pivot collar',(pivot.x,pivot.y,.026),.0033,.0018,.0013,gray)
  # Transparent twin blades: broad roots taper to rounded narrow tips.
  a=(-.85 if sx*sy==1 else .85)
  verts=[];faces=[]
  outline=[(.001,-.0018),(.006,-.0049),(.011,-.0057),(.017,-.0054),(.025,-.0042),(.033,-.003),(.0375,-.002),(.0375,.0008),(.033,.001),(.024,.0013),(.016,.0020),(.009,.0035),(.004,.0032),(.001,.0018)]
  for side in [-1,1]:
   st=len(verts)
   for z in [-.00035,.00035]:
    for x,y in outline:
     pitch=(.25-.16*(x/.0375))*(1 if sx*sy==1 else -1)
     lift=y*math.sin(pitch)+.0004*math.sin(pi*x/.0375)
     x*=side;y*=side;verts.append((mx+x*math.cos(a)-y*math.sin(a),my+x*math.sin(a)+y*math.cos(a),.0382+z+lift))
   N=len(outline);faces.extend([tuple(st+i for i in range(N-1,-1,-1)),tuple(st+N+i for i in range(N))])
   for i in range(N):j=(i+1)%N;faces.append((st+i,st+j,st+N+j,st+N+i))
  mesh=bpy.data.meshes.new('Airfoil mesh');mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new('Transparent two blade propeller',mesh);drone.objects.link(o);o.data.materials.append(clear);bevel(o,.00025)
  hub=cyl('Clear propeller hub',(mx,my,.0385),.0025,.006,clear);bevel(hub,.00065)
  port=box('Dedicated motor socket housing',(sx*.0242,sy*.024,.021),(.0024,.0046,.004),white,.0004)
  box('Motor socket dark recess',(sx*.02545,sy*.024,.021),(.00025,.0038,.0032),black,.0001)
  box('Motor two pin plug',(sx*.0260,sy*.024,.021),(.002,.0031,.0026),white,.0003)
  for offset,m in [(-.00045,mat('Motor red lead '+str(sx)+str(sy),(.42,.018,.012))),(.00045,mat('Motor blue lead '+str(sx)+str(sy),(.018,.12,.30)))]:
   # Most of each lead is enclosed in the motor cup/arm. Only the short
   # service loop at the body end is exposed; its end enters its own plug.
   # Stay inside the side wall of the arm, clear of its through-holes.
   # Vector handles prevent automatic spline tangents escaping the housing.
   normal=Vector((-direction.y,direction.x,0))
   enclosed=[root.lerp(end,t)+normal*(.0031+offset) for t in [.88,.65,.40,.08]]
   pts=[(mx,my,.020)]+[(v.x,v.y,.018) for v in enclosed]+[(sx*.027,sy*.028+offset,.0173),(sx*.0267,sy*.024+offset,.021)]
   wire('Motor lead to dedicated two pin plug',pts,.00025,m,'VECTOR')
# Pair of characteristic cable loops from side connector up to light module.
for sx in [-1,1]:
 for offset in [-.00085,0,.00085]:
  if sx==-1:
   pts=[(-.023,-.012+offset,.017),(-.032,-.014+offset,.025),(-.033,-.013+offset,.046),(-.019,-.007+offset,.050)]
  else:
   pts=[(.019,-.007+offset,.011),(.033,-.009+offset,.019),(.036,-.006+offset,.036),(.028,-.009+offset,.032),(.026,-.012+offset,.021),(.023,-.012+offset,.020)]
  wire('Three conductor module cable',pts,.00040)
 box('White cable connector',(sx*.023,-.012,.017 if sx==-1 else .020),(.003,.004,.0026),white,.0003)
# Add underbody PCB and battery seam detail.
module=rounded('White formation positioning module',(0,.004,.010),(.037,.042,.006),white,.003)
box('Module dark separation gap',(0,.004,.0137),(.032,.038,.0006),black,.0002)
for x in [-.012,-.006,0,.006,.012]:
 slot=box('Vent cutting tool',(x,-.012,.008),(.003,.008,.004),None,.0004)
 b=module.modifiers.new('Underside ventilation slots','BOOLEAN');b.operation='DIFFERENCE';b.object=slot;bpy.context.view_layer.objects.active=module;bpy.ops.object.modifier_apply(modifier=b.name);bpy.data.objects.remove(slot,do_unlink=True)
cyl('Downward positioning camera surround',(0,.009,.0072),.0065,.001,black)
cyl('Downward positioning lens',(0,.009,.0065),.004,.0006,glass)
box('USB socket metal rim',(.020,-.005,.017),(.003,.007,.003),silver,.0002)
box('USB dark opening',(.0216,-.005,.017),(.0004,.0048,.0014),black,.0001)
# Booleans run on unmodified solids; edge rounding and normals are finalized
# only after drilling. This avoids inverted triangles around concave n-gons.
for o in drone.objects:
 if o.type=='MESH':
  normals(o)
  if not any(m.type=='BEVEL' for m in o.modifiers):bevel(o,.00025)
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.length_unit='MILLIMETERS'
scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True
scene.world.color=(.25,.25,.25)
# Studio objects stay outside aircraft collection.
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,0));floor=bpy.context.object;floor.name='Studio floor';floor.data.materials.append(mat('Studio warm gray',(.22,.245,.26),0,.65))
def area(n,loc,power,size):
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.name=n;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector((0,0,.02))-o.location).to_track_quat('-Z','Y').to_euler()
area('Large softbox',(.1,-.16,.24),.8,.20);area('Fill',(-.20,-.02,.13),.5,.16);area('Rim',(.04,.16,.18),.9,.12)
bpy.ops.object.camera_add(location=(.195,-.25,.205));camera=bpy.context.object;camera.rotation_euler=(Vector((0,0,.027))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=.25;scene.camera=camera
scene.render.resolution_x=1500;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'
scene.render.image_settings.file_format='PNG';scene.render.filepath=os.path.join(OUT,'preview.png')
bpy.ops.object.select_all(action='DESELECT')
for o in drone.objects:o.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'litebee_fm10.blend'))
try:bpy.ops.export_scene.gltf(filepath=os.path.join(OUT,'litebee_fm10.glb'),use_selection=True,export_format='GLB')
except Exception as e:print('GLB export:',e)
# Render in a fresh process after export: Blender 5.2 can stall when Cycles
# follows a glTF exporter invocation in the same background process.

