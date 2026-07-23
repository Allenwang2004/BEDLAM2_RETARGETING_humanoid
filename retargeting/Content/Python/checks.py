# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
import glob
import os
import sys

if __name__ == '__main__':
    # Check if there are incomplete dirs in the animations dir and remove them.
    # Incomplete dirs are dirs with less than 2 files.
    root_dir_path = sys.argv[1]  # r"D:\UE_5.4\Engine\Content\BedlamRetarget\b2v2\animations"
    dir_paths = glob.glob(os.path.join(root_dir_path, "*"))
    incomplete_dirs = []
    # If a dir has less than 2 files, then it's incomplete
    for dir_path in dir_paths:
        if len(glob.glob(os.path.join(dir_path, "*"))) < 2:
            incomplete_dirs.append(dir_path)
    print(f"{len(incomplete_dirs)} out of {len(dir_paths)} dirs are incomplete.")
    # Remove those dirs
    for incomplete_dir in incomplete_dirs:
        # Force the deletion (bypass the dir is not empty WinError 145)
        os.system(f"rmdir /S /Q {incomplete_dir}")
    print("Done")
