import shutil
import signal
from datetime import datetime, timedelta
from pathlib import Path
from subprocess import Popen
from tempfile import mktemp
from typing import IO, Callable, List, Optional, Tuple

from girder_client import GirderClient
from girder_worker.task import Task
from girder_worker.utils import JobManager, JobStatus

from dive_utils import fromMeta
from dive_utils.constants import (
    CalibrationMarker,
    ImageSequenceType,
    MultiCamMarker,
    MultiType,
    TypeMarker,
    VideoType,
)
from dive_utils.types import GirderModel

TIMEOUT_COUNT = 'timeout_count'
TIMEOUT_LAST_CHECKED = 'last_checked'
TIMEOUT_CHECK_INTERVAL = 30


def check_canceled(task: Task, context: dict, force=True):
    """
    Only check for canceled task every interval unless force is true (default).
    This is an expensive operation that round-trips to the message broker.
    """
    if not context.get(TIMEOUT_COUNT):
        context[TIMEOUT_COUNT] = 0
    now = datetime.now()
    if (
        (now - context.get(TIMEOUT_LAST_CHECKED, now))
        > timedelta(seconds=TIMEOUT_CHECK_INTERVAL)
    ) or force:
        context[TIMEOUT_LAST_CHECKED] = now
        try:
            return task.canceled
        except (TimeoutError, ConnectionError) as err:
            context[TIMEOUT_COUNT] += 1
            print(
                f"Timeout N={context[TIMEOUT_COUNT]} for this task when checking for cancellation. {err}"
            )
    return False


def stream_subprocess(
    process: Popen,
    task: Task,
    context: dict,
    manager: JobManager,
    stderr_file: IO[bytes],
    keep_stdout: bool = False,
    cleanup: Optional[Callable] = None,
) -> str:
    """
    Stream live results from process to job manager

    :param process: Process to stream
    :param task: task to detect cancelation
    :param manager: job manager
    :param stderr_file: will log stderr to manager IF nonzero exit, else will close
    :param keep_stdout: will return stdout as a string if needed
    :param cleanup: a function to invoke if job errors or is canceled
    """
    start_time = datetime.now()
    stdout = ""

    if process.stdout is None:
        raise RuntimeError("Stdout must not be none")

    # call readline until it returns empty bytes
    for line in iter(process.stdout.readline, b''):
        line_str = line.decode('utf-8')
        manager.write(line_str)
        if keep_stdout:
            stdout += line_str

        if check_canceled(task, context, force=False):
            # Can never be sure what signal a process will respond to.
            process.send_signal(signal.SIGTERM)
            process.send_signal(signal.SIGKILL)

    # flush logs
    manager._flush()
    # Wait for exit up to 30 seconds after kill
    code = process.wait(30)

    if check_canceled(task, context):
        manager.write('\nCanceled during subprocess run.\n')
        manager.updateStatus(JobStatus.CANCELED)
        stderr_file.close()
        if cleanup:
            cleanup()
        return stdout

    if code > 0:
        stderr_file.seek(0)
        stderr = stderr_file.read().decode()
        stderr_file.close()
        if cleanup:
            cleanup()
        raise RuntimeError(
            'Pipeline exited with nonzero status code {}: {}'.format(
                process.returncode, stderr
            )
        )
    else:
        end_time = datetime.now()
        manager.write(f"\nProcess completed in {str((end_time - start_time))}\n")

    stderr_file.close()

    return stdout


def organize_folder_for_training(data_dir: Path, downloaded_groundtruth: Path):
    """
    Organize directory downloaded from girder into a structure compatible with Viame.

    Relevant documentation:
    https://viame.readthedocs.io/en/latest/section_links/object_detector_training.html
    """

    if downloaded_groundtruth.is_dir():
        files = list(downloaded_groundtruth.glob("*.csv"))

        if not files:
            raise Exception("No csv groundtruth files found.")

        groundtruth_file = files[0]
        temp_file = downloaded_groundtruth.parent / mktemp()

        # Replace directory with file of same name
        shutil.copyfile(groundtruth_file, temp_file)
        shutil.rmtree(downloaded_groundtruth)
        shutil.move(str(temp_file), downloaded_groundtruth)

    groundtruth = data_dir / "groundtruth.csv"
    shutil.move(str(downloaded_groundtruth), groundtruth)

    return groundtruth


