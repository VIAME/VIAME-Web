import glob
import json
import os
import random
import subprocess as sp

import cv2
import numpy as np
from tqdm import tqdm


def create_video(
    directory: str,
    width: int,
    height: int,
    fps: int,
    frames: int,
):
    os.mkdir(directory)

    for i in tqdm(range(int(frames))):
        # Random gray image in resolution width by height.
        img = np.random.randint(0, 255, (height, width), np.uint8)

        cv2.imwrite(directory + "/" + str(i).zfill(6) + ".jpg", img)
    process = sp.Popen(
        f"ffmpeg -y -r {fps} -i {directory}/%06d.jpg -vcodec libx264 -tune zerolatency -movflags +faststart {directory}/vid.mp4",
        stdout=sp.PIPE,
        shell=True,
        executable="/bin/bash",
    )
    fileList = glob.glob(f"{directory}/*.jpg")
    if process.stdout is None:
        raise RuntimeError("Stdout must not be none")
    for line in iter(process.stdout.readline, b""):
        line_str = line.decode("utf-8")
        print(line_str)

    # Iterate over the list of filepaths & remove each file.
    for filePath in fileList:
        os.remove(filePath)


def create_track_json(
    directory: str,
    image_count: int,
    track_count: int,
    type_count: int,
    max_track_length: int,
    width: int,
    height: int,
):
    """
    Read in JSON file and video file and extract bounds and create files for all the other data
    """
    types = []
    for type in range(type_count):
        types.append(f"Type_{type}")
    tracks = {}
    for track in tqdm(range(track_count)):

        track_obj = {
            "trackId": track,
            "begin": float("inf"),
            "end": float("-inf"),
            "confidencePairs": [
                [
                    types[random.randint(0, type_count - 1)],
                    random.randint(0, 100) / 100.0,
                ]
            ],
            "features": [],
        }
        start_frame = random.randint(0, image_count - 1)
        adjusted_max_track_length = max_track_length
        if image_count - start_frame < max_track_length:
            adjusted_max_track_length = image_count - start_frame
        if adjusted_max_track_length > 1:
            track_length = random.randint(1, adjusted_max_track_length)
        else:
            track_length = adjusted_max_track_length
        for frame in range(track_length):
            frame = start_frame + frame
            feature = {
                "frame": frame,
                "keyframe": True,
                "bounds": [0, 0, width, height],
            }
            track_obj["begin"] = min(track_obj["begin"], frame)
            track_obj["end"] = max(track_obj["end"], frame)
            track_obj["features"].append(feature)
        tracks[track] = track_obj
    json_file = f"{directory}/result_test.json"
    with open(json_file, "w") as outfile:
        json.dump(tracks, outfile)


def create_images(
    directory: str,
    images: int,
    width: int,
    height: int,
):
    # Create a folder to hold it
    os.mkdir(directory)
    for index in tqdm(range(images)):
        img = np.random.randint(0, 255, (height, width), np.uint8)
        cv2.imwrite(f"{directory}/image_{index}.jpg", img)
