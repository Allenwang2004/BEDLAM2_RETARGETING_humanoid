# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
import json

paths_json_file = "../../../paths.json"

def load_config(config_path):
    with open(config_path, "r") as f:
        config = json.load(f)
    return config

config = load_config(paths_json_file)

# need forward slashes "\" when calling via -ExecutePythonScript, for UNREAL_APP_PATH, UNREAL_PROJECT_PATH
PYTHON_SCRIPT_DIR = config['PYTHON_SCRIPT_DIR']
UNREAL_APP_PATH = config['UNREAL_APP_PATH']
UNREAL_PROJECT_PATH = config['UNREAL_PROJECT_PATH']
