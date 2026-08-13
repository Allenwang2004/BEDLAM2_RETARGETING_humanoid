# Sanity-check a folder of retargeted `qpos` npz clips against the MJCF they
# target (see docs/pipeline_human_to_robot.md).
#
# Nothing here proves the motion is *good* -- that needs eyes on a render. What
# it does catch is the failure modes a bad retarget actually produces: a
# collapsed or exploded solve (pelvis height far from the model's rest height,
# or drifting to absurd values), a non-unit root quaternion (which MuJoCo will
# silently renormalize, hiding the real error), NaN/Inf, hinge angles outside
# the plausible +-pi, and teleporting roots (per-frame jumps implying speeds no
# human reaches).
import argparse
from pathlib import Path

import mujoco
import numpy as np

# A human pelvis moving faster than this in a mocap clip means a discontinuity,
# not a motion -- sprinters peak around 12 m/s and that is the whole body, not
# a per-frame jump.
MAX_PLAUSIBLE_SPEED = 15.0  # m/s
QUAT_TOL = 1e-6


def check_clip(path, nq, rest_pelvis_z, fps):
    q = np.load(path)["qpos"]
    issues = []

    if q.ndim != 2 or q.shape[1] != nq:
        return q, [f"shape {q.shape} does not match nq={nq}"], {}

    if np.isnan(q).any() or np.isinf(q).any():
        issues.append(f"{int(np.isnan(q).sum())} NaN, {int(np.isinf(q).sum())} Inf")

    quat_err = np.abs(np.linalg.norm(q[:, 3:7], axis=1) - 1.0).max()
    if quat_err > QUAT_TOL:
        issues.append(f"root quaternion off unit norm by {quat_err:.2e}")

    hinge = q[:, 7:]
    if np.abs(hinge).max() > np.pi:
        issues.append(f"hinge angle {np.abs(hinge).max():.2f} rad exceeds pi")

    z = q[:, 2]
    # 0.4x-2.0x rest height spans crouching through jumping; outside that the
    # solve has almost certainly collapsed into the floor or shot upward.
    if z.min() < 0.4 * rest_pelvis_z or z.max() > 2.0 * rest_pelvis_z:
        issues.append(f"pelvis z out of range [{z.min():.2f}, {z.max():.2f}] "
                      f"vs rest {rest_pelvis_z:.2f}")

    step = np.linalg.norm(np.diff(q[:, :3], axis=0), axis=1)
    speed = step.max() * fps if len(step) else 0.0
    if speed > MAX_PLAUSIBLE_SPEED:
        issues.append(f"root jumps at {speed:.1f} m/s")

    stats = {"frames": len(q), "z_min": z.min(), "z_max": z.max(),
             "speed": speed, "hinge_max": np.abs(hinge).max()}
    return q, issues, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qpos_dir", type=Path, required=True)
    parser.add_argument("--mjcf", type=Path, required=True)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--verbose", action="store_true",
                        help="Print a line per clip, not just the failures.")
    args = parser.parse_args()

    model = mujoco.MjModel.from_xml_path(str(args.mjcf))
    rest_pelvis_z = float(model.qpos0[2])

    clips = sorted(args.qpos_dir.glob("*.npz"))
    if not clips:
        raise SystemExit(f"no .npz found in {args.qpos_dir}")

    total_frames = 0
    flagged = []
    for path in clips:
        _, issues, stats = check_clip(path, model.nq, rest_pelvis_z, args.fps)
        total_frames += stats.get("frames", 0)
        if issues:
            flagged.append((path.name, issues))
            print(f"FLAG {path.name}: {'; '.join(issues)}")
        elif args.verbose:
            print(f"ok   {path.name}: {stats['frames']:5d} frames  "
                  f"z {stats['z_min']:.2f}-{stats['z_max']:.2f}  "
                  f"peak {stats['speed']:.2f} m/s")

    print(f"\n{len(clips)} clips, {total_frames} frames "
          f"({total_frames / args.fps / 60:.1f} min at {args.fps:g} fps), "
          f"nq={model.nq}, rest pelvis z={rest_pelvis_z:.4f}")
    print(f"{len(clips) - len(flagged)} passed, {len(flagged)} flagged")


if __name__ == "__main__":
    main()
