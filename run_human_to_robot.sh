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
WORK="${2:-${REPO}/human_to_robot}"

PY="${REPO}/.venv/bin/python"
BLENDER=$("${PY}" -c "import json;print(json.load(open('${REPO}/paths.json'))['BLENDER_APP_PATH'])")
UE=$("${PY}" -c "import json;print(json.load(open('${REPO}/paths.json'))['UNREAL_APP_PATH'])")
UPROJECT=$("${PY}" -c "import json;print(json.load(open('${REPO}/paths.json'))['UNREAL_PROJECT_PATH'])")

SRC_POOL=/Game/BodyModels/AccadSrc
RETARGET_DIR=/Game/BodyModels/Robot/retargeting/accad

echo "==> [1/7] stage AMASS clips flat (symlinks)"
"${PY}" "${REPO}/processing/stage_amass_clips.py" \
    --input_dir "${AMASS_DIR}" --output_dir "${WORK}/staged"

echo "==> [2/7] SMPL-X npz -> FBX (Blender + SMPL-X add-on)"
# make_fbx_files.py writes into <output_dir>/animations/. It has no skip logic
# of its own, but re-exporting an existing FBX is idempotent, so a rerun is
# safe -- just slower than it needs to be.
cd "${REPO}"
"${PY}" make_fbx_files.py --input_dir "${WORK}/staged" --output_dir "${WORK}" \
    --anim_format AMASS --processes 6

echo "==> [3/7] import FBX into UE as animations"
"${PY}" "${REPO}/retargeting/Content/Python/import_batch.py" \
    --input_dir "${WORK}/animations" --output_dir "${SRC_POOL}" \
    --animation --num_batches 4 --processes 4

echo "==> [4/7] retarget SMPL-X -> robot (interactive Editor, not a commandlet)"
# IKRetargetBatchOperation.DuplicateAndRetarget asserts under -run=pythonscript,
# hence -ExecutePythonScript here.
"${UE}" "${UPROJECT}" -stdout -FullStdOutLogOutput \
    -ExecutePythonScript="retarget_amass_to_robot.py"

echo "==> [5/7] export retargeted AnimSequences back to FBX"
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

echo "==> [6/7] FBX -> per-frame world bone poses (Blender)"
cd "${REPO}/mujoco_qpos_pipeline"
"${BLENDER}" --background --python scripts/extract_fbx_pose.py -- \
    --folder "${WORK}" --tpose-fbx assets/robot/robot.fbx

echo "==> [7/7] world poses -> robot.xml qpos"
"${PY}" scripts/fbx_pose_to_qpos.py \
    --mjcf mjcf/robot.xml --skeleton-json assets/robot/robot.json --folder "${WORK}"

echo
echo "Done. $(ls "${WORK}/qpos" | wc -l | tr -d ' ') qpos clips in ${WORK}/qpos"
