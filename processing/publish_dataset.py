# Package one finished dataset's qpos clips into `<DATASET>.tar.gz`, upload it
# to a HuggingFace dataset repo, verify the upload, then delete the local
# archive. Run once per raw dataset, after run_human_to_robot.sh finishes:
#
#   python3 processing/publish_dataset.py --qpos_dir human_to_robot/<DATASET>/qpos
#
# <DATASET> is whatever the raw data folder was called -- run_human_to_robot.sh
# names the work directory after it, and this reads the name back off that
# directory. Nothing anywhere hardcodes a dataset name; --dataset_name only
# exists to override the derived one.
#
# Each run adds one more archive to the same repo, so the collection
# accumulates one dataset at a time.
#
# The archive is only deleted after the uploaded file has been read back from
# the Hub and its size and sha256 confirmed to match what was sent -- an upload
# that half-succeeded must not silently destroy the only local copy. Note the
# qpos clips themselves are never deleted, only the redundant .tar.gz.
import argparse
import hashlib
import json
import shutil
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from huggingface_hub import HfApi

CARD_HEADER = """---
license: other
license_name: amass
license_link: https://amass.is.tue.mpg.de/license.html
task_categories:
- robotics
tags:
- motion-capture
- retargeting
- mujoco
- amass
---

# AMASS motion retargeted to MuJoCo `robot.xml` qpos

Human motion capture from [AMASS](https://amass.is.tue.mpg.de/) (SMPL-X G),
retargeted onto the MuJoCo `robot.xml` skeleton through Unreal Engine's IK
Retargeter and converted back to MuJoCo `qpos`. Produced by
[bedlam2_retargeting](https://github.com/Allenwang2004/BEDLAM2_RETARGETING_humanoid)'s
`run_human_to_robot.sh` -- see `docs/pipeline_human_to_robot.md` there for the
full method.

One `.tar.gz` per source AMASS dataset. Each archive extracts to a folder of
`<Subject>__<clip>.npz` files, each holding a single `qpos` array of shape
`(nframes, 76)` at 30 fps: 7 free-joint values (pelvis world position in
metres + wxyz quaternion) followed by 23 bodies x 3 hinge DOFs. A
`manifest.json` alongside them lists every clip with its frame count.

```python
import numpy as np
qpos = np.load("ACCAD/Female1Walking__B1_-_stand_to_walk.npz")["qpos"]  # (187, 76)
```

Derived from AMASS and subject to the AMASS license -- not the license of the
retargeting code.

## Contents

"""


def sha256_of(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def build_manifest(qpos_dir, dataset_name):
    clips = []
    total_frames = 0
    for npz_path in sorted(qpos_dir.glob("*.npz")):
        with np.load(npz_path) as data:
            frames, dof = data["qpos"].shape
        clips.append({"clip": npz_path.stem, "frames": int(frames), "nq": int(dof)})
        total_frames += frames
    return {
        "dataset": dataset_name,
        "source": "AMASS (SMPL-X G)",
        "target": "MuJoCo robot.xml",
        "fps": 30,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "num_clips": len(clips),
        "total_frames": total_frames,
        "clips": clips,
    }


def build_archive(qpos_dir, dataset_name, staging_root):
    """Stage the clips under a folder named after the dataset, so the archive
    extracts to `<DATASET>/...` rather than spilling loose files into the
    extraction directory."""
    folder = staging_root / dataset_name
    folder.mkdir(parents=True)

    for npz_path in sorted(qpos_dir.glob("*.npz")):
        shutil.copy2(npz_path, folder / npz_path.name)

    manifest = build_manifest(qpos_dir, dataset_name)
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))

    archive = staging_root / f"{dataset_name}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(folder, arcname=dataset_name)
    return archive, manifest


