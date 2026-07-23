# End-to-End Pipeline Walkthrough: Cross-Embodiment Example Videos

This document records a concrete, reproducible run of the BEDLAM2 retargeting
pipeline: taking real AMASS motion capture, retargeting it onto SMPL-X bodies
with different proportions, and rendering example videos of the result. It
complements the top-level `README.md` (which covers the general tool) with
the specific data, configuration, and extra scripts (floor adjustment,
video rendering) needed to go from raw mocap to a finished video.

## 1. Environment

| Component | Version used |
|---|---|
| Unreal Engine | 5.4 (this repo's `5.4` branch) |
| Blender | 4.2.22 LTS |
| SMPL-X Blender add-on | 1.0.3 (20241129 build) |
| Python | via `uv`, `requirements.txt` (`smplx`, `torch`, `tqdm`, `bpy`) |

`paths.json` points at the local install paths for Blender and
`UnrealEditor-Cmd`, and at this repo's `retargeting.uproject` /
`Content/Python` directory. See `paths.json` for the exact fields.

Required UE plugins (Edit → Plugins): Python Editor Script Plugin, Python
Foundation Packages, Python Remote Execution.

Note on the SMPL-X add-on: newer Blender versions (4.2+) install add-ons as
namespaced extensions (`bl_ext.user_default.<name>`) instead of the classic
bare module name. `processing/fbx_toolkit.py` tries both names when enabling
the add-on so it works across Blender versions.

## 2. Input motion format

Source motion comes from **AMASS** (SMPL-X G format), not from a
BEDLAM-internal dataset. AMASS subject folders (e.g. `ACCAD`) contain, per
subject, one `<gender>_stagei.npz` (shape/calibration only — no usable pose
sequence) and many `<sequence>_stageii.npz` files (one per recorded motion,
with full `poses`/`trans`/`betas`).

For this walkthrough:
- **Bodies** (different proportions): the `_stagei.npz` file for each of two
  AMASS subjects — `Male1General_c3d` and `Female1General_c3d` — used only
  for their `betas`.
- **Animations**: four `_stageii.npz` motion clips, two per subject
  (`Stand`, `LiftBox`).

`make_fbx_files.py` names its outputs from the input file's *grandparent /
parent* folder names (BEDLAM's own convention: one motion per leaf folder),
not from the npz's own filename. AMASS's native layout puts many motions in
one subject folder, which collides under that convention. Each motion (and
each body) was therefore copied into its own two-level folder before
conversion:

```
fbx_src/
    animations_input/
        Male_Stand/subj/General_A1_-_Stand_stageii.npz
        Male_LiftBox/subj/General_A6_-_Lift_Box_stageii.npz
        Female_Stand/subj/A1_-_Stand_stageii.npz
        Female_LiftBox/subj/A6_-_lift_box_stageii.npz
    bodies_input/
        MaleBody/subj/male_stagei.npz
        FemaleBody/subj/female_stagei.npz
```

Conversion to FBX (both share one `--output_dir` so the tool's own
`animations/` / `bodies/` split isn't duplicated):

```bash
uv run make_fbx_files.py --input_dir fbx_src/animations_input --output_dir fbx --anim_format AMASS
uv run make_fbx_files.py --input_dir fbx_src/bodies_input --output_dir fbx --anim_format AMASS --tpose
```

This produces `fbx/animations/*.fbx` (baked motion, mesh included) and
`fbx/bodies/*.fbx` + `.npz` (T-pose, betas only).

Two fixes were needed in `processing/fbx_toolkit.py` for this to produce
correct, floor-aligned, correctly-gendered assets:
- `convert_to_fbx(..., snap_to_ground_plane=True)` — without this, the
  character floats above or sinks below the floor after conversion, which
  then produces incorrect IK retargeting (foot sliding/floating).
- `export_tpose_npz` now carries over the source npz's real `gender` instead
  of hardcoding `"neutral"`. The SMPL-X add-on builds the mesh from the
  gender-specific base template (which has sex-specific body geometry, not
  just shape-key deformation), so a body built from the neutral template
  looks visually ambiguous regardless of its betas.

Body/animation pairing CSV (`target_body,source_anim`):

```bash
uv run make_csv_file.py --bodies-dir fbx/bodies --animations-dir fbx/animations --output csv/test_retarget.csv
```

`make_csv_file.py` filters out pairs where the animation name is derived
from the same source as the body (self-retargeting). Because our body and
animation folder names are unrelated strings (`MaleBody` vs
`Male_Stand_subj`), all 8 cross combinations survive, including
cross-subject/cross-gender pairs (e.g. a male motion retargeted onto the
female-proportioned body).

## 3. Humanoid model / target bodies

Both bodies are SMPL-X, differing only in `betas` (real body-shape
coefficients from the two AMASS subjects) and gender-specific base template:

| Target | Source | betas (first 4 dims) |
|---|---|---|
| `MaleBody` | `Male1General_c3d/male_stagei.npz` | `[-1.32, 0.13, 2.07, -0.62]` |
| `FemaleBody` | `Female1General_c3d/female_stagei.npz` | `[0.49, -0.60, -1.99, -3.43]` |

The IK Retargeter used is the repo-provided `smplx_IKRetargeter` /
`smplx_IKRig` under `retargeting/Content/BodyModels/Smplx` — same rig for
both source and target skeletons, since both sides are SMPL-X.

## 4. Retargeting configuration (in Unreal Engine)

1. Open `retargeting/retargeting.uproject`, run `Widgets/HumanEngineWidget`
   as an Editor Utility Widget.
2. **Import**: run once with Input Directory = `fbx/animations`, Animation
   checked; once more with Input Directory = `fbx/bodies`, Animation
   unchecked. Pool dir used here: `/Engine/BedlamRetarget/batch_00` (kept
   outside `/Game` so this throwaway batch data doesn't pollute the
   project's tracked content — enable **Show Engine Content** in the
   Content Browser filters to see it).  
   For faster importing of the `.fbx` files, use `import_batch.py` script.
   Use `--animation` flag to import the animations.
   ```bash
   cd retargeting\Content\Python
   # Example of --num_batches 10 --processes 5: Splits the data into 10 batches. It will spawn 5 Unreal Engine at the same time to process the batches.
   # (use UE paths: either /Game or /Engine) --output_dir: /Engine/BedlamRetarget/batch_00
   uv run import_batch.py --input_dir /Users/coconut/bedlam2_retargeting/fbx --output_dir /Engine/BedlamRetarget/batch_00 --num_batches 10 --processes 5
   uv run import_batch.py --input_dir /Users/coconut/bedlam2_retargeting/fbx/bodies --output_dir /Engine/BedlamRetarget/batch_00 --num_batches 1 --processes 1
   ```
3. Before retargeting, verify in the IK Retargeter preview that source and
   target skeletons are both standing on the floor plane, and that IK is
   disabled (FK only) — see `docs/both_on_floor.png` / `docs/only_FK.png`.
4. **Retarget**: CSV path = `csv/test_retarget.csv`, Pool dir =
   `/Engine/BedlamRetarget/batch_00`. Produces 8 `Animation Sequence` assets
   under `retargeting/test_retarget/`, named `<body>+<source_anim>_Anim`.
   Use the `retarget_batch.py` script to retarget animations with multiple processes in batches.

   ```bash
   uv run retarget_batch.py --pool_dir /Engine/BedlamRetarget/batch_00 --csv_path_retargeting /Users/coconut/bedlam2_retargeting/csv/test_retarget.csv \
   --num_batches 10 \
   --processes 1
   ```
5. **Export**: In HumanEngineWidget, select all 8 sequences, export both FBX (with mesh) and NPZ
   **with betas** (the "with betas" NPZ export needs a Betas directory field
   pointed at `fbx/bodies` — without it, betas silently default to zero and
   the output looks like it's using the wrong/neutral body).

`retargeting/Content/Python/import_batch.py` and `retarget_batch.py` build
their Unreal launch command as a single string and pass it to
`subprocess.run(cmd)`. That works on Windows (`CreateProcess` accepts a full
command-line string) but silently fails with `FileNotFoundError` on
macOS/Linux, since `subprocess.run` without `shell=True` treats the whole
string as a single executable path. Both were fixed to
`subprocess.run(cmd, shell=True)`.

`retargeting/Content/Python/export_npz.py` also hardcoded
`data["gender"] = "neutral"` on every exported npz, independent of the
target body — same failure mode as the T-pose export bug above, just on the
UE side. Fixed so `get_betas_from_npz_dir` returns `(betas, gender)` read
from the matching body npz in the Betas directory, and that gender is
written into the exported npz.

## 5. Floor height correction (Step 5, post-export)

Retargeting between differently-proportioned skeletons (with IK disabled)
introduces vertical drift, since foot-ground contact isn't solved during FK
retargeting. This is corrected on the exported NPZ, not the FBX:

```bash
uv run adjust_floor_npz.py --input_dir output/npz_with_betas
```

Requires `body_models/SMPLX_NEUTRAL.npz` (SMPL-X, head-bun removed, from
smpl-x.is.tue.mpg.de) and the `tqdm` dependency (missing from
`requirements.txt`; added).

Output: `output/npz_with_betas_floor_adjusted/*.npz`. This is the
data that should be used for visualization — the raw
`retargeting_data/fbx/*.fbx` export is **not** floor-adjusted.

## 6. Video rendering procedure

The floor-adjusted NPZ files are converted back to mesh-bearing FBX (one
Blender invocation per file, to avoid `make_fbx_files.py`'s folder-based
naming collisions when all files share one flat parent directory):

```bash
BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"
for f in retargeting_data/npz_with_betas_floor_adjusted/*.npz; do
  name=$(basename "$f" .npz)
  "$BLENDER" --background --python processing/fbx_toolkit.py -- \
    --smplx_animation_path "$f" --out_fbx_path "videos_src/$name.fbx" --anim_format SMPL-X
done
```

Then rendered to individual `.mp4` files with two new scripts:

- `processing/render_worker.py` — Blender background script. Imports one
  FBX, sets the scene frame range to the imported action's actual range
  (Blender's default new-scene range would otherwise hold the last pose
  static for the remainder), computes the character's world-space bounding
  box (sampled at the start/middle/end frame, since retargeted subjects
  differ in size and root position — a fixed guessed camera position either
  clipped the subject or showed nothing), places a camera in front of the
  character (subjects face `-Y`) at a distance derived from the camera's
  actual horizontal/vertical FOV so the whole body fits regardless of size,
  and renders with the Workbench engine (fast, no material/lighting setup
  needed) to an FFmpeg/H.264 `.mp4`.
- `render_videos.py` — top-level driver (mirrors `make_fbx_files.py`'s
  pattern), loops over every FBX in an input directory and calls Blender
  once per file via `paths.json`'s `BLENDER_APP_PATH`.

```bash
uv run render_videos.py --input_dir videos_src --output_dir videos --fps 30
```

Result: `videos/<body>+<source_anim>.mp4`, 8 files for this run — each
pairing one of the two body proportions with one of the four source
motions, including cross-subject retargets.

## 7. Known pitfalls (for reproducing this run)

- Don't point `make_csv_file.py` / `make_fbx_files.py` at input folders whose
  body and animation both derive from the same subject name — the self-pair
  filter will silently drop those combinations.
- Don't use `_stagei.npz` files as an animation input — they hold no pose
  sequence and will fail AMASS import; they're only valid as a `betas`
  source for T-pose body generation.
- The "with betas" NPZ export in the widget requires the Betas directory
  field to be filled in; the checkbox alone is not sufficient and fails
  silently to all-zero betas.
- Always visualize the **floor-adjusted** NPZ (via `fbx_toolkit.py`), not
  the raw FBX exported directly from the retargeting step.
