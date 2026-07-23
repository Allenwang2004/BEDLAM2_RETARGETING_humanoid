# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
"""Create an IK Retargeter with `smplx_IKRig` as SOURCE and `CMU_IKRig` (or any
other target IK Rig) as TARGET, auto-mapping chains by exact name match.

Usage (run inside UnrealEditor-Cmd via -run=pythonscript):
    create_cmu_ik_retargeter.py <source_ik_rig_path> <target_ik_rig_path> <output_retargeter_path>
    e.g. create_cmu_ik_retargeter.py /Game/BodyModels/Smplx/smplx_IKRig \
                                      /Game/BodyModels/CMU/CMU_IKRig \
                                      /Game/BodyModels/CMU/CMU_IKRetargeter
"""
import sys
import unreal


def execute(source_ik_rig_path, target_ik_rig_path, output_retargeter_path):
    source_ik_rig = unreal.load_asset(name=source_ik_rig_path)
    target_ik_rig = unreal.load_asset(name=target_ik_rig_path)
    if source_ik_rig is None or target_ik_rig is None:
        print(f"ERROR: could not load source ({source_ik_rig_path}) "
              f"or target ({target_ik_rig_path}) IK Rig", file=sys.stderr)
        return

    package_path, asset_name = output_retargeter_path.rsplit("/", 1)

    if unreal.EditorAssetLibrary.does_asset_exist(output_retargeter_path):
        retargeter = unreal.load_asset(name=output_retargeter_path)
    else:
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        retargeter = asset_tools.create_asset(
            asset_name=asset_name,
            package_path=package_path,
            asset_class=unreal.IKRetargeter,
            factory=unreal.IKRetargetFactory(),
        )

    controller = unreal.IKRetargeterController.get_controller(retargeter)
    controller.set_ik_rig(unreal.RetargetSourceOrTarget.SOURCE, source_ik_rig)
    controller.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, target_ik_rig)
    controller.auto_map_chains(unreal.AutoMapChainType.EXACT, True)

    # Keep IK disabled (FK-only retargeting) per the repo's README/pipeline_walkthrough.md
    # convention -- IK is enabled by default per chain, but the goals (e.g. LeftFootIK)
    # were never initialized from a live preview pose here, so leaving IK on produces a
    # degenerate/collapsed solve.
    for chain_settings in controller.get_all_chain_settings():
        target_chain = chain_settings.target_chain
        settings = controller.get_retarget_chain_settings(target_chain)
        ik_settings = settings.get_editor_property("ik")
        ik_settings.set_editor_property("enable_ik", False)
        settings.set_editor_property("ik", ik_settings)
        controller.set_retarget_chain_settings(target_chain, settings)
        print(f"  Mapped: {chain_settings.target_chain} <- {chain_settings.source_chain} (IK disabled)")

    unreal.EditorAssetLibrary.save_asset(output_retargeter_path)
    print(f"Created/updated IK Retargeter at {output_retargeter_path}")


if __name__ == "__main__":
    _source_ik_rig_path = sys.argv[1]
    _target_ik_rig_path = sys.argv[2]
    _output_retargeter_path = sys.argv[3]
    execute(_source_ik_rig_path, _target_ik_rig_path, _output_retargeter_path)
