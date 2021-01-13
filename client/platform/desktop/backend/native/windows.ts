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
  NvidiaSmiReply,
  FFProbeResults,
  JsonMeta,
  DesktopJobUpdater,
} from 'platform/desktop/constants';

import { DatasetType } from 'viame-web-common/apispec';
import * as common from './common';

const DefaultSettings: Settings = {
  // The current settings schema config
  version: SettingsCurrentVersion,
  // A path to the VIAME base install
  viamePath: 'C:\\Program Files\\VIAME',
  // Path to a user data folder
  dataPath: npath.join(os.homedir(), 'VIAME_DATA'),
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

/**
 * Fashioned as a node.js implementation of viame_tasks.tasks.run_pipeline
 *
 * @param datasetIdPath dataset path absolute
 * @param pipeline pipeline file basename
 * @param settings global settings
 */
async function runPipeline(
  settings: Settings,
  runPipelineArgs: RunPipeline,
  updater: (msg: DesktopJobUpdate) => void,
): Promise<DesktopJob> {
  const { datasetId, pipeline } = runPipelineArgs;
  const isValid = await validateViamePath(settings);
  if (isValid !== true) {
    throw new Error(isValid);
  }

  const setupScriptPath = npath.join(settings.viamePath, 'setup_viame.bat');
  const pipelinePath = npath.join(settings.viamePath, 'configs/pipelines', pipeline.pipe);
  const projectInfo = await common.getValidatedProjectDir(settings, datasetId);
  const meta = await common.loadJsonMetadata(projectInfo.metaFileAbsPath);
  const jobWorkDir = await common.createKwiverRunWorkingDir(
    settings, [meta], pipeline.name,
  );

  const detectorOutput = npath.join(jobWorkDir, 'detector_output.csv');
  const trackOutput = npath.join(jobWorkDir, 'track_output.csv');
  const joblog = npath.join(jobWorkDir, 'runlog.txt');

  const modifiedCommand = `"${setupScriptPath.replace(/\\/g, '\\')}"`;

  let command: string[] = [];
  if (meta.type === 'video') {
    command = [
      `${modifiedCommand} &&`,
      'kwiver.exe runner',
      '-s input:video_reader:type=vidl_ffmpeg',
      `-p ${pipelinePath}`,
      `-s input:video_filename=${datasetId}`,
      `-s detector_writer:file_name=${detectorOutput}`,
      `-s track_writer:file_name=${trackOutput}`,
    ];
  } else if (meta.type === 'image-sequence') {
    // Create frame image manifest
    const manifestFile = npath.join(jobWorkDir, 'image-manifest.txt');
    // map image file names to absolute paths
    const fileData = meta.originalImageFiles
      .map((f) => npath.join(projectInfo.basePath, f))
      .join('\n');
    await fs.writeFile(manifestFile, fileData);
    command = [
      `${modifiedCommand} &&`,
      'kwiver.exe runner',
      `-p "${pipelinePath}"`,
      `-s input:video_filename="${manifestFile}"`,
      `-s detector_writer:file_name="${detectorOutput}"`,
      `-s track_writer:file_name="${trackOutput}"`,
    ];
  }

  const job = spawn(command.join(' '), {
    shell: true,
    cwd: jobWorkDir,
  });

  const jobBase: DesktopJob = {
    key: `pipeline_${job.pid}_${jobWorkDir}`,
    jobType: 'pipeline',
    pid: job.pid,
    pipeline,
    workingDir: jobWorkDir,
    datasetIds: [datasetId],
    exitCode: job.exitCode,
    startTime: new Date(),
  };

  const processChunk = (chunk: Buffer) => chunk
    .toString('utf-8')
    .split('\n')
    .filter((a) => a);

  job.stdout.on('data', (chunk: Buffer) => {
    // eslint-disable-next-line no-console
    console.log(chunk.toString('utf-8'));
    updater({
      ...jobBase,
      body: processChunk(chunk),
    });
    // No way in windows to display and log stdout at same time without 3rd party tools
    fs.appendFile(joblog, chunk.toString('utf-8'), (err) => {
      if (err) throw err;
    });
  });

  job.stderr.on('data', (chunk: Buffer) => {
    // eslint-disable-next-line no-console
    console.log(chunk.toString('utf-8'));
    updater({
      ...jobBase,
      body: processChunk(chunk),
    });
    fs.appendFile(joblog, chunk.toString('utf-8'), (err) => {
      if (err) throw err;
    });
  });

  job.on('exit', async (code) => {
    if (code === 0) {
      try {
        await common.processOtherAnnotationFiles(
          settings, datasetId, [trackOutput, detectorOutput],
        );
      } catch (err) {
        console.error(err);
      }
    }
    updater({
      ...jobBase,
      body: [''],
      exitCode: code,
      endTime: new Date(),
    });
  });

  return jobBase;
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

function checkMedia(settings: Settings, file: string): boolean {
  const setupScriptPath = npath.join(settings.viamePath, 'setup_viame.bat');

  const modifiedCommand = `"${setupScriptPath.replace(/\\/g, '\\')}"`;

  const ffprobePath = `${settings.viamePath}\\bin\\ffprobe.exe`;
  const ffprobeModified = `"${ffprobePath.replace(/\\/g, '\\')}"`;
  if (!fs.existsSync(setupScriptPath)) {
    throw new Error(`${modifiedCommand} does not exist and is required to convert files.  Please download and install the VIAME toolkit from the main page`);
  }
  const command = [
    `${modifiedCommand} &&`,
    `${ffprobeModified}`,
    '-print_format',
    'json',
    '-v',
    'quiet',
    '-show_format',
    '-show_streams',
    file,
  ];
  const result = spawnSync(command.join(' '),
    { shell: true });
  if (result.error) {
    throw result.error;
  }
  // TODO: I don't like the below for grabbing the JSON out of the return data
  const returnText = result.stdout.toString('utf-8');
  const firstIndex = returnText.indexOf('{');
  const lastIndex = returnText.lastIndexOf('}');
  if (firstIndex === -1 || lastIndex === -1) {
    throw new Error('No ffprobe JSON result found');
  }
  const json = returnText.substring(firstIndex, lastIndex + 1);
  const ffprobeJSON: FFProbeResults = JSON.parse(json);
  if (ffprobeJSON && ffprobeJSON.streams) {
    const websafe = ffprobeJSON.streams.filter((el) => el.codec_name === 'h264' && el.codec_type === 'video');

    return !!websafe.length;
  }
  return false;
}

function convertMedia(settings: Settings,
  meta: JsonMeta,
  mediaList: [string, string][],
  type: DatasetType,
  updater: DesktopJobUpdater,
  imageIndex = 0,
  key = ''): DesktopJob {
  //const joblog = npath.join(jobWorkDir, 'runlog.txt');

  const setupScriptPath = npath.join(settings.viamePath, 'setup_viame.bat');
  const ffmpegPath = `${settings.viamePath}\\bin\\ffmpeg.exe`;

  const modifiedCommand = `"${setupScriptPath.replace(/\\/g, '\\')}"`;
  const ffmpegModified = `"${ffmpegPath.replace(/\\/g, '\\')}"`;

  if (!fs.existsSync(setupScriptPath)) {
    throw new Error('ffmpeg does not exist and is required to convert files.  Please download and install the VIAME toolkit from the main page');
  }

  const commands: string[] = [`${modifiedCommand} &&`];
  if (type === 'video' && mediaList[0]) {
    commands.push(`${ffmpegModified} -i "${mediaList[0][0]}" -c:v libx264 -preset slow -crf 26 -c:a copy "${mediaList[0][1]}"`);
  } else if (type === 'image-sequence' && imageIndex < mediaList.length) {
    commands.push(`${ffmpegModified} -i "${mediaList[imageIndex][0]}" "${mediaList[imageIndex][1]}"`);
  }

  const job = spawn(commands.join(' '), {
    shell: true,
  });

  let jobKey = `convert_${job.pid}_${meta.originalBasePath}`;
  if (key.length) {
    jobKey = key;
  }

  const jobBase: DesktopJob = {
    key: jobKey,
    pid: job.pid,
    jobType: 'conversion',
    workingDir: meta.originalBasePath || DefaultSettings.dataPath,
    datasetIds: [meta.id],
    exitCode: job.exitCode,
    startTime: new Date(),
  };

  const processChunk = (chunk: Buffer) => chunk
    .toString('utf-8')
    .split('\n')
    .filter((a) => a);

  job.stdout.on('data', (chunk: Buffer) => {
    // eslint-disable-next-line no-console
    console.log(chunk.toString('utf-8'));
    updater({
      ...jobBase,
      body: processChunk(chunk),
    });
  });

  job.stderr.on('data', (chunk: Buffer) => {
    // eslint-disable-next-line no-console
    console.log(chunk.toString('utf-8'));
    updater({
      ...jobBase,
      body: processChunk(chunk),
    });
  });

  job.on('exit', async (code) => {
    if (code !== 0) {
      console.error('Error with running conversion');
    } else if (type === 'video' || (type === 'image-sequence' && imageIndex === mediaList.length - 1)) {
      common.completeConversion(settings, meta.id, jobKey);
      updater({
        ...jobBase,
        body: [''],
        exitCode: code,
        endTime: new Date(),
      });
    } else if (type === 'image-sequence') {
      updater({
        ...jobBase,
        body: [`Convertion ${imageIndex + 1} of ${mediaList.length} Complete`],
      });
      convertMedia(settings, meta, mediaList, type, updater, imageIndex + 1, jobKey);
    }
  });
  return jobBase;
}

export default {
  DefaultSettings,
  validateViamePath,
  runPipeline,
  nvidiaSmi,
  initialize,
  checkMedia,
  convertMedia,
};
