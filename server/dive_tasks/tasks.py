import json
import os
import shutil
import shlex
import tempfile
from pathlib import Path
from subprocess import DEVNULL, Popen, PIPE, TimeoutExpired
from typing import Dict, List, Tuple
from urllib import request
from urllib.parse import urlparse
import zipfile

from girder_client import GirderClient
from girder_worker.app import app
from girder_worker.task import Task
from girder_worker.utils import JobManager, JobStatus
from GPUtil import getGPUs

from dive_tasks.pipeline_discovery import discover_configs
from dive_tasks.utils import (
    get_video_filename,
    organize_folder_for_training,
    read_and_close_process_outputs,
)
from dive_utils.types import AvailableJobSchema, PipelineJob, UpgradeJob


EMPTY_JOB_SCHEMA: AvailableJobSchema = {
    'pipelines': {},
    'training': {
        'configs': [],
        'default': None,
    },
}
UPGRADE_JOB_DEFAULT: UpgradeJob = {
    'force': False,
    'urls': [
        'https://data.kitware.com/api/v1/item/6011e3452fa25629b91ade60/download',
        'https://viame.kitware.com/api/v1/item/60412dd253c5cf52641ffa1d/download',
        'https://data.kitware.com/api/v1/item/6011ebf72fa25629b91aef03/download',
        # 'https://data.kitware.com/api/v1/item/601b00d02fa25629b9391ad6/download',
    ],
}


def get_gpu_environment() -> Dict[str, str]:
    """Get environment variables for using CUDA enabled GPUs."""
    env = os.environ.copy()

    gpu_uuid = env.get("WORKER_GPU_UUID")
    gpus = [gpu.id for gpu in getGPUs() if gpu.uuid == gpu_uuid]

    # Only set this env var if WORKER_GPU_UUID was supplied,
    # and it matches an installed GPU
    if gpus:
        env["CUDA_VISIBLE_DEVICES"] = str(gpus[0])

    return env


class Config:
    def __init__(self):
        self.gpu_process_env = get_gpu_environment()
        self.viame_install_directory = os.environ.get(
            'VIAME_INSTALL_PATH',
            '/opt/noaa/viame',
        )
        self.addon_root_directory = os.environ.get(
            'ADDON_ROOT_DIR',
            '/tmp/addons',
        )

        self.viame_install_path = Path(self.viame_install_directory)
        assert self.viame_install_path.exists(), "VIAME Base install directory missing"

        # The subdirectory within VIAME_INSTALL_PATH where pipelines can be found
        self.pipeline_subdir = 'configs/pipelines'
        self.viame_pipeine_path = self.viame_install_path / self.pipeline_subdir
        assert self.viame_pipeine_path.exists(), "VIAME common pipe directory missing"

        self.addon_root_path = Path(self.addon_root_directory)
        self.addon_zip_path = self.addon_root_path / 'zips'
        self.addon_extracted_path = self.addon_root_path / 'extracted'

        self.addon_zip_path.mkdir(exist_ok=True, parents=True)
        self.addon_extracted_path.mkdir(exist_ok=True, parents=True)

    def get_extracted_pipeline_path(self, missing_ok=False) -> Path:
        """
        Includes subdirectory for pipelines
        """
        pipeline_path = self.addon_extracted_path / self.pipeline_subdir
        if not missing_ok:
            assert pipeline_path.exists(), f"Missing path {pipeline_path}"
        return pipeline_path


