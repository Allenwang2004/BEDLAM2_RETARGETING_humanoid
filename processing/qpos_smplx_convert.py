# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
"""Convert robot.xml MuJoCo qpos trajectories to/from a SMPL-X-like pose representation.

robotmotion/*.npz stores `qpos` arrays of shape (nframes, 76): a 7-dof freejoint
(3 world position + 4 world orientation quaternion, wxyz) for the Pelvis root,
followed by 23 bodies x 3 hinge joints each (axis order x, y, z, MuJoCo composition
order Rz(theta_z) @ Ry(theta_y) @ Rx(theta_x) -- confirmed empirically against
mj_forward, see docs/pipeline_new_mujoco_model.md's sibling doc for context).

This is NOT literal SMPL-X (no SMPL-X shape/mesh, no hands/jaw/eyes) -- it just
reshapes robot.xml's own 23-body kinematic tree into the same *layout* SMPL-X uses:
`trans` (3,), `root_orient` (3,) axis-angle, `pose_body` (69,) axis-angle, one 3-vector
per body instead of 3 separate hinge angles. Useful as an interchange format for tools
that expect axis-angle-per-joint (e.g. blending/interpolation code written for SMPL-X)
without pulling in FBX/Blender/UE.

The root freejoint's qpos IS the body's absolute world position/orientation (verified:
qpos0 at rest equals robot.xml's own body_pos/body_quat for Pelvis exactly), so
trans/root_orient round-trip with no ambiguity. Non-root hinge triplets round-trip
through scipy's XYZ-extrinsic Euler decomposition, which is exact except at gimbal-lock
(y = +-90 deg) where multiple (x, y, z) triplets map to the same rotation -- the
recovered angles can differ from the originals there while still being physically
equivalent. See test_qpos_smplx_roundtrip.py, which checks physical equivalence via
mj_forward rather than raw qpos equality for exactly this reason.
"""
import argparse

import numpy as np
from scipy.spatial.transform import Rotation

DEFAULT_MJCF = "/Users/coconut/mujoco_humanoid_retargeting/mjcf/robot.xml"
NUM_BODY_JOINTS = 23
QPOS_DIM = 7 + NUM_BODY_JOINTS * 3


def load_body_order(mjcf_path: str) -> list:
    """Ordered list of the 23 non-root body names, matching qpos[7:] triplet order."""
    import mujoco

    model = mujoco.MjModel.from_xml_path(mjcf_path)
    ordered = []
    for i in range(model.nbody):
        if model.body_jntnum[i] != 3:
            continue
        qadr = model.jnt_qposadr[model.body_jntadr[i]]
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
        ordered.append((qadr, name))
    ordered.sort(key=lambda pair: pair[0])
    body_names = [name for _, name in ordered]
    assert len(body_names) == NUM_BODY_JOINTS, (
        f"expected {NUM_BODY_JOINTS} 3-DOF bodies in {mjcf_path}, got {len(body_names)} "
        "-- this converter is hardcoded to robot.xml's topology, not a generic MJCF converter."
    )
    return body_names


def qpos_to_smplx_like(qpos: np.ndarray) -> dict:
    """qpos (T, 76) -> dict(trans (T,3), root_orient (T,3), pose_body (T,69)), all axis-angle."""
    qpos = np.asarray(qpos, dtype=np.float64)
    assert qpos.shape[-1] == QPOS_DIM, f"expected qpos dim {QPOS_DIM}, got {qpos.shape[-1]}"
    T = qpos.shape[0]

    trans = qpos[:, 0:3].copy()

    root_quat_wxyz = qpos[:, 3:7]
    root_quat_xyzw = root_quat_wxyz[:, [1, 2, 3, 0]]
    root_orient = Rotation.from_quat(root_quat_xyzw).as_rotvec()

    hinge = qpos[:, 7:].reshape(T, NUM_BODY_JOINTS, 3)
    pose_body = np.empty((T, NUM_BODY_JOINTS, 3), dtype=np.float64)
    for j in range(NUM_BODY_JOINTS):
        pose_body[:, j, :] = Rotation.from_euler("XYZ", hinge[:, j, :]).as_rotvec()

    return {
        "trans": trans,
        "root_orient": root_orient,
        "pose_body": pose_body.reshape(T, NUM_BODY_JOINTS * 3),
    }


def smplx_like_to_qpos(trans: np.ndarray, root_orient: np.ndarray, pose_body: np.ndarray) -> np.ndarray:
    """Inverse of qpos_to_smplx_like: trans/root_orient/pose_body (axis-angle) -> qpos (T, 76)."""
    trans = np.asarray(trans, dtype=np.float64)
    root_orient = np.asarray(root_orient, dtype=np.float64)
    pose_body = np.asarray(pose_body, dtype=np.float64)
    T = trans.shape[0]
    assert pose_body.shape[-1] == NUM_BODY_JOINTS * 3

    qpos = np.empty((T, QPOS_DIM), dtype=np.float64)
    qpos[:, 0:3] = trans

    root_quat_xyzw = Rotation.from_rotvec(root_orient).as_quat()
    qpos[:, 3:7] = root_quat_xyzw[:, [3, 0, 1, 2]]  # xyzw -> wxyz

    pose_body = pose_body.reshape(T, NUM_BODY_JOINTS, 3)
    for j in range(NUM_BODY_JOINTS):
        euler = Rotation.from_rotvec(pose_body[:, j, :]).as_euler("XYZ")
        qpos[:, 7 + 3 * j : 7 + 3 * j + 3] = euler

    return qpos


def convert_qpos_file_to_smplx_like(input_npz: str, output_npz: str, mjcf_path: str = DEFAULT_MJCF):
    data = np.load(input_npz)
    smplx_like = qpos_to_smplx_like(data["qpos"])
    body_order = load_body_order(mjcf_path)
    np.savez(
        output_npz,
        trans=smplx_like["trans"],
        root_orient=smplx_like["root_orient"],
        pose_body=smplx_like["pose_body"],
        body_order=np.array(body_order),
    )


def convert_smplx_like_file_to_qpos(input_npz: str, output_npz: str):
    data = np.load(input_npz)
    qpos = smplx_like_to_qpos(data["trans"], data["root_orient"], data["pose_body"])
    np.savez(output_npz, qpos=qpos)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_to_smplx = sub.add_parser("to-smplx", help="qpos npz -> SMPL-X-like npz")
    p_to_smplx.add_argument("--input", required=True)
    p_to_smplx.add_argument("--output", required=True)
    p_to_smplx.add_argument("--mjcf", default=DEFAULT_MJCF)

    p_to_qpos = sub.add_parser("to-qpos", help="SMPL-X-like npz -> qpos npz")
    p_to_qpos.add_argument("--input", required=True)
    p_to_qpos.add_argument("--output", required=True)

    args = parser.parse_args()
    if args.cmd == "to-smplx":
        convert_qpos_file_to_smplx_like(args.input, args.output, args.mjcf)
    elif args.cmd == "to-qpos":
        convert_smplx_like_file_to_qpos(args.input, args.output)


if __name__ == "__main__":
    main()
