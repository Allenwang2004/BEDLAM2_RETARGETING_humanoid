# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
"""Render motion clips to individual video files.

Two modes:

  --qpos_dir   Replay MuJoCo `qpos` clips on their MJCF and render offscreen.
               This is the one to use for eyeballing pipeline output: it shows
               the actual deliverable driving the actual robot model, so it
               exercises every stage including the final FBX -> qpos step, and
               the model's checkered floor makes foot penetration or floating
               obvious. Samples a random subset by default.

  --input_dir  Render FBX animations (with mesh) through Blender. The original
               behaviour, kept for checking the intermediate FBX stage.

Examples:
    # 10 random clips from a finished dataset
    python3 render_videos.py --qpos_dir human_to_robot/ACCAD/qpos \
        --output_dir human_to_robot/ACCAD/videos --num 10

    # every FBX in a directory, via Blender
    python3 render_videos.py --input_dir human_to_robot/ACCAD/fbx \
        --output_dir human_to_robot/ACCAD/videos_fbx
"""
import argparse
import json
import random
import subprocess
from pathlib import Path

PATHS_JSON_PATH = "paths.json"
DEFAULT_MJCF = Path("mujoco_qpos_pipeline/mjcf/robot.xml")


def render_one(blender_app_path, fbx_path, out_video_path, fps):
    script_name = "processing/render_worker.py"
    subprocess_args = [
        blender_app_path, "--background", "--python", script_name, "--",
        "--fbx_path", str(fbx_path),
        "--out_video_path", str(out_video_path),
        "--fps", str(fps),
    ]
    subprocess.run(subprocess_args)


def render_qpos_clip(model, renderer, camera_id, qpos, out_video_path, fps):
    """Replay one qpos clip and write it out as mp4."""
    import imageio
    import mujoco

    data = mujoco.MjData(model)
    with imageio.get_writer(str(out_video_path), fps=fps, macro_block_size=1) as writer:
        for frame_qpos in qpos:
            data.qpos[:] = frame_qpos
            # mj_forward, not mj_step: the clip already prescribes every joint
            # angle, so this is pure kinematics -- running physics would let the
            # model fall away from the motion we are trying to look at.
            mujoco.mj_forward(model, data)
            renderer.update_scene(data, camera=camera_id)
            writer.append_data(renderer.render())


def render_qpos_dir(args):
    import mujoco
    import numpy as np

    clips = sorted(args.qpos_dir.glob("*.npz"))
    if not clips:
        raise SystemExit(f"no .npz clips found in {args.qpos_dir}")

    if args.num is not None and args.num < len(clips):
        # Seeded so a reported problem can be reproduced exactly; the seed is
        # printed rather than hidden for that reason.
        rng = random.Random(args.seed)
        clips = sorted(rng.sample(clips, args.num))
        print(f"sampled {len(clips)} of {len(sorted(args.qpos_dir.glob('*.npz')))} "
              f"clips (seed {args.seed})")

    model = mujoco.MjModel.from_xml_path(str(args.mjcf))
    camera_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, args.camera)
    if camera_id < 0:
        available = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_CAMERA, i)
                     for i in range(model.ncam)]
        raise SystemExit(f"camera {args.camera!r} not in {args.mjcf}; "
                         f"available: {available}")

    renderer = mujoco.Renderer(model, height=args.height, width=args.width)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for i, clip_path in enumerate(clips, 1):
        with np.load(clip_path) as npz:
            qpos = npz["qpos"]
        if qpos.shape[1] != model.nq:
            print(f"  SKIP {clip_path.name}: nq {qpos.shape[1]} != model {model.nq}")
            continue
        out_video_path = args.output_dir / f"{clip_path.stem}.mp4"
        print(f"[{i}/{len(clips)}] {clip_path.stem}  "
              f"{len(qpos)} frames -> {out_video_path.name}")
        render_qpos_clip(model, renderer, camera_id, qpos, out_video_path, args.fps)

    print(f"\nDone. {len(clips)} videos in {args.output_dir}")


def render_fbx_dir(args):
    with open(PATHS_JSON_PATH, 'r') as f:
        blender_app_path = json.load(f).get("BLENDER_APP_PATH")
    if not blender_app_path:
        raise ValueError(f"BLENDER_APP_PATH not found in {PATHS_JSON_PATH}")

    fbx_files = sorted(args.input_dir.glob("*.fbx"))
    print(f"Found {len(fbx_files)} fbx files in {args.input_dir}")

    if args.num is not None and args.num < len(fbx_files):
        rng = random.Random(args.seed)
        fbx_files = sorted(rng.sample(fbx_files, args.num))
        print(f"sampled {len(fbx_files)} of them (seed {args.seed})")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for fbx_path in fbx_files:
        out_video_path = args.output_dir / f"{fbx_path.stem}.mp4"
        print(f"Rendering {fbx_path.name} -> {out_video_path}")
        render_one(blender_app_path, fbx_path, out_video_path, args.fps)

    print("Done.")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--qpos_dir', type=Path,
                        help="Directory of MuJoCo qpos .npz clips.")
    source.add_argument('--input_dir', type=Path,
                        help="Directory containing FBX animations (with mesh).")
    parser.add_argument('--output_dir', type=Path, required=True,
                        help="Destination directory for rendered videos.")
    parser.add_argument('--num', type=int, default=10,
                        help="Render this many randomly sampled clips "
                             "(default 10). Pass 0 for all of them.")
    parser.add_argument('--seed', type=int, default=0,
                        help="Sampling seed, so a run can be reproduced.")
    parser.add_argument('--fps', type=int, default=30)
    parser.add_argument('--mjcf', type=Path, default=DEFAULT_MJCF,
                        help="MJCF the qpos clips target (qpos mode only).")
    parser.add_argument('--camera', default='front_side',
                        help="Named camera in the MJCF (qpos mode only). "
                             "robot.xml has back, side, front_side -- all of "
                             "which track the body, so the robot stays framed.")
    parser.add_argument('--width', type=int, default=640)
    parser.add_argument('--height', type=int, default=480)
    args = parser.parse_args()

    if args.num == 0:
        args.num = None

    if args.qpos_dir is not None:
        render_qpos_dir(args)
    else:
        render_fbx_dir(args)


if __name__ == '__main__':
    main()
