# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
import math
import unreal
from pathlib import Path
import os


class Human:
    def __init__(self, asset_path: str):
        self.asset_path = asset_path


class HumanFactory:
    def __init__(self, pool_dir: str):
        self.pool_dir = pool_dir

    @staticmethod
    def _get_assets_by_human_from_input_dir(fbx_dir, max_num: int = 100000) -> list:
        human_assets = []
        # Find fbx files
        detected_fbx_paths = list(Path(fbx_dir).glob("*.fbx"))
        for i, fbx_path in enumerate(detected_fbx_paths):
            human_assets.append(str(fbx_path))
            # Stop if max_num_humans is reached
            if i >= max_num - 1:
                break
        return human_assets

    @staticmethod
    def fbx_options(animation_bool=False):
        options = unreal.FbxImportUI()
        options.import_mesh = True
        options.import_textures = True
        options.import_materials = False
        options.import_as_skeletal = True
        options.import_animations = animation_bool
        # Physics asset can be shared by all humans
        options.create_physics_asset = False
        return options

    def import_assets(self, filepaths, animation_bool=False):
        new_dirs = []
        tasks = unreal.Array(unreal.AssetImportTask)

        for p in filepaths:
            human_name = os.path.basename(p).split(".")[0]

            if animation_bool:
                relative_game_path = f"{self.pool_dir}/animations/{human_name}"
            else:
                relative_game_path = f"{self.pool_dir}/bodies/{human_name}"

            if unreal.EditorAssetLibrary.does_directory_exist(relative_game_path):
                unreal.log(f"Human (directory) {relative_game_path} already exists. Skipping.")
                continue

            # Create directory if it does not exist
            if not unreal.EditorAssetLibrary.does_directory_exist(relative_game_path):
                unreal.EditorAssetLibrary.make_directory(relative_game_path)

            task = unreal.AssetImportTask()
            task.automated = True
            task.destination_path = relative_game_path
            task.destination_name = f"{human_name}"
            task.filename = p
            task.save = False
            task.replace_existing = False
            task.options = self.fbx_options(animation_bool)
            tasks.append(task)
            new_dirs.append(relative_game_path)

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
        return new_dirs

    def import_humans_to_project(self, input_dir, max_num=5, animation_bool=False, batch_size=1000):
        # Method called by import_humans.py (via Blueprint)
        unreal.log("Start importing assets to project...")
        all_fbx_paths = self._get_assets_by_human_from_input_dir(input_dir, max_num)

        # Split the fbx_paths into batches of batch_size
        for i in range(0, len(all_fbx_paths), batch_size):
            batch_fbx_paths = all_fbx_paths[i:i + batch_size]
            # Import the assets from the current batch with the specified animation settings
            self.import_assets(batch_fbx_paths, animation_bool=animation_bool)
            # Save all assets that have been modified but not yet saved
            unreal.EditorLoadingAndSavingUtils.save_dirty_packages(save_map_packages=True, save_content_packages=True)

        unreal.log("Finished importing assets to project.")

    def import_humans_to_project_worker(self, input_dir, animation_bool, current_batch, num_batches):
        # Method called by import_humans_worker.py (via import_batch.py)
        import_fbx_paths = self._get_assets_by_human_from_input_dir(input_dir)
        section_length = math.ceil(len(import_fbx_paths) / num_batches)
        start_index = current_batch * section_length
        end_index = start_index + section_length
        if end_index > len(import_fbx_paths):
            end_index = len(import_fbx_paths)
        print(
            f"Processing section: {current_batch}, total sections: {num_batches}, range: [{start_index}:{end_index}]")
        import_fbx_paths = import_fbx_paths[start_index: end_index]
        self.import_assets(import_fbx_paths, animation_bool=animation_bool)
        # Important: Save all assets that have been modified but not yet saved
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(save_map_packages=True, save_content_packages=True)
