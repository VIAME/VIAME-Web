/**
 * VIAME process manager for linux platform
 */
import os from 'os';
import npath from 'path';
import { spawn } from 'child_process';
import fs from 'fs-extra';
import { xml2json } from 'xml-js';

import {
  Settings, SettingsCurrentVersion,
  DesktopJob, RunPipeline,
  NvidiaSmiReply,
  RunTraining,
  DesktopJobUpdater,
  ConversionArgs,
  CheckMediaResults,
} from 'platform/desktop/constants';
import { observeChild } from 'platform/desktop/backend/native/processManager';
import * as viame from './viame';
import { spawnResult } from './utils';

const DefaultSettings: Settings = {
  // The current settings schema config
  version: SettingsCurrentVersion,
  // A path to the VIAME base install
  viamePath: '/opt/noaa/viame',
  // Path to a user data folder
  dataPath: npath.join(os.homedir(), 'VIAME_DATA'),
  // Overrides
  overrides: {
    viamePath: process.env.DIVE_VIAME_INSTALL_PATH || undefined,
  }
};

const ViameLinuxConstants = {
  setup: 'setup_viame.sh',
  trainingExe: 'viame_train_detector',
  kwiverExe: 'kwiver',
  shell: '/bin/bash',
  ffmpeg: {
    // Ready indicates that the proper ffmpeg settings have been learned from the system.
    ready: false,
    initialization: '', // command to initialize
    path: '', // location of the ffmpeg executable
    // Default video args
    videoArgs: [
      '-c:v libx264',
      '-preset slow',
      '-crf 26',
      // https://askubuntu.com/questions/1315697/could-not-find-tag-for-codec-pcm-s16le-in-stream-1-codec-not-currently-support
      '-c:a aac',
      /**
       * TODO: Upgrade to ffmpeg 4, use `round` instead of `ceil`
       * 3.4 is part of 18.04LTS, so we should support it
       *
       * References:
       * https://github.com/Kitware/dive/pull/602 (Anamorphic Video Support)
       * https://video.stackexchange.com/questions/20871/how-do-i-convert-anamorphic-hdv-video-to-normal-h-264-video-with-ffmpeg-how-to
       */
      '-vf "scale=ceil(iw*sar/2)*2:ceil(ih/2)*2,setsar=1"',
    ].join(' '),
  },
};

const ViameBundledFFMPEGVideoArgs = [
  '-c:v h264',
  '-c: a copy',
  '-vf "scale=ceil(iw*sar/2)*2:ceil(ih/2)*2,setsar=1"',
].join(' ');

function sourceString(settings: Settings) {
  const setupScriptAbs = npath.join(settings.viamePath, ViameLinuxConstants.setup);
  return `. "${setupScriptAbs}"`;
}

async function validateViamePath(settings: Settings): Promise<true | string> {
  const setupScriptPath = npath.join(settings.viamePath, ViameLinuxConstants.setup);
  const setupExists = await fs.pathExists(setupScriptPath);
  if (!setupExists) {
    return `${setupScriptPath} does not exist`;
  }

  const trainingScriptPath = npath.join(settings.viamePath, 'bin', ViameLinuxConstants.trainingExe);
  const trainingExists = await fs.pathExists(trainingScriptPath);
  if (!trainingExists) {
    return `${trainingScriptPath} does not exist`;
  }

  const kwiverExistsOnPath = observeChild(spawn(
    `${sourceString(settings)} && which ${ViameLinuxConstants.kwiverExe}`,
    { shell: '/bin/bash' },
  ));
  return new Promise((resolve) => {
    kwiverExistsOnPath.on('exit', (code) => {
      if (code === 0) {
        resolve(true);
      } else {
        resolve('kwiver failed to initialize');
      }
    });
  });
}

async function runPipeline(
  settings: Settings,
  runPipelineArgs: RunPipeline,
  updater: DesktopJobUpdater,
): Promise<DesktopJob> {
  return viame.runPipeline(settings, runPipelineArgs, updater, validateViamePath, {
    ...ViameLinuxConstants,
    setupScriptAbs: sourceString(settings),
  });
}

async function train(
  settings: Settings,
  runTrainingArgs: RunTraining,
  updater: DesktopJobUpdater,
): Promise<DesktopJob> {
  return viame.train(settings, runTrainingArgs, updater, validateViamePath, {
    ...ViameLinuxConstants,
    setupScriptAbs: sourceString(settings),
  });
}

