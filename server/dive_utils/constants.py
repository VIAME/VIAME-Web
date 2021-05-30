import re

SETTINGS_CONST_JOBS_CONFIGS = 'jobs_configs'

ImageSequenceType = "image-sequence"
VideoType = "video"
MultiType = 'multi'
DefaultVideoFPS = 10

webValidImageFormats = {"png", "jpg", "jpeg"}
validImageFormats = {*webValidImageFormats, "tif", "tiff", "sgi", "bmp", "pgm"}
validVideoFormats = {"mp4", "avi", "mov", "mpg", "mpeg", "wmv", "flv"}

calibrationFormats = {'npz'}

videoRegex = re.compile(r"(\." + r"|\.".join(validVideoFormats) + ')$', re.IGNORECASE)
imageRegex = re.compile(r"(\." + r"|\.".join(validImageFormats) + ')$', re.IGNORECASE)
calibrationRegEx = re.compile(
    r"(\." + r"|\.".join(calibrationFormats) + ')$', re.IGNORECASE
)
safeImageRegex = re.compile(
    r"(\." + r"|\.".join(webValidImageFormats) + ')$', re.IGNORECASE
)
csvRegex = re.compile(r"\.csv$", re.IGNORECASE)
jsonRegex = re.compile(r"\.json$", re.IGNORECASE)
ymlRegex = re.compile(r"\.ya?ml$", re.IGNORECASE)

ImageMimeTypes = {
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
    "image/x-portable-anymap",
    "image/x-portable-bitmap",
    "image/x-portable-graymap",
    "image/x-rgb",
}

VideoMimeTypes = {
    "video/mpeg",
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-flv",
    "video/x-ms-wmv",
}

# Metadata markers
DatasetMarker = "annotate"
DetectionMarker = "detection"
PublishedMarker = "published"
ForeignMediaIdMarker = "foreign_media_id"
TrainedPipelineMarker = "trained_pipeline"
TypeMarker = "type"
AssetstoreSourceMarker = "import_source"
AssetstoreSourcePathMarker = "import_path"
FPSMarker = "fps"
# MultiCam Metadata markers
MultiCamMarker = "multiCam"  # Metadata Marker for Group of Cameras
SingleMultiCamMarker = "multiCamera"  # Marker for data for one camera in multicam
CalibrationMarker = "calibration"
SubTypeMarker = 'subType'
StereoSubTypeMarker = 'stereo'
MultiCamSubTypeMarker = 'multicam'
OriginalFPSMarker = "originalFps"
OriginalFPSStringMarker = "originalFpsString"

# Other constants
TrainedPipelineCategory = "trained"
StereoPipelineMarker = "measurement"

# The name of the folder where any user specific data should be stored
# (created as a folder of that user)
ViameDataFolderName = "VIAME"

# job constants
JOBCONST_DATASET_ID = 'datset_id'
JOBCONST_TRAINING_INPUT_IDS = 'training_input_ids'
JOBCONST_TRAINING_CONFIG = 'training_config'
JOBCONST_RESULTS_FOLDER_ID = 'results_folder_id'
JOBCONST_PIPELINE_NAME = 'pipeline_name'
JOBCONST_PRIVATE_QUEUE = 'private_queue'

# User queue constants
UserPrivateQueueEnabledMarker = 'user_private_queue_enabled'
