from dataclasses import dataclass, field
from typing import Dict, List, Optional

from girder.models.file import File

from dive_utils.models import Feature, Track

from . import BoilerError, kpf, models


@dataclass
class Detection:
    frame: int
    box: models.Box
    keyframe: bool = False

    geom_id: Optional[int] = None
    timestamp: Optional[float] = None


@dataclass
class Actor:
    actor_id: int
    actor_type: str = 'other'
    detections: List[Detection] = field(default_factory=lambda: [])
    begin: Optional[int] = 0
    end: Optional[int] = 0

    confidence: Optional[float] = None
    activity_id: Optional[int] = None
    activity: Optional[str] = None
    activity_con: Optional[float] = None
    src_status: Optional[str] = None


def load_kpf_as_tracks(ymls):
    types = None
    activity = None
    geom = None

    actor_map = {}
    activity_map = {}
    error_report = {}
    try:
        for file in ymls:
            rows = b"".join(list(File().download(file, headers=False)())).decode(
                "utf-8"
            )
            yml = kpf.load_yaml(rows)
            for row in yml:
                if kpf.TYPES in row:
                    types = rows
                    break
                elif kpf.GEOM in row:
                    geom = rows
                    break
                elif kpf.ACTIVITY in row:
                    activity = rows
                    break

        if types:
            deserialize_types(types, actor_map)
        else:
            print("WARNING: types yaml was not given")
        if geom:
            deserialize_geom(geom, actor_map)
        else:
            print("WARNING: geom yaml was not given")
            raise BoilerError('GEOM yaml needed to create Tracks')
        if activity:
            deserialize_activities(activity, activity_map, actor_map)
        else:
            print("WARNING: activity yaml was not given")

        tracks = parse_actor_map_to_tracks(actor_map)
        return {
            trackId: track.dict(exclude_none=True) for trackId, track in tracks.items()
        }
    except Exception as e:
        error_report['error'] = str(e)
        return error_report


def parse_actor_map_to_tracks(actor_map) -> Dict[int, Track]:
    tracks = {}
    ids = {}
    i = 1
    for actor_id in actor_map:
        actor = actor_map[actor_id]
        for detection in actor.detections:
            bounds = [
                float(detection.box.left),
                float(detection.box.bottom),
                float(detection.box.right),
                float(detection.box.top),
            ]
            feat_attributes = {}
            if detection.timestamp is not None:
                feat_attributes['timestamp'] = detection.timestamp
            if detection.geom_id is not None:
                feat_attributes['geom_id'] = detection.geom_id

            feature = Feature(
                frame=detection.frame, bounds=bounds, attributes=feat_attributes
            )

            # Create a new track per actor id
            if actor_id not in ids:
                ids[actor_id] = i
                confidence_pairs = [(actor.actor_type, actor.confidence)]
                track_attributes = {
                    'actor_id': actor_id,
                    'activity_id': actor.activity_id,
                    'activity': actor.activity,
                    'confidence': actor.activity_con,
                    'status': actor.src_status,
                }
                tracks[i] = Track(
                    begin=actor.begin,
                    end=actor.end,
                    trackId=i,
                    confidencePairs=confidence_pairs,
                    attributes=track_attributes,
                )
                i += 1

            track = tracks[ids[actor_id]]
            track.features.append(feature)

    return tracks


def deserialize_types(file, actor_map):
    yml = kpf.load_yaml(file)
    for type_packet in yml:
        if kpf.TYPES in type_packet:
            kpf_types = type_packet[kpf.TYPES]
            id1 = kpf_types[kpf.ACTOR_ID]
            cset3 = kpf_types[kpf.CSET3]
            cset3keys = list(cset3.keys())
            if len(cset3keys) != 1:
                raise BoilerError(
                    f'{kpf.CSET3} should only have 1 key, found {cset3keys}'
                )
            name = cset3keys[0]
            if id1 in actor_map:
                actor_map[id1].actor_type = name
                actor_map[id1].actor_id = id1
            else:
                actor_map[id1] = Actor(
                    actor_type=name, detections=[], actor_id=id1, confidence=cset3[name]
                )  # type: ignore


