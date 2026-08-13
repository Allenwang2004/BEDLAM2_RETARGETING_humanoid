# Stage AMASS motion clips into the flat layout `make_fbx_files.py` needs.
#
# AMASS ships one subject folder per capture session with many motions inside
# it (`<Subject>_c3d/<clip>_stageii.npz`). `make_fbx_files.py` names its output
# from the input file's parent/grandparent folders, so pointing it straight at
# an AMASS tree makes every clip in a subject folder resolve to the SAME output
# name and silently overwrite each other. Its other branch -- input .npz sitting
# directly in input_dir -- uses the file's own stem instead, which is unique as
# long as we fold the subject name into it.
#
# So: symlink every `*_stageii.npz` flat into one directory as
# `<Subject>__<clip>.npz`. Symlinks keep this free (AMASS is ~1 GB for ACCAD
# alone) and leave raw_data/ untouched.
#
# `*_stagei.npz` files are skipped -- they hold only shape/calibration data with
# no usable pose sequence, and would fail the FBX conversion.
import argparse
import re
from pathlib import Path

# UE asset names may not contain parentheses and friends; AMASS clip names do
# (e.g. "B18_-_walk_to_leap_to_walk(1)"). Normalize here so the name survives
# unchanged all the way through FBX -> UE asset -> exported FBX -> qpos npz,
# which is what lets the final .npz be traced back to its source clip.
_UNSAFE = re.compile(r"[^A-Za-z0-9_-]+")


def staged_name(npz_path):
    subject = npz_path.parent.name
    if subject.endswith("_c3d"):
        subject = subject[: -len("_c3d")]
    clip = npz_path.stem
    if clip.endswith("_stageii"):
        clip = clip[: -len("_stageii")]
    return _UNSAFE.sub("_", f"{subject}__{clip}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input_dir", type=Path, required=True,
                        help="AMASS dataset root, e.g. raw_data/ACCAD")
    parser.add_argument("--output_dir", type=Path, required=True,
                        help="Flat directory of symlinks to feed make_fbx_files.py")
    parser.add_argument("--limit", type=int, default=None,
                        help="Stage only the first N clips (for pilot runs).")
    args = parser.parse_args()

    clips = sorted(p for p in args.input_dir.rglob("*.npz")
                   if not p.stem.endswith("_stagei"))
    if args.limit is not None:
        clips = clips[: args.limit]

    args.output_dir.mkdir(parents=True, exist_ok=True)

    seen = {}
    for src in clips:
        name = staged_name(src)
        if name in seen:
            raise SystemExit(f"name collision: {src} and {seen[name]} both -> {name}")
        seen[name] = src
        link = args.output_dir / f"{name}.npz"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(src.resolve())

    print(f"staged {len(seen)} clips into {args.output_dir}")


if __name__ == "__main__":
    main()
