# robotmotion (qpos) -> robot_child (qpos) pipeline

Converts a MuJoCo `qpos` motion clip authored for `robot.xml` (e.g. any
`.npz` under `robotmotion/`, shape `(nframes, 76)`) into the equivalent
motion for `robot_child.xml` -- same topology, smaller proportions -- by
round-tripping it through Unreal's IK Retargeter. Everything needed lives in
this repo; nothing here depends on the sibling `mujoco_humanoid_retargeting`
checkout anymore.

Validated end-to-end on `robotmotion/headstand/headstand_0.npz`: the
resulting `robot_child` qpos's Pelvis position scales from the source by
~0.611x on every axis, at every frame checked -- exactly `robot_child`'s own
rest-pose Pelvis height ratio (`0.584578 / 0.9567`), confirming the
retargeter is correctly adapting to the smaller skeleton rather than just
copying numbers through.

## Layout

```
mujoco_qpos_pipeline/
    mjcf/robot.xml, robot_child.xml          # MuJoCo models (source of truth for qpos layout)
    assets/robot/robot.fbx, robot.json       # base armature FBX + skeleton JSON (source topology)
    assets/robot/robot_child.fbx, robot_child.json   # same, target topology
    scripts/qpos_to_world_pose.py            # stage 1 (forward):  qpos -> world_pose.json      [this repo's .venv, mujoco]
    scripts/world_pose_to_fbx.py             # stage 2 (forward):  world_pose.json -> animated FBX [Blender]
    scripts/extract_fbx_pose.py              # stage 1 (reverse):  retargeted FBX -> pose.json    [Blender]
    scripts/fbx_pose_to_qpos.py              # stage 2 (reverse):  pose.json -> qpos npz          [this repo's .venv, mujoco]
    example_run/robot_child_motion_example/  # sample output from the validation run above

fbx/bodies/robot_child.fbx                   # same file as assets/robot/robot_child.fbx, used for the one-time UE body import

processing/qpos_smplx_convert.py             # NOT part of this pipeline -- a from-scratch alternative
processing/test_qpos_smplx_roundtrip.py      # that writes AnimSequences directly via UE's AnimDataController,
                                              # skipping Blender/FBX entirely. Documented but not wired in; see
                                              # "Alternative: skip Blender entirely" below.

retargeting/Content/Python/
    smoketest_retarget_robot_child.py                    # retargets Robot's own completed clips onto robot_child
    smoketest_retarget_robotmotion_to_robot_child.py     # retargets robotmotion-derived clips onto robot_child (step 4 below)
    export_anim_dir_fbx.py                               # exports AnimSequences under a UE dir back to FBX (step 5)
    import_batch.py, create_robot_ik_rig.py,
    create_ik_retargeter.py, retarget.py                 # generic UE-side building blocks these two scripts use
```

`paths.json` (repo root) already points at the UE executable/project and
Blender; all commands below assume it's configured and that
`retargeting/Content/BodyModels/Robot_child/` and
`.../RobotMotionSrc/` already exist (see "One-time setup").

## One-time setup (already done for `robot_child`; redo only for a new target body)

1. `fbx/bodies/robot_child.fbx` imported as a body:
   ```bash
   cd retargeting/Content/Python
   python3 import_batch.py --input_dir /Users/coconut/bedlam2_retargeting/fbx/bodies \
     --output_dir /Game/BodyModels/Robot_child --num_batches 1 --processes 1
   ```
2. IK Rig for it (bone names are identical to `Robot`'s, so
   `create_robot_ik_rig.py` is reused verbatim):
   ```bash
   UnrealEditor-Cmd retargeting.uproject -run=pythonscript -script="create_robot_ik_rig.py \
     /Game/BodyModels/Robot_child/bodies/robot_child/robot_child /Game/BodyModels/Robot_child/RobotChild_IKRig"
   ```
3. IK Retargeter, source = `Robot_IKRig` (works directly for robotmotion-derived
   clips too, since they share `robot.fbx`'s bone names -- no need to stage
   through Robot's own skeletal mesh):
   ```bash
   UnrealEditor-Cmd retargeting.uproject -run=pythonscript -script="create_ik_retargeter.py \
     /Game/BodyModels/Robot/Robot_IKRig /Game/BodyModels/Robot_child/RobotChild_IKRig \
     /Game/BodyModels/Robot_child/RobotChild_IKRetargeter"
   ```

## Per-clip pipeline

### 1. qpos -> world_pose.json (this repo's `.venv`, has `mujoco`)

```bash
cd mujoco_qpos_pipeline
source ../.venv/bin/activate
python3 scripts/qpos_to_world_pose.py \
  --qpos_npz ../robotmotion/<motion>/<clip>.npz \
  --mjcf mjcf/robot.xml \
  --output /tmp/<clip>_world_pose.json --fps 30
```

Runs `mj_forward` per frame on `robot.xml`, dumps every body's world
position/orientation to JSON.

### 2. world_pose.json -> animated FBX (Blender)

```bash
blender --background --python scripts/world_pose_to_fbx.py -- \
  --world_pose /tmp/<clip>_world_pose.json \
  --skeleton_json assets/robot/robot.json \
  --armature_fbx assets/robot/robot.fbx \
  --out_fbx /tmp/<clip>.fbx
```

Poses+keyframes `robot.fbx`'s armature one frame at a time and exports. Note
the known, non-fatal caveat below -- the exported FBX carries a residual
~0.01 object-level scale that UE's IK Retargeter complains about (via a
handled `ensure`, not an error) but does not appear to corrupt.

### 3. Import the FBX as an animation

