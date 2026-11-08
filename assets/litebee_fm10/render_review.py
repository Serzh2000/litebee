"""Render the assembled aircraft and the corrected motor/landing-rail detail."""
import bpy, sys
from pathlib import Path
from mathutils import Vector

root=Path(__file__).resolve().parent
scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.samples=48
scene.cycles.use_denoising=True
scene.render.filepath=str(root/'preview.png')
if '--detail' in sys.argv:
 scene.camera.location=(.115,-.13,.075)
 scene.camera.rotation_euler=(Vector((.052,-.046,.022))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
 scene.camera.data.ortho_scale=.057
 scene.render.resolution_x=1100
 scene.render.resolution_y=1000
 scene.render.filepath=str(root/'motor_detail.png')
bpy.ops.render.render(write_still=True)
