from typing import List, Optional
import xml

import pymongo
from girder.api import access
from girder.api.describe import Description, autoDescribeRoute, describeRoute
from girder.api.rest import Resource
from girder.constants import AccessType
from girder.exceptions import GirderException, RestException
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.setting import Setting
from girder.models.token import Token
from girder.models.user import User
from girder_jobs.models.job import Job

from dive_tasks.tasks import (
    UPGRADE_JOB_DEFAULT_URLS,
    convert_images,
    convert_video,
    run_pipeline,
    train_pipeline,
    upgrade_pipelines,
)
from dive_utils import TRUTHY_META_VALUES, asbool, fromMeta, models
from dive_utils.constants import (
    SETTINGS_CONST_JOBS_CONFIGS,
    DatasetMarker,
    ForeignMediaIdMarker,
    PublishedMarker,
    TrainedPipelineCategory,
    csvRegex,
    xmlRegex,
    imageRegex,
    safeImageRegex,
    videoRegex,
    ymlRegex,
)
from dive_utils.types import (
    AvailableJobSchema,
    GirderModel,
    PipelineDescription,
    PipelineJob,
)

from .pipelines import load_pipelines, verify_pipe
from .serializers import meva as meva_serializer
from .training import ensure_csv_detections_file, training_output_folder
from .transforms import GetPathFromItemId
from .utils import (
    createSoftClone,
    detections_item,
    get_or_create_auxiliary_folder,
    getCloneRoot,
    getTrackAndAttributesFromCSV,
    getTrackAndAttributesFromXML,
    move_existing_result_to_auxiliary_folder,
    saveCSVImportAttributes,
    saveTracks,
    verify_dataset,
)

JOBCONST_DATASET_ID = 'datset_id'
JOBCONST_TRAINING_INPUT_IDS = 'training_input_ids'
JOBCONST_TRAINING_CONFIG = 'training_config'
JOBCONST_RESULTS_FOLDER_ID = 'results_folder_id'
JOBCONST_PIPELINE_NAME = 'pipeline_name'


