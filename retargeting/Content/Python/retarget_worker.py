# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
import math
import os
import sys
import unreal
import retarget
from importlib import reload
reload(retarget)
from retarget import execute, ignore_already_retargeted, get_retargeting_couples_from_csv_file


if __name__ == '__main__':
    # This script is used by the retarget_batch.py
    print("Starting retargeting (retarget.py)...")
    csv_path_retargeting = sys.argv[1]
    ik_retargeter_path = sys.argv[2]
    source_ik_rig_path = sys.argv[3]
    target_ik_rig_path = sys.argv[4]
    pool_dir = sys.argv[5]
    batch_index = int(sys.argv[6])
    num_batches = int(sys.argv[7])

    if len(sys.argv) > 8:
        max_rows_num = int(sys.argv[8])
    else:
        max_rows_num = None

    # Get the paths (dirs) from the csv file
    all_target_body_names, all_source_animation_names = get_retargeting_couples_from_csv_file(csv_path_retargeting)

    # Retarget the animations
    out_dir = f"{pool_dir}/retargeting/{os.path.basename(csv_path_retargeting).split('.')[0]}"

    if max_rows_num is not None:
        all_target_body_names = all_target_body_names[:max_rows_num]
        all_source_animation_names = all_source_animation_names[:max_rows_num]

    # Based on batch_index and batch_size, select the subset of the data
    batch_size = math.ceil(len(all_target_body_names) / num_batches)
    start_index = batch_index * batch_size
    end_index = start_index + batch_size
    all_target_body_names = all_target_body_names[start_index:end_index]
    all_source_animation_names = all_source_animation_names[start_index:end_index]

    # Ignore already retargeted (by checking if the file exists in the out_dir)
    all_target_body_names, all_source_animation_names = ignore_already_retargeted(
        all_target_body_names, all_source_animation_names, out_dir
    )

    for target_name, source_name in zip(all_target_body_names, all_source_animation_names):
        execute(
            target_dir=f"{pool_dir}/bodies/{target_name}",
            source_skel_path=f"{pool_dir}/animations/{source_name}/{source_name}",
            source_anim_path=f"{pool_dir}/animations/{source_name}/{source_name}_Anim",
            ik_retargeter_path=ik_retargeter_path,
            source_ik_rig_path=source_ik_rig_path,
            target_ik_rig_path=target_ik_rig_path,
            out_dir=out_dir,
        )
    unreal.log("Done")
