# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
import os
import sys
import unreal


def find_asset_by_class(asset_class_to_find, directory, name_suffix=None):
    # Return first one found
    asset_paths = unreal.EditorAssetLibrary.list_assets(directory)
    for asset_path in asset_paths:
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        asset_class = asset.__class__
        if asset_class == asset_class_to_find:
            if name_suffix is None:
                return asset
            else:
                asset_name = os.path.basename(asset_path)
                if asset_name.endswith(name_suffix):
                    return asset
    return None


def execute(target_dir, source_skel_path, source_anim_path, ik_retargeter_path, source_ik_rig_path, target_ik_rig_path, out_dir):

    # Load source and target skeletal meshes
    source_skel_mesh = unreal.load_asset(name=source_skel_path)
    target_skel_mesh = find_asset_by_class(unreal.SkeletalMesh, target_dir)

    if source_skel_mesh is None or target_skel_mesh is None:
        unreal.log_warning(f"Could not find source or target skeletal mesh for source: {source_skel_path}, target dir: {target_dir}")
        return

    # Get the skeletal mesh from the source_skel
    source_skel_mesh = unreal.SkeletalMesh.cast(source_skel_mesh)

    # Get the skeletal mesh from the target_skel
    target_skel_mesh = unreal.SkeletalMesh.cast(target_skel_mesh)

    #  Ensure the file path is correct for the location of your asset in your project.
    rtg = unreal.load_asset(name=ik_retargeter_path)

    # Get the IK Retargeter controller.
    rtg_controller = unreal.IKRetargeterController.get_controller(rtg)

    # Load the Source and Target IK Rigs.
    source_ik_rig = unreal.load_asset(name=source_ik_rig_path)
    target_ik_rig = unreal.load_asset(name=target_ik_rig_path)

    # Assign the Source and Target IK Rigs.
    rtg_controller.set_ik_rig(unreal.RetargetSourceOrTarget.SOURCE, source_ik_rig)
    rtg_controller.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, target_ik_rig)

    # Get the Source and Target IK Rig assigned to the IK Retargeter asset.
    rtg_controller.get_ik_rig(unreal.RetargetSourceOrTarget.SOURCE)
    rtg_controller.get_ik_rig(unreal.RetargetSourceOrTarget.TARGET)

    # Assign the Source and Target Skeletal Meshes.
    rtg_controller.set_preview_mesh(unreal.RetargetSourceOrTarget.SOURCE, source_skel_mesh)
    rtg_controller.set_preview_mesh(unreal.RetargetSourceOrTarget.TARGET, target_skel_mesh)

    # Get the Source and Target Skeletal Meshes assigned to the IK Retargeter asset.
    rtg_controller.get_preview_mesh(unreal.RetargetSourceOrTarget.SOURCE)
    rtg_controller.get_preview_mesh(unreal.RetargetSourceOrTarget.TARGET)

    # Force a remap on every run so a stale mapping from a previous IK Rig
    # swap doesn't linger. EXACT (not FUZZY): FUZZY's closest-name matching
    # has been observed to map a lowercase target chain (e.g. "root") to a
    # differently-cased, nonexistent source chain name (e.g. "Root"), which
    # silently drops FK retargeting for that chain instead of erroring.
    rtg_controller.auto_map_chains(unreal.AutoMapChainType.EXACT, True)

    # Use the asset subsystem to get asset data.
    asset_subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

    # Get the source animation blueprint
    if source_anim_path is None:
        unreal.log_warning("No source anim found!")
        return

    assets_to_retarget = [
        asset_subsystem.find_asset_data(source_anim_path),
    ]
    dir_basename = os.path.basename(target_dir)

    if not unreal.EditorAssetLibrary.does_directory_exist(out_dir):
        unreal.EditorAssetLibrary.make_directory(out_dir)

    batch_op = unreal.IKRetargetBatchOperation.duplicate_and_retarget(
        assets_to_retarget,
        source_skel_mesh,
        target_skel_mesh,
        rtg,
        search="",
        replace="",
        prefix=f"{dir_basename}+",
        suffix=""
    )
    # First move the motion retargeted files
    for x in batch_op:
        asset_path = str(x.package_name)
        unreal.EditorAssetLibrary.rename_asset(asset_path, asset_path.replace("/Game", out_dir))


