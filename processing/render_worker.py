# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
import argparse
import math
import sys
from pathlib import Path

import bpy
import mathutils


def get_mesh_world_bbox(frame):
    bpy.context.scene.frame_set(frame)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bbox_min = mathutils.Vector((float('inf'),) * 3)
    bbox_max = mathutils.Vector((float('-inf'),) * 3)
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.to_mesh()
        for v in mesh.vertices:
            world_co = eval_obj.matrix_world @ v.co
            bbox_min.x = min(bbox_min.x, world_co.x)
            bbox_min.y = min(bbox_min.y, world_co.y)
            bbox_min.z = min(bbox_min.z, world_co.z)
            bbox_max.x = max(bbox_max.x, world_co.x)
            bbox_max.y = max(bbox_max.y, world_co.y)
            bbox_max.z = max(bbox_max.z, world_co.z)
        eval_obj.to_mesh_clear()
    return bbox_min, bbox_max


def setup_camera_and_light(scene):
    # Frame the camera around the character's actual bounding box (sampled
    # across the clip) instead of a fixed guessed position, since retargeted
    # subjects differ in body size and root position.
    sample_frames = sorted(set([
        scene.frame_start,
        (scene.frame_start + scene.frame_end) // 2,
        scene.frame_end,
    ]))
    bbox_min = mathutils.Vector((float('inf'),) * 3)
    bbox_max = mathutils.Vector((float('-inf'),) * 3)
    for frame in sample_frames:
        f_min, f_max = get_mesh_world_bbox(frame)
        bbox_min.x, bbox_min.y, bbox_min.z = min(bbox_min.x, f_min.x), min(bbox_min.y, f_min.y), min(bbox_min.z, f_min.z)
        bbox_max.x, bbox_max.y, bbox_max.z = max(bbox_max.x, f_max.x), max(bbox_max.y, f_max.y), max(bbox_max.z, f_max.z)

    center = (bbox_min + bbox_max) / 2
    size = bbox_max - bbox_min

    cam_data = bpy.data.cameras.new("DemoCamera")
    cam_obj = bpy.data.objects.new("DemoCamera", cam_data)
    scene.collection.objects.link(cam_obj)

    margin = 1.3
    # angle_x/angle_y depend on the render resolution's aspect ratio and must
    # be read after resolution is set, so that a tall subject is fit against
    # the (narrower) vertical FOV, not the wider horizontal one.
    distance_for_width = (size.x / 2) / math.tan(cam_data.angle_x / 2)
    distance_for_height = (size.z / 2) / math.tan(cam_data.angle_y / 2)
    distance = max(distance_for_width, distance_for_height) * margin
    distance = max(distance, 2.0)

    # Characters face -Y, so place the camera on the +Y side to shoot the front.
    cam_obj.location = mathutils.Vector((center.x, center.y + distance, center.z))
    direction = center - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam_obj

    sun_data = bpy.data.lights.new("DemoSun", type='SUN')
    sun_data.energy = 3.0
    sun_obj = bpy.data.objects.new("DemoSun", sun_data)
    scene.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = (math.radians(45), 0.0, math.radians(45))


def render_video(fbx_path: Path, out_video_path: Path, fps: int = 30):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx_path))

    scene = bpy.context.scene

    # Size the frame range to the imported animation instead of relying on
    # Blender's default new-scene range (which would hold the last pose for
    # the remaining frames if the action is shorter).
    frame_starts, frame_ends = [], []
    for action in bpy.data.actions:
        start, end = action.frame_range
        frame_starts.append(start)
        frame_ends.append(end)
    if frame_ends:
        scene.frame_start = int(min(frame_starts))
        scene.frame_end = int(max(frame_ends))

    scene.render.fps = fps
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720

    setup_camera_and_light(scene)

    out_video_path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(out_video_path)

    bpy.ops.render.render(animation=True)


def main():
    parser = argparse.ArgumentParser(description="Render a single FBX animation to a video file.")
    parser.add_argument('--fbx_path', type=Path, required=True)
    parser.add_argument('--out_video_path', type=Path, required=True)
    parser.add_argument('--fps', type=int, default=30)

    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parser.parse_args(argv)

    render_video(args.fbx_path, args.out_video_path, args.fps)


if __name__ == '__main__':
    main()
