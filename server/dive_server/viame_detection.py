from typing import List

from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import Resource, setContentDisposition, setResponseHeader
from girder.constants import AccessType, TokenScope
from girder.exceptions import RestException
from girder.models.file import File
from girder.models.folder import Folder
from girder.models.item import Item
from girder.utility import ziputil

from dive_server import multicam
from dive_server.serializers import viame
from dive_server.utils import (
    detections_file,
    detections_item,
    getCloneRoot,
    getTrackData,
    saveTracks,
    verify_dataset,
)
from dive_utils import TRUTHY_META_VALUES, fromMeta, models
from dive_utils.constants import (
    FPSMarker,
    ImageSequenceType,
    MultiCamMarker,
    SingleMultiCamMarker,
    TypeMarker,
    VideoType,
    imageRegex,
    safeImageRegex,
    videoRegex,
)


class ViameDetection(Resource):
    def __init__(self):
        super(ViameDetection, self).__init__()
        self.resourceName = "viame_detection"
        self.route("GET", (), self.get_detection)
        self.route("PUT", (), self.save_detection)
        self.route("GET", ("clip_meta",), self.get_clip_meta)
        self.route("GET", (":id", "export"), self.get_export_urls)
        self.route("GET", (":id", "export_detections"), self.export_detections)
        self.route("GET", (":id", "export_all"), self.export_all)

    def _get_clip_meta(self, folder):
        videoUrl = None
        video = None

        if fromMeta(folder, SingleMultiCamMarker) in TRUTHY_META_VALUES:
            item = Item().findOne(
                {
                    'folderId': folder['_id'],
                    'meta.codec': 'h264',
                    'meta.source_video': {
                        '$in': [
                            # In a previous version, source_video was unset
                            None,
                            False,
                        ]
                    },
                }
            )
        # Find a video tagged with an h264 codec left by the transcoder
        else:
            item = Item().findOne(
                {
                    'folderId': getCloneRoot(self.getCurrentUser(), folder)['_id'],
                    'meta.codec': 'h264',
                    'meta.source_video': {
                        '$in': [
                            # In a previous version, source_video was unset
                            None,
                            False,
                        ]
                    },
                }
            )
        if item:
            video = Item().childFiles(item)[0]
            videoUrl = f'/api/v1/file/{str(video["_id"])}/download'

        return {
            'folder': folder,
            'detection': detections_item(folder),
            'video': video,
            'videoUrl': videoUrl,
        }

    def _generate_detections(self, folder, excludeBelowThreshold):
        file = detections_file(folder, strict=True)

        # TODO: deprecated, remove after we migrate everyone to json
        if "csv" in file["exts"]:
            return File().download(file)

        filename = folder["name"] + ".csv"

        fps = None
        imageFiles = None
        source_type = fromMeta(folder, TypeMarker)
        if source_type == VideoType:
            fps = fromMeta(folder, FPSMarker)
        elif source_type == ImageSequenceType:
            imageFiles = [
                f['name']
                for f in Folder()
                .childItems(folder, filters={"lowerName": {"$regex": safeImageRegex}})
                .sort("lowerName")
            ]
        thresholds = fromMeta(folder, "confidenceFilters", {})
        track_dict = getTrackData(file)

        def downloadGenerator():
            for data in viame.export_tracks_as_csv(
                track_dict,
                excludeBelowThreshold,
                thresholds=thresholds,
                filenames=imageFiles,
                fps=fps,
            ):
                yield data

        return filename, downloadGenerator

    @access.user
    @autoDescribeRoute(
        Description("Export VIAME data")
        .modelParam(
            "id",
            description="folder id of a clip",
            model=Folder,
            required=True,
            level=AccessType.READ,
        )
        .param(
            "excludeBelowThreshold",
            "Exclude tracks with confidencePairs below set threshold",
            paramType="query",
            dataType="boolean",
            default=False,
        )
    )
    def get_export_urls(self, folder, excludeBelowThreshold):
        verify_dataset(folder)
        folderId = str(folder['_id'])
        export_all = f'/api/v1/folder/{folderId}/download'
        export_media = None
        export_detections = None

        clipMeta = self._get_clip_meta(folder)
        detection = clipMeta.get('detection')
        if detection:
            export_detections = (
                f'/api/v1/viame_detection/{folderId}/export_detections'
                f'?excludeBelowThreshold={excludeBelowThreshold}'
            )
            export_all = (
                f'/api/v1/viame_detection/{folderId}/export_all'
                f'?excludeBelowThreshold={excludeBelowThreshold}'
            )

        source_type = fromMeta(folder, TypeMarker)
        if source_type == VideoType:
            export_media = clipMeta.get('videoUrl')
        elif source_type == ImageSequenceType:
            export_media = (
                f'/api/v1/viame_detection/{folderId}/export_all'
                f'?excludeBelowThreshold={excludeBelowThreshold}&includeDetections=false'
            )

        # No-copy import data does not support mimeFilter.
        # We cannot detect which collections are from no-copy imported data, so
        # disable all image download from collections
        if folder['baseParentType'] == 'collection':
            export_media = None

        return {
            'mediaType': source_type,
            'exportAllUrl': export_all,
            'exportMediaUrl': export_media,
            'exportDetectionsUrl': export_detections,
            'currentThresholds': fromMeta(folder, "confidenceFilters", {}),
        }

    @access.public(scope=TokenScope.DATA_READ, cookie=True)
    @autoDescribeRoute(
        Description("Export detections of a clip into CSV format.")
        .modelParam(
            "id",
            description="folder id of a clip",
            model=Folder,
            required=True,
            level=AccessType.READ,
        )
        .param(
            "excludeBelowThreshold",
            "Exclude tracks with confidencePairs below set threshold",
            paramType="query",
            dataType="boolean",
            default=False,
        )
    )
    def export_detections(self, folder, excludeBelowThreshold):
        verify_dataset(folder)
        filename, gen = self._generate_detections(folder, excludeBelowThreshold)
        setContentDisposition(filename)
        return gen

    @access.public(scope=TokenScope.DATA_READ, cookie=True)
    @autoDescribeRoute(
        Description("Export detections of a clip into CSV format.")
        .modelParam(
            "id",
            description="folder id of a clip",
            model=Folder,
            required=True,
            level=AccessType.READ,
        )
        .param(
            "includeMedia",
            "Include media content",
            paramType="query",
            dataType="boolean",
            default=True,
        )
        .param(
            "includeDetections",
            "Include detection content",
            paramType="query",
            dataType="boolean",
            default=True,
        )
        .param(
            "excludeBelowThreshold",
            "Exclude tracks with confidencePairs below set threshold",
            paramType="query",
            dataType="boolean",
            default=False,
        )
    )
    def export_all(
        self, folder, includeMedia, includeDetections, excludeBelowThreshold
    ):
        verify_dataset(folder)
        _, gen = self._generate_detections(folder, excludeBelowThreshold)
        setResponseHeader('Content-Type', 'application/zip')
        setContentDisposition(folder['name'] + '.zip')
        user = self.getCurrentUser()
        mediaFolder = getCloneRoot(user, folder)
        source_type = fromMeta(mediaFolder, TypeMarker)
        mediaRegex = None
        if source_type == ImageSequenceType:
            mediaRegex = imageRegex
        elif source_type == VideoType:
            mediaRegex = videoRegex

        def stream():
            z = ziputil.ZipGenerator(folder['name'])

            if includeMedia:
                # Add media
                for item in Folder().childItems(
                    mediaFolder,
                    filters={"lowerName": {"$regex": mediaRegex}},
                ):
                    for (path, file) in Item().fileList(item):
                        for data in z.addFile(file, path):
                            yield data
                        break  # Media items should only have 1 valid file

            if includeDetections:
                # add JSON detections
                for (path, file) in Folder().fileList(
                    folder,
                    user=user,
                    subpath=False,
                    mimeFilter={'application/json'},
                ):
                    for data in z.addFile(file, path):
                        yield data
                # add CSV detections
                for data in z.addFile(gen, "output_tracks.csv"):
                    yield data
            yield z.footer()

        return stream

    @access.user
    @autoDescribeRoute(
        Description("Get detections of a clip").modelParam(
            "folderId",
            description="folder id of a clip",
            model=Folder,
            paramType="query",
            required=True,
            level=AccessType.READ,
        )
    )
    def get_detection(self, folder):
        verify_dataset(folder)
        file = detections_file(folder)
        if file is None:
            return {}
        if "csv" in file["exts"]:
            raise RestException(
                'Cannot get detections until postprocessing is complete.'
            )
        return File().download(file, contentDisposition="inline")

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
    def get_clip_meta(self, folder):
        verify_dataset(folder)
        return self._get_clip_meta(folder)

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
            "tracks", "upsert and delete tracks", paramType="body", requireObject=True
        )
    )
    def save_detection(self, folder, tracks):
        verify_dataset(folder)
        user = self.getCurrentUser()
        upsert: List[dict] = tracks.get('upsert', [])
        delete: List[str] = tracks.get('delete', [])
        track_dict = getTrackData(detections_file(folder))

        for track_id in delete:
            track_dict.pop(str(track_id), None)
        for track in upsert:
            validated: models.Track = models.Track(**track)
            track_dict[str(validated.trackId)] = validated.dict(exclude_none=True)

        upserted_len = len(upsert)
        deleted_len = len(delete)

        if upserted_len or deleted_len:
            saveTracks(folder, track_dict, user)

        return {
            "updated": upserted_len,
            "deleted": deleted_len,
        }
