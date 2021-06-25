import click

from scripts import generateLargeDataset


@click.group()
@click.version_option()
def cli():
    pass


@cli.command(name="generate-data")
@click.option('--images', default=100, help='Number of Images')
@click.option('--tracks', default=100, help='Number of Tracks')
@click.option('--types', default=10, help='Number of Types')
@click.option('--track_length', default=1, help='Max Track Length')
@click.option('--directory', default="./dataset", help='outputDirectory')
def main(images, tracks, types, track_length, directory):
    generateLargeDataset.create_images(directory, images)
    generateLargeDataset.create_track_json(
        directory, images, tracks, types, track_length
    )
