# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
"""Dump the bone hierarchy of a skeletal mesh asset.

Usage (run inside UnrealEditor-Cmd via -run=pythonscript):
    dump_skeleton_bones.py <skeletal_mesh_path>
"""
import sys
import unreal


def execute(skeletal_mesh_path):
    skeletal_mesh = unreal.load_asset(name=skeletal_mesh_path)
    if skeletal_mesh is None:
        print(f"ERROR: could not load asset at {skeletal_mesh_path}", file=sys.stderr)
        return

    skeleton = skeletal_mesh.get_editor_property("skeleton")
    pose = skeleton.get_reference_pose()
    bone_names = unreal.AnimPoseExtensions.get_bone_names(pose)
    print(f"Num bones: {len(bone_names)}")
    for bone_name in bone_names:
        print(f"  {bone_name}")


if __name__ == "__main__":
    _skeletal_mesh_path = sys.argv[1]
    execute(_skeletal_mesh_path)
