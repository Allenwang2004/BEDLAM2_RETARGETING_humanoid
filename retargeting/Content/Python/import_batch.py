# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
from multiprocessing import Pool
import subprocess
import sys
import time
import argparse
import os
from handle_paths import UNREAL_APP_PATH, UNREAL_PROJECT_PATH, PYTHON_SCRIPT_DIR

def convert_backslashes_to_forwardslashes(path):
    return path.replace('\\', '/').replace('//', '/')


# Globals
IMPORT_SCRIPT_PATH = os.path.join(PYTHON_SCRIPT_DIR, "import_humans_worker.py")
GUI_OFF = True


def worker(input_dir, output_dir, animation_flag, batch_index, num_batches):
    if GUI_OFF:
        cmd_off = (f"\"{UNREAL_APP_PATH}\" \"{UNREAL_PROJECT_PATH}\" "
                   f"-run=pythonscript -script=\"{IMPORT_SCRIPT_PATH} "
                   f"{input_dir} {output_dir} {animation_flag} {batch_index} {num_batches}\"")
        print(f"Executing command: {cmd_off}", file=sys.stderr)
        subprocess.run(cmd_off, shell=True)
    else:
        cmd_off = (f"\"{UNREAL_APP_PATH}\" \"{UNREAL_PROJECT_PATH}\" "
                   f"-stdout -FullStdOutLogOutput -ExecutePythonScript=\"{IMPORT_SCRIPT_PATH} "
                   f"{input_dir} {output_dir} {animation_flag} {batch_index} {num_batches}\"")
        print(f"Executing command: {cmd_off}", file=sys.stderr)
        subprocess.run(cmd_off, shell=True)

    return True


def worker_args(args):
    return worker(*args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch import FBX files to Unreal Engine project")
    parser.add_argument("--input_dir", type=str, required=True, help="Directory containing FBX files to import")
    parser.add_argument("--output_dir", type=str, required=True, help="output dir, e.g. /Engine/BedlamRetarget/test or /Game/BedlamRetarget/test")
    parser.add_argument("--animation", help="Import as animations (default: False)", action="store_true")
    parser.add_argument("--num_batches", type=int, help="Number of batches to split the import into")
    parser.add_argument("--processes", type=int, help="Number of processes to use for parallel import")
    _args = parser.parse_args()

    # input_dir =  r"D:\UE_5.4\Engine\Content\BedlamRetarget\b2v3\4_motion_retargeting"
    print(f"Starting pool with {_args.processes} processes, batches: {_args.num_batches}\n", file=sys.stderr)
    pool = Pool(_args.processes)

    start_time = time.perf_counter()
    tasklist = []
    for _batch_index in range(_args.num_batches):
        anim_flag = 1 if _args.animation else 0
        _input_dir = convert_backslashes_to_forwardslashes(_args.input_dir)
        tasklist.append((_input_dir, _args.output_dir, anim_flag, _batch_index, _args.num_batches))

    result = pool.map(worker_args, tasklist)

    print(f"Finished. Total batch conversion time: {(time.perf_counter() - start_time):.1f}s")
