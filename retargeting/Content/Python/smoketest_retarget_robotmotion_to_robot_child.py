# Retarget every robotmotion-derived clip (already converted to FBX on
# robot.fbx's own armature and imported under SRC_POOL, see
# docs/robotmotion_to_robot_child_pipeline.md steps 1-3) onto Robot_child --
# source_ik_rig is Robot_IKRig since the robotmotion-derived FBX shares
# robot.fbx's bone names, no need to stage through Robot's own skeletal mesh.
#
# SOURCE_CLIPS is populated by scanning SRC_POOL itself, not a hardcoded
# list -- whatever's been imported there (via import_batch.py) gets
# retargeted. Already-retargeted clips (asset already exists in OUT_DIR) are
# skipped, so reruns after importing more clips only process the new ones.
import unreal
import retarget
from importlib import reload
reload(retarget)
from retarget import execute, ignore_already_retargeted

SRC_POOL = "/Game/BodyModels/RobotMotionSrc/animations"
OUT_DIR = "/Game/BodyModels/Robot_child/retargeting/robotmotion_smoketest"


def list_imported_clips(src_pool):
    all_assets = unreal.EditorAssetLibrary.list_assets(src_pool, recursive=True)
    prefix = src_pool.rstrip("/") + "/"
    clip_names = set()
    for asset_path in all_assets:
        relative = asset_path[len(prefix):] if asset_path.startswith(prefix) else asset_path
        clip_names.add(relative.split("/")[0])
    return sorted(clip_names)


SOURCE_CLIPS = list_imported_clips(SRC_POOL)
unreal.log_warning(f"DIAG: found {len(SOURCE_CLIPS)} imported clips under {SRC_POOL}")

target_names = ["robot_child"] * len(SOURCE_CLIPS)
target_names, SOURCE_CLIPS = ignore_already_retargeted(target_names, SOURCE_CLIPS, OUT_DIR)
unreal.log_warning(f"DIAG: {len(SOURCE_CLIPS)} clip(s) remaining after skipping already-retargeted ones")

for source_name in SOURCE_CLIPS:
    unreal.log_warning(f"DIAG: retargeting robotmotion clip {source_name} -> robot_child")
    execute(
        target_dir="/Game/BodyModels/Robot_child/bodies/robot_child",
        source_skel_path=f"{SRC_POOL}/{source_name}/{source_name}",
        source_anim_path=f"{SRC_POOL}/{source_name}/{source_name}_Anim",
        ik_retargeter_path="/Game/BodyModels/Robot_child/RobotChild_IKRetargeter",
        source_ik_rig_path="/Game/BodyModels/Robot/Robot_IKRig",
        target_ik_rig_path="/Game/BodyModels/Robot_child/RobotChild_IKRig",
        out_dir=OUT_DIR,
    )

unreal.log_warning("DIAG: ROBOTMOTION RETARGET DONE")
