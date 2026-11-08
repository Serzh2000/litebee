import bpy
from pathlib import Path
from mathutils import Vector

root = Path(__file__).resolve().parent
scene = bpy.context.scene
studio = bpy.data.collections.get('Collection')
if studio:
    studio.name = 'Studio lighting and camera'
scene.render.filepath = str(root / 'preview.png')
aircraft = bpy.data.collections['LiteBee FM aircraft']
bpy.ops.object.select_all(action='DESELECT')
for o in aircraft.objects:
    o.select_set(True)
bpy.context.view_layer.objects.active = next(o for o in aircraft.objects if o.type == 'MESH')
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            space.clip_start = 0.0001
            space.clip_end = 100
            space.shading.type = 'MATERIAL'
            space.region_3d.view_location = Vector((0, 0, .025))
            space.region_3d.view_distance = .26
            space.region_3d.view_rotation = scene.camera.rotation_euler.to_quaternion()
scene['reference_notes'] = 'Photographic reconstruction of one LiteBee Wing FM aircraft. See README.ru.md and reference_board.jpg. Not factory CAD.'
bpy.ops.wm.save_as_mainfile(filepath=str(root / 'litebee_fm10.blend'))
# A top view enables direct comparison to the downloaded top reference.
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x = 1100
scene.render.resolution_y = 1100
scene.render.resolution_percentage = 100
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.display.shading.background_type = 'WORLD'
scene.world.color = (.15, .15, .15)
scene.camera.location = (0, 0, .4)
scene.camera.rotation_euler = (0, 0, 0)
scene.camera.data.ortho_scale = .22
for o in studio.objects:
    if o.type == 'MESH':
        o.hide_render = True
scene.render.filepath = str(root / 'top_view.png')
bpy.ops.render.render(write_still=True)
