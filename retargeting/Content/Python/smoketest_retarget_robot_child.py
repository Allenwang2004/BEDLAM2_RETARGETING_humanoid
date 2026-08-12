# Smoke test: retarget a couple of Robot's already-completed clips onto Robot_child
# using RobotChild_IKRetargeter (source=Robot_IKRig, target=RobotChild_IKRig).
import unreal
import retarget
from importlib import reload
reload(retarget)
from retarget import execute

SOURCE_CLIPS = [
    "A1_-_Stand_stageii",
    "A11_-_crawl_forward_stageii",
]

OUT_DIR = "/Game/BodyModels/Robot_child/retargeting/smoketest"

for source_name in SOURCE_CLIPS:
    unreal.log_warning(f"DIAG: retargeting {source_name} -> robot_child")
    execute(
        target_dir="/Game/BodyModels/Robot_child/bodies/robot_child",
        source_skel_path="/Game/BodyModels/Robot/bodies/robot",
        source_anim_path=f"/Game/BodyModels/Robot/retargeting/robot/robot+{source_name}_Anim",
        ik_retargeter_path="/Game/BodyModels/Robot_child/RobotChild_IKRetargeter",
        source_ik_rig_path="/Game/BodyModels/Robot/Robot_IKRig",
        target_ik_rig_path="/Game/BodyModels/Robot_child/RobotChild_IKRig",
        out_dir=OUT_DIR,
    )

unreal.log_warning("DIAG: SMOKETEST DONE")