@app.task(bind=True, acks_late=True)
def upgrade_pipelines(self: Task, upgradeJob: UpgradeJob = UPGRADE_JOB_DEFAULT):
    """ Install addons from zip files over HTTP """
    conf = Config()
    manager: JobManager = self.job_manager
    total = len(upgradeJob['urls'])
    # zipfiles to extract after download is complete
    addons_to_update_update: List[Path] = []

    for idx, addon in enumerate(upgradeJob['urls']):
        download_name = urlparse(addon).path.replace('/', '_')
        zipfile_path = conf.addon_zip_path / f'{download_name}.zip'
        if not zipfile_path.exists() or upgradeJob['force']:
            # Update the zipfile if force option set or file not exists
            manager.write(f'Downloading {addon} to {zipfile_path}\n')
            # TODO wrap try catch
            request.urlretrieve(addon, filename=zipfile_path)
        else:
            manager.write(f'Skipping download of {zipfile_path}\n')
        addons_to_update_update.append(zipfile_path)
        if self.canceled:
            manager.updateStatus(JobStatus.CANCELED)
            return JobStatus.CANCELED

    # remove and recreate the existing addon pipeline directory
    shutil.rmtree(conf.addon_extracted_path)
    # copy over data from built image, which causes mkdir() for all parents
    shutil.copytree(
        conf.viame_pipeine_path, conf.get_extracted_pipeline_path(missing_ok=True)
    )
    # Extract zipfiles over newly copied files.  Right now the zip archives
    # MUST contain the pipeline subdir (e.g. configs/pipelines) in their
    # internal structure.
    for zipfile_path in addons_to_update_update:
        manager.write(
            f'Extracting {zipfile_path} to {str(conf.addon_extracted_path)}\n'
        )
        z = zipfile.ZipFile(zipfile_path)
        z.extractall(conf.addon_extracted_path)

    if self.canceled:
        # Remove everything
        shutil.rmtree(conf.addon_extracted_path)
        manager.updateStatus(JobStatus.CANCELED)
        self.girder_client.post('viame/update_job_configs', json=EMPTY_JOB_SCHEMA)
        return JobStatus.CANCELED

    # finally, crawl the new files and report results
    summary = discover_configs(conf.get_extracted_pipeline_path())
    self.girder_client.post('viame/update_job_configs', json=summary)


@app.task(bind=True, acks_late=True)
def run_pipeline(self: Task, params: PipelineJob):
    conf = Config()
    manager: JobManager = self.job_manager

    # Extract params
    pipeline = params["pipeline"]
    input_folder = params["input_folder"]
    input_type = params["input_type"]
    output_folder = params["output_folder"]

    # Create temporary files/folders, removed at the end of the function
    input_path = Path(tempfile.mkdtemp())
    trained_pipeline_folder = Path(tempfile.mkdtemp())
    detector_output_path = tempfile.NamedTemporaryFile(suffix=".csv", delete=False).name
    track_output_path = tempfile.NamedTemporaryFile(suffix=".csv", delete=False).name

    self.girder_client.downloadFolderRecursive(input_folder, input_path)

    if pipeline["type"] == "trained":
        self.girder_client.downloadFolderRecursive(
            pipeline["folderId"], str(trained_pipeline_folder)
        )
        pipeline_path = trained_pipeline_folder / pipeline["pipe"]
    else:
        pipeline_path = conf.get_extracted_pipeline_path() / pipeline["pipe"]

    if input_type == 'video':
        # filter files for source video file
        source_video = get_video_filename(input_folder, self.girder_client)
        # Preserving default behavior incase new stuff fails
        if source_video is None:
            raise Exception(
                'Error finding valid video file in folder: {}'.format(input_folder)
            )
        input_file = os.path.join(input_path, source_video)

        command = [
            f"cd {shlex.quote(str(conf.viame_install_path))} &&",
            ". ./setup_viame.sh &&",
            "kwiver runner",
            "-s input:video_reader:type=vidl_ffmpeg",
            f"-p {shlex.quote(str(pipeline_path))}",
            f"-s input:video_filename={shlex.quote(input_file)}",
            f"-s detector_writer:file_name={shlex.quote(detector_output_path)}",
            f"-s track_writer:file_name={shlex.quote(track_output_path)}",
        ]
    elif input_type == 'image-sequence':
        resp = self.girder_client.get(
            'viame/valid_images', params={'folderId': input_folder}
        )
        filtered_directory_files = [item['name'] for item in resp.json()]
        if len(filtered_directory_files) == 0:
            raise ValueError('No media files found in {}'.format(input_path))

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp2:
            temp2.writelines(
                (
                    (os.path.join(input_path, file_name) + "\n").encode()
                    for file_name in sorted(filtered_directory_files)
                )
            )
            image_list_file = temp2.name
        command = [
            f"cd {shlex.quote(str(conf.viame_install_path))} &&",
            ". ./setup_viame.sh &&",
            "kwiver runner",
            f"-p {shlex.quote(str(pipeline_path))}",
            f"-s input:video_filename={shlex.quote(image_list_file)}",
            f"-s detector_writer:file_name={shlex.quote(detector_output_path)}",
            f"-s track_writer:file_name={shlex.quote(track_output_path)}",
        ]
    else:
        raise ValueError('Unknown input type: {}'.format(input_type))

    cmd = " ".join(command)
    print('Running command:', cmd)

    process_log_file = tempfile.TemporaryFile()
    process_err_file = tempfile.TemporaryFile()

    process = Popen(
        cmd,
        stderr=process_err_file,
        stdout=process_log_file,
        shell=True,
        executable='/bin/bash',
        env=conf.gpu_process_env,
    )

    stdout, stderr = read_and_close_process_outputs(
        process, self, process_log_file, process_err_file
    )
    if self.canceled:
        manager.updateStatus(JobStatus.CANCELED)
        return

    if process.returncode > 0:
        raise RuntimeError(
            'Pipeline exited with nonzero status code {}: {}'.format(
                process.returncode, stderr
            )
        )
    else:
        manager.write(stdout + "\n" + stderr)

    if os.path.getsize(track_output_path) > 0:
        output_path = track_output_path
    else:
        output_path = detector_output_path
    manager.updateStatus(JobStatus.PUSHING_OUTPUT)
    newfile = self.girder_client.uploadFileToFolder(output_folder, output_path)

    self.girder_client.addMetadataToItem(newfile["itemId"], {"pipeline": pipeline})
    self.girder_client.post(
        f'viame/postprocess/{output_folder}', data={"skipJobs": True}
    )

    # Files
    os.remove(track_output_path)
    os.remove(detector_output_path)

    # Folders
    shutil.rmtree(input_path, ignore_errors=True)
    shutil.rmtree(trained_pipeline_folder, ignore_errors=True)

    if self.canceled:
        manager.updateStatus(JobStatus.CANCELED)
        return