def deserialize_geom(file, actor_map):
    # kpf.deserialize_geom(file, actor_map)
    yml = kpf.load_yaml(file)
    for geom_packet in yml:
        if kpf.GEOM in geom_packet:
            geom = geom_packet[kpf.GEOM]
            actor_id = geom[kpf.ACTOR_ID]
            frame = geom[kpf.FRAME]
            timestamp = geom.get(kpf.SECONDS, None)
            geom_id = geom.get(kpf.GEOM_ID, None)
            box = geom[kpf.BOX]
            box = [int(n) for n in box.split(' ')]
            if len(box) != 4:
                raise BoilerError('expect bounding box to have 4 values')
            keyframe = False
            if kpf.KEYFRAME in geom:
                keyframe = geom[kpf.KEYFRAME]
            box = models.Box(left=box[0], top=box[1], right=box[2], bottom=box[3])
            detection = Detection(
                frame=frame,
                box=box,
                keyframe=keyframe,
                geom_id=geom_id,
                timestamp=timestamp,
            )

            if actor_id in actor_map:
                actor_map[actor_id].detections.append(detection)
            else:
                actor_map[actor_id] = Actor(  # type: ignore
                    actor_type='other',
                    begin=frame,
                    end=frame,
                    detections=[detection],
                    actor_id=actor_id,
                )


def deserialize_activities(file, activity_map, actor_map):
    yml = kpf.load_yaml(file)
    for activity_packet in yml:
        if kpf.ACTIVITY in activity_packet:
            activity = _deserialize_activity(activity_packet, actor_map)
            activity_map[activity.activity_id] = activity


def _deserialize_activity(activity_packet, actor_map):
    """
    returns activity instanceActor(
    """
    activity = activity_packet[kpf.ACTIVITY]
    timespans = activity[kpf.TIMESPANS]
    frame_timespan = kpf._deserialize_frame_timespan(timespans)
    actors = activity[kpf.ACTORS]
    activity_type_obj = activity[kpf.ACTIVITY_TYPE]
    activity_type_keys = list(activity_type_obj.keys())
    if len(activity_type_keys) != 1:
        raise BoilerError(f'{activity_type_obj} should only have 1 key')
    activity_type = activity_type_keys[0]
    confidence = float(activity_type_obj[activity_type])

    status = None
    if kpf.STATUS in activity:
        # status = ActivityPipelineStatuses(activity[kpf.STATUS])
        status = activity[kpf.STATUS]

    return models.Activity(  # type: ignore
        activity_id=activity[kpf.ACTIVITY_ID],
        activity_type=activity_type,
        begin=frame_timespan[0],
        end=frame_timespan[1],
        status=status,
        actors=[
            _deserialize_actor(
                a,
                actor_map,
                activity[kpf.ACTIVITY_ID],
                activity_type,
                confidence,
                status,
            )
            for a in actors
        ],
    )


def _deserialize_actor(
    actor, actor_map, activity_id, activity_type, confidence, status
):
    if kpf.ACTOR_ID not in actor:
        raise BoilerError(f'actor {actor} missing {kpf.ACTOR_ID}')
    if kpf.TIMESPANS not in actor:
        raise BoilerError(f'actor {actor} missing {kpf.TIMESPANS}')
    actor_id = actor[kpf.ACTOR_ID]
    timespans = actor[kpf.TIMESPANS]
    frame_timespan = kpf._deserialize_frame_timespan(timespans)
    if actor_id in actor_map:
        actor_map[actor_id].begin = frame_timespan[0]
        actor_map[actor_id].end = frame_timespan[1]
        actor_map[actor_id].activity_id = activity_id
        actor_map[actor_id].activity = activity_type
        actor_map[actor_id].src_status = status
        actor_map[actor_id].activity_con = confidence
    else:
        actor_map[actor_id] = Actor(  # type: ignore
            actor_id=actor_id,
            begin=frame_timespan[0],
            end=frame_timespan[1],
            activity_id=activity_id,
            activity=activity_type,
            src_status=status,
            confidence=confidence,
        )
    return actor_map[actor_id]
