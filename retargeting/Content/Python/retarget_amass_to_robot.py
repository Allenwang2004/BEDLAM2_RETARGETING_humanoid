# Retarget every AMASS/SMPL-X clip imported under SRC_POOL onto the MuJoCo
# `robot` skeleton -- the human -> humanoid half of
# docs/pipeline_human_to_robot.md (steps 1-3 produce SRC_POOL's contents).
#
# Source rig is smplx_IKRig because the imported clips ride SMPL-X's own
# armature (the Blender SMPL-X add-on's output); Robot_IKRig's retarget chains
# were deliberately named to match smplx_IKRig's 1:1 (see
# create_robot_ik_rig.py), so create_ik_retargeter.py's EXACT auto-mapping
# lines them up without any manual chain editing.
#
# Same self-scanning/resumable shape as
# smoketest_retarget_robotmotion_to_robot_child.py: SOURCE_CLIPS comes from
# scanning SRC_POOL, and clips already present in OUT_DIR are skipped, so this
# can be rerun after importing more clips (or after a crash) and only does the
# outstanding work.
#
# Must run in the interactive Editor, NOT -run=pythonscript:
#   UnrealEditor-Cmd retargeting.uproject -stdout -FullStdOutLogOutput \
#     -ExecutePythonScript="retarget_amass_to_robot.py"
# (IKRetargetBatchOperation.DuplicateAndRetarget asserts under the commandlet.)
import unreal
import retarget
from importlib import reload
reload(retarget)
from retarget import execute, ignore_already_retargeted

SRC_POOL = "/Game/BodyModels/AccadSrc/animations"
TARGET_BODY_DIR = "/Game/BodyModels/Robot/bodies"
OUT_DIR = "/Game/BodyModels/Robot/retargeting/accad"

SOURCE_IK_RIG = "/Game/BodyModels/Smplx/smplx_IKRig"
TARGET_IK_RIG = "/Game/BodyModels/Robot/Robot_IKRig"
IK_RETARGETER = "/Game/BodyModels/Robot/Robot_IKRetargeter"


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

# retarget.execute() prefixes outputs with basename(target_dir) + "+", so the
# skip-check below must use that same "bodies+<clip>_Anim" name.
target_names = ["bodies"] * len(SOURCE_CLIPS)
target_names, SOURCE_CLIPS = ignore_already_retargeted(target_names, SOURCE_CLIPS, OUT_DIR)
unreal.log_warning(f"DIAG: {len(SOURCE_CLIPS)} clip(s) remaining after skipping already-retargeted ones")

for i, source_name in enumerate(SOURCE_CLIPS, 1):
    unreal.log_warning(f"DIAG: [{i}/{len(SOURCE_CLIPS)}] retargeting {source_name} -> robot")
    execute(
        target_dir=TARGET_BODY_DIR,
        source_skel_path=f"{SRC_POOL}/{source_name}/{source_name}",
        source_anim_path=f"{SRC_POOL}/{source_name}/{source_name}_Anim",
        ik_retargeter_path=IK_RETARGETER,
        source_ik_rig_path=SOURCE_IK_RIG,
        target_ik_rig_path=TARGET_IK_RIG,
        out_dir=OUT_DIR,
    )

unreal.log_warning("DIAG: AMASS -> ROBOT RETARGET DONE")