```bash
cd ../retargeting/Content/Python
python3 import_batch.py --input_dir <dir containing the .fbx from step 2> \
  --output_dir /Game/BodyModels/RobotMotionSrc --animation --num_batches 1 --processes 1
```

Creates `/Game/BodyModels/RobotMotionSrc/animations/<clip>/{<clip>, <clip>_Anim}`.
Caution: `humans.py`'s naming truncates at the first `.` in the filename
(`crawl-0.4-0-d_0.fbx` -> asset name `crawl-0`), which collides across the
many robotmotion filenames that contain literal dots (e.g. `crawl-0.4-0-u_0`
would collide with `crawl-0.4-0-d_0`) -- import one clip at a time into its
own input directory, or fix the naming before batch-importing many.

### 4. Retarget onto robot_child (needs the interactive Editor, not a commandlet --

`IKRetargetBatchOperation.DuplicateAndRetarget` asserts under `-run=pythonscript`)

```bash
UnrealEditor-Cmd retargeting.uproject -stdout -FullStdOutLogOutput \
  -ExecutePythonScript="smoketest_retarget_robotmotion_to_robot_child.py"
```

`SOURCE_CLIPS` is populated by scanning `RobotMotionSrc/animations/` itself
(`list_imported_clips()`) -- whatever's been imported there via step 3 gets
picked up automatically, no manual list to edit. Already-retargeted clips
(asset already exists under `OUT_DIR`) are skipped via `retarget.py`'s
`ignore_already_retargeted()`, so reruns after importing more clips only
process the new ones. It calls `retarget.execute(...)` with
`source_ik_rig=Robot_IKRig`, `target_ik_rig=RobotChild_IKRig`,
`ik_retargeter=RobotChild_IKRetargeter`, writing to
`/Game/BodyModels/Robot_child/retargeting/robotmotion_smoketest/`.

### 5. Export the retargeted AnimSequence(s) back to FBX

```bash
UnrealEditor-Cmd retargeting.uproject -run=pythonscript -script="export_anim_dir_fbx.py \
  /Game/BodyModels/Robot_child/retargeting/robotmotion_smoketest <output_dir>/fbx"
```

(`<output_dir>` needs a `fbx/` subfolder for the next step -- point this
directly at `<output_dir>/fbx`.)

### 6. FBX -> world pose (Blender) -> robot_child qpos (this repo's `.venv`)

```bash
cd ../../mujoco_qpos_pipeline
blender --background --python scripts/extract_fbx_pose.py -- \
  --folder <output_dir> --tpose-fbx assets/robot/robot_child.fbx

source ../.venv/bin/activate
python3 scripts/fbx_pose_to_qpos.py \
  --mjcf mjcf/robot_child.xml \
  --skeleton-json assets/robot/robot_child.json \
  --folder <output_dir>
```

Writes `<output_dir>/qpos/<clip>.npz` -- this is the `robot_child_motion.npz`
deliverable, same `(nframes, 76)` qpos layout as the input, just retargeted
onto `robot_child`'s proportions. `example_run/robot_child_motion_example/`
has two already-generated samples.

## Known caveat: non-unit scale on qpos-derived source animations

Every bone of every qpos-derived clip (built via step 2) carries a redundant
`scale3d ~= (0.01, 0.01, 0.01)` in UE's world/component-space pose (confirmed
via `get_bone_pose(..., WORLD)` -- `LOCAL`-space bone transforms are clean).
This trips `IKRetargetProcessor.cpp`'s `ensureMsgf(bHasNoScale, ...)` -- a
handled, non-fatal, editor-only sanity check, logged once per Editor session
(not once per clip -- UE's `ensure()` suppresses repeats at the same
call-site, which is why only the first clip processed in a given session
shows the warning even though every clip triggers the same condition).

Root cause: `build_armature_fbx.py` (the script that builds `robot.fbx` /
`robot_child.fbx`, not present in this repo -- lives in the sibling
`mujoco_humanoid_retargeting` checkout) pre-scales coordinates by
`WORLD_SCALE=100` and declares the exported FBX's unit as centimeters
(`scene.unit_settings.scale_length = 0.01`) so the numbers read correctly as
real-world size. `world_pose_to_fbx.py` re-imports that FBX and, at export,
re-declares/re-bakes scale in a way that doesn't survive a fresh reimport
cleanly -- two different fixes were tried and empirically fell short (see the
`mujoco_humanoid_retargeting` session history for what was tried and why
each one failed the fresh-reimport test). Actually eliminating it requires
reworking `build_armature_fbx.py` to not pre-scale by 100 at all, which means
rebuilding `robot.fbx`/`robot_child.fbx`/`robot_elderly.fbx` and re-doing the
already-completed retargets built from them -- not done.

Practically: every numeric spot-check so far (frame count, duration,
root position/orientation, and the 0.611x proportional-scaling check above)
has come out correct despite this, so it appears to be a harmless artifact
that UE's retarget code discards rather than a real correctness bug -- but
this has only been verified by checking outputs, not by reading the engine's
internal handling of the scale value, so treat it as a known yellow flag
rather than a cleared one.

## Alternative: skip Blender entirely

`processing/qpos_smplx_convert.py` already gives an exact, validated (540/540
clips round-tripped, see `processing/test_qpos_smplx_roundtrip.py`)
qpos <-> per-joint-axis-angle conversion. UE 5.4's Python API has
`unreal.AnimDataController.set_bone_track_keys`, confirmed present and
capable of writing bone-track translation/rotation/scale directly -- scale
fixed to `(1,1,1)` always, so this route can't reproduce the issue above at
all, and skips steps 2 and 6 (both Blender stages) completely. Not built yet;
next step if the scale caveat above ever turns out to matter, or just to cut
the Blender dependency out of the loop.
