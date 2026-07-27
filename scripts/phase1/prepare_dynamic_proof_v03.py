import bpy
import math
import sys
from pathlib import Path
from mathutils import Vector


def look_at(obj, point):
    direction = Vector(point) - obj.location
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()


def set_key(bone, frame, rotation=None, location=None):
    bone.rotation_mode = 'XYZ'
    if rotation is not None:
        bone.rotation_euler = [math.radians(v) for v in rotation]
        bone.keyframe_insert(data_path='rotation_euler', frame=frame)
    if location is not None:
        bone.location = location
        bone.keyframe_insert(data_path='location', frame=frame)


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if len(args) != 2:
        raise SystemExit('usage: blender --background source.blend --python prepare_dynamic_proof_v03.py -- output.blend output.mp4')
    out_blend = str(Path(args[0]).resolve())
    out_mp4 = str(Path(args[1]).resolve())

    scene = bpy.data.scenes.get('BDA_Female_Dynamic')
    if scene is None:
        raise RuntimeError('BDA_Female_Dynamic scene not found')
    bpy.context.window.scene = scene

    armatures = [o for o in scene.objects if o.type == 'ARMATURE']
    if not armatures:
        raise RuntimeError('No armature found in BDA_Female_Dynamic')
    arm = next((o for o in armatures if 'female' in o.name.lower()), armatures[0])

    # Replace the previous exaggerated animation with a restrained, physically plausible proof.
    arm.animation_data_clear()
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)

    bones = arm.pose.bones
    head = bones.get('head')
    neck = bones.get('neck01') or bones.get('neck02')
    spine = bones.get('spine03') or bones.get('spine02') or bones.get('spine01')
    root = bones.get('root') or bones.get('pelvis')
    l_arm = bones.get('upperarm01.L') or bones.get('upperarm.L')
    r_arm = bones.get('upperarm01.R') or bones.get('upperarm.R')
    l_fore = bones.get('lowerarm01.L') or bones.get('lowerarm.L')
    r_fore = bones.get('lowerarm01.R') or bones.get('lowerarm.R')

    frames = [1, 18, 36, 54, 72]
    # Neutral dancer stance, a small breath, eyes/attention shift expressed by head and neck,
    # then a restrained turn toward camera. Avoids the previous unnatural head roll.
    if root:
        for f, z in zip(frames, [0.0, 0.004, 0.0, 0.003, 0.0]):
            set_key(root, f, rotation=(0, 0, 0), location=(0, 0, z))
    if spine:
        for f, rot in zip(frames, [(0, 0, 0), (-0.4, 0, 0), (0, 0, 0), (-0.25, 0, 0), (0, 0, 0)]):
            set_key(spine, f, rotation=rot)
    if neck:
        for f, rot in zip(frames, [(0, 0, 0), (0, 0, 0), (0, 0, -3), (0, 0, -7), (0, 0, -10)]):
            set_key(neck, f, rotation=rot)
    if head:
        for f, rot in zip(frames, [(0, 0, 0), (0, 0, 0), (0, 0, -4), (0, 0, -10), (0, 0, -16)]):
            set_key(head, f, rotation=rot)
    if l_arm:
        for f, rot in zip(frames, [(0, 0, 7), (0, 0, 6), (0, 0, 5), (0, 0, 4), (0, 0, 3)]):
            set_key(l_arm, f, rotation=rot)
    if r_arm:
        for f, rot in zip(frames, [(0, 0, -7), (0, 0, -6), (0, 0, -5), (0, 0, -4), (0, 0, -3)]):
            set_key(r_arm, f, rotation=rot)
    if l_fore:
        for f in frames:
            set_key(l_fore, f, rotation=(0, 0, -2))
    if r_fore:
        for f in frames:
            set_key(r_fore, f, rotation=(0, 0, 2))

    # Smooth all curves.
    if arm.animation_data and arm.animation_data.action:
        for fc in arm.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'

    # Camera: full-height portrait framing with enough room context to prove true 3D parallax.
    cam = scene.camera
    if cam is None:
        cam_data = bpy.data.cameras.new('FemaleProofCamera')
        cam = bpy.data.objects.new('FemaleProofCamera', cam_data)
        scene.collection.objects.link(cam)
        scene.camera = cam
    target = arm.matrix_world.translation + Vector((0.0, 0.0, 0.98))
    cam.location = target + Vector((0.0, -3.35, 0.22))
    cam.data.lens = 58
    cam.data.sensor_width = 36
    look_at(cam, target)

    # A restrained camera drift creates visible spatial parallax without fake zooming.
    cam.keyframe_insert(data_path='location', frame=1)
    cam.location.x += 0.14
    cam.location.y += 0.08
    look_at(cam, target + Vector((0.0, 0.0, 0.02)))
    cam.keyframe_insert(data_path='location', frame=72)
    cam.keyframe_insert(data_path='rotation_euler', frame=1)
    cam.keyframe_insert(data_path='rotation_euler', frame=72)

    # Add soft, natural classroom lighting; avoid dark stylization and harsh outlines.
    for o in list(scene.objects):
        if o.type == 'LIGHT' and o.name.startswith('Proof_'):
            bpy.data.objects.remove(o, do_unlink=True)
    def area(name, loc, energy, size, color):
        data = bpy.data.lights.new(name, type='AREA')
        data.energy = energy
        data.shape = 'DISK'
        data.size = size
        data.color = color
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = loc
        look_at(obj, target)
        return obj
    area('Proof_Key', (-2.2, -2.0, 3.2), 900, 3.5, (1.0, 0.91, 0.79))
    area('Proof_Fill', (2.4, -1.5, 2.3), 520, 3.0, (0.84, 0.91, 1.0))
    area('Proof_Rim', (0.6, 1.2, 3.0), 650, 2.5, (1.0, 0.86, 0.68))

    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.frame_start = 1
    scene.frame_end = 72
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
    scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
    scene.render.filepath = out_mp4
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = 'RGB'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.render.use_file_extension = True
    if hasattr(scene, 'eevee'):
        scene.eevee.taa_samples = 16
    if hasattr(scene, 'render'):
        scene.render.use_motion_blur = True
        scene.render.motion_blur_shutter = 0.35

    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    print('prepared', out_blend, out_mp4, 'armature', arm.name, 'camera', tuple(cam.location))


if __name__ == '__main__':
    main()
