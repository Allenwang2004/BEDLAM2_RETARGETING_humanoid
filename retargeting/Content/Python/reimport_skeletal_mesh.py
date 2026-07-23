# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
"""Reimport an FBX onto an *existing* SkeletalMesh asset in place (mesh
geometry / bone roll updates only -- bone names and hierarchy must be
unchanged). Reuses the existing Skeleton asset so IK Rigs, IK Retargeters,
and already-baked AnimSequences that reference it keep working without
needing to be rebuilt.

Usage (run inside UnrealEditor-Cmd via -run=pythonscript):
    reimport_skeletal_mesh.py <fbx_path> <destination_path> <destination_name>
    e.g. reimport_skeletal_mesh.py /path/to/humanoid_CMU.fbx \
                                    /Game/BodyModels/CMU/bodies/humanoid_CMU \
                                    humanoid_CMU
"""
import sys
import unreal


def execute(fbx_path, destination_path, destination_name):
    options = unreal.FbxImportUI()
    options.import_mesh = True
    options.import_textures = True
    options.import_materials = False
    options.import_as_skeletal = True
    options.import_animations = False
    options.create_physics_asset = False

    existing_skeleton = unreal.load_asset(name=f"{destination_path}/{destination_name}_Skeleton")
    if existing_skeleton is not None:
        options.skeleton = existing_skeleton
        print("Reusing existing skeleton:", existing_skeleton.get_path_name())
    else:
        print("WARNING: existing skeleton not found, will create a new one")

    task = unreal.AssetImportTask()
    task.automated = True
    task.destination_path = destination_path
    task.destination_name = destination_name
    task.filename = fbx_path
    task.save = True
    task.replace_existing = True
    task.replace_existing_settings = True
    task.options = options

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    print("Reimported:", task.imported_object_paths)


if __name__ == "__main__":
    _fbx_path = sys.argv[1]
    _destination_path = sys.argv[2]
    _destination_name = sys.argv[3]
    execute(_fbx_path, _destination_path, _destination_name)
