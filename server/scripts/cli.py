import csv
import json
from typing import BinaryIO, Dict

import click

from dive_server.serializers import kwcoco, viame
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


@cli.group(name="convert")
@click.version_option()
def convert():
    pass


@convert.command(name="coco2dive")
@click.argument('input', type=click.File('rb'))
@click.option('--output', type=click.File('wt'), default='result.json')
@click.option('--output-attrs', type=click.File('wt'), default='attributes.json')
def convert_coco(input, output, output_attrs):
    coco_json = json.load(input)
    tracks, attributes = kwcoco.load_coco_as_tracks_and_attributes(coco_json)
    json.dump(tracks, output, indent=4)
    json.dump(attributes, output_attrs, indent=4)
    click.echo(f'wrote output {output.name}')
    click.echo(f'wrote attrib {output_attrs.name}')


@convert.command(name="viame2dive")
@click.argument('input', type=click.File('rt'))
@click.option('--output', type=click.File('wt'), default='result.json')
@click.option('--output-attrs', type=click.File('wt'), default='attributes.json')
def convert_viame_csv(input, output, output_attrs):
    rows = input.readlines()
    tracks, attributes = viame.load_csv_as_tracks_and_attributes(rows)
    json.dump(tracks, output, indent=4)
    json.dump(attributes, output_attrs, indent=4)
    click.echo(f'wrote output {output.name}')
    click.echo(f'wrote attrib {output_attrs.name}')
