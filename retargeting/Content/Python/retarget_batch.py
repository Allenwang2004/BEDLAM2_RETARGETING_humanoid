# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
from multiprocessing import Pool
import subprocess
import sys
import time
import argparse
import os

# need forward slashes "\" when calling via -ExecutePythonScript, for UNREAL_APP_PATH, UNREAL_PROJECT_PATH
from handle_paths import PYTHON_SCRIPT_DIR, UNREAL_APP_PATH, UNREAL_PROJECT_PATH

# Globals for retarget_batch.py
IK_RETARGETER_PATH = "/Game/BodyModels/Smplx/smplx_IKRetargeter"
SOURCE_IK_RIG_PATH = "/Game/BodyModels/Smplx/smplx_IKRig"
TARGET_IK_RIG_PATH = "/Game/BodyModels/Smplx/smplx_IKRig"

PYTHON_SCRIPT_PATH = os.path.join(PYTHON_SCRIPT_DIR, "retarget_worker.py")
# Must run with the interactive Editor (not the -run=pythonscript commandlet):
# IKRetargetBatchOperation.DuplicateAndRetarget crashes under the commandlet
# with `Assertion failed: IsValid() [SharedPointer.h]` -- it depends on an
# editor-only context (viewport/world) the commandlet never initializes.
GUI_OFF = False


def worker(pool_dir, csv_retargeting, batch_index, num_batches,
           ik_retargeter_path=IK_RETARGETER_PATH,
           source_ik_rig_path=SOURCE_IK_RIG_PATH,
           target_ik_rig_path=TARGET_IK_RIG_PATH):
    if GUI_OFF:
        cmd_off = (f"\"{UNREAL_APP_PATH}\" \"{UNREAL_PROJECT_PATH}\" "
                   f"-run=pythonscript -script=\"{PYTHON_SCRIPT_PATH} "
                   f"{csv_retargeting} {ik_retargeter_path} {source_ik_rig_path} {target_ik_rig_path} {pool_dir} {batch_index} {num_batches}\"")
        print(f"Executing command: {cmd_off}", file=sys.stderr)
        subprocess.run(cmd_off, shell=True)
    else:
        cmd_off = (f"\"{UNREAL_APP_PATH}\" \"{UNREAL_PROJECT_PATH}\" "
                   f"-stdout -FullStdOutLogOutput -ExecutePythonScript=\"{PYTHON_SCRIPT_PATH} "
                   f"{csv_retargeting} {ik_retargeter_path} {source_ik_rig_path} {target_ik_rig_path} {pool_dir} {batch_index} {num_batches}\"")
        print(f"Executing command: {cmd_off}", file=sys.stderr)
        subprocess.run(cmd_off, shell=True)

    return True


def worker_args(args):
    return worker(*args)


if __name__ == "__main__":
    # Note that this script is not used by the UE widget. It is for command-line batch processing only.
    parser = argparse.ArgumentParser(description="Batch retargeting to Unreal Engine project")
    parser.add_argument("--pool_dir", type=str, help="Containing bodies and animations assets")
    parser.add_argument("--csv_path_retargeting", type=str, help="Import as animations (default: False)")
    parser.add_argument("--num_batches", type=int, help="Number of batches to split the import into")
    parser.add_argument("--processes", type=int, help="Number of processes to use for parallel import")
    parser.add_argument("--ik_retargeter_path", type=str, default=IK_RETARGETER_PATH,
                         help="IK Retargeter asset path (default: smplx_IKRetargeter)")
    parser.add_argument("--source_ik_rig_path", type=str, default=SOURCE_IK_RIG_PATH,
                         help="Source IK Rig asset path (default: smplx_IKRig)")
    parser.add_argument("--target_ik_rig_path", type=str, default=TARGET_IK_RIG_PATH,
                         help="Target IK Rig asset path (default: smplx_IKRig)")
    _args = parser.parse_args()

    _pool_dir = _args.pool_dir
    _csv_path_retargeting = _args.csv_path_retargeting
    _num_batches = _args.num_batches
    _processes = _args.processes

    print(f"Starting pool with {_processes} processes, batches: {_num_batches}\n", file=sys.stderr)
    pool = Pool(_processes)

    start_time = time.perf_counter()
    tasklist = []
    for _batch_index in range(_num_batches):
        tasklist.append((_pool_dir, _csv_path_retargeting, _batch_index, _num_batches,
                          _args.ik_retargeter_path, _args.source_ik_rig_path, _args.target_ik_rig_path))

    result = pool.map(worker_args, tasklist)

    print(f"Finished. Total batch conversion time: {(time.perf_counter() - start_time):.1f}s")
