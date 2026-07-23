# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
import unreal
import os
import sys


def export_selected_assets(output_dir: str, export_mesh: bool = False):
    """
    Export selected assets.
    """
    # Get selected assets from content browser
    selected_assets = unreal.EditorUtilityLibrary.get_selected_assets()
    # Iterate over selection and export
    for selectedAsset in selected_assets:

        if not isinstance(selectedAsset, unreal.AnimSequence):
            unreal.log(f"Skipping {selectedAsset.get_name()}. Only AnimSequence assets are supported.")
            continue

        asset_name = selectedAsset.get_name()
        export_task = unreal.AssetExportTask()
        export_task.automated = True
        export_task.object = selectedAsset
        export_task.prompt = False
        export_task.filename = os.path.join(fr"{output_dir}", f'{asset_name}.fbx')
        export_task.options = unreal.FbxExportOption()

        export_task.options.set_editor_property(
            name="bExportPreviewMesh",
            value=export_mesh
        )

        fbx_exporter = unreal.AnimSequenceExporterFBX()
        export_task.exporter = fbx_exporter
        fbx_exporter.run_asset_export_task(export_task)


if __name__ == '__main__':
    _output_dir = sys.argv[1]
    _output_dir = os.path.join(_output_dir, "fbx")
    os.makedirs(_output_dir, exist_ok=True)
    _export_mesh = bool(int(sys.argv[2]))
    export_selected_assets(_output_dir, _export_mesh)
    unreal.log("Exported selected assets to FBX")
