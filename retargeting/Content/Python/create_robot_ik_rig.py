# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
"""Create an IK Rig for the MuJoCo robot skeleton (`robot.fbx`), mirroring the
retarget-chain layout of the repo's `smplx_IKRig` so it can be used as the
TARGET rig in an IK Retargeter with `smplx_IKRig` as SOURCE.

Robot skeleton hierarchy (from mjcf/robot.xml, no zero-offset merges):
    humanoid_CMU_armature (leftover Blender object-name bone, ignored -- same
        pattern as humanoid_CMU's own skeleton, see create_cmu_ik_rig.py)
        Pelvis
            L_Hip -> L_Knee -> L_Ankle -> L_Toe
            R_Hip -> R_Knee -> R_Ankle -> R_Toe
            Torso -> Spine -> Chest
                Neck -> Head
                L_Thorax -> L_Shoulder -> L_Elbow -> L_Wrist -> L_Hand
                R_Thorax -> R_Shoulder -> R_Elbow -> R_Wrist -> R_Hand

Usage (run inside UnrealEditor-Cmd via -ExecutePythonScript):
    create_robot_ik_rig.py <skeletal_mesh_path> <output_ik_rig_path>
    e.g. create_robot_ik_rig.py /Game/BodyModels/Robot/bodies/robot \
                                 /Game/BodyModels/Robot/Robot_IKRig
"""
import sys
import unreal

# (chain_name, start_bone, end_bone, goal_name) - goal_name is "None" for chains with no IK goal.
# Named to match smplx_IKRig's chain names 1:1 so an IK Retargeter can
# auto-map SOURCE (smplx) -> TARGET (this rig) chains by name.
RETARGET_CHAINS = [
    # No "root" chain -- "Pelvis" IS the retarget-root bone itself (the extra
    # "humanoid_CMU_armature" bone above it is ignored, same as CMU's rig
    # ignores its own leftover top bone). Mapping a "root" chain onto Pelvis
    # would double-apply rotation (FK chain rotation + Retarget Root
    # Settings) and tip the whole body over.
    ("Spine", "Torso", "Chest", "None"),
    ("neck", "Neck", "Neck", "None"),
    ("head", "Head", "Head", "None"),
    ("LeftLeg", "L_Hip", "L_Ankle", "LeftFootIK"),
    ("RightLeg", "R_Hip", "R_Ankle", "RightFootIK"),
    ("LeftClavicle", "L_Thorax", "L_Thorax", "None"),
    ("RightClavicle", "R_Thorax", "R_Thorax", "None"),
    ("LeftArm", "L_Shoulder", "L_Wrist", "None"),
    ("RightArm", "R_Shoulder", "R_Wrist", "None"),
]

# (goal_name, bone_name)
GOALS = [
    ("root_Goal", "Pelvis"),
    ("LeftFootIK", "L_Ankle"),
    ("RightFootIK", "R_Ankle"),
]

RETARGET_ROOT_BONE = "Pelvis"


def execute(skeletal_mesh_path, output_ik_rig_path):
    skeletal_mesh = unreal.load_asset(name=skeletal_mesh_path)
    if skeletal_mesh is None:
        print(f"ERROR: could not load skeletal mesh at {skeletal_mesh_path}", file=sys.stderr)
        return

    package_path, asset_name = output_ik_rig_path.rsplit("/", 1)

    if unreal.EditorAssetLibrary.does_asset_exist(output_ik_rig_path):
        print(f"IK Rig already exists at {output_ik_rig_path}, editing in place.")
        ik_rig = unreal.load_asset(name=output_ik_rig_path)
    else:
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        ik_rig = asset_tools.create_asset(
            asset_name=asset_name,
            package_path=package_path,
            asset_class=unreal.IKRigDefinition,
            factory=unreal.IKRigDefinitionFactory(),
        )

    controller = unreal.IKRigController.get_controller(ik_rig)
    controller.set_skeletal_mesh(skeletal_mesh)

    solver_index = controller.add_solver(unreal.IKRigFBIKSolver)
    controller.set_root_bone(RETARGET_ROOT_BONE, solver_index)

    controller.set_retarget_root(RETARGET_ROOT_BONE)

    for goal_name, bone_name in GOALS:
        controller.add_new_goal(goal_name, bone_name)
        controller.connect_goal_to_solver(goal_name, solver_index)

    for chain_name, start_bone, end_bone, goal_name in RETARGET_CHAINS:
        controller.add_retarget_chain(chain_name, start_bone, end_bone, goal_name)

    unreal.EditorAssetLibrary.save_asset(output_ik_rig_path)
    print(f"Created/updated IK Rig at {output_ik_rig_path}")


if __name__ == "__main__":
    _skeletal_mesh_path = sys.argv[1]
    _output_ik_rig_path = sys.argv[2]
    execute(_skeletal_mesh_path, _output_ik_rig_path)