class Viame(Resource):
    def __init__(self):
        super(Viame, self).__init__()
        self.resourceName = "viame"

        self.route("GET", ("datasets",), self.list_datasets)
        self.route("POST", ("dataset", ":id", "clone"), self.clone_dataset)
        self.route("GET", ("brand_data",), self.get_brand_data)
        self.route("GET", ("pipelines",), self.get_pipelines)
        self.route("GET", ("training_configs",), self.get_training_configs)
        self.route("POST", ("pipeline",), self.run_pipeline_task)
        self.route("POST", ("train",), self.run_training)
        self.route("POST", ("upgrade_pipelines",), self.upgrade_pipelines)
        self.route("POST", ("update_job_configs",), self.update_job_configs)
        self.route("POST", ("postprocess", ":id"), self.postprocess)
        self.route("PUT", ("metadata", ":id"), self.update_metadata)
        self.route("PUT", ("attributes",), self.save_attributes)
        self.route("POST", ("validate_files",), self.validate_files)
        self.route("GET", ("valid_images",), self.get_valid_images)

    @access.admin
    @autoDescribeRoute(
        Description("Upgrade addon pipelines")
        .param(
            "force",
            "Force re-download of all addons.",
            paramType="query",
            dataType="boolean",
            default=False,
            required=False,
        )
        .jsonParam(
            "urls",
            "List of public URLs for addon zipfiles",
            paramType='body',
            requireArray=True,
            required=False,
            default=UPGRADE_JOB_DEFAULT_URLS,
        )
    )
    def upgrade_pipelines(self, force: bool, urls: List[str]):
        token = Token().createToken(user=self.getCurrentUser(), days=1)
        Setting().set(SETTINGS_CONST_JOBS_CONFIGS, None)
        upgrade_pipelines.delay(
            urls=urls,
            force=force,
            girder_job_title="Upgrade Pipelines",
            girder_client_token=str(token["_id"]),
        )

    @access.admin
    @autoDescribeRoute(
        Description("Persist discovered job configurations").jsonParam(
            "configs",
            "Replace static job configurations",
            required=True,
            requireObject=True,
            paramType='body',
        )
    )
    def update_job_configs(self, configs: AvailableJobSchema):
        Setting().set(SETTINGS_CONST_JOBS_CONFIGS, configs)

    @access.public
    @autoDescribeRoute(Description("Get custom brand data"))
    def get_brand_data(self):
        adminUserIds = [user['_id'] for user in User().getAdmins()]
        # Find an item owned by an admin with meta.brand=True
        data = Item().findOne(
            {
                'meta.brand': {'$in': TRUTHY_META_VALUES},
                'creatorId': {'$in': adminUserIds},
            }
        )
        if data is not None:
            return data['meta']
        return {}

    @access.user
    @describeRoute(
        Description("List datasets in the system")
        .pagingParams("created")
        .param(
            PublishedMarker,
            'Return only published datasets',
            required=False,
            default=False,
            dataType='boolean',
        )
    )
    def list_datasets(self, params):
        limit, offset, sort = self.getPagingParameters(params)
        query = {
            f'meta.{DatasetMarker}': {'$in': TRUTHY_META_VALUES},
        }
        if self.boolParam(PublishedMarker, params):
            query = {
                '$and': [
                    query,
                    {f'meta.{PublishedMarker}': {'$in': TRUTHY_META_VALUES}},
                ]
            }
        return Folder().findWithPermissions(
            query, offset=offset, limit=limit, sort=sort, user=self.getCurrentUser()
        )

    @access.user
    @autoDescribeRoute(
        Description("Clone a dataset")
        .modelParam(
            "id",
            description="Dataset clone source",
            model=Folder,
            level=AccessType.READ,
        )
        .modelParam(
            "parentFolderId",
            description="Parent folder of the clone",
            paramType="formData",
            destName="parentFolder",
            model=Folder,
            level=AccessType.WRITE,
        )
        .param(
            "name",
            "Name for new dataset",
            paramType="formData",
            dataType="string",
            default=None,
            required=False,
        )
    )
    def clone_dataset(self, folder, parentFolder, name):
        verify_dataset(folder)
        owner = self.getCurrentUser()
        return createSoftClone(owner, folder, parentFolder, name)

    @access.user
    @describeRoute(Description("Get available pipeline configurations"))
    def get_pipelines(self, params):
        return load_pipelines(self.getCurrentUser())

    @access.user
    @autoDescribeRoute(Description("Get available training configs"))
    def get_training_configs(self, params):
        static_job_configs: AvailableJobSchema = (
            Setting().get(SETTINGS_CONST_JOBS_CONFIGS) or {}
        )
        return static_job_configs.get('training', {})

    @access.user
    @autoDescribeRoute(
        Description("Run viame pipeline")
        .modelParam(
            "folderId",
            description="Folder id of a video clip",
            model=Folder,
            paramType="query",
            required=True,
            level=AccessType.WRITE,
        )
        .jsonParam("pipeline", "The pipeline to run on the dataset", required=True)
    )
    def run_pipeline_task(self, folder, pipeline: PipelineDescription):
        """
        Run a pipeline on a dataset.

        :param folder: The girder folder containing the dataset to run on.
        :param pipeline: The pipeline to run the dataset on.
        """
        user = self.getCurrentUser()
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

        params: PipelineJob = {
            "input_folder": folder_id_str,
            "input_type": fromMeta(folder, "type", required=True),
            "output_folder": folder_id_str,
            "pipeline": pipeline,
            "pipeline_input": detection_csv,
        }
        newjob = run_pipeline.apply_async(
            queue="pipelines",
            kwargs=dict(
                params=params,
                girder_job_title=f"Running {pipeline['name']} on {str(folder['name'])}",
                girder_client_token=str(token["_id"]),
                girder_job_type="pipelines",
            ),
        )
        newjob.job[JOBCONST_DATASET_ID] = folder_id_str
        newjob.job[JOBCONST_RESULTS_FOLDER_ID] = folder_id_str
        newjob.job[JOBCONST_PIPELINE_NAME] = pipeline['name']
        # Allow any users with accecss to the input data to also
        # see and possibly manage the job
        Job().copyAccessPolicies(folder, newjob.job)
        Job().save(newjob.job)
        return newjob.job

    @access.user
    @autoDescribeRoute(
        Description("Run training on a folder")
        .jsonParam(
            "folderIds",
            description="Array of folderIds to run training on",
            paramType="body",
        )
        .param(
            "pipelineName",
            description="The name of the resulting pipeline",
            paramType="query",
            required=True,
        )
        .param(
            "config",
            description="The configuration to use for training",
            paramType="query",
            required=True,
        )
    )
    def run_training(self, folderIds, pipelineName, config):
        user = self.getCurrentUser()
        token = Token().createToken(user=user, days=14)

        detection_list = []
        folder_list = []
        folder_names = []
        if folderIds is None or len(folderIds) == 0:
            raise RestException("No folderIds in param")

        for folderId in folderIds:
            folder = Folder().load(folderId, level=AccessType.READ, user=user)
            if folder is None:
                raise RestException(f"Cannot access folder {folderId}")
            getCloneRoot(user, folder)
            folder_names.append(folder['name'])
            # Ensure detection has a csv format
            # TODO: Move this into worker job
            train_on_detections_item = detections_item(folder, strict=True)
            ensure_csv_detections_file(folder, train_on_detections_item, user)
            detection_list.append(train_on_detections_item)
            folder_list.append(folder)

        # Ensure the folder to upload results to exists
        results_folder = training_output_folder(user)

        newjob = train_pipeline.apply_async(
            queue="training",
            kwargs=dict(
                results_folder=results_folder,
                source_folder_list=folder_list,
                groundtruth_list=detection_list,
                pipeline_name=pipelineName,
                config=config,
                girder_client_token=str(token["_id"]),
                girder_job_title=(
                    f"Running training on folder: {', '.join(folder_names)}"
                ),
                girder_job_type="training",
            ),
        )
        newjob.job[JOBCONST_TRAINING_INPUT_IDS] = folderIds
        newjob.job[JOBCONST_RESULTS_FOLDER_ID] = str(results_folder['_id'])
        newjob.job[JOBCONST_TRAINING_CONFIG] = config
        newjob.job[JOBCONST_PIPELINE_NAME] = pipelineName
        Job().save(newjob.job)
        return newjob.job

    @access.user
    @autoDescribeRoute(
        Description("Test whether or not a set of files are safe to upload").jsonParam(
            "files", "", paramType="body"
        )
    )
    def validate_files(self, files):
        ok = True
        message = ""
        mediatype = ""
        videos = [f for f in files if videoRegex.search(f)]
        csvs = [f for f in files if csvRegex.search(f)]
        images = [f for f in files if imageRegex.search(f)]
        ymls = [f for f in files if ymlRegex.search(f)]
        xmls = [f for f in files if xmlRegex.search(f)]
        if len(videos) and len(images):
            ok = False
            message = "Do not upload images and videos in the same batch."
        elif len(csvs) > 1:
            ok = False
            message = "Can only upload a single CSV Annotation per import"
        elif len(csvs) == 1 and len(ymls):
            ok = False
            message = "Cannot mix annotation import types"
        elif len(videos) > 1 and (len(csvs) or len(ymls)):
            ok = False
            message = (
                "Annotation upload is not supported when multiple videos are uploaded"
            )
        elif (not len(videos)) and (not len(images)):
            ok = False
            message = "No supported media-type files found"
        elif len(videos):
            mediatype = 'video'
        elif len(images):
            mediatype = 'image-sequence'

        return {
            "ok": ok,
            "message": message,
            "type": mediatype,
            "media": images + videos,
            "annotations": csvs + ymls + xmls,
        }

    @access.user
    @autoDescribeRoute(
        Description("Post-processing to be run after media/annotation import")
        .modelParam(
            "id",
            description="Folder containing the items to process",
            model=Folder,
            level=AccessType.WRITE,
        )
        .param(
            "skipJobs",
            "Whether to skip processing that might dispatch worker jobs",
            paramType="formData",
            dataType="boolean",
            default=False,
            required=False,
        )
    )
    def postprocess(self, folder, skipJobs):
        """
        Post-processing to be run after media/annotation import


        When skipJobs=False, the following may run as jobs:
            Transcoding of Video
            Transcoding of Images
            Conversion of KPF annotations into track JSON

        In either case, the following may run synchronously:
            Conversion of CSV annotations into track JSON
        """
        user = self.getCurrentUser()
        auxiliary = get_or_create_auxiliary_folder(folder, user)
        isClone = fromMeta(folder, ForeignMediaIdMarker, None) is not None

        if not skipJobs and not isClone:
            token = Token().createToken(user=user, days=2)
            # transcode VIDEO if necessary
            videoItems = Folder().childItems(
                folder, filters={"lowerName": {"$regex": videoRegex}}
            )

            for item in videoItems:
                convert_video.delay(
                    path=GetPathFromItemId(str(item["_id"])),
                    folderId=str(item["folderId"]),
                    auxiliaryFolderId=auxiliary["_id"],
                    itemId=str(item["_id"]),
                    girder_job_title=(
                        "Converting {} to a web friendly format".format(
                            str(item["_id"])
                        )
                    ),
                    girder_client_token=str(token["_id"]),
                )

            # transcode IMAGERY if necessary
            imageItems = Folder().childItems(
                folder, filters={"lowerName": {"$regex": imageRegex}}
            )
            safeImageItems = Folder().childItems(
                folder, filters={"lowerName": {"$regex": safeImageRegex}}
            )

            if imageItems.count() > safeImageItems.count():
                convert_images.delay(
                    folderId=folder["_id"],
                    girder_client_token=str(token["_id"]),
                    girder_job_title=(
                        f"Converting {folder['_id']} to a web friendly format",
                    ),
                )

            elif imageItems.count() > 0:
                folder["meta"][DatasetMarker] = True

            # transform KPF if necessary
            ymlItems = Folder().childItems(
                folder, filters={"lowerName": {"$regex": ymlRegex}}
            )
            if ymlItems.count() > 0:
                # There might be up to 3 yamls
                allFiles = [Item().childFiles(item)[0] for item in ymlItems]
                saveTracks(folder, meva_serializer.load_kpf_as_tracks(allFiles), user)
                ymlItems.rewind()
                for item in ymlItems:
                    Item().move(item, auxiliary)

            Folder().save(folder)

        # transform CSV if necessasry
        csvItems = Folder().childItems(
            folder,
            filters={"lowerName": {"$regex": csvRegex}},
            sort=[("created", pymongo.DESCENDING)],
        )
        if csvItems.count() >= 1:
            file = Item().childFiles(csvItems.next())[0]
            (tracks, attributes) = getTrackAndAttributesFromCSV(file)
            saveTracks(folder, tracks, user)
            saveCSVImportAttributes(folder, attributes, user)
            csvItems.rewind()
            for item in csvItems:
                Item().move(item, auxiliary)

        # transcode XML if necessary
        xmlItems = Folder().childItems(
            folder,
            filters={"lowerName": {"$regex": xmlRegex}},
            sort=[("created", pymongo.DESCENDING)],
        )
        print(xmlItems)
        if xmlItems.count() >= 1:
            file = Item().childFiles(xmlItems.next())[0]
            tracks = getTrackAndAttributesFromXML(file)
            saveTracks(folder, tracks, user)
            for item in xmlItems:
                Item().move(item, auxiliary)

        return folder

    @access.user
    @autoDescribeRoute(
        Description("Save mutable metadata for a dataset")
        .modelParam(
            "id",
            description="datasetId or folder for the metadata",
            model=Folder,
            level=AccessType.WRITE,
        )
        .jsonParam(
            "data",
            "JSON with the metadata to set",
            requireObject=True,
            paramType="body",
        )
        .errorResponse('Using a reserved metadata key', 400)
    )
    def update_metadata(self, folder, data):
        verify_dataset(folder)
        validated = models.MetadataMutableUpdate(**data)
        for name, value in validated.dict(exclude_none=True).items():
            folder['meta'][name] = value
        Folder().save(folder)
        return folder['meta']

    @access.user
    @autoDescribeRoute(
        Description("")
        .modelParam(
            "folderId",
            description="folder id of a clip",
            model=Folder,
            paramType="query",
            required=True,
            level=AccessType.WRITE,
        )
        .jsonParam(
            "attributes",
            "upsert and delete attributes",
            paramType="body",
            requireObject=True,
        )
    )
    def save_attributes(self, folder, attributes):
        verify_dataset(folder)
        upsert = attributes.get('upsert', [])
        delete = attributes.get('delete', [])
        attributes_dict = fromMeta(folder, 'attributes', {})
        for attribute_id in delete:
            attributes_dict.pop(str(attribute_id), None)
        for attribute in upsert:
            validated: models.Attribute = models.Attribute(**attribute)
            attributes_dict[str(validated.key)] = validated.dict(exclude_none=True)

        upserted_len = len(upsert)
        deleted_len = len(delete)

        if upserted_len or deleted_len:
            folder['meta']['attributes'] = attributes_dict
            Folder().save(folder)

        return {
            "updated": upserted_len,
            "deleted": deleted_len,
        }

    @access.user
    @autoDescribeRoute(
        Description("").modelParam(
            "folderId",
            description="folder id of a clip",
            model=Folder,
            paramType="query",
            required=True,
            level=AccessType.READ,
        )
    )
    def get_valid_images(self, folder):
        return Folder().childItems(
            getCloneRoot(self.getCurrentUser(), folder),
            filters={"lowerName": {"$regex": safeImageRegex}},
            sort=[("lowerName", pymongo.ASCENDING)],
        )
