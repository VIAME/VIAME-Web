from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field, validator
from pydantic.types import ConstrainedInt, conlist
from typing_extensions import Literal


class GeoJSONGeometry(BaseModel):
    type: str
    # support point, line, or polygon,
    coordinates: Union[List[float], List[List[float]], List[List[List[float]]]]


class GeoJSONFeature(BaseModel):
    type: str
    geometry: GeoJSONGeometry
    properties: Dict[str, Union[bool, float, str]]


class GeoJSONFeatureCollection(BaseModel):
    type: str
    features: List[GeoJSONFeature]


class Feature(BaseModel):
    """Feature represents a single detection in a track."""

    frame: int
    bounds: List[int]
    attributes: Optional[Dict[str, Union[bool, float, str]]]
    geometry: Optional[GeoJSONFeatureCollection] = None
    head: Optional[Tuple[float, float]] = None
    tail: Optional[Tuple[float, float]] = None
    fishLength: Optional[float] = None
    interpolate: Optional[bool] = False
    keyframe: Optional[bool] = True


class Track(BaseModel):
    begin: int
    end: int
    trackId: int
    features: List[Feature] = Field(default_factory=lambda: [])
    confidencePairs: List[Tuple[str, float]] = Field(default_factory=lambda: [])
    attributes: Dict[str, Any] = Field(default_factory=lambda: {})

    @validator('features')
    def validateFeatures(cls, v: List[Feature], values: dict):
        if len(v) > 0:
            trackId = values.get('trackId')
            begin = values.get('begin')
            end = values.get('end')
            print(trackId, begin, end)
            if v[0].frame != begin:
                raise ValueError(
                    f'trackId={trackId} begin={begin} does not match features[0]={v[0].frame}'
                )
            if v[-1].frame != end:
                raise ValueError(
                    f'trackId={trackId} end={end} does not match features[-1]={v[-1].frame}'
                )
        return v

    def exceeds_thresholds(self, thresholds: Dict[str, float]) -> bool:
        defaultThresh = thresholds.get('default', 0)
        return any(
            [
                confidence >= thresholds.get(field, defaultThresh)
                for field, confidence in self.confidencePairs
            ]
        )

    def __hash__(self):
        return self.trackId


class Attribute(BaseModel):
    belongs: Literal['track', 'detection']
    datatype: Literal['text', 'number', 'boolean']
    values: Optional[List[str]]
    name: str
    key: str


class CustomStyle(BaseModel):
    color: Optional[str]
    strokeWidth: Optional[float]
    opacity: Optional[float]
    fill: Optional[bool]

    class Config:
        extra = 'forbid'


class MetadataMutableUpdate(BaseModel):
    """Update schema for mutable metadata fields"""

    customTypeStyling: Optional[Dict[str, CustomStyle]]
    confidenceFilters: Optional[Dict[str, float]]

    class Config:
        extra = 'forbid'


class SummaryItemSchema(BaseModel):
    value: str
    total_tracks: int
    total_detections: int
    found_in: List[str]


class PublicDataSummary(BaseModel):
    label_summary_items: List[SummaryItemSchema]


class PrivateQueueEnabledResponse(BaseModel):
    enabled: bool
    token: Optional[dict]


class CocoMetadata(BaseModel):
    categories: Dict[int, dict]
    keypoint_categories: Dict[int, dict]
    images: Dict[int, dict]
    videos: Dict[int, dict]


# interpolate all features [a, b)
def interpolate(a: Feature, b: Feature) -> List[Feature]:
    if a.interpolate is False:
        raise ValueError('Cannot interpolate feature without interpolate enabled')
    if b.frame <= a.frame:
        raise ValueError('b.frame must be larger than a.frame')
    feature_list = [a]
    frame_range = b.frame - a.frame
    for frame in range(1, frame_range):
        delta = frame / frame_range
        inverse_delta = 1 - delta
        bounds: List[float] = [
            round((abox * inverse_delta) + (bbox * delta))
            for (abox, bbox) in zip(a.bounds, b.bounds)
        ]
        feature_list.append(
            Feature(frame=a.frame + frame, bounds=bounds, keyframe=False)
        )
    return feature_list
