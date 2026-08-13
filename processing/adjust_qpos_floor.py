# Correct the residual vertical offset in retargeted qpos clips.
#
# UE's IK Retargeter scales root translation by the source/target rest-height
# ratio, which normalises overall stature but not limb proportions -- so each
# clip lands with a constant vertical error whose sign depends on the source
# subject's leg-to-torso ratio. Measured across ACCAD: 44 of 252 clips never
# touch the floor (up to +10.7 cm), 196 sink into it (down to -23.3 cm).
#
#   python3 processing/adjust_qpos_floor.py --qpos_dir human_to_robot/ACCAD/qpos
#   python3 processing/adjust_qpos_floor.py --qpos_dir ... --confirm
#
# The correction is ONE offset per clip, not per frame. Per-frame snapping would
# hold the lowest point on the floor at all times, flattening every flight phase
# -- running and jumping would turn into skating. A single offset preserves all
# relative motion and only fixes where the clip sits.
#
# The offset puts a low percentile (not the minimum -- see --percentile) of the
# clip's lowest-contact height on z=0. Clips are tagged with `floor_offset`,
# which a re-run undoes before re-deriving, so repeated runs converge rather
# than stacking shifts.
#
# This is the qpos counterpart of npz_toolkit.adjust_floor, which does the same
# job for SMPL-X output by rebuilding the body mesh and reading its lowest
# vertex. That one cannot be reused here: it needs SMPL-X poses/betas to build a
# mesh from, works in the Y-up convention, and its median estimator is tuned for
# a mesh whose lowest vertex genuinely rests on the floor during stance.
import argparse
from pathlib import Path

import mujoco
import numpy as np


def lowest_point_z(model, data):
    """World z of the lowest support point over all non-plane geoms.

    Uses each geom's actual extent and orientation rather than its centre:
    a foot box lying flat reaches ~8 cm below its centre, so centre-based
    measurement would report contact while the mesh is still buried.
    """
    lowest = np.inf
    for i in range(model.ngeom):
        geom_type = model.geom_type[i]
        if geom_type == mujoco.mjtGeom.mjGEOM_PLANE:
            continue
        centre_z = data.geom_xpos[i][2]
        size = model.geom_size[i]
        if geom_type == mujoco.mjtGeom.mjGEOM_SPHERE:
            z = centre_z - size[0]
        elif geom_type == mujoco.mjtGeom.mjGEOM_CAPSULE:
            # half-length along the capsule's own z axis, then the cap radius
            rot = data.geom_xmat[i].reshape(3, 3)
            z = centre_z - abs(rot[2, 2]) * size[1] - size[0]
        elif geom_type == mujoco.mjtGeom.mjGEOM_BOX:
            rot = data.geom_xmat[i].reshape(3, 3)
            z = centre_z - float(np.abs(rot[2, :]) @ size[:3])
        else:
            z = centre_z - model.geom_rbound[i]
        lowest = min(lowest, z)
    return lowest


def ground_profile(model, qpos):
    data = mujoco.MjData(model)
    profile = np.empty(len(qpos))
    for frame, q in enumerate(qpos):
        data.qpos[:] = q
        mujoco.mj_forward(model, data)
        profile[frame] = lowest_point_z(model, data)
    return profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qpos_dir", type=Path, required=True)
    parser.add_argument("--mjcf", type=Path,
                        default=Path("mujoco_qpos_pipeline/mjcf/robot.xml"))
    parser.add_argument("--confirm", action="store_true",
                        help="Write the corrected clips. Without this, only "
                             "measures and reports.")
    parser.add_argument("--tolerance", type=float, default=0.001,
                        help="Leave clips already within this many metres of "
                             "the floor untouched (default 1 mm).")
    parser.add_argument("--percentile", type=float, default=5.0,
                        help="Percentile of the per-frame lowest-contact height "
                             "to put on the floor (default 5). Measured on "
                             "ACCAD's 252 clips, against the alternatives:\n"
                             "  min    24 clips left hovering >2cm, 0%% frames penetrating\n"
                             "  p1     14 clips hovering, 0%% penetrating\n"
                             "  p5      0 clips hovering, 0.2%% penetrating\n"
                             "  median  0 clips hovering, 10.1%% penetrating\n"
                             "The strict minimum is hostage to a single bad "
                             "frame; the median (which npz_toolkit.adjust_floor "
                             "uses for SMPL-X meshes, where the lowest vertex "
                             "really does rest on the floor during stance) sits "
                             "far above the true contact for these hovering "
                             "retargeted feet.")
    args = parser.parse_args()

    model = mujoco.MjModel.from_xml_path(str(args.mjcf))
    clips = sorted(args.qpos_dir.glob("*.npz"))
    if not clips:
        raise SystemExit(f"no .npz clips found in {args.qpos_dir}")

    offsets, adjusted, skipped = [], 0, 0
    for path in clips:
        with np.load(path) as npz:
            data = dict(npz)
        qpos = data["qpos"].copy()

        # Undo any previous correction first, so re-running (in particular with
        # a different --percentile) re-derives the offset from the untouched
        # motion instead of stacking a second shift on top of the first.
        previous = float(data["floor_offset"]) if "floor_offset" in data else 0.0
        if previous:
            qpos[:, 2] -= previous
            skipped += 1

        gap = float(np.percentile(ground_profile(model, qpos), args.percentile))
        offsets.append(gap)
        if abs(gap) <= args.tolerance and not previous:
            continue

        if args.confirm:
            qpos[:, 2] -= gap
            data["qpos"] = qpos
            data["floor_offset"] = np.array(-gap)
            np.savez(path, **data)
        adjusted += 1

    if skipped:
        print(f"{skipped} clip(s) had an earlier correction -- undone and redone")

    if offsets:
        arr = np.array(offsets)
        print(f"{len(arr)} clips measured")
        print(f"  ground gap before: min {arr.min():+.4f}  "
              f"median {np.median(arr):+.4f}  max {arr.max():+.4f} m")
        print(f"  floating >1cm: {(arr > 0.01).sum()}   "
              f"penetrating <-1cm: {(arr < -0.01).sum()}")
        print(f"  {'corrected' if args.confirm else 'would correct'}: {adjusted}")

    if not args.confirm:
        print("\ndry run -- rerun with --confirm to write the corrected clips")


if __name__ == "__main__":
    main()