@app.task(bind=True, acks_late=True)
def train_pipeline(
    self: Task,
    results_folder: Dict,
    source_folder_list: List[Dict],
    groundtruth_list: List[Dict],
    pipeline_name: str,
    config: str,
):
    """
    Train a pipeline by making a call to viame_train_detector

    :param source_folder_list: The Girder Folders to pull training data from
    :param results_folder: The Girder Folder to place the results of training into
    :param groundtruth_list: A list of relative paths to either a file containing detections,
        or a folder containing that file.
    :param pipeline_name: The base name of the resulting pipeline.
    """
    conf = Config()
    gc: GirderClient = self.girder_client
    manager: JobManager = self.job_manager

    viame_install_path = Path(conf.viame_install_path)
    pipeline_base_path = Path(conf.get_extracted_pipeline_path())
    training_executable = viame_install_path / "bin" / "viame_train_detector"
    config_file = pipeline_base_path / config

    pipeline_name = pipeline_name.replace(" ", "_")

    if len(source_folder_list) != len(groundtruth_list):
        raise Exception("Ground truth doesn't exist for all folders")

    # List of folderIds used for training
    trained_on_list: List[str] = []
    # List of[input folder / ground truth file] pairs for creating input lists
    input_groundtruth_list: List[Tuple[Path, Path]] = []
    # root_data_dir is the directory passed to `viame_train_detector`
    with tempfile.TemporaryDirectory() as _temp_dir_string:
        manager.updateStatus(JobStatus.FETCHING_INPUT)
        root_data_dir = Path(_temp_dir_string)

        for index in range(len(source_folder_list)):
            source_folder = source_folder_list[index]
            groundtruth = groundtruth_list[index]
            download_path = Path(tempfile.mkdtemp(dir=root_data_dir))
            trained_on_list.append(str(source_folder["_id"]))

            # Generator of items
            training_data = gc.listItem(source_folder["_id"])

            # Download data onto server
            gc.downloadItem(str(groundtruth["_id"]), download_path)
            for item in training_data:
                gc.downloadItem(str(item["_id"]), download_path)

            # Organize data
            groundtruth_path = download_path / groundtruth["name"]
            groundtruth_file = organize_folder_for_training(
                root_data_dir, download_path, groundtruth_path
            )
            # We point to file if is a video
            if source_folder.get("meta", {}).get("type") == "video":
                video_file = get_video_filename(source_folder["_id"], gc)
                if video_file is None:
                    raise Exception(
                        'Error finding valid video file in folder: {}'.format(
                            source_folder["_id"]
                        )
                    )
                download_path = download_path / video_file

            input_groundtruth_list.append((download_path, groundtruth_file))

        input_folder_file_list = root_data_dir / "input_folder_list.txt"
        ground_truth_file_list = root_data_dir / "input_truth_list.txt"
        with open(input_folder_file_list, "w+") as data_list:
            folder_paths = [f"{item[0]}\n" for item in input_groundtruth_list]
            data_list.writelines(folder_paths)
        with open(ground_truth_file_list, "w+") as truth_list:
            truth_paths = [f"{item[1]}\n" for item in input_groundtruth_list]
            truth_list.writelines(truth_paths)

        # Completely separate directory from `root_data_dir`
        with tempfile.TemporaryDirectory() as _training_output_path:
            training_output_path = Path(_training_output_path)
            command = [
                f". {conf.viame_install_path}/setup_viame.sh &&",
                str(training_executable),
                "-il",
                str(input_folder_file_list),
                "-it",
                str(ground_truth_file_list),
                "-c",
                str(config_file),
                "--no-query",
            ]

            process_log_file = tempfile.TemporaryFile()
            process_err_file = tempfile.TemporaryFile()
            manager.updateStatus(JobStatus.RUNNING)
            cmd = " ".join(command)
            print('Running command:', cmd)
            # Call viame_train_detector
            process = Popen(
                " ".join(command),
                stdout=process_log_file,
                stderr=process_err_file,
                shell=True,
                executable='/bin/bash',
                cwd=training_output_path,
                env=conf.gpu_process_env,
            )

            stdout, stderr = read_and_close_process_outputs(
                process, self, process_log_file, process_err_file
            )
            manager.write(stdout + "\n" + stderr)
            if self.canceled:
                manager.updateStatus(JobStatus.CANCELED)
                return
            training_results_path = training_output_path / "category_models"

            # Get all files/folders in directory
            training_output = list(training_results_path.glob("*"))
            if process.returncode or not training_output:
                raise RuntimeError(
                    "Training output failed or didn't produce results, discarding..."
                )
            else:
                manager.updateStatus(JobStatus.PUSHING_OUTPUT)

            # This is the name of the folder that is uploaded to the
            # "Training Results" girder folder
            girder_output_folder = gc.createFolder(
                results_folder["_id"],
                pipeline_name,
                metadata={
                    "trained_pipeline": True,
                    "trained_on": trained_on_list,
                },
            )

            gc.upload(f"{training_results_path}/*", girder_output_folder["_id"])

    if self.canceled:
        manager.updateStatus(JobStatus.CANCELED)
        return


