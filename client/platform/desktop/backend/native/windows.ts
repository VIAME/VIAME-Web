/**
 * VIAME process manager for windows platform
 */
import os from 'os';
import npath from 'path';
import { spawn, spawnSync } from 'child_process';
import fs from 'fs-extra';
import { xml2json } from 'xml-js';

import {
  Settings, SettingsCurrentVersion,
  DesktopJob, DesktopJobUpdate, RunPipeline,
  NvidiaSmiReply, RunTraining, FFProbeResults, ConversionArgs, DesktopJobUpdater,
} from 'platform/desktop/constants';

import * as viame from './viame';

const DefaultSettings: Settings = {
  // The current settings schema config
  version: SettingsCurrentVersion,
  // A path to the VIAME base install
  viamePath: 'C:\\Program Files\\VIAME',
  // Path to a user data folder
  dataPath: npath.join(os.homedir(), 'VIAME_DATA'),
};

const ViameWindowsConstants = {
  setup: 'setup_viame.bat',
  trainingExe: 'viame_train_detector.exe',
  kwiverExe: 'kwiver.exe',
  shell: true,
  ffmpeg: {
    initialization: 'setup_viame.bat', // command to initialize
    path: '\\bin\\ffprobe.exe', // location of the ffmpeg executable
    encoding: '-c:v libx264 -preset slow -crf 26 -c:a copy', //encoding mode used
  },

};

let programFiles = 'C:\\Program Files';
// There exists no app.getPath('programfiles') so we need to
// check the variable for the default location
async function initialize() {
  const environmentVarPath = spawn('cmd.exe', ['/c', 'echo %PROGRAMFILES%'], { shell: true });
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
  const kwiverExistsOnPath = spawn(
    `${modifiedCommand} && kwiver.exe help`, {
      shell: true,
    },
  );
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
  updater: (msg: DesktopJobUpdate) => void,
): Promise<DesktopJob> {
  return viame.runPipeline(settings, runPipelineArgs, updater, validateFake, {
    ...ViameWindowsConstants,
    setupScriptAbs: `"${npath.join(settings.viamePath, ViameWindowsConstants.setup)}"`,
  });
}

async function train(
  settings: Settings,
  runTrainingArgs: RunTraining,
  updater: (msg: DesktopJobUpdate) => void,
): Promise<DesktopJob> {
  return viame.train(settings, runTrainingArgs, updater, validateFake, {
    ...ViameWindowsConstants,
    setupScriptAbs: `"${npath.join(settings.viamePath, ViameWindowsConstants.setup)}"`,
  });
}

function checkDefaultNvidiaSmi(resolve: (value: NvidiaSmiReply) => void) {
  const smi = spawn(`"${programFiles}\\NVIDIA Corporation\\NVSMI\\nvidia-smi.exe"`, ['-q', '-x'], { shell: true });
  let result = '';
  smi.stdout.on('data', (chunk) => {
    result = result.concat(chunk.toString('utf-8'));
  });

  smi.on('close', (exitCode) => {
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
    const pathsmi = spawn('nvidia-smi', ['-q', '-x'], { shell: true });
    let result = '';
    pathsmi.stdout.on('data', (chunk) => {
      // eslint-disable-next-line no-console
      console.log(chunk.toString('utf-8'));
      result = result.concat(chunk.toString('utf-8'));
    });

    pathsmi.on('close', (exitCode) => {
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
 * Checs the video file for the codec type and
 * returns true if it is x264, if not will return false for media conversion
 */
function checkMedia(settings: Settings, file: string): boolean {
  const setupScriptAbs = npath.join(settings.viamePath, ViameWindowsConstants.setup);
  return viame.checkMedia({
    ...ViameWindowsConstants,
    setupScriptAbs: `. "${setupScriptAbs}"`,
  }, file);
}

function convertMedia(settings: Settings,
  args: ConversionArgs,
  updater: DesktopJobUpdater): DesktopJob {
  const setupScriptAbs = npath.join(settings.viamePath, ViameWindowsConstants.setup);
  return viame.convertMedia(settings, args, updater, {
    ...ViameWindowsConstants,
    setupScriptAbs: `. "${setupScriptAbs}"`,
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