def update_card(api, repo_id, dataset_name, manifest):
    """Keep a table of published datasets on the repo's card. Read-modify-write
    so each dataset added later joins the existing rows instead of replacing
    them."""
    rows = {}
    try:
        card_path = api.hf_hub_download(repo_id=repo_id, filename="README.md",
                                        repo_type="dataset")
        for line in Path(card_path).read_text().splitlines():
            if line.startswith("| `") and ".tar.gz`" in line:
                name = line.split("`")[1].removesuffix(".tar.gz")
                rows[name] = line
    except Exception:
        pass  # no card yet, or it has no table -- start a fresh one

    minutes = manifest["total_frames"] / manifest["fps"] / 60
    rows[dataset_name] = (f"| `{dataset_name}.tar.gz` | {manifest['num_clips']} "
                          f"| {manifest['total_frames']} | {minutes:.1f} min |")

    table = ["| Archive | Clips | Frames | Duration |", "|---|---:|---:|---:|"]
    table += [rows[k] for k in sorted(rows)]

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(CARD_HEADER + "\n".join(table) + "\n")
        card = f.name
    api.upload_file(path_or_fileobj=card, path_in_repo="README.md",
                    repo_id=repo_id, repo_type="dataset",
                    commit_message=f"Update dataset card for {dataset_name}")
    Path(card).unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qpos_dir", type=Path, required=True,
                        help="Folder of finished qpos .npz clips.")
    parser.add_argument("--dataset_name", default=None,
                        help="Names the folder inside the archive and the "
                             "archive itself. Defaults to the work directory's "
                             "name (the parent of --qpos_dir), which "
                             "run_human_to_robot.sh takes from the raw AMASS "
                             "folder you handed it -- so whatever that folder "
                             "was called is what gets published.")
    parser.add_argument("--repo_id", default="coconut19/amass-robot-qpos")
    parser.add_argument("--public", action="store_true",
                        help="Create the repo public. Default is private: these "
                             "clips derive from AMASS, whose license does not "
                             "permit redistribution.")
    parser.add_argument("--keep_archive", type=Path, default=None,
                        help="Also copy the .tar.gz here before deleting the "
                             "staging copy (default: no local copy kept).")
    parser.add_argument("--dry_run", action="store_true",
                        help="Build and verify the archive, but do not upload.")
    args = parser.parse_args()

    clips = sorted(args.qpos_dir.glob("*.npz"))
    if not clips:
        raise SystemExit(f"no .npz clips found in {args.qpos_dir}")

    # <work_dir>/qpos -> <work_dir>'s name. Falls back to the qpos folder's own
    # name if it was pointed somewhere without that layout.
    dataset_name = args.dataset_name
    if dataset_name is None:
        resolved = args.qpos_dir.resolve()
        dataset_name = (resolved.parent.name if resolved.name == "qpos"
                        else resolved.name)
        print(f"dataset name (from {args.qpos_dir}): {dataset_name}")

    api = HfApi()
    staging_root = Path(tempfile.mkdtemp(prefix="publish_dataset_"))
    try:
        archive, manifest = build_archive(args.qpos_dir, dataset_name, staging_root)
        size = archive.stat().st_size
        digest = sha256_of(archive)
        print(f"{dataset_name}: {manifest['num_clips']} clips, "
              f"{manifest['total_frames']} frames "
              f"({manifest['total_frames'] / manifest['fps'] / 60:.1f} min)")
        print(f"archive {archive.name}  {size / 1e6:.1f} MB  sha256 {digest[:16]}...")

        if args.dry_run:
            print("dry run: not uploading, archive left at", archive)
            staging_root = None  # skip cleanup so the archive survives
            return

        api.create_repo(repo_id=args.repo_id, repo_type="dataset",
                        private=not args.public, exist_ok=True)

        path_in_repo = f"{dataset_name}.tar.gz"
        api.upload_file(path_or_fileobj=str(archive), path_in_repo=path_in_repo,
                        repo_id=args.repo_id, repo_type="dataset",
                        commit_message=f"Add {dataset_name} "
                                       f"({manifest['num_clips']} clips)")

        # Verify from the Hub's own view before destroying the local archive.
        info = api.get_paths_info(repo_id=args.repo_id, paths=[path_in_repo],
                                  repo_type="dataset", expand=True)
        if not info:
            raise SystemExit(f"upload verification failed: {path_in_repo} not "
                             f"found in {args.repo_id} after upload")
        remote = info[0]
        remote_sha = getattr(getattr(remote, "lfs", None), "sha256", None)
        if remote.size != size:
            raise SystemExit(f"upload verification failed: remote size "
                             f"{remote.size} != local {size}")
        if remote_sha and remote_sha != digest:
            raise SystemExit(f"upload verification failed: remote sha256 "
                             f"{remote_sha} != local {digest}")
        print(f"verified on Hub: {remote.size} bytes"
              + (f", sha256 matches" if remote_sha else " (no lfs sha to compare)"))

        update_card(api, args.repo_id, dataset_name, manifest)

        if args.keep_archive:
            args.keep_archive.mkdir(parents=True, exist_ok=True)
            shutil.copy2(archive, args.keep_archive / archive.name)
            print(f"kept a local copy at {args.keep_archive / archive.name}")

        print(f"\nhttps://huggingface.co/datasets/{args.repo_id}/blob/main/{path_in_repo}")
        print(f"local archive deleted; {len(clips)} qpos clips remain in {args.qpos_dir}")
    finally:
        if staging_root is not None:
            shutil.rmtree(staging_root, ignore_errors=True)


if __name__ == "__main__":
    main()