def get_retargeting_couples_from_csv_file(csv_path):
    # Csv structure: target_name_1 source_name_1\n
    source_names = []
    target_names = []
    with open(csv_path, 'r') as file:
        lines = file.readlines()
        # Skip title (target_body,source_anim)
        for line in lines[1:]:
            target_name, source_name = line.split(',')
            # Remove any trailing newline from the strings
            target_names.append(target_name.rstrip())
            source_names.append(source_name.rstrip())
    # Returns the dirs of the assets
    return target_names, source_names


def create_motion_extractor_modifier_transl_speed_xyz(bone_name):
    # Create a Motion Extractor Modifier
    motion_extractor_modifier = unreal.MotionExtractorModifier()
    # Set the bone name for the Motion Extractor Modifier
    motion_extractor_modifier.bone_name = bone_name
    # Set the motion type for the Motion Extractor Modifier
    motion_extractor_modifier.motion_type = unreal.MotionExtractor_MotionType.TRANSLATION_SPEED
    # Set the motion axis for the Motion Extractor Modifier
    motion_extractor_modifier.axis = unreal.MotionExtractor_Axis.XYZ
    return motion_extractor_modifier


def ignore_already_retargeted(target_body_names, source_animation_names, retarget_dir):
    updated_target_body_names, updated_source_animation_names = [], []
    # Remove if the retargeting has already been done
    for target_name, source_name in zip(target_body_names, source_animation_names):
        target_path = os.path.join(f"{retarget_dir}/{target_name}+{source_name}_Anim")
        if not unreal.EditorAssetLibrary.does_asset_exist(target_path):
            updated_target_body_names.append(target_name)
            updated_source_animation_names.append(source_name)
    return updated_target_body_names, updated_source_animation_names


if __name__ == '__main__':
    print("Starting retargeting (retarget.py)...")
    _csv_path_retargeting = sys.argv[1]
    _ik_retargeter_path = sys.argv[2]
    _source_ik_rig_path = sys.argv[3]
    _target_ik_rig_path = sys.argv[4]
    _pool_dir = sys.argv[5]

    if len(sys.argv) > 6:
        max_rows_num = int(sys.argv[6])
    else:
        max_rows_num = None

    # Get the paths (dirs) from the csv file
    all_target_body_names, all_source_animation_names = get_retargeting_couples_from_csv_file(_csv_path_retargeting)

    # Retarget the animations
    out_dir = f"{_pool_dir}/retargeting/{os.path.basename(_csv_path_retargeting).split('.')[0]}"

    if max_rows_num is not None:
        all_target_body_names = all_target_body_names[:max_rows_num]
        all_source_animation_names = all_source_animation_names[:max_rows_num]

    # Ignore already retargeted (by checking if the file exists in the out_dir)
    all_target_body_names, all_source_animation_names = ignore_already_retargeted(
        all_target_body_names, all_source_animation_names, out_dir
    )

    for target_name, source_name in zip(all_target_body_names, all_source_animation_names):
        execute(
            target_dir=f"{_pool_dir}/bodies/{target_name}",
            source_skel_path=f"{_pool_dir}/animations/{source_name}/{source_name}",
            source_anim_path=f"{_pool_dir}/animations/{source_name}/{source_name}_Anim",
            ik_retargeter_path=_ik_retargeter_path,
            source_ik_rig_path=_source_ik_rig_path,
            target_ik_rig_path=_target_ik_rig_path,
            out_dir=out_dir,
        )
    unreal.log("Done")
