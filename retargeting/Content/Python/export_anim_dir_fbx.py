# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
"""Export every AnimSequence asset under a UE content directory to FBX (with
mesh), without relying on a Content Browser selection (unlike export_fbx.py,
which is meant for the GUI widget). Useful for headless verification of
retargeted animations (e.g. `/Game/BodyModels/CMU/retargeting/cmu_retarget`).

Usage (run inside UnrealEditor-Cmd via -run=pythonscript):
    export_anim_dir_fbx.py <content_dir> <output_dir>
"""
import os
import sys
import unreal


def execute(content_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    asset_paths = unreal.EditorAssetLibrary.list_assets(content_dir, recursive=True)

    exported = 0
    for asset_path in asset_paths:
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        if not isinstance(asset, unreal.AnimSequence):
            continue

        asset_name = asset.get_name()
        export_task = unreal.AssetExportTask()
        export_task.automated = True
        export_task.object = asset
        export_task.prompt = False
        export_task.filename = os.path.join(output_dir, f"{asset_name}.fbx")
        export_task.options = unreal.FbxExportOption()
        export_task.options.set_editor_property(name="bExportPreviewMesh", value=True)

        fbx_exporter = unreal.AnimSequenceExporterFBX()
        export_task.exporter = fbx_exporter
        fbx_exporter.run_asset_export_task(export_task)
        print(f"Exported {asset_path} -> {export_task.filename}")
        exported += 1

    print(f"Exported {exported} AnimSequence assets from {content_dir} to {output_dir}")


if __name__ == "__main__":
    _content_dir = sys.argv[1]
    _output_dir = sys.argv[2]
    execute(_content_dir, _output_dir)