// Based on https://github.com/chrisallenlane/node-nvidia-smi
async function nvidiaSmi(): Promise<NvidiaSmiReply> {
  return new Promise((resolve) => {
    const smi = observeChild(spawn('nvidia-smi', ['-q', '-x']));
    let result = '';
    smi.stdout.on('data', (chunk) => {
      result = result.concat(chunk.toString('utf-8'));
    });
    smi.on('exit', (exitCode) => {
      let jsonStr = 'null'; // parses to null
      if (exitCode === 0) {
        jsonStr = xml2json(result, { compact: true });
      }
      resolve({
        output: JSON.parse(jsonStr),
        exitCode,
        error: result,
      });
    });
    smi.on('error', (err) => {
      resolve({
        output: null,
        exitCode: -1,
        error: err.message,
      });
    });
  });
}

/**
 * one time per launch configuration for ffmpeg and ffprobe
 * Linux version is more complicated for multiple VIAME versions and local ffmpeg
 */
async function ffmpegCommand(settings: Settings) {
  if (ViameLinuxConstants.ffmpeg.ready) {
    return;
  }
  const ffmpegPathViame = `${settings.viamePath}/bin/ffmpeg`;
  const init = `${sourceString(settings)} &&`;
  const errorLog = [];
  //First lets see if the VIAME install has libx264
  const ffmpegViameExists = fs.existsSync(`${settings.viamePath}/bin/ffmpeg`);
  if (ffmpegViameExists) {
    const viameffmpeg = await spawnResult(`${init} "${ffmpegPathViame}" -encoders`, '/bin/bash');
    if (viameffmpeg.output) {
      if (viameffmpeg.output.includes('libx264')) {
        ViameLinuxConstants.ffmpeg.initialization = init;
        ViameLinuxConstants.ffmpeg.path = ffmpegPathViame;
        ViameLinuxConstants.ffmpeg.ready = true;
        return;
      }
    }
    if (viameffmpeg.exitCode === -1) {
      errorLog.push(viameffmpeg.error);
    }
  }
  //Now we need to test for a local install with libx264
  const localffmpeg = await spawnResult('ffmpeg -encoders', '/bin/bash');
  if (localffmpeg.output) {
    if (localffmpeg.output.includes('libx264')) {
      ViameLinuxConstants.ffmpeg.initialization = '';
      ViameLinuxConstants.ffmpeg.path = 'ffmpeg';
      ViameLinuxConstants.ffmpeg.ready = true;
      return;
    }
  }
  if (localffmpeg.exitCode === -1) {
    errorLog.push(localffmpeg.error);
  }

  // As long as VIAMEffmpeg exists we can attempt to use nvida encoding
  if (ffmpegViameExists) {
    ViameLinuxConstants.ffmpeg.initialization = init;
    ViameLinuxConstants.ffmpeg.path = ffmpegPathViame;
    ViameLinuxConstants.ffmpeg.videoArgs = ViameBundledFFMPEGVideoArgs;
    ViameLinuxConstants.ffmpeg.ready = true;
    return;
  }
  //We make it down here we have no way to convert the video file
  if (errorLog.length) {
    throw new Error(`ffmpeg errors: ${errorLog.join(' | ')}`);
  }
  throw new Error('ffmpeg not installed, please download and install VIAME Toolkit from the main page');
}

/**
 * Checs the video file for the codec type and
 * returns true if it is x264, if not will return false for media conversion
 */
async function checkMedia(settings: Settings, file: string): Promise<CheckMediaResults> {
  await ffmpegCommand(settings);
  return viame.checkMedia({
    ...ViameLinuxConstants,
    setupScriptAbs: sourceString(settings),
  }, file);
}

async function convertMedia(settings: Settings,
  args: ConversionArgs,
  updater: DesktopJobUpdater): Promise<DesktopJob> {
  await ffmpegCommand(settings);
  return viame.convertMedia(settings, args, updater, {
    ...ViameLinuxConstants,
    setupScriptAbs: sourceString(settings),
  });
}


export default {
  DefaultSettings,
  nvidiaSmi,
  checkMedia,
  convertMedia,
  runPipeline,
  train,
  validateViamePath,
};
