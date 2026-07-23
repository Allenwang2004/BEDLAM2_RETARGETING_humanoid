# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
from importlib import *
import humans
import sys
# Reload modules (Unreal Engine does not reload modules automatically)
reload(humans)
from humans import HumanFactory

BATCH_SIZE = 100

if __name__ == '__main__':
    input_dir = sys.argv[1]
    pool_dir = sys.argv[2]
    animation_bool = bool(int(sys.argv[3]))
    max_humans = int(sys.argv[4])
    human_factory = HumanFactory(pool_dir)
    # Saves every BATCH_SIZE humans to avoid memory issues
    human_factory.import_humans_to_project(input_dir, max_humans, animation_bool, BATCH_SIZE)