def download_source_media(
    girder_client: GirderClient, folder: GirderModel, dest: Path
) -> List[str]:
    """
    Download source media for folder from girder
    """
    if fromMeta(folder, TypeMarker) == ImageSequenceType:
        image_items = girder_client.get(
            'viame/valid_images', {'folderId': folder["_id"]}
        )
        for item in image_items:
            girder_client.downloadItem(str(item["_id"]), str(dest))
        return [str(dest / item['name']) for item in image_items]
    elif fromMeta(folder, TypeMarker) == VideoType:
        clip_meta = girder_client.get(
            "viame_detection/clip_meta", {'folderId': folder['_id']}
        )
        destination_path = str(dest / clip_meta['video']['name'])
        girder_client.downloadFile(str(clip_meta['video']['_id']), destination_path)
        return [destination_path]
    elif fromMeta(folder, TypeMarker) == MultiType:
        cameras = fromMeta(folder, MultiCamMarker)['cameras']
        downloads = []
        for key in cameras.keys():
            camera = cameras[key]
            camera_folder = Path(dest / key)
            camera_folder.mkdir()
            baseId = camera['originalBaseId']
            destination_path = str(dest / key)
            if camera['type'] == ImageSequenceType:
                image_items = girder_client.get(
                    'viame/valid_images', {'folderId': baseId}
                )
                for item in image_items:
                    girder_client.downloadItem(str(item["_id"]), str(destination_path))
                    downloads.append(str(camera_folder / item['name']))
            elif camera['type'] == VideoType:
                clip_meta = girder_client.get(
                    "viame_detection/clip_meta", {'folderId': baseId}
                )
                destination_path = str(camera_folder / clip_meta['video']['name'])
                girder_client.downloadFile(
                    str(clip_meta['video']['_id']), destination_path
                )
                downloads.append(destination_path)
        # Multicamera calibration matrix addition
        calibration_id = fromMeta(folder, MultiCamMarker)[CalibrationMarker]
        if calibration_id is not None:
            calibration_data = girder_client.get(f'item/{calibration_id}')
            if calibration_data is not None:
                girder_client.downloadItem(calibration_id, str(dest))
                downloads.append(str(dest / calibration_data['name']))

        return downloads
    else:
        raise Exception(f"unexpected folder {str(folder)}")


def write_multiCam_pipeline_args(
    base_path: Path, input_media_list: List[str], input_folder: GirderModel
) -> Tuple[dict, dict]:
    multicam_meta = fromMeta(input_folder, MultiCamMarker)
    cameras = multicam_meta['cameras']
    counter = 0
    arg_pair = {}
    out_files = {}
    # media_list contains a sub folder for each item which needs to be written out
    for key in cameras.keys():
        camera = cameras[key]
        input_arg = (
            f'input{counter + 1}:video_filename'  # lock for the stereo pipeline as well
        )

        output_filename = f'computed_tracks_{key}.csv'
        output_filename = str(base_path / output_filename)
        output_arg = f"detector_writer{counter +1}:file_name"
        arg_pair[output_arg] = output_filename
        out_files[key] = output_filename
        if camera['type'] == ImageSequenceType:
            file_name = f'{str(base_path)}/input{counter + 1}_images.txt'  # This is locked in the pipeline for now
            with open(file_name, "w+") as img_list_file:
                for item in input_media_list:
                    if f'/{key}/' in item:
                        img_list_file.write(f'{item}\n')
            arg_pair[input_arg] = file_name
        elif camera['type'] == VideoType:
            # Each video file should be in a folder which has the camera name
            for media_file in input_media_list:
                path = Path(media_file)
                if key == str(path.parent).replace(f'{str(base_path)}/', ''):
                    vid_type_arg = f'input{counter +1}:video_reader_type'
                    vid_type = 'vidl_ffmpeg'
                    arg_pair[vid_type_arg] = vid_type
                    arg_pair[input_arg] = media_file
        # Now we filter and write the image files
        counter = counter + 1

    return arg_pair, out_files


def get_multiCam_calibration_arg(
    girder_client: GirderClient, image_media_list: List[str], input_folder: GirderModel
):
    multicam_meta = fromMeta(input_folder, MultiCamMarker)
    if multicam_meta[CalibrationMarker] is not None:
        calibration_id = multicam_meta[CalibrationMarker]
        calibration_data = girder_client.get(f'item/{calibration_id}')
        print(calibration_data)
        if calibration_data is not None:
            calibration_name = calibration_data['name']
            print(f'Calibration Name: {calibration_name}')
            for item in image_media_list:
                if calibration_name in item:
                    return f'-s measurer:calibration_file="{item}"'
    return ''
