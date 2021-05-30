from typing import Dict, Optional

from girder.constants import AccessType
from girder.exceptions import RestException
from girder.models.folder import Folder
from girder.models.setting import Setting
from girder.models.token import Token
from girder.models.user import User
from girder_jobs.models.job import Job

from dive_server.multicam import get_multicam_default_folder_id
from dive_server.training import ensure_csv_detections_file
from dive_server.utils import (
    detections_item,
    getCloneRoot,
    move_existing_result_to_auxiliary_folder,
)
from dive_tasks.tasks import EMPTY_JOB_SCHEMA
from dive_tasks.tasks import run_pipeline as async_run_pipeline
from dive_utils import TRUTHY_META_VALUES, asbool, fromMeta
from dive_utils.constants import (
    JOBCONST_DATASET_ID,
    JOBCONST_PIPELINE_NAME,
    JOBCONST_PRIVATE_QUEUE,
    JOBCONST_RESULTS_FOLDER_ID,
    SETTINGS_CONST_JOBS_CONFIGS,
    MultiType,
    StereoPipelineMarker,
    TrainedPipelineCategory,
    TrainedPipelineMarker,
    UserPrivateQueueEnabledMarker,
)
from dive_utils.types import (
    AvailableJobSchema,
    GirderModel,
    PipelineCategory,
    PipelineDescription,
    PipelineJob,
)


def _load_dynamic_pipelines(user: User) -> Dict[str, PipelineCategory]:
    """Add any additional dynamic pipelines to the existing pipeline list."""

    pipelines: Dict[str, PipelineCategory] = {}
    pipelines[TrainedPipelineCategory] = {"pipes": [], "description": ""}
    for folder in Folder().findWithPermissions(
        query={f"meta.{TrainedPipelineMarker}": {'$in': TRUTHY_META_VALUES}},
        user=user,
    ):
        pipename = None
        for item in Folder().childItems(folder):
            if item['name'].endswith('.pipe'):
                pipename = item['name']
        if pipename is not None:
            pipelines[TrainedPipelineCategory]["pipes"].append(
                {
                    "name": folder["name"],
                    "type": TrainedPipelineCategory,
                    "pipe": pipename,
                    "folderId": str(folder["_id"]),
                }
            )
    return pipelines


def load_pipelines(user: User) -> Dict[str, PipelineCategory]:
    """Load all static and dynamic pipelines"""
    static_job_configs: AvailableJobSchema = (
        Setting().get(SETTINGS_CONST_JOBS_CONFIGS) or EMPTY_JOB_SCHEMA
    )
    static_pipelines = static_job_configs.get('pipelines', {})
    dynamic_pipelines = _load_dynamic_pipelines(user)
    static_pipelines.update(dynamic_pipelines)
    return static_pipelines


def verify_pipe(user: User, pipeline: PipelineDescription):
    """Verify a pipeline exists and is runnable"""
    missing_exception = RestException(
        (
            f'No such pipeline exists for type={pipeline["type"]} pipe={pipeline["pipe"]}. '
            'A pipeline upgrade may be outstanding or somethiung might have gone wrong. '
            'If you think this is an error, contact the server operator.'
        )
    )
    all_pipelines = load_pipelines(user)
    try:
        category_pipes = all_pipelines[pipeline['type']]['pipes']
        matchs = [
            pipe
            for pipe in category_pipes
            if (
                pipe["pipe"] == pipeline["pipe"]
                and pipeline['type'] == pipe['type']
                and pipeline['folderId'] == pipe['folderId']
            )
        ]
        if len(matchs) != 1:
            raise missing_exception
    except KeyError:
        raise missing_exception


def run_pipeline(
    user: GirderModel,
    folder: GirderModel,
    pipeline: PipelineDescription,
    queue: str,
) -> GirderModel:
    """
    Run a pipeline on a dataset.

    :param folder: The girder folder containing the dataset to run on.
    :param pipeline: The pipeline to run the dataset on.
    """

    verify_pipe(user, pipeline)
    getCloneRoot(user, folder)

    folder_id_str = str(folder["_id"])
    # First, verify that no other outstanding jobs are running on this dataset
    existing_jobs = Job().findOne(
        {
            JOBCONST_DATASET_ID: folder_id_str,
            'status': {
                # Find jobs that are inactive, queued, or running
                # https://github.com/girder/girder/blob/main/plugins/jobs/girder_jobs/constants.py
                '$in': [0, 1, 2]
            },
        }
    )
    if existing_jobs is not None:
        raise RestException(
            (
                f"A pipeline for {folder_id_str} is already running. "
                "Only one outstanding job may be run at a time for "
                "a dataset."
            )
        )

    token = Token().createToken(user=user, days=14)

    requires_input = False  # include CSV input for pipe
    if pipeline["type"] == TrainedPipelineCategory:
        # Verify that the user has READ access to the pipe they want to run
        pipeFolder = Folder().load(
            pipeline["folderId"], level=AccessType.READ, user=user
        )
        requires_input = asbool(fromMeta(pipeFolder, "requires_input"))
    elif pipeline["pipe"].startswith('utility_'):
        # TODO Temporary inclusion of utility pipes which take csv input
        requires_input = True

    detection_csv: Optional[GirderModel] = None
    if requires_input:
        # Ensure detection has a csv detections item
        detection = detections_item(folder, strict=True)
        detection_csv = ensure_csv_detections_file(folder, detection, user)

    move_existing_result_to_auxiliary_folder(folder, user)
    job_is_private = user.get(UserPrivateQueueEnabledMarker, False)

    input_folder_id_str = folder_id_str
    input_folder = folder
    if folder['meta']['type'] == MultiType:
        if pipeline["type"] != StereoPipelineMarker:
            input_folder_id_str = get_multicam_default_folder_id(folder)
            # Lets get the base display folder instead of the all data
            input_folder = Folder().load(
                input_folder_id_str, level=AccessType.READ, user=user
            )

    params: PipelineJob = {
        "input_folder": input_folder_id_str,
        "input_type": fromMeta(input_folder, "type", required=True),
        "output_folder": folder_id_str,
        "pipeline": pipeline,
        "pipeline_input": detection_csv,
    }
    newjob = async_run_pipeline.apply_async(
        queue=queue,
        kwargs=dict(
            params=params,
            girder_job_title=f"Running {pipeline['name']} on {str(folder['name'])}",
            girder_client_token=str(token["_id"]),
            girder_job_type="private" if job_is_private else "pipelines",
        ),
    )
    newjob.job[JOBCONST_PRIVATE_QUEUE] = job_is_private
    newjob.job[JOBCONST_DATASET_ID] = folder_id_str
    newjob.job[JOBCONST_RESULTS_FOLDER_ID] = folder_id_str
    newjob.job[JOBCONST_PIPELINE_NAME] = pipeline['name']
    # Allow any users with accecss to the input data to also
    # see and possibly manage the job
    Job().copyAccessPolicies(folder, newjob.job)
    Job().save(newjob.job)
    return newjob.job
