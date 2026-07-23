# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
"""Create an IK Rig for the MuJoCo/CMU humanoid skeleton (`humanoid_CMU.fbx`),
mirroring the retarget-chain layout of the repo's `smplx_IKRig` so it can be
used as the TARGET rig in an IK Retargeter with `smplx_IKRig` as SOURCE.

CMU skeleton hierarchy (from dm_control's humanoid_CMU.xml):
    root
        lhipjoint -> lfemur -> ltibia -> lfoot -> ltoes
        rhipjoint -> rfemur -> rtibia -> rfoot -> rtoes
        lowerback -> upperback -> thorax
            lowerneck -> upperneck -> head
            lclavicle -> lhumerus -> lradius -> lwrist -> lhand -> {lfingers, lthumb}
            rclavicle -> rhumerus -> rradius -> rwrist -> rhand -> {rfingers, rthumb}

Usage (run inside UnrealEditor-Cmd via -run=pythonscript):
    create_cmu_ik_rig.py <skeletal_mesh_path> <output_ik_rig_path>
    e.g. create_cmu_ik_rig.py /Game/BodyModels/CMU/bodies/humanoid_CMU/humanoid_CMU \
                               /Game/BodyModels/CMU/CMU_IKRig
"""
import sys
import unreal

# (chain_name, start_bone, end_bone, goal_name) - goal_name is "" for chains with no IK goal.
# Named to match smplx_IKRig's chain names 1:1 where an equivalent body part exists,
# so an IK Retargeter can auto-map SOURCE (smplx) -> TARGET (this rig) chains by name.
RETARGET_CHAINS = [
    # No "root" chain here (unlike smplx_IKRig, which has a separate static
    # "root" bone above its "pelvis" retarget-root bone and maps a "root"
    # chain to that static bone). Our skeleton has no such extra static bone
    # -- "root" IS the retarget-root bone itself -- so also mapping a "root"
    # chain onto it would apply FK rotation on top of the Retarget Root
    # Settings' own contribution to the same bone, double-applying rotation.
    #
    # lowerback/lhipjoint/rhipjoint have zero offset from "root" in the MJCF and
    # get merged into it by build_armature_fbx.py, so chains start one bone later.
    ("Spine", "upperback", "thorax", "None"),
    ("neck", "lowerneck", "upperneck", "None"),
    ("head", "head", "head", "None"),
    ("LeftLeg", "lfemur", "lfoot", "LeftFootIK"),
    ("RightLeg", "rfemur", "rfoot", "RightFootIK"),
    ("LeftClavicle", "lclavicle", "lclavicle", "None"),
    ("RightClavicle", "rclavicle", "rclavicle", "None"),
    ("LeftArm", "lhumerus", "lwrist", "None"),
    ("RightArm", "rhumerus", "rwrist", "None"),
]

# (goal_name, bone_name)
GOALS = [
    ("root_Goal", "root"),
    ("LeftFootIK", "lfoot"),
    ("RightFootIK", "rfoot"),
]

RETARGET_ROOT_BONE = "root"


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
