import npath from 'path';
import fs from 'fs-extra';
import {
  FrameImage,
  MultiCamMedia,
} from 'dive-common/apispec';

import { JsonMeta } from 'platform/desktop/constants';

function transcodeMultiCam(
  jsonMeta: JsonMeta,
  item: string,
  projectDirAbsPath: string,
) {
  let destLoc = '';
  if (jsonMeta.multiCam) {
    let breakFlag = false;
    Object.entries(jsonMeta.multiCam.cameras).forEach(([key, val]) => {
      if (item.includes(val.originalBasePath) && !breakFlag) {
        const extension = val.type === 'video' ? '.mp4' : '.png';
        destLoc = item.replace(npath.extname(item), extension);

        if (val.type === 'image-sequence') {
          if (!val.transcodedImageFiles) {
          // eslint-disable-next-line no-param-reassign
            val.transcodedImageFiles = [];
          }
          if (val.originalImageFiles.includes(npath.basename(item))) {
            destLoc = destLoc.replace(val.originalBasePath, `${projectDirAbsPath}/${key}`);
            val.transcodedImageFiles.push(npath.basename(destLoc));
            breakFlag = true;
          }
        } else if (val.type === 'video') {
          if (item === npath.join(val.originalBasePath, val.originalVideoFile)) {
            destLoc = destLoc.replace(val.originalBasePath, `${projectDirAbsPath}/${key}`);
            // eslint-disable-next-line no-param-reassign
            val.transcodedVideoFile = npath.basename(destLoc);
            breakFlag = true;
          }
        }
      }
    });
  }
  return destLoc;
}

function getTranscodedMultiCamType(imageListFile: string, jsonMeta: JsonMeta) {
  // Look through cameras trying to find the match for the key/name and type to return back the type
  if (jsonMeta.multiCam) {
    const base = npath.basename(imageListFile).replace(npath.extname(imageListFile), '');
    let type;
    Object.values(jsonMeta.multiCam.cameras).forEach((val) => {
      if (val.originalImageFiles.map((item) => item.replace(npath.extname(item), '')).includes(base)) {
        type = val.type;
      }
      if (val.originalVideoFile.includes(base)) {
        type = val.type;
      }
    });
    if (type) {
      return type;
    }
  }
  throw new Error(`No associate type for ${imageListFile} in multiCam data`);
}

function writeMultiCamStereoPipelineArgs(jobWorkDir: string, meta: JsonMeta) {
  const argFilePair: Record<string, string> = {};
  const outFiles: Record<string, string> = {};
  if (meta.multiCam && meta.multiCam.cameras) {
    let i = 0;
    Object.entries(meta.multiCam.cameras).forEach(([key, list]) => {
      const { originalBasePath } = list;
      const outputFileName = `computed_tracks_${key}.csv`;
      const outputArg = `detector_writer${i + 1}:file_name`;
      argFilePair[outputArg] = outputFileName;
      outFiles[key] = outputFileName;
      const inputArg = `input${i + 1}:video_filename`;
      if (list.type === 'image-sequence') {
        const inputFileName = npath.join(jobWorkDir, `input${i + 1}_images.txt`);
        const inputFile = fs.createWriteStream(inputFileName);
        list.originalImageFiles.forEach((image) => inputFile.write(`${npath.join(originalBasePath, image)}\n`));
        inputFile.end();
        argFilePair[inputArg] = inputFileName;
      } else if (list.originalVideoFile) {
        const vidFile = list.transcodedVideoFile
          ? list.transcodedVideoFile : list.originalVideoFile;
        const vidTypeArg = `input${i + 1}:video_reader:type`;
        const vidType = 'vidl_ffmpeg';
        argFilePair[vidTypeArg] = vidType;
        argFilePair[inputArg] = npath.join(originalBasePath, vidFile);
      }
      i += 1;
    });
  }
  return { argFilePair, outFiles };
}

function getMultiCamUrls(
  projectMetaData: JsonMeta,
  projectBasePath: string,
  makeMediaUrl: (path: string) => string,
) {
  if (projectMetaData.multiCam && projectMetaData.multiCam.display) {
    //Confirm we have a imageList for the display
    const displayCamera = projectMetaData.multiCam.cameras[projectMetaData.multiCam.display];
    if (!displayCamera) {
      throw new Error(`The default display of ${projectMetaData.multiCam.display} is not in the list of cameras`);
    }
    const multiCamMedia: MultiCamMedia = {
      cameras: {},
      display: projectMetaData.multiCam.display,
    };

    Object.entries(projectMetaData.multiCam.cameras).forEach(([key, value]) => {
      let imageData = [] as FrameImage[];
      let videoUrl = '';
      if (value.type === 'image-sequence') {
        let displayFilenames = value.originalImageFiles;
        let { originalBasePath } = value;
        // Filter transcoded images to use left/right files)
        if (value.transcodedImageFiles && value.transcodedImageFiles.length) {
          displayFilenames = value.transcodedImageFiles;
          originalBasePath = npath.join(projectBasePath, key);
        }
        imageData = displayFilenames.map((filename: string) => ({
          url: makeMediaUrl(npath.join(originalBasePath, filename)),
          filename,
        }));
      } else if (value.type === 'video') {
        let displayFilename = value.originalVideoFile;
        let { originalBasePath } = displayCamera;
        if (value.transcodedVideoFile) {
          displayFilename = `${value.transcodedVideoFile}`;
          originalBasePath = npath.join(projectBasePath, key);
        }
        videoUrl = makeMediaUrl(npath.join(originalBasePath, displayFilename));
      } else {
        throw new Error('There is no default display for the multicam dataset');
      }
      multiCamMedia.cameras[key] = {
        imageData,
        videoUrl,
        type: value.type,
      };
    });
    return multiCamMedia;
  }
  throw new Error('There is no multiCam data associated with this');
}

function getMultiCamVideoPath(meta: JsonMeta) {
  if (meta.multiCam && meta.multiCam.display) {
    if (meta.multiCam.cameras[meta.multiCam.display]) {
      const display = meta.multiCam.cameras[meta.multiCam.display];
      if (display.transcodedVideoFile) {
        return display.transcodedVideoFile;
      }
      return display.originalVideoFile;
    }
    throw new Error(`No video exists for the display file of ${meta.multiCam.display}`);
  }
  throw new Error(`${meta.id} does not contain multiCam data`);
}

function getMultiCamImageFiles(meta: JsonMeta) {
  if (meta.multiCam && meta.multiCam.display) {
    if (meta.multiCam.cameras[meta.multiCam.display]) {
      const display = meta.multiCam.cameras[meta.multiCam.display];
      return display.originalImageFiles;
    }
    throw new Error(`No Image list exists for the display file of ${meta.multiCam.display}`);
  }
  throw new Error(`${meta.id} does not contain multiCam data`);
}

export {
  transcodeMultiCam,
  writeMultiCamStereoPipelineArgs,
  getMultiCamVideoPath,
  getMultiCamImageFiles,
  getMultiCamUrls,
  getTranscodedMultiCamType,
};
