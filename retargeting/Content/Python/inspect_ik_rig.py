# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
"""Dump an IKRigDefinition asset's solvers / retarget root / chains / goals.

Usage (run inside UnrealEditor-Cmd via -run=pythonscript):
    inspect_ik_rig.py <ik_rig_asset_path>
    e.g. inspect_ik_rig.py /Game/BodyModels/Smplx/smplx_IKRig
"""
import sys
import unreal


def execute(ik_rig_path):
    ik_rig = unreal.load_asset(name=ik_rig_path)
    if ik_rig is None:
        print(f"ERROR: could not load asset at {ik_rig_path}", file=sys.stderr)
        return

    controller = unreal.IKRigController.get_controller(ik_rig)

    skel_mesh = controller.get_skeletal_mesh()
    print(f"Skeletal mesh: {skel_mesh.get_path_name() if skel_mesh else None}")

    print(f"Retarget root: {controller.get_retarget_root()}")

    num_solvers = controller.get_num_solvers()
    print(f"Num solvers: {num_solvers}")
    for i in range(num_solvers):
        solver = controller.get_solver_at_index(i)
        print(f"  Solver[{i}]: class={solver.get_class().get_name()} "
              f"enabled={controller.get_solver_enabled(i)} "
              f"root_bone={controller.get_root_bone(i)} "
              f"end_bone={controller.get_end_bone(i)}")

    chains = controller.get_retarget_chains()
    print(f"Num retarget chains: {len(chains)}")
    for chain in chains:
        start_bone = chain.get_editor_property("start_bone").get_editor_property("bone_name")
        end_bone = chain.get_editor_property("end_bone").get_editor_property("bone_name")
        print(f"  Chain: name={chain.chain_name} "
              f"start={start_bone} end={end_bone} "
              f"goal={chain.ik_goal_name}")

    goals = controller.get_all_goals()
    print(f"Num goals: {len(goals)}")
    for goal in goals:
        print(f"  Goal: name={goal.goal_name} bone={controller.get_bone_for_goal(goal.goal_name)}")


if __name__ == "__main__":
    _ik_rig_path = sys.argv[1]
    execute(_ik_rig_path)
