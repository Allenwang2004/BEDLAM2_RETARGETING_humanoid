# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
"""Round-trip test for qpos_smplx_convert.py: qpos -> SMPL-X-like -> qpos.

Raw qpos values are NOT compared directly for pass/fail: the per-body hinge
triplet is recovered via Euler decomposition, which has valid alternate
solutions at gimbal lock (y = +-90 deg) that reproduce the identical physical
pose with different angle numbers. So the ground truth here is mj_forward's
own world-space body transforms (xpos/xquat) for the original qpos vs. the
round-tripped qpos, compared body-by-body, frame-by-frame, over every clip in
robotmotion/.

Usage:
    python3 processing/test_qpos_smplx_roundtrip.py
    python3 processing/test_qpos_smplx_roundtrip.py --limit 20 --verbose
"""
import argparse
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from qpos_smplx_convert import DEFAULT_MJCF, qpos_to_smplx_like, smplx_like_to_qpos

DEFAULT_ROBOTMOTION_DIR = os.path.join(os.path.dirname(__file__), "..", "robotmotion")


def world_pose_batch(model, data, qpos_batch: np.ndarray):
    """Run mj_forward per frame, return (T, nbody, 3) xpos and (T, nbody, 4) xquat (wxyz)."""
    import mujoco

    T = qpos_batch.shape[0]
    xpos = np.empty((T, model.nbody, 3))
    xquat = np.empty((T, model.nbody, 4))
    for t in range(T):
        data.qpos[:] = qpos_batch[t]
        mujoco.mj_forward(model, data)
        xpos[t] = data.xpos
        xquat[t] = data.xquat
    return xpos, xquat


def quat_angle_diff_deg(q1_wxyz: np.ndarray, q2_wxyz: np.ndarray) -> np.ndarray:
    """Angle (deg) of the relative rotation between two batches of quaternions, any shape (..., 4)."""
    dot = np.abs(np.sum(q1_wxyz * q2_wxyz, axis=-1))
    dot = np.clip(dot, -1.0, 1.0)
    return np.degrees(2.0 * np.arccos(dot))


def test_one_file(model, data, npz_path: str):
    qpos = np.load(npz_path)["qpos"]

    smplx_like = qpos_to_smplx_like(qpos)
    qpos_rt = smplx_like_to_qpos(smplx_like["trans"], smplx_like["root_orient"], smplx_like["pose_body"])

    raw_diff = np.max(np.abs(qpos - qpos_rt))

    xpos_a, xquat_a = world_pose_batch(model, data, qpos)
    xpos_b, xquat_b = world_pose_batch(model, data, qpos_rt)

    pos_err = np.max(np.linalg.norm(xpos_a - xpos_b, axis=-1))
    ang_err_deg = np.max(quat_angle_diff_deg(xquat_a, xquat_b))

    return {
        "file": npz_path,
        "nframes": qpos.shape[0],
        "raw_qpos_max_abs_diff": raw_diff,
        "world_pos_max_err_m": pos_err,
        "world_angle_max_err_deg": ang_err_deg,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", default=DEFAULT_ROBOTMOTION_DIR)
    parser.add_argument("--mjcf", default=DEFAULT_MJCF)
    parser.add_argument("--limit", type=int, default=None, help="only test the first N files (default: all)")
    parser.add_argument("--pos-tol-m", type=float, default=1e-6)
    parser.add_argument("--angle-tol-deg", type=float, default=1e-3)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    import mujoco

    model = mujoco.MjModel.from_xml_path(args.mjcf)
    data = mujoco.MjData(model)

    files = sorted(glob.glob(os.path.join(args.dir, "**", "*.npz"), recursive=True))
    if args.limit:
        files = files[: args.limit]
    if not files:
        print(f"No .npz files found under {args.dir}")
        sys.exit(1)

    print(f"Testing {len(files)} clips from {args.dir} against {args.mjcf}\n")

    results = []
    failures = []
    for i, f in enumerate(files):
        r = test_one_file(model, data, f)
        results.append(r)
        ok = r["world_pos_max_err_m"] <= args.pos_tol_m and r["world_angle_max_err_deg"] <= args.angle_tol_deg
        if not ok:
            failures.append(r)
        if args.verbose or not ok:
            status = "OK" if ok else "FAIL"
            rel = os.path.relpath(r["file"], args.dir)
            print(
                f"[{status}] {rel}: nframes={r['nframes']} "
                f"raw_qpos_max_abs_diff={r['raw_qpos_max_abs_diff']:.3e} "
                f"world_pos_max_err={r['world_pos_max_err_m']:.3e} m "
                f"world_angle_max_err={r['world_angle_max_err_deg']:.3e} deg"
            )
        elif (i + 1) % 50 == 0:
            print(f"  ...{i + 1}/{len(files)} clips checked")

    raw_diffs = np.array([r["raw_qpos_max_abs_diff"] for r in results])
    pos_errs = np.array([r["world_pos_max_err_m"] for r in results])
    ang_errs = np.array([r["world_angle_max_err_deg"] for r in results])

    print("\n=== Summary ===")
    print(f"Clips tested: {len(results)}")
    print(f"Raw qpos abs diff   -- max: {raw_diffs.max():.3e}  mean: {raw_diffs.mean():.3e}")
    print(f"World position err  -- max: {pos_errs.max():.3e} m  mean: {pos_errs.mean():.3e} m")
    print(f"World angle err     -- max: {ang_errs.max():.3e} deg  mean: {ang_errs.mean():.3e} deg")
    print(
        f"Pass (pos_tol={args.pos_tol_m} m, angle_tol={args.angle_tol_deg} deg): "
        f"{len(results) - len(failures)}/{len(results)}"
    )

    if failures:
        print(f"\n{len(failures)} clip(s) exceeded tolerance:")
        for r in sorted(failures, key=lambda r: -r["world_angle_max_err_deg"])[:20]:
            print(
                f"  {os.path.relpath(r['file'], args.dir)}: "
                f"pos_err={r['world_pos_max_err_m']:.3e} m, angle_err={r['world_angle_max_err_deg']:.3e} deg"
            )
        sys.exit(1)

    print("\nAll clips round-trip to the same physical pose within tolerance.")


if __name__ == "__main__":
    main()
