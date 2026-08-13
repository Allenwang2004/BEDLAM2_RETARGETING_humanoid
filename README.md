# Retargeting for BEDLAM 2.0

This repository provides tools to retarget humanoid motion capture data onto humanoid characters — transferring motion
from a source humanoid to target skeletons with different body proportions and morphologies.

Retargeting transfers motion from one skeleton to another, enabling the augmentation of SMPL-X data with various body
shapes while preserving motion quality.

This repository contains the retargeting tool developed
for [BEDLAM 2.0 NeurIPS 2025](https://bedlam2.is.tuebingen.mpg.de/), built
on [Unreal Engine's IK Retargeter](https://dev.epicgames.com/documentation/en-us/unreal-engine/ik-rig-animation-retargeting-in-unreal-engine?application_version=5.3)
by Epic Games.

We use branche: `5.4`.

For the latest UE retargeting features, visit
the [Unreal Engine documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/ik-rig-animation-retargeting-in-unreal-engine).

For the rendering pipeline of BEDLAM 2.0 and other useful tools, please refer to the [BEDLAM2 Render Tools](https://github.com/PerceivingSystems/bedlam2_render).

## Pipeline: AMASS human motion → MuJoCo `robot.xml` qpos

The concrete, reproducible run this repo is currently built around — real human mocap retargeted onto the MuJoCo
`robot.xml` skeleton, ending in per-clip `qpos` arrays. Full details in
[docs/pipeline_human_to_robot.md](docs/pipeline_human_to_robot.md); the generic 5-step tool it is built on is
documented further below.

```bash
./run_human_to_robot.sh [<amass_dataset_dir>] [<work_dir>]   # defaults: raw_data/ACCAD, human_to_robot/
```

Deliverable: `<work_dir>/qpos/<Subject>__<clip>.npz`, each a `(nframes, 76)` `qpos` array at 30 fps — 7 free-joint
values (pelvis world position + quaternion) followed by 23 bodies × 3 hinge DOFs. Every stage is resumable, so
rerunning after an interruption or after adding more clips only does the outstanding work.

Validate the result with:

```bash
python3 processing/check_qpos_output.py --qpos_dir human_to_robot/qpos \
    --mjcf mujoco_qpos_pipeline/mjcf/robot.xml --verbose
```

### Source data

This pipeline expects **AMASS in SMPL-X G (gendered)** form — the per-subject `<clip>_stageii.npz` files, not the
`_stagei.npz` shape/calibration files, which carry no pose sequence. Download it from
[amass.is.tue.mpg.de](https://amass.is.tue.mpg.de/) under your own account; it is not redistributable, so
`raw_data/` is gitignored.

## Requirements:

- [Unreal Engine](https://www.unrealengine.com/) 5.4
  - Enable Python plugin
  - Enable Python Foundation Packages Plugin (numpy) _(for using .npz files)_
  - Enable Python Remote Execution
- [SMPL-X Blender add-on (20241129)](https://smpl-x.is.tue.mpg.de/) _(for exporting SMPL-X .fbx files from
  .npz files)_
- Python environment with the `requirements.txt` dependencies installed.

## Getting started:

1. Open the project in Unreal Engine.
2. Enable the widget: Right-Click on the `Widgets/HumanEngineWidget` and select `Run Editor Utility Widget`.
3. Edit the `paths.json` file in this folder to set your own paths.

## Retargeting Pipeline in 5 steps:

### Step 1: Dataset preparation (FBX files and CSV file)

Source motion is AMASS/SMPL-X `.npz` (see "Source data" above).

#### Prepare FBX directories:
- `animations` directory with `.fbx` files (source animations).

For converting to `.fbx` files, use the following script, or the [BEDLAM2 Render Tools (smplx_anim_to_fbx)](https://github.com/PerceivingSystems/bedlam2_render/tree/main/blender/smplx_anim_to_fbx) code.
```bash
# Make source animation FBX files from NPZ files (animations dir)
uv run make_fbx_files.py --input_dir <input_npz_dir> --output_dir <output_fbx_dir> --anim_format AMASS
```

Note: output names are derived from the input file's parent/grandparent folder names, so pointing this straight at an
AMASS tree makes every clip in a subject folder collapse onto one name and overwrite the others. Flatten the tree
first — `processing/stage_amass_clips.py` symlinks each clip out as a uniquely named `<Subject>__<clip>.npz`, which
is the layout `make_fbx_files.py` names from the file's own stem.

Exported `.fbx` files structure example:

```
fbx/
    animations/
        it_4027_XL_2000.fbx
        it_4034_L_2000.fbx
        ...
    bodies/
        it_4009_M.fbx
        it_4027_XL.fbx
        ...
```

#### Prepare the CSV file with the pairs

```bash
uv run make_csv_file.py --bodies-dir <bodies_fbx_dir> --animations-dir <animations_fbx_dir> --output <output_csv_file>
```

### Step 2: Import FBX files to Unreal Engine

For faster importing of the `.fbx` files, use `import_batch.py` script.

```bash
cd retargeting\Content\Python
# Example of --num_batches 10 --processes 5: Splits the data into 10 batches. It will spawn 5 Unreal Engine at the same time to process the batches.
# (use UE paths: either \Game or \Engine) --output_dir: \Engine\BedlamRetarget\b2_testing_tool
python import_batch.py --input_dir <input_dir_of_fbx_files> --output_dir <output_abs_dir_of_uassets> --num_batches 10 --processes 5 --animation
```

Or use the GUI widget. Click on `Import` button and set the Animation toggle button, to import FBX files from an _absolute path directory_:

- check `Animation` (boolean) to import the animation as well -> saves in `{working_dir}/animations/`.
- uncheck `Animation` (boolean) to import the skeleton only -> saves in `{working_dir}/bodies/`.

Imported `.uasset` files structure example:

```
working_dir/
    animations/
        it_4027_XL_2000/
            it_4009_M_2000.uasset
            it_4009_M_2000_Anim.uasset
            it_4009_M_2000_Skeleton.uasset
        ...
    bodies/
        it_4009_M/
            it_4009_M.uasset 
            it_4009_M_Skeleton.uasset
        ...
```

#### Make sure all animations and skeletal meshes are on the floor level

#### Use a IK Rig

You may use your own IK Rig as well. If the source and target skeletons have different chain names, they must be mapped
in the IK Retargeter.

### Step 3: Retarget animations to target bodies

#### Retargeting with multiple processes (recommended)

Use the `retarget_batch.py` script to retarget animations with multiple processes in batches.

```bash
 python .\retarget_batch.py \
 --pool_dir <working dir> \  # e.g. /Game/BodyModels/Robot
 --csv_path_retargeting <csv_file_path> \
 --num_batches 100 \
 --ik_retargeter_path /Game/BodyModels/Robot/Robot_IKRetargeter \
  --source_ik_rig_path /Game/BodyModels/Smplx/smplx_IKRig \
  --target_ik_rig_path /Game/BodyModels/Robot/Robot_IKRig \
 --processes 10
 --
```

Or Click the `Retarget` from the GUI widget.

It saves in `{working_dir}/retargeting/`.

Find the **retargeted animations** (Animation Sequences) in the following structure:

```working_dir/
    animations/
        ...
    bodies/
        ...
    retargeting/
        <csv_filename>/
            it_4009_M+it_4009_M_2000_Anim.uasset
            it_4009_M+it_4027_XL_2000_Anim.uasset
            it_4027_XL+it_4039_L_2001_Anim.uasset
            ...
        ...
```
### Step 4: Export the retarget result in FBX files

After retargeting, select the Animation Sequences (retargeted animations) to export.
We can export as `.fbx` files (with or without mesh) using the GUI widget.
