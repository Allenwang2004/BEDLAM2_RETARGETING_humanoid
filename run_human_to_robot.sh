#!/usr/bin/env bash
# End-to-end: AMASS (SMPL-X G) human motion -> MuJoCo robot.xml qpos.
#
# See docs/pipeline_human_to_robot.md for what each stage does and why.
# Every stage is resumable: rerunning skips clips that already have output, so
# an interrupted run (or a newly added AMASS dataset) only does the new work.
#
#   ./run_human_to_robot.sh [<amass_dataset_dir>] [<work_dir>]
#
# Deliverable: <work_dir>/qpos/<Subject>__<clip>.npz, each (nframes, 76).

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMASS_DIR="${1:-${REPO}/raw_data/ACCAD}"

# The dataset name (ACCAD, CMU, KIT, ...) namespaces everything downstream: the
# work directory, the UE import pool, the UE retarget output directory, and the
# archive published to HuggingFace. Keeping them separate is what makes feeding
# a second dataset later safe -- step 5 exports a UE directory wholesale, so a
# shared pool would re-export every already-finished dataset each time.
DATASET="$(basename "${AMASS_DIR}")"
WORK="${2:-${REPO}/human_to_robot/${DATASET}}"

# The name becomes part of UE content paths, where spaces and punctuation are
# not valid -- catch that here rather than halfway through a multi-hour run.
if [[ ! "${DATASET}" =~ ^[A-Za-z0-9_-]+$ ]]; then
    echo "ERROR: dataset folder name '${DATASET}' must match [A-Za-z0-9_-]+" >&2
    echo "       (it is used verbatim in Unreal content paths). Rename it." >&2
    exit 1
fi

PY="${REPO}/.venv/bin/python"
BLENDER=$("${PY}" -c "import json;print(json.load(open('${REPO}/paths.json'))['BLENDER_APP_PATH'])")
UE=$("${PY}" -c "import json;print(json.load(open('${REPO}/paths.json'))['UNREAL_APP_PATH'])")
UPROJECT=$("${PY}" -c "import json;print(json.load(open('${REPO}/paths.json'))['UNREAL_PROJECT_PATH'])")

# Must match retarget_amass_to_robot.py's own derivation from AMASS_DATASET.
export AMASS_DATASET="${DATASET}"
POOL_NAME="$("${PY}" -c "print('${DATASET}'.capitalize())")"
SRC_POOL="/Game/BodyModels/${POOL_NAME}Src"
RETARGET_DIR="/Game/BodyModels/Robot/retargeting/$("${PY}" -c "print('${DATASET}'.lower())")"

echo "==> dataset=${DATASET}  work=${WORK}"
echo "    UE pool=${SRC_POOL}  retarget out=${RETARGET_DIR}"

echo "==> [1/8] stage AMASS clips flat (symlinks)"
"${PY}" "${REPO}/processing/stage_amass_clips.py" \
    --input_dir "${AMASS_DIR}" --output_dir "${WORK}/staged"

echo "==> [2/8] SMPL-X npz -> FBX (Blender + SMPL-X add-on)"
# make_fbx_files.py writes into <output_dir>/animations/. It has no skip logic
# of its own, but re-exporting an existing FBX is idempotent, so a rerun is
# safe -- just slower than it needs to be.
cd "${REPO}"
"${PY}" make_fbx_files.py --input_dir "${WORK}/staged" --output_dir "${WORK}" \
    --anim_format AMASS --processes 6

echo "==> [3/8] import FBX into UE as animations"
# Must run from the script's own directory: handle_paths.py looks for
# "../../../paths.json" relative to the current working directory, not to
# itself, so invoking it by absolute path from anywhere else fails.
cd "${REPO}/retargeting/Content/Python"
"${PY}" import_batch.py \
    --input_dir "${WORK}/animations" --output_dir "${SRC_POOL}" \
    --animation --num_batches 4 --processes 4
cd "${REPO}"

