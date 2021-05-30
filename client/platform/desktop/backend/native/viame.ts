import npath from 'path';
import { spawn } from 'child_process';
import fs from 'fs-extra';

import {
  Settings, DesktopJob, RunPipeline, RunTraining, FFProbeResults,
  ConversionArgs,
  DesktopJobUpdater,
  CheckMediaResults,
} from 'platform/desktop/constants';
import { cleanString } from 'platform/desktop/sharedUtils';
import { serialize } from 'platform/desktop/backend/serializers/viame';
import { observeChild } from 'platform/desktop/backend/native/processManager';

import * as common from './common';
import { jobFileEchoMiddleware, spawnResult } from './utils';
import {
  getMultiCamImageFiles, getMultiCamVideoPath,
  getTranscodedMultiCamType, writeMultiCamStereoPipelineArgs,
} from './multiCamUtils';


const PipelineRelativeDir = 'configs/pipelines';
const DiveJobManifestName = 'dive_job_manifest.json';

interface FFmpegSettings {
  initialization: string;
  path: string;
  videoArgs: string;
}

export interface ViameConstants {
  setupScriptAbs: string; // abs path setup comman
  trainingExe: string; // name of training binary on PATH
  kwiverExe: string; // name of kwiver binary on PATH
  shell: string | boolean; // shell arg for spawn
  ffmpeg: FFmpegSettings; //ffmpeg settings
}

/**
 * a node.js implementation of dive_tasks.tasks.run_pipeline
 */
