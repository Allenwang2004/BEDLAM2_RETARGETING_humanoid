# Reclaim the disk one processed dataset leaves behind.
#
# A single ACCAD-sized run costs roughly 1.8 GB across the local work directory
# and the UE project, of which only the ~20 MB `qpos/` folder is the actual
# deliverable. Everything else is a reproducible intermediate, so once a dataset
# is published there is no reason to keep it.
#
#   python3 processing/cleanup_dataset.py --dataset ACCAD            # show what would go
#   python3 processing/cleanup_dataset.py --dataset ACCAD --confirm  # actually delete
#
# Deliberately NOT wired into publish_dataset.py: deletion is irreversible for
# the untracked UE assets, so it stays an explicit, separate decision.
#
# `qpos/` is never touched. Pass --include-qpos only if the archive is safely on
# the Hub and you want the local copy gone too.
import argparse
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def dir_size(path):
    # lstat, not stat: `staged/` is full of symlinks into raw_data/, and
    # following them would report the whole source dataset's size as though
    # deleting the links reclaimed it (they occupy essentially nothing, and
    # raw_data/ is not touched here).
    total = 0
    for f in path.rglob("*"):
        st = f.lstat()
        if not (st.st_mode & 0o170000) == 0o040000:  # skip directories
            total += st.st_size
    return total


def targets_for(dataset, include_qpos):
    """The four places one dataset's intermediates accumulate. Names must match
    run_human_to_robot.sh / retarget_amass_to_robot.py, which derive the UE
    paths from the dataset name the same way."""
    work = REPO / "human_to_robot" / dataset
    ue = REPO / "retargeting" / "Content" / "BodyModels"

    paths = [
        (work / "staged", "symlinks to the raw AMASS npz"),
        (work / "animations", "SMPL-X FBX built by Blender"),
        (work / "animations_missing", "re-import staging for failed clips"),
        (work / "fbx", "retargeted FBX exported from UE"),
        (work / "fbx_pose", "per-frame world bone poses (JSON)"),
        (ue / f"{dataset.capitalize()}Src", "UE import pool"),
        (ue / "Robot" / "retargeting" / dataset.lower(), "UE retarget output"),
    ]
    if include_qpos:
        paths.append((work / "qpos", "FINAL qpos clips"))
    return [(p, why) for p, why in paths if p.exists()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True,
                        help="Dataset name, i.e. the raw AMASS folder's name.")
    parser.add_argument("--confirm", action="store_true",
                        help="Actually delete. Without this, only reports.")
    parser.add_argument("--include-qpos", action="store_true",
                        help="Also delete the final qpos clips. Only after the "
                             "archive is confirmed on the Hub.")
    args = parser.parse_args()

    targets = targets_for(args.dataset, args.include_qpos)
    if not targets:
        print(f"nothing to clean for {args.dataset}")
        return

    total = 0
    for path, why in targets:
        size = dir_size(path)
        total += size
        print(f"{size / 1e6:9.1f} MB  {path.relative_to(REPO)}  ({why})")
    print(f"{total / 1e6:9.1f} MB  total")

    if not args.confirm:
        print("\ndry run -- rerun with --confirm to delete")
        return

    for path, _ in targets:
        shutil.rmtree(path)
        print(f"deleted {path.relative_to(REPO)}")
    print(f"\nfreed {total / 1e6:.1f} MB")

    if not args.include_qpos:
        qpos = REPO / "human_to_robot" / args.dataset / "qpos"
        if qpos.exists():
            print(f"kept {len(list(qpos.glob('*.npz')))} qpos clips in "
                  f"{qpos.relative_to(REPO)}")


if __name__ == "__main__":
    main()
