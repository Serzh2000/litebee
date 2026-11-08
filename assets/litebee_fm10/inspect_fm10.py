"""Run with Blender --background litebee_fm10.blend --python inspect_fm10.py."""
import bpy
import bmesh
import json
import math
from pathlib import Path
from mathutils import Vector

root = Path(__file__).resolve().parent
scene = bpy.context.scene
meshes = [o for o in scene.objects if o.type == 'MESH' and not any(t in o.name.lower() for t in ('floor', 'ground', 'backdrop', 'stage', 'plinth'))]
deps = bpy.context.evaluated_depsgraph_get()
points = [o.matrix_world @ Vector(c) for o in meshes for c in o.evaluated_get(deps).bound_box]
minimum = [min(v[i] for v in points) for i in range(3)]
maximum = [max(v[i] for v in points) for i in range(3)]
report = {
    'blender_version': bpy.app.version_string,
    'mesh_objects': len(meshes),
    'materials': len(bpy.data.materials),
    'collections': [c.name for c in bpy.data.collections],
    'bounds_min_m': minimum,
    'bounds_max_m': maximum,
    'bounds_dimensions_mm': [(maximum[i] - minimum[i]) * 1000 for i in range(3)],
    'finite_vertices': all(math.isfinite(v) for o in meshes for p in o.data.vertices for v in p.co),
    'empty_meshes': [o.name for o in meshes if not o.data.vertices],
    'camera': scene.camera.name if scene.camera else None,
    'units': scene.unit_settings.system,
}
open_meshes=[]
for o in meshes:
    bm=bmesh.new();bm.from_mesh(o.data)
    boundary=sum(not e.is_manifold for e in bm.edges)
    if boundary:open_meshes.append({'name':o.name,'non_manifold_edges':boundary})
    bm.free()
report['non_manifold_meshes']=open_meshes
plugs=[o for o in scene.objects if o.name.startswith('Motor two pin plug')]
leads=[o for o in scene.objects if o.name.startswith('Motor lead to dedicated two pin plug')]
def in_plug(point,plug):
    local=plug.matrix_world.inverted()@point
    return all(min(c[i] for c in plug.bound_box)-1e-6<=local[i]<=max(c[i] for c in plug.bound_box)+1e-6 for i in range(3))
ends=[o.matrix_world@o.data.splines[0].bezier_points[-1].co for o in leads]
report['motor_plugs']=len(plugs)
report['motor_supply_leads']=len(leads)
report['all_motor_leads_end_inside_plugs']=bool(leads) and all(any(in_plug(p,o) for o in plugs) for p in ends)
assert meshes and report['finite_vertices'] and not report['empty_meshes'], report
if leads:assert len(plugs)==4 and len(leads)==8 and report['all_motor_leads_end_inside_plugs'],report
with (root / 'verification.json').open('w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
print('MODEL_VERIFICATION', json.dumps(report, ensure_ascii=False))
