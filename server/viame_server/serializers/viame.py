"""
VIAME Fish format deserializer
"""
import csv
import io
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from dacite import Config, from_dict
from girder.models.file import File
from viame_server.serializers.models import Feature, Track, interpolate


def row_info(row: List[str]) -> Tuple[int, int, List[float], float]:
    trackId = int(row[0])
    filename = str(row[1])
    frame = int(row[2])

    bounds = [round(float(x)) for x in row[3:7]]
    fish_length = float(row[8])

    return trackId, filename, frame, bounds, fish_length


def _deduceType(value: str) -> Union[bool, float, str]:
    if value == "true":
        return True
    if value == "false":
        return False
    try:
        number = float(value)
        return number
    except ValueError:
        return value

def create_geoJSONFeature(type:str, coords: List[float], key=''):
    feature = {
        "type": "Feature",
        "propertes": {
            "key": key
        },
        "geometry":{
            "type": type
        },
    }
    if 'Polygon' in type:
        feature['geometry']['coordinates'] = [coords]
    else:
        feature['geometry']['coordinates'] = coords

    return feature




def _parse_row(row: List[str]) -> Tuple[Dict, Dict, Dict, List]:
    """
    parse a single CSV line into its composite track and detection parts
    """
    features = {}
    attributes = {}
    track_attributes = {}
    confidence_pairs = [
        [row[i], float(row[i + 1])]
        for i in range(9, len(row), 2)
        if not row[i].startswith("(")
    ]
    start = len(row) - 1 if len(row) % 2 == 0 else len(row) - 2

    for j in range(start, len(row)):
        if row[j].startswith("(kp)"):
            if "head" in row[j]:
                groups = re.match(r"\(kp\) head ([0-9]+) ([0-9]+)", row[j])
                if groups:
                    features["head"] = (groups[1], groups[2])
            elif "tail" in row[j]:
                groups = re.match(r"\(kp\) tail ([0-9]+) ([0-9]+)", row[j])
                if groups:
                    features["tail"] = (groups[1], groups[2])
        if row[j].startswith("(atr)"):
            groups = re.match(r"\(atr\) (.+) (.+)", row[j])
            if groups:
                attributes[groups[1]] = _deduceType(groups[2])
        if row[j].startswith("(trk-atr)"):
            groups = re.match(r"\(trk-atr\) (.+) (.+)", row[j])
            if groups:
                track_attributes[groups[1]] = _deduceType(groups[2])
        if row[j].startswith("(poly)"):
            groups = re.match(r"(\(poly\)) ((?:[0-9]+\.[0-9]+\s)+)", row[j])
            if groups:
                temp = groups[2].split() 
                coords = list(zip(temp[::2], temp[1::2]))
                print(coords)
                #now we form the geoJSON feature for this track/frame
                features["geometry"] = {
                    "type" : "FeatureCollection",
                    "features": [create_geoJSONFeature('Polygon', coords)]
                 }

    return features, attributes, track_attributes, confidence_pairs


def _parse_row_for_tracks(row: List[str]) -> Tuple[Feature, Dict, Dict, List]:
    head_tail_feature, attributes, track_attributes, confidence_pairs = _parse_row(row)
    trackId, filename, frame, bounds, fishLength = row_info(row)

    feature = Feature(
        frame,
        bounds,
        attributes=attributes or None,
        fishLength=fishLength if fishLength > 0 else None,
        **head_tail_feature,
    )

    # Pass the rest of the unchanged info through as well
    return feature, attributes, track_attributes, confidence_pairs


def load_csv_as_tracks(file):
    """
    Convert VIAME web CSV to json tracks.
    Expect detections to be in increasing order (either globally or by track).
    """
    rows = (
        b"".join(list(File().download(file, headers=False)()))
        .decode("utf-8")
        .split("\n")
    )
    reader = csv.reader(row for row in rows if (not row.startswith("#") and row))
    tracks = {}
    for row in reader:
        (
            feature,
            attributes,
            track_attributes,
            confidence_pairs,
        ) = _parse_row_for_tracks(row)

        trackId, _, frame, _, _ = row_info(row)

        if trackId not in tracks:
            tracks[trackId] = Track(frame, frame, trackId)

        track = tracks[trackId]
        track.begin = min(frame, track.begin)
        track.end = max(track.end, frame)
        track.features.append(feature)
        track.confidencePairs = confidence_pairs

        for (key, val) in track_attributes:
            track.attributes[key] = val

    return {trackId: track.asdict() for trackId, track in tracks.items()}


def write_track_to_csv(track: Track, csv_writer, filenames=None):
    def valueToString(value):
        if value is True:
            return "true"
        elif value is False:
            return "false"
        return str(value)

    columns: List[Any] = []
    for index, keyframe in enumerate(track.features):
        features = [keyframe]

        # If this is not the last keyframe, and interpolation is
        # enabled for this keyframe, interpolate
        if keyframe.interpolate and index < len(track.features) - 1:
            nextKeyframe = track.features[index + 1]
            # interpolate all features in [a,b)
            features = interpolate(keyframe, nextKeyframe)

        for feature in features:
            columns = [
                track.trackId,
                "",
                feature.frame,
                *feature.bounds,
                track.confidencePairs[-1][1],
                feature.fishLength or -1,
            ]

            if filenames:
                columns[1] = filenames[feature.frame]

            for pair in track.confidencePairs:
                columns.extend(list(pair))

            if feature.head and feature.tail:
                columns.extend(
                    [
                        f"(kp) head {feature.head[0]} {feature.head[1]}",
                        f"(kp) tail {feature.tail[0]} {feature.tail[1]}",
                    ]
                )

            if feature.attributes:
                for key, val in feature.attributes.items():
                    columns.append(f"(atr) {key} {valueToString(val)}")
            

            if track.attributes:
                for key, val in track.attributes.items():
                    columns.append(f"(trk-atr) {key} {valueToString(val)}")

            if feature.geometry and "FeatureCollection" in feature.geometry.type:
                for geoJSONFeature in feature.geometry.features:
                    if 'Polygon' in geoJSONFeature.geometry.type:
                        #Coordinates need to be flattened out from their list of tuples
                        coordinates = [item for sublist in geoJSONFeature.geometry.coordinates[0] for item in sublist]
                        columns.append(f"(poly) {' '.join(map(str, coordinates))}")

            csv_writer.writerow(columns)


def export_tracks_as_csv(file, excludeBelowThreshold, thresholds, filenames=None) -> str:
    """
    Export track json to a CSV format.

    file: The detections JSON file
    excludeBelowThreshold: 
    """

    track_json = json.loads(
        b"".join(list(File().download(file, headers=False)())).decode()
    )

    tracks = {
        # Config kwarg needed to convert lists into tuples
        trackId: from_dict(Track, track, config=Config(cast=[Tuple]))
        for trackId, track in track_json.items()
    }

    with io.StringIO() as csvFile:
        writer = csv.writer(csvFile)

        for track in tracks.values():
            if (not excludeBelowThreshold) or track.exceeds_thresholds(thresholds):
                write_track_to_csv(track, writer, filenames)

        return csvFile.getvalue()
