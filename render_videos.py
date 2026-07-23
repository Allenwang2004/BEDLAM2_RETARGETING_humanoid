# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PATHS_JSON_PATH = "paths.json"


def render_one(blender_app_path, fbx_path, out_video_path, fps):
    script_name = "processing/render_worker.py"
    subprocess_args = [
        blender_app_path, "--background", "--python", script_name, "--",
        "--fbx_path", str(fbx_path),
        "--out_video_path", str(out_video_path),
        "--fps", str(fps),
    ]
    subprocess.run(subprocess_args)


def main():
    parser = argparse.ArgumentParser(description="Render every FBX in a directory to an individual video file.")
    parser.add_argument('--input_dir', type=Path, required=True, help="Directory containing FBX animations (with mesh).")
    parser.add_argument('--output_dir', type=Path, required=True, help="Destination directory for rendered videos.")
    parser.add_argument('--fps', type=int, default=30)
    args = parser.parse_args()

    with open(PATHS_JSON_PATH, 'r') as f:
        blender_app_path = json.load(f).get("BLENDER_APP_PATH")
    if not blender_app_path:
        raise ValueError(f"BLENDER_APP_PATH not found in {PATHS_JSON_PATH}")

    fbx_files = sorted(args.input_dir.glob("*.fbx"))
    print(f"Found {len(fbx_files)} fbx files in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for fbx_path in fbx_files:
        out_video_path = args.output_dir / f"{fbx_path.stem}.mp4"
        print(f"Rendering {fbx_path.name} -> {out_video_path}")
        render_one(blender_app_path, fbx_path, out_video_path, args.fps)

    print("Done.")


if __name__ == '__main__':
    main()