@app.task(bind=True, acks_late=True)
def convert_video(self: Task, path, folderId, auxiliaryFolderId, itemId):
    # Delete is true, so the tempfile is deleted when the block closes.
    # We are only using this to get a name, and recreating it below.
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=True) as temp:
        output_path = temp.name

    gc: GirderClient = self.girder_client
    manager: JobManager = self.job_manager

    # Extract metadata
    file_name = os.path.join(path, os.listdir(path)[0])
    command = [
        "ffprobe",
        "-print_format",
        "json",
        "-v",
        "quiet",
        "-show_format",
        "-show_streams",
        file_name,
    ]

    with tempfile.TemporaryFile() as process_log_file:
        process = Popen(command, stderr=DEVNULL, stdout=process_log_file)
        stdout, stderr = read_and_close_process_outputs(process, self, process_log_file)
        if self.canceled:
            manager.updateStatus(JobStatus.CANCELED)
            return
        if process.returncode > 0:
            raise RuntimeError(
                'could not execute ffprobe {}: {}'.format(process.returncode, stderr)
            )

        jsoninfo = json.loads(stdout)
        videostream = list(
            filter(lambda x: x["codec_type"] == "video", jsoninfo["streams"])
        )
        if len(videostream) != 1:
            raise Exception(
                'Expected 1 video stream, found {}'.format(len(videostream))
            )

    process_log_file = tempfile.TemporaryFile()
    process_err_file = tempfile.TemporaryFile()
    process = Popen(
        [
            "ffmpeg",
            "-i",
            file_name,
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "26",
            "-c:a",
            "copy",
            # see native/<platform> code for a discussion of this option
            "-vf",
            "scale=ceil(iw*sar/2)*2:ceil(ih/2)*2,setsar=1",
            output_path,
        ],
        stdout=process_log_file,
        stderr=process_err_file,
    )

    stdout, stderr = read_and_close_process_outputs(
        process, self, process_log_file, process_err_file
    )

    output = stdout + "\n" + stderr
    manager.write(output)
    if self.canceled:
        manager.updateStatus(JobStatus.CANCELED)
        return
    if process.returncode == 0:
        manager.updateStatus(JobStatus.PUSHING_OUTPUT)
        new_file = gc.uploadFileToFolder(folderId, output_path)
        gc.addMetadataToItem(
            new_file['itemId'],
            {
                "source_video": False,
                "transcoder": "ffmpeg",
                "codec": "h264",
            },
        )
        gc.addMetadataToItem(
            itemId,
            {
                "source_video": True,
                "codec": videostream[0]["codec_name"],
            },
        )
        gc.addMetadataToFolder(
            folderId,
            {
                "fps": 5,  # TODO: current time system doesn't allow for non-int framerates
                "annotate": True,  # mark the parent folder as able to annotate.
                "ffprobe_info": videostream[0],
            },
        )

    os.remove(output_path)

    if self.canceled:
        manager.updateStatus(JobStatus.CANCELED)
        return


