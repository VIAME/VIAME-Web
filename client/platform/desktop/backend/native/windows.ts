/**
 * VIAME process manager for windows platform
 */
import os from 'os';
import npath from 'path';
import { spawn } from 'child_process';
import fs from 'fs-extra';
import { xml2json } from 'xml-js';

import { observeChild } from 'platform/desktop/backend/native/processManager';
import {
  Settings, SettingsCurrentVersion,
  DesktopJob, RunPipeline, NvidiaSmiReply, RunTraining,
  ConversionArgs, DesktopJobUpdater, CheckMediaResults,
} from 'platform/desktop/constants';

import * as viame from './viame';
import { spawnResult } from './utils';

const DefaultSettings: Settings = {
  // The current settings schema config
  version: SettingsCurrentVersion,
  // A path to the VIAME base install
  viamePath: 'C:\\Program Files\\VIAME',
  // Path to a user data folder
  dataPath: npath.join(os.homedir(), 'VIAME_DATA'),
  // Overrides
  overrides: {
    viamePath: process.env.DIVE_VIAME_INSTALL_PATH || undefined,
  }
};

const ViameWindowsConstants = {
  setup: 'setup_viame.bat',
  trainingExe: 'viame_train_detector.exe',
  kwiverExe: 'kwiver.exe',
  shell: true,
  ffmpeg: {
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
      // https://video.stackexchange.com/questions/20871/how-do-i-convert-anamorphic-hdv-video-to-normal-h-264-video-with-ffmpeg-how-to
      '-vf "scale=ceil(iw*sar/2)*2:ceil(ih/2)*2,setsar=1"',
    ].join(' '),
  },
};

function sourceString(settings: Settings) {
  const setupScriptAbs = npath.join(settings.viamePath, ViameWindowsConstants.setup);
  return `"${setupScriptAbs}" >NUL`;
}

let programFiles = 'C:\\Program Files';
// There exists no app.getPath('programfiles') so we need to
// check the variable for the default location
async function initialize() {
  const environmentVarPath = observeChild(spawn('cmd.exe', ['/c', 'echo %PROGRAMFILES%'], { shell: true }));
  environmentVarPath.stdout.on('data', (data) => {
    const trimmed = data.toString().trim();
    programFiles = trimmed;
    DefaultSettings.viamePath = `${trimmed}\\VIAME`;
  });
}

async function validateViamePath(settings: Settings): Promise<true | string> {
  const setupScriptPath = npath.join(settings.viamePath, 'setup_viame.bat');
  const setupExists = await fs.pathExists(setupScriptPath);
  if (!setupExists) {
    return `${setupScriptPath} does not exist`;
  }

  const modifiedCommand = `"${setupScriptPath.replace(/\\/g, '\\')}"`;
  const kwiverExistsOnPath = observeChild(spawn(
    `${modifiedCommand} && kwiver.exe help`, {
      shell: true,
    },
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

// Mock the validate call when starting jobs because it just takes too long to run.
// TODO: maybe perform a lightweight check or some other test that doesn't spawn() kwiver
const validateFake = () => Promise.resolve(true as true);

async function runPipeline(
  settings: Settings,
  runPipelineArgs: RunPipeline,
  updater: DesktopJobUpdater,
): Promise<DesktopJob> {
  return viame.runPipeline(settings, runPipelineArgs, updater, validateFake, {
    ...ViameWindowsConstants,
    setupScriptAbs: `"${npath.join(settings.viamePath, ViameWindowsConstants.setup)}"`,
  });
}

async function train(
  settings: Settings,
  runTrainingArgs: RunTraining,
  updater: DesktopJobUpdater,
): Promise<DesktopJob> {
  return viame.train(settings, runTrainingArgs, updater, validateFake, {
    ...ViameWindowsConstants,
    setupScriptAbs: `"${npath.join(settings.viamePath, ViameWindowsConstants.setup)}"`,
  });
}

function checkDefaultNvidiaSmi(resolve: (value: NvidiaSmiReply) => void) {
  const smi = observeChild(spawn(
    `"${programFiles}\\NVIDIA Corporation\\NVSMI\\nvidia-smi.exe"`,
    ['-q', '-x'],
    { shell: true },
  ));
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
}

// Note: this is the most recent location for the nvidia-smi
// it doesn't guarantee that the system doesn't have a relevant GPU
async function nvidiaSmi(): Promise<NvidiaSmiReply> {
  return new Promise((resolve) => {
    const pathsmi = observeChild(spawn('nvidia-smi', ['-q', '-x'], { shell: true }));
    let result = '';
    pathsmi.stdout.on('data', (chunk) => {
      // eslint-disable-next-line no-console
      console.log(chunk.toString('utf-8'));
      result = result.concat(chunk.toString('utf-8'));
    });

    pathsmi.on('exit', (exitCode) => {
      let jsonStr = 'null'; // parses to null
      if (exitCode === 0) {
        jsonStr = xml2json(result, { compact: true });
        resolve({
          output: JSON.parse(jsonStr),
          exitCode,
          error: result,
        });
      } else {
        checkDefaultNvidiaSmi(resolve);
      }
    });
    pathsmi.on('error', () => {
      checkDefaultNvidiaSmi(resolve);
    });
  });
}

/**
 * one time per launch configuration for ffmpeg and ffprobe
 */
async function ffmpegCommand(settings: Settings) {
  if (ViameWindowsConstants.ffmpeg.ready) {
    return;
  }
  const ffmpegPath = npath.join(settings.viamePath, '/bin/ffmpeg.exe');
  const init = `${sourceString(settings)} &&`;
  //First lets see if the VIAME install has libx264
  const modifiedCommand = `"${ffmpegPath.replace(/\\/g, '\\')}"`;

  const viameffmpeg = await spawnResult(`${init} ${modifiedCommand} -encoders`, true);
  if (viameffmpeg.output) {
    const ffmpegOutput = viameffmpeg.output;
    if (ffmpegOutput.includes('libx264')) {
      ViameWindowsConstants.ffmpeg.initialization = init;
      ViameWindowsConstants.ffmpeg.path = ffmpegPath;
      ViameWindowsConstants.ffmpeg.ready = true;
      return;
    }
  }
  throw new Error(`ffmpeg not installed, please download and install VIAME Toolkit from the main page: ${viameffmpeg.error}`);
}

/**
 * Checks the video file for the codec type and
 * returns true if it is x264, if not will return false for media conversion
 */
async function checkMedia(settings: Settings, file: string): Promise<CheckMediaResults> {
  await ffmpegCommand(settings);
  return viame.checkMedia({
    ...ViameWindowsConstants,
    setupScriptAbs: sourceString(settings),
  }, file);
}

async function convertMedia(settings: Settings,
  args: ConversionArgs,
  updater: DesktopJobUpdater): Promise<DesktopJob> {
  await ffmpegCommand(settings);
  return viame.convertMedia(settings, args, updater, {
    ...ViameWindowsConstants,
    setupScriptAbs: sourceString(settings),
  });
}

export default {
  DefaultSettings,
  validateViamePath,
  runPipeline,
  train,
  nvidiaSmi,
  initialize,
  checkMedia,
  convertMedia,
};
