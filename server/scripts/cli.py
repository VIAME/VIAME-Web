import json
from typing import BinaryIO, Dict

import click

from dive_utils import models
from scripts import generateLargeDataset


@click.group()
@click.version_option()
def cli():
    pass


@cli.command(
    name='verify-dive-json', help="Verify a DIVE json schema file for correctness"
)
@click.argument('input', type=click.File('rb'))
def verify_dive_json(input: BinaryIO):
    trackdicts: Dict[str, dict] = json.load(input)
    for t in trackdicts.values():
        models.Track(**t)


@cli.command(name="generate-data", help="Generate fake datasets for testing")
@click.option('--images', default=100, help='Number of Images')
@click.option('--video/--no-video', default=False, help="Video type dataset")
@click.option('--frames', default=100, help='Video Frames')
@click.option("--width", default=10, help="Video Frames")
@click.option("--height", default=10, help="Video Frames")
@click.option("--fps", default=1, help="Video Frames")
@click.option('--tracks', default=100, help='Number of Tracks')
@click.option('--types', default=10, help='Number of Types')
@click.option('--track_length', default=1, help='Max Track Length')
@click.option('--directory', default="./dataset", help='outputDirectory')
def main(
    images, video, frames, width, height, fps, tracks, types, track_length, directory
):
    if video is False:
        generateLargeDataset.create_images(directory, images, width, height)
    else:
        generateLargeDataset.create_video(directory, width, height, fps, frames)
    generateLargeDataset.create_track_json(
        directory,
        images,
        tracks,
        types,
        track_length,
        width,
        height,
    )