# Verify the import actually happened. One of the parallel UE workers has been
# seen hang in a ZenServer recovery loop, doing nothing while its siblings
# finished -- and it fails SILENTLY: the asset directories still get created,
# just without the _Anim inside. Worse, humans.py skips any clip whose
# directory already exists, so a naive re-run repairs nothing. Delete the
# incomplete directories and re-import only those.
POOL_FS="${REPO}/retargeting/Content/BodyModels/${POOL_NAME}Src/animations"
for attempt in 1 2 3; do
    "${PY}" - "$POOL_FS" "${WORK}" <<'PYEOF' && break
import shutil, sys
from pathlib import Path
pool, work = Path(sys.argv[1]), Path(sys.argv[2])
missing = []
for fbx in sorted((work / "animations").glob("*.fbx")):
    asset_dir = pool / fbx.stem
    if not (asset_dir / f"{fbx.stem}_Anim.uasset").exists():
        if asset_dir.exists():
            shutil.rmtree(asset_dir)   # or humans.py will skip it as "already imported"
        missing.append(fbx)
retry = work / "animations_missing"
shutil.rmtree(retry, ignore_errors=True)
if missing:
    retry.mkdir(parents=True)
    for fbx in missing:
        (retry / fbx.name).hardlink_to(fbx.resolve())
    print(f"    {len(missing)} clip(s) failed to import -- retrying those")
sys.exit(1 if missing else 0)
PYEOF
    echo "==> [3/8] re-import attempt ${attempt}"
    cd "${REPO}/retargeting/Content/Python"
    "${PY}" import_batch.py \
        --input_dir "${WORK}/animations_missing" --output_dir "${SRC_POOL}" \
        --animation --num_batches 1 --processes 1
    cd "${REPO}"
done

echo "==> [4/8] retarget SMPL-X -> robot (interactive Editor, not a commandlet)"
# IKRetargetBatchOperation.DuplicateAndRetarget asserts under -run=pythonscript,
# hence -ExecutePythonScript here.
"${UE}" "${UPROJECT}" -stdout -FullStdOutLogOutput \
    -ExecutePythonScript="retarget_amass_to_robot.py"

echo "==> [5/8] export retargeted AnimSequences back to FBX"
"${UE}" "${UPROJECT}" -run=pythonscript \
    -script="export_anim_dir_fbx.py ${RETARGET_DIR} ${WORK}/fbx"

# retarget.py names its output "<basename of target body dir>+<clip>_Anim";
# the target mesh sits directly in .../Robot/bodies, so that prefix is the
# literal string "bodies+". Strip it (and the _Anim suffix) here so the clip
# name that reaches the final qpos npz is the AMASS one and nothing else.
for f in "${WORK}"/fbx/bodies+*_Anim.fbx; do
    [ -e "$f" ] || continue
    base="$(basename "$f")"; base="${base#bodies+}"; base="${base%_Anim.fbx}"
    mv "$f" "${WORK}/fbx/${base}.fbx"
done

echo "==> [6/8] FBX -> per-frame world bone poses (Blender)"
cd "${REPO}/mujoco_qpos_pipeline"
"${BLENDER}" --background --python scripts/extract_fbx_pose.py -- \
    --folder "${WORK}" --tpose-fbx assets/robot/robot.fbx

echo "==> [7/8] world poses -> robot.xml qpos"
"${PY}" scripts/fbx_pose_to_qpos.py \
    --mjcf mjcf/robot.xml --skeleton-json assets/robot/robot.json --folder "${WORK}"

echo "==> [8/8] correct the residual floor offset"
# UE's retargeter normalises stature but not limb proportions, leaving every
# clip a constant height off the floor -- feet hovering or sunk. Must run
# before the clips are treated as final.
cd "${REPO}"
"${PY}" processing/adjust_qpos_floor.py --qpos_dir "${WORK}/qpos" --confirm

echo
echo "Done. $(ls "${WORK}/qpos" | wc -l | tr -d ' ') qpos clips in ${WORK}/qpos"
echo
echo "Next:"
echo "  python3 processing/check_qpos_output.py --qpos_dir ${WORK}/qpos --mjcf mujoco_qpos_pipeline/mjcf/robot.xml"
echo "  python3 render_videos.py --qpos_dir ${WORK}/qpos --output_dir ${WORK}/videos --num 10"
echo "  python3 processing/publish_dataset.py --qpos_dir ${WORK}/qpos"
echo "  python3 processing/cleanup_dataset.py --dataset ${DATASET} --confirm"
