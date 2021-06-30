import functools
import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Generator, List, Optional, Tuple, Type

import pymongo
from girder.constants import AccessType
from girder.exceptions import RestException
from girder.models.file import File
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.model_base import AccessControlledModel
from girder.models.upload import Upload
from pydantic.main import BaseModel
from pymongo.cursor import Cursor

from dive_server.serializers import viame
from dive_utils import asbool, fromMeta, models, strNumericCompare
from dive_utils.constants import (
    ConfidenceFiltersMarker,
    DatasetMarker,
    DetectionMarker,
    ForeignMediaIdMarker,
    FPSMarker,
    ImageSequenceType,
    PublishedMarker,
    TypeMarker,
    VideoType,
    csvRegex,
    jsonRegex,
    safeImageRegex,
)
from dive_utils.types import GirderModel


class PydanticModel(AccessControlledModel):
    schema: Type[BaseModel]

    def initialize(self, name: str, schema: Type[BaseModel]):
        self.name = name
        self.schema = schema
        self.exposeFields(AccessType.READ, schema.schema()['properties'].keys())

    def validate(self, doc: dict):
        validated = self.schema(**doc)
        return validated.dict()

    def create(self, item: BaseModel):
        return self.save(item.dict())


def all_detections_items(folder: Folder) -> Cursor:
    """caller is responsible for verifying access permissions"""
    return (
        Item()
        .find({f"meta.{DetectionMarker}": str(folder['_id'])})
        .sort([("created", -1)])
    )


def detections_item(folder: Folder, strict=False) -> Optional[GirderModel]:
    all_items = all_detections_items(folder)
    first_item = next(all_items, None)
    if first_item is None and strict:
        raise RestException(f"No detections for folder {folder['name']}")
    return first_item


def detections_file(folder: Folder, strict=False) -> Optional[GirderModel]:
    item = detections_item(folder, strict)
    if item is None and not strict:
        return None
    first_file = next(Item().childFiles(item), None)
    if first_file is None and strict:
        raise RestException(f"No file associated with detection item {item}")
    return first_file


def get_static_pipelines_path() -> Path:
    pipeline_path = None

    env_pipelines_path = os.getenv("VIAME_PIPELINES_PATH")
    if env_pipelines_path is None:
        raise Exception(
            "No pipeline path specified. "
            "Please set the VIAME_PIPELINES_PATH environment variable.",
        )

    pipeline_path = Path(env_pipelines_path)
    if not pipeline_path.exists():
        raise Exception("Specified pipeline path does not exist!")

    return pipeline_path


def get_or_create_auxiliary_folder(folder, user):
    return Folder().createFolder(folder, "auxiliary", reuseExisting=True, creator=user)


def move_existing_result_to_auxiliary_folder(folder, user):
    auxiliary = get_or_create_auxiliary_folder(folder, user)
    for item in all_detections_items(folder):
        Item().move(item, auxiliary)


def itemIsWebsafeVideo(item: Item) -> bool:
    return fromMeta(item, "codec") == "h264"


def getTrackData(file: Optional[File]) -> Dict[str, dict]:
    if file is None:
        return {}
    if "csv" in file["exts"]:
        (tracks, attributes) = viame.load_csv_as_tracks_and_attributes(
            b"".join(list(File().download(file, headers=False)()))
            .decode("utf-8")
            .splitlines()
        )
        return tracks
    return json.loads(b"".join(list(File().download(file, headers=False)())).decode())


def getTrackAndAttributesFromCSV(file: File) -> Tuple[dict, dict]:
    if file is None:
        return ({}, {})
    if "csv" in file["exts"]:
        return viame.load_csv_as_tracks_and_attributes(
            b"".join(list(File().download(file, headers=False)()))
            .decode("utf-8")
            .splitlines()
        )
    return ({}, {})


def saveTracks(folder, tracks, user):
    timestamp = datetime.now().strftime("%m-%d-%Y_%H:%M:%S")
    item_name = f"result_{timestamp}.json"

    move_existing_result_to_auxiliary_folder(folder, user)
    newResultItem = Item().createItem(item_name, user, folder)
    Item().setMetadata(newResultItem, {"detection": str(folder["_id"])}, allowNull=True)

    json_bytes = json.dumps(tracks).encode()
    byteIO = io.BytesIO(json_bytes)
    Upload().uploadFromFile(
        byteIO,
        len(json_bytes),
        item_name,
        parentType="item",
        parent=newResultItem,
        user=user,
        mimeType="application/json",
    )


def saveCSVImportAttributes(folder, attributes, user):
    attributes_dict = fromMeta(folder, 'attributes', {})
    # we dont overwrite any existing meta attributes
    for attribute in attributes.values():
        validated: models.Attribute = models.Attribute(**attribute)
        if attribute['key'] not in attributes_dict:
            attributes_dict[str(validated.key)] = validated.dict(exclude_none=True)

    folder['meta']['attributes'] = attributes_dict
    Folder().save(folder)


def verify_dataset(folder: GirderModel):
    """Verify that a given folder is a DIVE dataset"""

    if not asbool(fromMeta(folder, DatasetMarker, False)):
        raise RestException(f'Source folder is not a valid DIVE dataset')
    return True


