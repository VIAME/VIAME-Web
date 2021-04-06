import re

SETTINGS_CONST_JOBS_CONFIGS = 'jobs_configs'

ImageSequenceType = "image-sequence"
VideoType = "video"

webValidImageFormats = {"png", "jpg", "jpeg"}
validImageFormats = {*webValidImageFormats, "tif", "tiff", "sgi", "bmp", "pgm"}
validVideoFormats = {"mp4", "avi", "mov", "mpg", "mpeg", "flv"}

videoRegex = re.compile(r"(\." + r"|\.".join(validVideoFormats) + ')$', re.IGNORECASE)
imageRegex = re.compile(r"(\." + r"|\.".join(validImageFormats) + ')$', re.IGNORECASE)
safeImageRegex = re.compile(
    r"(\." + r"|\.".join(webValidImageFormats) + ')$', re.IGNORECASE
)
csvRegex = re.compile(r"\.csv$", re.IGNORECASE)
ymlRegex = re.compile(r"\.ya?ml$", re.IGNORECASE)
xmlRegex = re.compile(r"\.xml$", re.IGNORECASE)

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
}

# Metadata markers
DatasetMarker = "annotate"
DetectionMarker = "detection"
PublishedMarker = "published"
ForeignMediaIdMarker = "foreign_media_id"
TrainedPipelineMarker = "trained_pipeline"
TypeMarker = "type"

# Other constants
TrainedPipelineCategory = "trained"

# The name of the folder where any user specific data should be stored
# (created as a folder of that user)
ViameDataFolderName = "VIAME"
