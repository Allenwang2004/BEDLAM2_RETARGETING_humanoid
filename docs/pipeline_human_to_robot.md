# AMASS human motion -> `robot.xml` qpos pipeline

Converts real human motion capture from **AMASS (SMPL-X G)** into MuJoCo `qpos`
for `robot.xml` -- the human -> humanoid counterpart of
[robotmotion_to_robot_child_pipeline.md](robotmotion_to_robot_child_pipeline.md),
which retargets robot motion onto a smaller robot. Both converge on the same
reverse half (FBX -> world pose -> qpos), so only the source half differs: here
the motion starts as SMPL-X body parameters rather than as qpos.

Run the whole thing with:

```bash
./run_human_to_robot.sh [<amass_dataset_dir>] [<work_dir>]
# defaults: raw_data/ACCAD, human_to_robot/
```

Deliverable: `<work_dir>/qpos/<Subject>__<clip>.npz`, each holding a
`(nframes, 76)` `qpos` array at 30 fps -- 7 free-joint values (pelvis world
position + quaternion) followed by 23 bodies x 3 hinge DOFs, the same layout
`robotmotion/`'s own clips use.

## Prerequisites

Same as the robot pipeline (`paths.json` pointing at UE 5.4 and Blender), plus
the [SMPL-X Blender add-on](https://smpl-x.is.tue.mpg.de/) 1.0.3 (20241129) for
step 2. The UE assets it retargets between already exist in the repo:
`Smplx/smplx_IKRig` (source) and `Robot/Robot_IKRig` (target), whose retarget
chains were deliberately given matching names so `create_ik_retargeter.py`'s
EXACT auto-mapping lines them up -- see `create_robot_ik_rig.py`.

## Stages

### 1. Stage the AMASS clips flat

```bash
python3 processing/stage_amass_clips.py \
    --input_dir raw_data/ACCAD --output_dir human_to_robot/staged
```

AMASS ships one folder per capture subject with many motions inside
(`<Subject>_c3d/<clip>_stageii.npz`), but `make_fbx_files.py` derives its
output name from the input's parent/grandparent folders -- so every clip in a
subject folder resolves to the same name and silently overwrites the others.
Its other branch, for `.npz` sitting directly in `input_dir`, uses the file's
own stem instead. So this step symlinks every clip flat as
`<Subject>__<clip>.npz`, which is unique across the whole dataset and survives
unchanged all the way to the final qpos filename.

`_stagei.npz` files are skipped: they carry only shape/calibration data with no
usable pose sequence.

### 2. SMPL-X npz -> FBX (Blender)

```bash
python3 make_fbx_files.py --input_dir human_to_robot/staged \
    --output_dir human_to_robot --anim_format AMASS --processes 6
```

`--anim_format AMASS` matters: it selects the importer's AMASS coordinate
convention. `fbx_toolkit.py` reads each clip's `gender` field so the add-on
builds the body from the matching gendered template, and snaps it to the ground
plane. Writes `human_to_robot/animations/<clip>.fbx` (~2 MB each).

### 3. Import into UE

```bash
python3 retargeting/Content/Python/import_batch.py \
    --input_dir human_to_robot/animations --output_dir /Game/BodyModels/AccadSrc \
    --animation --num_batches 4 --processes 4
```

Creates `/Game/BodyModels/AccadSrc/animations/<clip>/{<clip>, <clip>_Anim}`.

### 4. Retarget SMPL-X -> robot

```bash
UnrealEditor-Cmd retargeting.uproject -stdout -FullStdOutLogOutput \
    -ExecutePythonScript="retarget_amass_to_robot.py"
```

Must be the interactive Editor, not `-run=pythonscript`:
`IKRetargetBatchOperation.DuplicateAndRetarget` asserts under the commandlet.

`retarget_amass_to_robot.py` scans `AccadSrc/animations` for whatever has been
imported and skips clips already present in the output directory, so it is
resumable. Source rig `smplx_IKRig`, target rig `Robot_IKRig`, retargeter
`Robot_IKRetargeter`; output lands in
`/Game/BodyModels/Robot/retargeting/accad/` as `bodies+<clip>_Anim`.

### 5. Export back to FBX

```bash
UnrealEditor-Cmd retargeting.uproject -run=pythonscript \
    -script="export_anim_dir_fbx.py /Game/BodyModels/Robot/retargeting/accad human_to_robot/fbx"
```

`run_human_to_robot.sh` then strips the `bodies+` prefix and `_Anim` suffix from
the exported filenames (`retarget.py` builds that prefix from the target body
directory's basename, which for `Robot/bodies` is the literal word "bodies"),
so the AMASS clip name is what reaches the final npz.

### 6-7. FBX -> world pose -> qpos

```bash
cd mujoco_qpos_pipeline
blender --background --python scripts/extract_fbx_pose.py -- \
    --folder ../human_to_robot --tpose-fbx assets/robot/robot.fbx
python3 scripts/fbx_pose_to_qpos.py --mjcf mjcf/robot.xml \
    --skeleton-json assets/robot/robot.json --folder ../human_to_robot
```

Identical to the robot pipeline's reverse half, just pointed at `robot.xml` /
`robot.json` instead of the `robot_child` pair. Writes
`human_to_robot/qpos/<clip>.npz`.

## Validation

`processing/check_qpos_output.py` runs over the produced qpos folder and reports
per-clip pelvis height, quaternion norm, hinge-angle range, NaN/Inf counts and
implied travel speed. Spot-checked on the first two clips:

| clip | frames | pelvis z | travel |
|---|---|---|---|
| `Female1General__A1_-_Stand` | 91 | 1.062-1.065 m, essentially static | 0.13 m/s peak |
| `Female1Walking__B1_-_stand_to_walk` | 187 | 0.981-1.056 m | 4.14 m over 6.2 s = 0.66 m/s |

Both have unit-norm quaternions, no NaN/Inf, and hinge angles within +-1.14 rad.
A standing clip staying at a constant pelvis height and a walk clip advancing at
a plausible human walking speed is the cheap end-to-end sanity check that the
retarget did not collapse or explode.

Note the pelvis sits around 1.02-1.06 m while `robot.xml`'s own rest pelvis
height is 0.9567 m: the retargeter preserves the source human's proportions
rather than snapping to the robot's rest pose, so a taller-than-rest pelvis is
expected, not a bug.

## Known caveat

The `_stagei.npz` shape files are unused here -- every clip is retargeted onto
the single `robot` body, so the source subject's `betas` only influence the
motion through the SMPL-X armature's proportions at step 2, not through any
per-body variation on the target. Retargeting onto multiple differently-sized
robot bodies (as `robot_child` does) would be a separate pass.
