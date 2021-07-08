#!/usr/bin/env node
/// <reference types="@types/geojson" />

/**
 * Command-line entrypoints into serializers and other tooling.
 * See README.md for usage
 */
import OS from 'os';
import npath from 'path';
import { Writable } from 'stream';
import { stdout, stderr } from 'process';
import yargs from 'yargs';
import fs from 'fs-extra';

import Vue from 'vue';
import CompositionApi from '@vue/composition-api';

import Track from 'vue-media-annotator/track';

import { DesktopJobUpdate, RunPipeline, RunTraining } from 'platform/desktop/constants';
import { loadJsonTracks, loadJsonMetadata } from 'platform/desktop/backend/native/common';
import linux from './native/linux';
import win32 from './native/windows';
import * as common from './native/common';
import { parseFile, serialize } from './serializers/viame';

function getCurrentPlatform() {
  const platform = OS.platform() === 'win32' ? win32 : linux;
  if (OS.platform() === 'win32') {
    win32.initialize();
  }
  return platform;
}

// https://stackoverflow.com/questions/21491567/how-to-implement-a-writable-stream
function echoStream() {
  return new Writable({
    write(chunk, encoding, next) {
      stdout.write(chunk.toString());
      next();
    },
  });
}

function updater(update: DesktopJobUpdate) {
  update.body.forEach((s) => stdout.write(s));
}

async function parseViameFile(file: string) {
  const data = await parseFile(file);
  stdout.write(JSON.stringify(data));
}

async function parseJsonFile(filepath: string, metapath: string) {
  await Promise.all([
    loadJsonTracks(filepath),
    loadJsonMetadata(metapath),
  ]).then(([input, meta]) => serialize(echoStream(), input, meta));
}

function settingsArgs() {
  yargs.option('datapath', {
    describe: 'path to DIVA data',
  });
  yargs.option('viamepath', {
    describe: 'path to VIAME install',
  });
}

const { argv } = yargs
  .scriptName('divecli')
  .command('viame2json [file]', 'Convert VIAME CSV to JSON', (y) => {
    y.positional('file', {
      description: 'The file to parse',
      type: 'string',
    }).demandOption('file');
  })
  .command('json2viame [file] [meta]', 'Convert JSON to VIAME CSV', () => {
    yargs.positional('file', {
      description: 'The file to parse',
      type: 'string',
    });
    yargs.positional('meta', {
      description: 'The metadata to parse',
      type: 'string',
    });
    yargs.demandOption(['file', 'meta']);
  })
  .command('list-config', 'List viame pipeline configuration', settingsArgs)
  .command('run-pipeline', 'Run a pipeline', () => {
    settingsArgs();
    yargs.option('id', {
      describe: 'dataset id',
    });
    yargs.option('pipe', {
      describe: 'pipe filename',
    });
    yargs.option('type', {
      describe: 'Pipeline type',
    });
    yargs.demandOption(['type', 'pipe', 'id']);
  })
  .command('run-training', 'Run training', () => {
    settingsArgs();
    yargs.option('id', {
      describe: 'One or more dataset IDs to train on',
    }).array('id');
    yargs.option('config', {
      describe: 'Training configuration file',
    });
    yargs.option('name', {
      describe: 'New pipeline name created by training',
    });
    yargs.option('annotatedFramesOnly', {
      describe: 'Train only on annotated frames',
      type: 'boolean',
      default: false,
    });
    yargs.demandOption(['id', 'config', 'name']);
  })
  .command('stats', 'Show stats on existing data', () => {
    settingsArgs();
  })
  .demandCommand()
  .help();

function getSettings() {
  const platform = getCurrentPlatform();
  return {
    platform,
    ...platform.DefaultSettings,
    dataPath: argv.datapath as string || platform.DefaultSettings.dataPath,
    viamePath: argv.viamepath as string || platform.DefaultSettings.viamePath,
  };
}

if (argv._.includes('viame2json')) {
  parseViameFile(argv.file as string);
} else if (argv._.includes('json2viame')) {
  parseJsonFile(argv.file as string, argv.meta as string);
} else if (argv._.includes('list-config')) {
  const settings = getSettings();
  const run = async () => {
    const pipelines = await common.getPipelineList(settings);
    const trainingConfig = await common.getTrainingConfigs(settings);
    stdout.write(JSON.stringify({
      pipelines,
      trainingConfig,
    }, undefined, 2));
  };
  run();
} else if (argv._.includes('run-pipeline')) {
  const settings = getSettings();
  const pipeargs: RunPipeline = {
    datasetId: argv.id as string,
    pipeline: {
      name: 'cli',
      pipe: argv.pipe as string,
      type: argv.type as string,
    },
  };
  const run = async () => {
    const job = await settings.platform.runPipeline(settings, pipeargs, updater);
    stdout.write(JSON.stringify(job, undefined, 2));
  };
  run();
} else if (argv._.includes('run-training')) {
  const settings = getSettings();
  const trainargs: RunTraining = {
    datasetIds: argv.id as string[],
    trainingConfig: argv.config as string,
    pipelineName: argv.name as string,
    annotatedFramesOnly: argv.annotatedFramesOnly as boolean,
  };
  const run = async () => {
    const job = await settings.platform.train(settings, trainargs, updater);
    stdout.write(JSON.stringify(job, undefined, 2));
  };
  run();
} else if (argv._.includes('stats')) {
  Vue.use(CompositionApi); // needed for Track hydration.
  const settings = getSettings();
  const dspath = npath.join(settings.dataPath, common.ProjectsFolderName);
  const run = async () => {
    const dsids = await fs.readdir(dspath);
    const good: unknown[] = [];
    await Promise.all(dsids.map(async (id) => {
      try {
        const proj = await common.getValidatedProjectDir(settings, id);
        const meta = await common.loadJsonMetadata(proj.metaFileAbsPath);
        const tracks = await common.loadJsonTracks(proj.trackFileAbsPath);
        const tracklist = Object.values(tracks);
        const hydrated = tracklist.map((t) => Track.fromJSON(t));
        const labels = new Set<string>();
        hydrated.forEach((t) => t.confidencePairs.forEach((cp) => {
          labels.add(cp[0]);
        }));
        good.push({
          name: meta.name,
          id: meta.id,
          type: meta.type,
          imageCount: meta.originalImageFiles.length,
          txImageCount: meta.transcodedImageFiles?.length,
          originalVideoFile: meta.originalVideoFile,
          txVideoFile: meta.transcodedVideoFile,
          tracks: tracklist.length,
          features: tracklist.map((t) => t.features).length,
          labels: Array.from(labels),
        });
      } catch (err) {
        stderr.write(`Invalid project: ${id}: ${err}\n`);
      }
    }));
    stdout.write(JSON.stringify(good, undefined, 2));
  };
  run();
} else {
  stdout.write(`Invalid command: ${argv._}\n`);
  yargs.showHelp();
}