def process_csv(folder: GirderModel, user: GirderModel):
    """If there's a CSV in the folder, process it as a detections object"""
    csvItems = Folder().childItems(
        folder,
        filters={"lowerName": {"$regex": csvRegex}},
        sort=[("created", pymongo.DESCENDING)],
    )
    if csvItems.count() >= 1:
        auxiliary = get_or_create_auxiliary_folder(folder, user)
        file = Item().childFiles(csvItems.next())[0]
        (tracks, attributes) = getTrackAndAttributesFromCSV(file)
        saveTracks(folder, tracks, user)
        saveCSVImportAttributes(folder, attributes, user)
        csvItems.rewind()
        for item in csvItems:
            Item().move(item, auxiliary)
        return True
    return False


def process_json(folder: GirderModel, user: GirderModel):
    # Find a json if it exists
    jsonItems = list(
        Folder().childItems(
            folder,
            filters={"lowerName": {"$regex": jsonRegex}},
            sort=[("created", pymongo.DESCENDING)],
        )
    )
    for item in jsonItems:
        item['meta'][DetectionMarker] = str(folder['_id'])
        Item().save(item)
    if len(jsonItems):
        move_existing_result_to_auxiliary_folder(folder, user)
        return True
    return False


def getCloneRoot(owner: GirderModel, source_folder: GirderModel):
    """Get the source media folder associated with a clone"""
    verify_dataset(source_folder)
    next_id = fromMeta(source_folder, ForeignMediaIdMarker, False)
    while next_id is not False:
        """Recurse through source folders to find the root, allowing clones of clones"""
        source_folder = Folder().load(
            next_id,
            level=AccessType.READ,
            user=owner,
        )
        if source_folder is None:
            raise RestException(
                f"Referenced media source missing. Folder Id {next_id} was not found."
                " This may be a cloned dataset where the source was deleted."
            )
        verify_dataset(source_folder)
        next_id = fromMeta(source_folder, ForeignMediaIdMarker, False)
    return source_folder


def createSoftClone(
    owner: GirderModel,
    source_folder: GirderModel,
    parent_folder: GirderModel,
    name: str = None,
):
    """Create a no-copy clone of folder with source_id for owner"""

    cloned_folder = Folder().createFolder(
        parent_folder,
        name or source_folder['name'],
        description=f'Clone of {source_folder["name"]}.',
        reuseExisting=False,
    )
    cloned_folder['meta'] = source_folder['meta']
    media_source_folder = getCloneRoot(owner, source_folder)
    cloned_folder['meta'][ForeignMediaIdMarker] = str(media_source_folder['_id'])
    cloned_folder['meta'][PublishedMarker] = False
    # ensure confidence filter metadata exists
    if ConfidenceFiltersMarker not in cloned_folder['meta']:
        cloned_folder['meta'][ConfidenceFiltersMarker] = {'default': 0.1}

    Folder().save(cloned_folder)
    get_or_create_auxiliary_folder(cloned_folder, owner)
    source_detections = detections_item(source_folder)
    if source_detections is not None:
        cloned_detection_item = Item().copyItem(
            source_detections, creator=owner, folder=cloned_folder
        )
        cloned_detection_item['meta'][DetectionMarker] = str(cloned_folder['_id'])
        Item().save(cloned_detection_item)
    else:
        saveTracks(cloned_folder, {}, owner)
    return cloned_folder


def valid_images(
    folder: GirderModel,
    user: GirderModel,
) -> List[GirderModel]:
    """
    Any time images are used where frame alignment
    matters, this function must be used
    """

    images = Folder().childItems(
        getCloneRoot(user, folder),
        filters={"lowerName": {"$regex": safeImageRegex}},
    )

    def unwrapItem(item1, item2):
        return strNumericCompare(item1['name'], item2['name'])

    return sorted(
        images,
        key=functools.cmp_to_key(unwrapItem),
    )


def get_annotation_csv_generator(
    folder: GirderModel, user: GirderModel, excludeBelowThreshold=False, typeFilter=[]
) -> Tuple[str, Callable[[], Generator[str, None, None]]]:
    """
    Get the annotation generator for a folder
    """
    fps = None
    imageFiles = None

    source_type = fromMeta(folder, TypeMarker)
    if source_type == VideoType:
        fps = fromMeta(folder, FPSMarker)
    elif source_type == ImageSequenceType:
        imageFiles = [img['name'] for img in valid_images(folder, user)]

    thresholds = fromMeta(folder, "confidenceFilters", {})
    annotation_file = detections_file(folder, strict=False)
    track_dict = getTrackData(annotation_file)
    typeFilterSet = set(typeFilter)

    def downloadGenerator():
        for data in viame.export_tracks_as_csv(
            track_dict,
            excludeBelowThreshold,
            thresholds=thresholds,
            filenames=imageFiles,
            fps=fps,
            typeFilter=typeFilterSet,
        ):
            yield data

    filename = folder["name"] + ".csv"
    return filename, downloadGenerator