async function runPipeline(
  settings: Settings,
  runPipelineArgs: RunPipeline,
  updater: DesktopJobUpdater,
  validateViamePath: (settings: Settings) => Promise<true | string>,
  viameConstants: ViameConstants,
): Promise<DesktopJob> {
  const { datasetId, pipeline } = runPipelineArgs;

  const isValid = await validateViamePath(settings);
  if (isValid !== true) {
    throw new Error(isValid);
  }

  let pipelinePath = npath.join(settings.viamePath, PipelineRelativeDir, pipeline.pipe);
  if (runPipelineArgs.pipeline.type === 'trained') {
    pipelinePath = pipeline.pipe;
  }
  const projectInfo = await common.getValidatedProjectDir(settings, datasetId);
  const meta = await common.loadJsonMetadata(projectInfo.metaFileAbsPath);
  const jobWorkDir = await common.createKwiverRunWorkingDir(settings, [meta], pipeline.name);

  const detectorOutput = npath.join(jobWorkDir, 'detector_output.csv');
  let trackOutput = npath.join(jobWorkDir, 'track_output.csv');
  const joblog = npath.join(jobWorkDir, 'runlog.txt');

  //TODO: TEMPORARY FIX FOR DEMO PURPOSES
  let requiresInput = false;
  if ((/utility_/g).test(pipeline.pipe)) {
    requiresInput = true;
  }
  let groundTruthFileName;
  if (requiresInput) {
    groundTruthFileName = `groundtruth_${meta.id}.csv`;
    const groundTruthFileStream = fs.createWriteStream(
      npath.join(jobWorkDir, groundTruthFileName),
    );
    const inputData = await common.loadJsonTracks(projectInfo.trackFileAbsPath);
    await serialize(groundTruthFileStream, inputData, meta);
    groundTruthFileStream.end();
  }

  let metaType = meta.type;

  if (metaType === 'multi' && meta.multiCam) {
    metaType = meta.multiCam.cameras[meta.multiCam.display].type;
  }

  let command: string[] = [];
  if (metaType === 'video') {
    let videoAbsPath = npath.join(meta.originalBasePath, meta.originalVideoFile);
    if (meta.type === 'multi') {
      videoAbsPath = getMultiCamVideoPath(meta);
    } else if (meta.transcodedVideoFile) {
      videoAbsPath = npath.join(projectInfo.basePath, meta.transcodedVideoFile);
    }
    command = [
      `${viameConstants.setupScriptAbs} &&`,
      `"${viameConstants.kwiverExe}" runner`,
      '-s "input:video_reader:type=vidl_ffmpeg"',
      `-p "${pipelinePath}"`,
      `-s input:video_filename="${videoAbsPath}"`,
      `-s downsampler:target_frame_rate=${meta.fps}`,
      `-s detector_writer:file_name="${detectorOutput}"`,
      `-s track_writer:file_name="${trackOutput}"`,
    ];
  } else if (metaType === 'image-sequence') {
    // Create frame image manifest
    const manifestFile = npath.join(jobWorkDir, 'image-manifest.txt');
    // map image file names to absolute paths
    let imageList = meta.originalImageFiles;
    if (meta.type === 'multi') {
      imageList = getMultiCamImageFiles(meta);
    }
    const fileData = imageList
      .map((f) => npath.join(meta.originalBasePath, f))
      .join('\n');
    await fs.writeFile(manifestFile, fileData);
    command = [
      `${viameConstants.setupScriptAbs} &&`,
      `"${viameConstants.kwiverExe}" runner`,
      `-p "${pipelinePath}"`,
      `-s input:video_filename="${manifestFile}"`,
      `-s detector_writer:file_name="${detectorOutput}"`,
      `-s track_writer:file_name="${trackOutput}"`,
    ];
  }
  if (requiresInput) {
    command.push(`-s detection_reader:file_name="${groundTruthFileName}"`);
    command.push(`-s track_reader:file_name="${groundTruthFileName}"`);
  }

  let multiOutFiles: Record<string, string>;
  if (meta.multiCam && pipeline.type === 'measurement') {
    const { argFilePair, outFiles } = writeMultiCamStereoPipelineArgs(jobWorkDir, meta);
    Object.entries(argFilePair).forEach(([arg, file]) => {
      command.push(`-s ${arg}="${file}"`);
    });
    multiOutFiles = {};
    Object.entries(outFiles).forEach(([key, val]) => {
      multiOutFiles[key] = npath.join(jobWorkDir, val);
    });
    trackOutput = npath.join(jobWorkDir, outFiles[meta.multiCam.display]);
    if (meta.multiCam.calibration) {
      command.push(`-s measurer:calibration_file="${meta.multiCam.calibration}"`);
    }
  } else if (pipeline.type === 'measurement') {
    throw new Error('Attempting to run a multicam pipeline on non multicam data');
  }

  const job = observeChild(spawn(command.join(' '), {
    shell: viameConstants.shell,
    cwd: jobWorkDir,
  }));

  const jobBase: DesktopJob = {
    key: `pipeline_${job.pid}_${jobWorkDir}`,
    command: command.join(' '),
    jobType: 'pipeline',
    pid: job.pid,
    args: runPipelineArgs,
    title: runPipelineArgs.pipeline.name,
    workingDir: jobWorkDir,
    datasetIds: [datasetId],
    exitCode: job.exitCode,
    startTime: new Date(),
  };

  fs.writeFile(npath.join(jobWorkDir, DiveJobManifestName), JSON.stringify(jobBase));

  updater({
    ...jobBase,
    body: [''],
  });

  job.stdout.on('data', jobFileEchoMiddleware(jobBase, updater, joblog));
  job.stderr.on('data', jobFileEchoMiddleware(jobBase, updater, joblog));

  job.on('exit', async (code) => {
    if (code === 0) {
      try {
        const { attributes } = await common.processOtherAnnotationFiles(
          settings, datasetId, [trackOutput, detectorOutput], multiOutFiles,
        );
        if (attributes) {
          meta.attributes = attributes;
          await common.saveMetadata(settings, datasetId, meta);
        }
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

/**
 * a node.js implementation of dive_tasks.tasks.run_training
 */
async function train(
  settings: Settings,
  runTrainingArgs: RunTraining,
  updater: DesktopJobUpdater,
  validateViamePath: (settings: Settings) => Promise<true | string>,
  viameConstants: ViameConstants,
): Promise<DesktopJob> {
  const isValid = await validateViamePath(settings);
  if (isValid !== true) {
    throw new Error(isValid);
  }

  /* Zip together project info and meta */
  const infoAndMeta = await Promise.all(
    runTrainingArgs.datasetIds.map(async (id) => {
      const projectInfo = await common.getValidatedProjectDir(settings, id);
      const meta = await common.loadJsonMetadata(projectInfo.metaFileAbsPath);
      return { projectInfo, meta };
    }),
  );
  const jsonMetaList = infoAndMeta.map(({ meta }) => meta);

  // Working dir for training
  const jobWorkDir = await common.createKwiverRunWorkingDir(
    settings, jsonMetaList, runTrainingArgs.pipelineName,
  );

  // Argument files for training
  const inputFolderFileList = npath.join(jobWorkDir, 'input_folder_list.txt');
  const groundTruthFileList = npath.join(jobWorkDir, 'input_truth_list.txt');

  const groundtruthFilenames = await Promise.all(
    infoAndMeta.map(async ({ meta, projectInfo }) => {
      // Organize data for training
      const groundTruthFileName = `groundtruth_${meta.id}.csv`;
      const groundTruthFileStream = fs.createWriteStream(
        npath.join(jobWorkDir, groundTruthFileName),
      );
      const inputData = await common.loadJsonTracks(projectInfo.trackFileAbsPath);
      await serialize(groundTruthFileStream, inputData, meta);
      groundTruthFileStream.end();
      return groundTruthFileName;
    }),
  );

  // Write groundtruth filenames to list
  const groundtruthFile = fs.createWriteStream(groundTruthFileList);
  groundtruthFilenames.forEach((name) => groundtruthFile.write(`${name}\n`));
  groundtruthFile.end();

  // Write input folder paths to list
  const inputFile = fs.createWriteStream(inputFolderFileList);
  infoAndMeta.forEach(({ projectInfo, meta }) => {
    if (meta.type === 'video') {
      let videopath = '';
      /* If the video has been transcoded, use that video */
      if (meta.transcodedVideoFile) {
        videopath = npath.join(projectInfo.basePath, meta.transcodedVideoFile);
      } else {
        videopath = npath.join(meta.originalBasePath, meta.originalVideoFile);
      }
      inputFile.write(`${videopath}`);
    } else if (meta.type === 'image-sequence') {
      inputFile.write(`${npath.join(meta.originalBasePath)}\n`);
    }
  });
  inputFile.end();

  const joblog = npath.join(jobWorkDir, 'runlog.txt');
  const configFilePath = npath.join(
    settings.viamePath, PipelineRelativeDir, runTrainingArgs.trainingConfig,
  );

  const command = [
    `${viameConstants.setupScriptAbs} &&`,
    `"${viameConstants.trainingExe}"`,
    `--input-list "${inputFolderFileList}"`,
    `--input-truth "${groundTruthFileList}"`,
    `--config "${configFilePath}"`,
    '--no-query',
    '--no-adv-prints',
    '--no-embedded-pipe',
  ];

  const job = observeChild(spawn(command.join(' '), {
    shell: viameConstants.shell,
    cwd: jobWorkDir,
  }));

  const cleanPipelineName = cleanString(runTrainingArgs.pipelineName);

  const jobBase: DesktopJob = {
    key: `pipeline_${job.pid}_${jobWorkDir}`,
    command: command.join(' '),
    jobType: 'pipeline',
    pid: job.pid,
    args: runTrainingArgs,
    title: cleanPipelineName,
    workingDir: jobWorkDir,
    datasetIds: runTrainingArgs.datasetIds,
    exitCode: job.exitCode,
    startTime: new Date(),
  };

  fs.writeFile(npath.join(jobWorkDir, DiveJobManifestName), JSON.stringify(jobBase));

  updater({
    ...jobBase,
    body: [''],
  });

  job.stdout.on('data', jobFileEchoMiddleware(jobBase, updater, joblog));
  job.stderr.on('data', jobFileEchoMiddleware(jobBase, updater, joblog));
  job.on('exit', async (code) => {
    let exitCode = code;
    const bodyText = [''];
    if (code === 0) {
      try {
        await common.processTrainedPipeline(
          settings, runTrainingArgs, jobWorkDir,
        );
      } catch (err) {
        console.error(err);
        exitCode = 1;
        bodyText.unshift(err.toString('utf-8'));
        fs.appendFile(joblog, bodyText[0], (error) => {
          if (error) throw error;
        });
      }
    }
    updater({
      ...jobBase,
      body: bodyText,
      exitCode,
      endTime: new Date(),
    });
  });
  return jobBase;
}

async function checkMedia(
  viameConstants: ViameConstants,
  file: string,
): Promise<CheckMediaResults> {
  const ffprobePath = `${viameConstants.ffmpeg.path.replace('ffmpeg', 'ffprobe')}`;
  const command = [
    viameConstants.ffmpeg.initialization,
    `"${ffprobePath}"`,
    '-print_format',
    'json',
    '-v',
    'quiet',
    '-show_format',
    '-show_streams',
    `"${file}"`,
  ];
  const result = await spawnResult(command.join(' '), viameConstants.shell);
  if (result.error || result.output === null) {
    throw result.error || 'Error using ffprobe';
  }
  const returnText = result.output;
  const ffprobeJSON: FFProbeResults = JSON.parse(returnText);

  if (ffprobeJSON && ffprobeJSON.streams?.length) {
    const videoStream = ffprobeJSON.streams.filter((el) => el.codec_type === 'video');
    if (videoStream.length === 0 || !videoStream[0].avg_frame_rate) {
      throw Error('FFProbe found that video stream has no avg_frame_rate');
    }
    const originalFpsString = videoStream[0].avg_frame_rate;
    const [dividend, divisor] = originalFpsString.split('/').map((v) => Number.parseInt(v, 10));
    const originalFps = dividend / divisor;
    const websafe = videoStream
      .filter((el) => el.codec_name === 'h264')
      .filter((el) => el.sample_aspect_ratio === '1:1');

    return { websafe: !!websafe.length, originalFps, originalFpsString };
  }
  throw Error(`FFProbe did not return a valid value for ${file}`);
}

async function convertMedia(settings: Settings,
  args: ConversionArgs,
  updater: DesktopJobUpdater,
  viameConstants: ViameConstants,
  mediaIndex = 0,
  key = '',
  baseWorkDir = ''): Promise<DesktopJob> {
  // Image conversion needs to utilize the baseWorkDir, init or vids create their own directory
  const jobWorkDir = baseWorkDir || await common.createKwiverRunWorkingDir(settings, [args.meta], 'conversion');
  const joblog = npath.join(jobWorkDir, 'runlog.txt');
  const commands = [];

  let multiType = '';
  if (args.meta.type === 'multi' && mediaIndex < args.mediaList.length) {
    multiType = getTranscodedMultiCamType(args.mediaList[mediaIndex][1], args.meta);
  }
  commands.push(
    viameConstants.ffmpeg.initialization,
    `"${viameConstants.ffmpeg.path}"`,
    `-i "${args.mediaList[mediaIndex][0]}"`,
  );
  if ((args.meta.type === 'video' || multiType === 'video') && mediaIndex < args.mediaList.length) {
    commands.push(
      viameConstants.ffmpeg.videoArgs,
    );
  }
  commands.push(
    `"${args.mediaList[mediaIndex][1]}"`,
  );

  const job = observeChild(spawn(commands.join(' '), { shell: viameConstants.shell }));
  let jobKey = `convert_${job.pid}_${jobWorkDir}`;
  if (key.length) {
    jobKey = key;
  }
  const jobBase: DesktopJob = {
    key: jobKey,
    pid: job.pid,
    command: commands.join(' '),
    args,
    title: `converting ${args.meta.name}`,
    jobType: 'conversion',
    workingDir: jobWorkDir,
    datasetIds: [args.meta.id],
    exitCode: job.exitCode,
    startTime: new Date(),
  };

  fs.writeFile(npath.join(jobWorkDir, DiveJobManifestName), JSON.stringify(jobBase));

  job.stdout.on('data', jobFileEchoMiddleware(jobBase, updater, joblog));
  job.stderr.on('data', jobFileEchoMiddleware(jobBase, updater, joblog));

  job.on('exit', async (code) => {
    if (code !== 0) {
      console.error('Error with running conversion');
      updater({
        ...jobBase,
        body: [''],
        exitCode: code,
        endTime: new Date(),
      });
    } else if (mediaIndex === args.mediaList.length - 1) {
      common.completeConversion(settings, args.meta.id, jobKey);
      updater({
        ...jobBase,
        body: [''],
        exitCode: code,
        endTime: new Date(),
      });
    } else {
      updater({
        ...jobBase,
        body: [`Conversion ${mediaIndex + 1} of ${args.mediaList.length} Complete`],
      });
      convertMedia(settings, args, updater, viameConstants, mediaIndex + 1, jobKey, jobWorkDir);
    }
  });
  return jobBase;
}
export {
  runPipeline,
  train,
  checkMedia,
  convertMedia,
};