@app.task(bind=True, acks_late=True)
def convert_images(self: Task, folderId):
    """
    Ensures that all images in a folder are in a web friendly format (png or jpeg).

    If conversions succeeds for an image, it will replace the image with an image
    of the same name, but in a web friendly extension.

    Returns the number of images successfully converted.
    """
    gc: GirderClient = self.girder_client
    manager: JobManager = self.job_manager

    items = gc.listItem(folderId)
    skip_item = (
        lambda item: item["name"].endswith(".png")
        or item["name"].endswith(".jpeg")
        or item["name"].endswith(".jpg")
    )
    items_to_convert = [item for item in items if not skip_item(item)]

    count = 0
    with tempfile.TemporaryDirectory() as temp:
        dest_dir = Path(temp)

        for item in items_to_convert:
            # Assumes 1 file per item
            gc.downloadItem(item["_id"], dest_dir, item["name"])

            item_path = dest_dir / item["name"]
            new_item_path = dest_dir / ".".join([*item["name"].split(".")[:-1], "png"])

            process_log_file = tempfile.TemporaryFile()
            process_err_file = tempfile.TemporaryFile()
            process = Popen(
                ["ffmpeg", "-i", item_path, new_item_path],
                stdout=process_log_file,
                stderr=process_err_file,
            )

            stdout, stderr = read_and_close_process_outputs(
                process, self, process_log_file, process_err_file
            )

            if self.canceled:
                manager.updateStatus(JobStatus.CANCELED)
                return

            output = ""
            if len(stdout):
                output = f"{stdout}\n"
            if len(stderr):
                output = f"{output}{stderr}\n"

            manager.write(output)

            if process.returncode == 0:
                gc.uploadFileToFolder(folderId, new_item_path)
                gc.delete(f"item/{item['_id']}")
                count += 1

    gc.addMetadataToFolder(
        str(folderId),
        {"annotate": True},  # mark the parent folder as able to annotate.
    )

    if self.canceled:
        manager.updateStatus(JobStatus.CANCELED)
        return
    return count
